"""L4 关系抽取（零依赖纯规则：基于实体候选的共现 + 中间短语规则）。

Approach A 精简版：只依赖 entity_candidates（L1→L2→L3 产物），
无任何 LLM / 外部 NLP 依赖，保证离线可用 & <=250 LOC。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple


# 关键词：只要出现这类词，频次=1 也作为关系候选（强先验动词）
_KW_RE = re.compile(r"([是属于作为包括具有驱动构建推动负责包含关联管理支撑服务提供处理执行分析记录采集传输保障支持实施配置监控优化协同集成构建组成]){1,3}")

# I4T2 4 类关系类型规则：匹配 phrase 中任意关键字 -> 优先归类
# 注意：匹配顺序有优先级，从高到低
_REL_TYPE_RULES: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("is_a", (
        "是", "属于", "作为", "就是", "乃", "为", "系", "归类为", "归类于", "本质是",
        "本质为", "可视为", "可看作", "又称", "即", "一种", "一类", "是一种", "是一类",
        "包括在", "归属于", "is a kind of", "is a type of", "is a",
    )),
    ("part_of", (
        "组成", "构成", "包含", "隶属于", "部分", "分为", "划分成", "分解为",
        "由...构成", "由...组成", "含", "含有", "成员", "组成部分", "构成部分",
        "part of", "consists of", "composed of", "contains", "include",
    )),
    ("attribute_of", (
        "具有", "拥有", "属性", "特征", "参数", "特性", "性质", "指标", "值为",
        "设定为", "配置为", "等于", "为", "表现为", "呈现", "attribute", "property",
        "feature", "characteristic", "parameter",
    )),
    ("related_to", (
        "关联", "关系", "联系", "连接", "相关", "涉及", "对应", "匹配",
        "使用", "利用", "采用", "驱动", "构建", "推动", "负责", "管理", "支撑",
        "服务", "提供", "处理", "执行", "分析", "记录", "采集", "传输", "保障",
        "支持", "实施", "配置", "监控", "优化", "协同", "集成",
    )),
)
_REL_TYPE_DEFAULT = "related_to"

# 切句标点：中英文句号、分号、问号、感叹号、换行
_SENT_SPLIT_RE = re.compile(r"[。；？!?;；\n\r]+")

# 中文字符（用于 relation_phrase 长度过滤，1~8 字）
_CN_CHAR_RE = re.compile(r"[\u4e00-\u9fffA-Za-z0-9_]")


class RuleBasedRelationExtractor:
    """规则关系抽取器（共现 + 近邻窗口 + 动词关键词）。

    公开方法：
        extract(*, text, entity_candidates, extra_docs=None, **kwargs)
            -> List[候选关系 Dict]，与 entity_candidate schema 对齐，
               semantic_type 固定为 "关系类型"
    """

    def __init__(self, *, max_relation_distance: int = 20) -> None:
        self.max_relation_distance = int(max_relation_distance or 20)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------
    def extract(
        self,
        *,
        text: str,
        entity_candidates: List[Dict[str, Any]],
        extra_docs: Optional[List[str]] = None,
        **_: Any,
    ) -> List[Dict[str, Any]]:
        """抽取 entity_candidates 之间的关系三元组。

        输出 Dict 字段对齐 ol_candidates schema，便于后续 Quality Gate
        和 candidate_store 复用同一套管线。
        """
        # 1. 收集参与匹配的 surface 词：canonical + synonyms
        surfaces: List[Tuple[str, str]] = []  # (surface, canonical)
        seen_surface: set = set()
        for ec in entity_candidates or []:
            canon = (ec.get("canonical") or "").strip()
            if not canon:
                continue
            for surf in [canon, *(ec.get("synonyms") or []), *(ec.get("aliases") or [])]:
                s = (surf or "").strip()
                if not s or s in seen_surface:
                    continue
                seen_surface.add(s)
                surfaces.append((s, canon))
        if not surfaces:
            return []
        # 按长度降序，优先长词匹配（避免 "人工智能" 先被 "人工" 吃了）
        surfaces.sort(key=lambda t: -len(t[0]))

        # 2. 切句
        docs: List[str] = [text or "", *(extra_docs or [])]
        all_text = "\n".join(d for d in docs if d)
        sentences: List[str] = [
            s.strip() for s in _SENT_SPLIT_RE.split(all_text) if s and s.strip()
        ]
        if not sentences:
            return []

        # 3. 每句收集 entity matches -> 取实体对 -> 统计频次
        #    freq[(s_canon, phrase, o_canon)] = (count, sample_sent)
        freq: Dict[Tuple[str, str, str], Tuple[int, str]] = defaultdict(lambda: (0, ""))

        for sent in sentences:
            matches = self._find_all_entity_matches(sent, surfaces)
            # matches: List[(start, end, canonical)]，按 start 升序
            n = len(matches)
            for i in range(n):
                si, ei, sc = matches[i]
                for j in range(i + 1, n):
                    sj, ej, oc = matches[j]
                    if sc == oc:
                        continue  # 同实体跳过
                    if (sj - ei) > self.max_relation_distance:
                        continue
                    if sj < ei:
                        # 实体词有重叠，跳过
                        continue
                    raw_phrase = sent[ei:sj].strip()
                    phrase = self._normalize_phrase(raw_phrase)
                    if not phrase:
                        continue
                    key = (sc, phrase, oc)
                    old_cnt, old_sample = freq[key]
                    freq[key] = (
                        old_cnt + 1,
                        (old_sample or sent),
                    )

        if not freq:
            return []

        max_freq = max(c for (c, _) in freq.values()) or 1

        # 4. 过滤：频次>=2 或 命中关键词
        results: List[Dict[str, Any]] = []
        for (subj, phrase, obj), (f, sample) in freq.items():
            hit_kw = bool(_KW_RE.search(phrase))
            if f < 2 and not hit_kw:
                continue
            confidence = min(1.0, f / max(max_freq, 1))
            # 命中关键词给予一个基础置信度
            if hit_kw and confidence < 0.55:
                confidence = 0.55
            canonical_key = f"{subj}_{phrase}_{obj}"
            rel_type, rel_rule, rel_score = RuleBasedRelationExtractor.classify_relation_type(
                phrase, frequency=f
            )
            results.append({
                "canonical": canonical_key,
                "semantic_type": "关系类型",
                "synonyms": [phrase, f"{subj}{phrase}{obj}"],
                "near_synonyms": [],
                "aliases": [],
                "definition": f"通过语料推断：{subj} —{phrase}→ {obj}",
                "examples": [sample] if sample else [],
                "confidence": round(confidence, 3),
                "source_text": sample or "",
                "provenance": {
                    "L4": True,
                    "subject_canonical": subj,
                    "object_canonical": obj,
                    "relation_phrase": phrase,
                    "frequency": f,
                    "algorithm": "rule_based_cooccurrence",
                    "relation_type": rel_type,
                    "relation_type_rule": rel_rule,
                    "relation_type_score": round(rel_score, 3),
                },
                "status": "new",
                "stoplist_flag": False,
            })
        # 按置信度降序
        results.sort(key=lambda c: -float(c.get("confidence") or 0.0))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _find_all_entity_matches(
        sent: str, surfaces: List[Tuple[str, str]]
    ) -> List[Tuple[int, int, str]]:
        found: List[Tuple[int, int, str]] = []
        used: List[Tuple[int, int]] = []  # 被占用的 [start, end) 区间，防重叠
        for surf, canon in surfaces:
            pat = re.escape(surf)
            for m in re.finditer(pat, sent):
                s, e = m.start(), m.end()
                if any(not (e <= us or s >= ue) for us, ue in used):
                    continue
                used.append((s, e))
                found.append((s, e, canon))
        found.sort(key=lambda x: x[0])
        return found

    @staticmethod
    def _normalize_phrase(raw: str) -> str:
        if not raw:
            return ""
        # 去前后空白与常见边界标点
        phrase = raw.strip(" ,，、:：;；|/\\-—_[]()（）【】\"'`\t")
        # 长度过滤：1~8 个有效字符（中文/英文/数字/下划线）
        chars = _CN_CHAR_RE.findall(phrase)
        if not (1 <= len(chars) <= 8):
            return ""
        # 纯标点
        if not chars:
            return ""
        return phrase

    # ------------------------------------------------------------------
    # I4T2: 4 类关系类型分类
    # ------------------------------------------------------------------
    @staticmethod
    def classify_relation_type(
        phrase: str,
        *,
        frequency: int = 1,
    ) -> Tuple[str, str, float]:
        """把关系短语分到 4 类之一（有优先级）。

        Returns:
            (relation_type ∈ {is_a,part_of,attribute_of,related_to},
             matched_rule_keyword,
             score 0.3~1.0)
        """
        p = str(phrase or "").strip()
        if not p:
            return _REL_TYPE_DEFAULT, "empty_phrase_default", 0.3
        # 按优先级匹配：is_a > part_of > attribute_of > related_to
        for rel_type, keywords in _REL_TYPE_RULES:
            for kw in keywords:
                if not kw:
                    continue
                if kw in p:
                    # 基础分：频率越高分越高；匹配更长关键词分更高
                    base = 0.55 + min(0.3, 0.04 * int(frequency or 1))
                    bonus = min(0.15, 0.02 * len(kw))
                    score = min(1.0, base + bonus)
                    return rel_type, kw, score
        # 无匹配：related_to 默认低频分
        score = 0.35 + min(0.2, 0.03 * int(frequency or 1))
        return _REL_TYPE_DEFAULT, "default_fallback", score
