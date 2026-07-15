"""L3 语义分类器（规则+词典，零 ML 依赖）。

Protocol L3Classifier.classify():
  输入 ConceptCandidate[] → 输出 ClassifiedCandidate[]：
    - semantic_type：中文枚举对齐 USL SemanticType（对象类型/关系类型/属性/动作类型/过程类型/规则类型）
    - domain_id：匹配 domain code，若匹配不到则 None（等待后续人工指定）
    - definition：若有上下文，则取包含 canonical 的最近一句作为定义
    - stoplist_flag：若术语命中 builtin_stopwords 或明显非术语（代词/功能词），标记为停用词候选

本实现基于"语义特征字典"的启发式规则，后续可替换为 embedding + KNN（Iter 3）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# 语义类型特征词 → 命中即加权为该类型
_SEMANTIC_TYPE_HINTS: Dict[str, List[str]] = {
    # 关系类型：典型 包含_的_，A与B的关系动词
    "关系类型": [
        "关系", "关联", "从属", "隶属", "属于", "包含", "包括", "组成",
        "连接", "链接", "属于", "对应", "匹配", "对应于", "指向", "引用",
        "依赖", "影响", "导致", "引起", "作用于", "作用在",
    ],
    # 属性类型：值/数量/程度/...后缀
    "属性": [
        "属性", "值", "数量", "程度", "等级", "评分", "状态", "时间",
        "日期", "重量", "长度", "高度", "宽度", "深度", "面积", "体积",
        "价格", "成本", "频率", "速度", "温度", "尺寸", "颜色",
    ],
    # 动作类型：动词+宾语（动宾短语）
    "动作类型": [
        "执行", "调用", "发起", "处理", "操作", "计算", "分析", "决策",
        "创建", "删除", "修改", "更新", "提交", "审批", "审核", "发送",
        "接收", "开始", "停止", "暂停", "触发", "启动", "结束",
    ],
    # 过程类型：流程/序列/生命周期
    "过程类型": [
        "过程", "流程", "事件", "阶段", "步骤", "环节", "周期", "生命周期",
        "场景", "用例", "情节", "任务", "作业", "工序",
    ],
    # 规则类型：规则/约束
    "规则类型": [
        "规则", "约束", "条件", "策略", "阈值", "限制", "范式", "定律",
        "模式", "标准", "规范", "准则", "约定", "假设",
    ],
}

_BUILTIN_STOP_FLAGS: List[str] = [
    "什么", "怎么", "如何", "为什么", "哪里", "哪个", "时候", "地方",
    "现在", "以前", "以后", "今天", "明天", "昨天", "于是", "然后",
    "可以", "可能", "应该", "必须", "需要", "已经", "仍然",
]


class RuleBasedClassifier:
    """规则+词典启发式 L3 分类器。实现 L3Classifier Protocol。"""

    def classify(
        self,
        concepts,  # List[ConceptCandidate]
        *,
        domains: Optional[List[Dict[str, Any]]] = None,
        existing_examples: Optional[Dict[str, List[str]]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):  # -> List[ClassifiedCandidate]
        cfg = config or {}
        default_type = str(cfg.get("default_type", "对象类型"))
        existing_examples = existing_examples or {}

        # domain 匹配索引：{code: 小写化 tokens set}
        domain_index: List[Tuple[str, set]] = []
        for d in (domains or []):
            tokens: set = set()
            for field in ("code", "display_name", "description"):
                v = d.get(field)
                if not v:
                    continue
                # 分字 token（中文每字+英文词）
                tokens.update(self._ngram_tokens(str(v)))
            for s in (d.get("synonyms") or []):
                tokens.update(self._ngram_tokens(str(s)))
            for k, v in (d.get("en_mapping") or {}).items():
                tokens.add(str(k).lower())
                tokens.add(str(v).lower())
            domain_index.append((d["code"], tokens))

        results = []
        for c in concepts:
            canon = str(c.get("canonical") or "")
            type_scores: Dict[str, float] = {k: 0.0 for k in _SEMANTIC_TYPE_HINTS}

            # 特征词打分
            for stype, hints in _SEMANTIC_TYPE_HINTS.items():
                score = 0.0
                for hint in hints:
                    if hint in canon:
                        score += 1.0 / max(len(hint), 1)
                # 上下文包含特征词（弱加权）
                for ctx in (c.get("provenance") or {}).get("sample_contexts", []):
                    for hint in hints:
                        if hint in ctx:
                            score += 0.08
                type_scores[stype] = round(score, 3)

            best_type = max(type_scores.items(), key=lambda kv: kv[1])
            if best_type[1] > 0.0:
                semantic_type = best_type[0]
            else:
                semantic_type = default_type

            # stoplist_flag
            stop_flag = bool(
                canon in _BUILTIN_STOP_FLAGS
                or any(flag == canon for flag in _BUILTIN_STOP_FLAGS)
                or len(canon) == 1
            )

            # domain 匹配：canonical 字集 与 domain 字集的交集比例
            canon_tokens = self._ngram_tokens(canon)
            # 追加同义词
            for s in c.get("synonyms") or []:
                canon_tokens.update(self._ngram_tokens(str(s)))
            for s in c.get("near_synonyms") or []:
                canon_tokens.update(self._ngram_tokens(str(s)))

            domain_id: Optional[str] = None
            best_domain_score = 0.0
            for code, dset in domain_index:
                if not canon_tokens or not dset:
                    continue
                overlap = canon_tokens & dset
                score = len(overlap) / max(len(canon_tokens), 1)
                if score > best_domain_score and score >= 0.2:  # 至少20%覆盖
                    best_domain_score = score
                    domain_id = code

            # 定义：选取包含 canonical 的第一个上下文句子，前后截断 256 字
            definition = ""
            for ctx in (c.get("provenance") or {}).get("sample_contexts", []):
                if canon and canon in str(ctx):
                    s = str(ctx)
                    i = s.find(canon)
                    lo = max(0, i - 60)
                    hi = min(len(s), i + len(canon) + 60)
                    definition = s[lo:hi].strip()
                    break

            # 综合置信度
            type_conf = min(1.0, 0.5 + 0.5 * (best_type[1] if best_type[1] > 0 else 0.4))
            domain_conf = best_domain_score
            base_conf = float(c.get("confidence") or 0.0)
            final_conf = round(base_conf * (0.6 + 0.25 * type_conf + 0.15 * domain_conf), 4)

            results.append({
                "canonical": canon,
                "semantic_type": semantic_type,
                "domain_id": domain_id,
                "definition": definition,
                "confidence": final_conf,
                "examples": (c.get("provenance") or {}).get("sample_contexts", [])[:6],
                "stoplist_flag": stop_flag,
                # L2 继承字段
                "synonyms": list(c.get("synonyms") or []),
                "near_synonyms": list(c.get("near_synonyms") or []),
                "aliases": list(c.get("aliases") or []),
                "source_text": c.get("source_text") or "",
                "provenance": {
                    **(c.get("provenance") or {}),
                    "l3_type_scores": type_scores,
                    "l3_domain_score": round(domain_conf, 4),
                },
                "frequency": int(c.get("frequency") or 0),
            })

        return results

    # ------------------------------------------------------------------
    @staticmethod
    def _ngram_tokens(text: str) -> set:
        """字级 1gram + 2gram + 英文词，用作 domain 匹配特征。"""
        s = str(text).lower().strip()
        toks: set = set()
        en = ""
        cn_chars: List[str] = []
        for ch in s:
            cp = ord(ch)
            if 0x4e00 <= cp <= 0x9fff:
                cn_chars.append(ch)
                if en:
                    toks.add(en)
                    en = ""
            elif ch.isalnum() or ch in ("_", "-"):
                en += ch
                if cn_chars:
                    toks.update(cn_chars)
                    # bigram
                    for i in range(len(cn_chars) - 1):
                        toks.add(cn_chars[i] + cn_chars[i + 1])
                    cn_chars = []
            else:
                if en:
                    toks.add(en)
                    en = ""
                if cn_chars:
                    toks.update(cn_chars)
                    for i in range(len(cn_chars) - 1):
                        toks.add(cn_chars[i] + cn_chars[i + 1])
                    cn_chars = []
        if en:
            toks.add(en)
        if cn_chars:
            toks.update(cn_chars)
            for i in range(len(cn_chars) - 1):
                toks.add(cn_chars[i] + cn_chars[i + 1])
        return toks
