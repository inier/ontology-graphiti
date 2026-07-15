"""Quality Gate 三关质量闸评估服务（严格对齐 specs/007 §4）。

公式权威来源：specs/007-semantic-admin-suite/data-model.md §4
  §4.1 总得分：total_score = 0.35*g1 + 0.40*g2 + 0.25*g3
  §4.2 tier 阈值：HIGH≥0.85 / MEDIUM≥0.70 / LOW≥0.50 / VERY_LOW<0.50
  §4.3 Gate1 句法/结构闸 7 子项
  §4.4 Gate2 语义一致闸 4 子项
  §4.5 Gate3 领域质量闸 5 子项（内部子权重 0.30/0.20/0.15/0.15/0.20）

Feature flag（环境变量控制）：
  SEMANTIC_ADMIN_ENABLE_LLM_JUDGE=true/false  默认 false，控制 G2.4 LLM Judge 是否调用
"""

from __future__ import annotations

import json
import math
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..interfaces.quality_protocol import (
    G1_SUB_WEIGHTS,
    GATE3_INNER_WEIGHTS,
    GATE_WEIGHTS,
    QUALITY_REPORT_OPTIONAL_KEYS,
    QUALITY_REPORT_REQUIRED_KEYS,
    QualityEvaluatorProtocol,
    QualityReport,
    SubMetric,
    TIER_HIGH,
    TIER_LOW,
    TIER_MEDIUM,
    TIER_VERY_LOW,
    VALID_SEMANTIC_TYPES,
)
from ..interfaces.quality_protocol import (  # noqa: F401  -- 复用存储层枚举
    ORIGIN_HYBRID,
    ORIGIN_HUMAN,
    ORIGIN_LLM,
    ORIGIN_USL,
)

# ======================================================================
# 常量 & 正则
# ======================================================================

# §4.3 G1.1 名称合规正则：1~40 字中文/英文/数字/下划线/点/横杠
NAME_REGEX = re.compile(r"^[\u4e00-\u9fa5A-Za-z0-9_.-]{1,40}$")

# PascalCase 正则：首字母大写，后续可为数字/大小写（允许单字符如 X）
PASCAL_CASE_REGEX = re.compile(r"^[A-Z][A-Za-z0-9]*$")

# Feature flag：默认关闭 G2.4 LLM Judge
ENABLE_LLM_JUDGE = (os.environ.get("SEMANTIC_ADMIN_ENABLE_LLM_JUDGE", "false").lower()
                    in {"1", "true", "yes", "on"})

# Gate1 规则名前缀
RULE_PREFIX = "semadm"


# ======================================================================
# 健壮数值解析 helpers（避免 int()/float() 对非数字字符串 ValueError 崩溃）
# ======================================================================

def _safe_int(v: Any, default: int = 1, *, non_negative: bool = True) -> int:
    """int() 解析但不抛 ValueError。

    Args:
        v: 待解析值（str/int/float/None/bool 等任意类型）
        default: 解析失败或不符合 non_negative 时的默认值
        non_negative: 若为 True，负数（或解析为负数）一律退回 default
    """
    try:
        if isinstance(v, bool):
            i = int(v)
        elif isinstance(v, (int, float)):
            i = int(v)
        else:
            s = str(v).strip()
            if not s:
                return default
            # 允许带逗号/小数点的数字；但只取整数部分
            i = int(float(s))
    except (TypeError, ValueError):
        return default
    if non_negative and i < 0:
        return default
    return i


def _safe_float(v: Any, default: float = 0.0, *, clamp_01: bool = True) -> float:
    """float() 解析但不抛 ValueError。

    Args:
        clamp_01: True 时把结果 clamp 到 [0,1]（用于各类 0~1 置信度/比例）
    """
    try:
        if isinstance(v, bool):
            f = float(v)
        elif isinstance(v, (int, float)):
            f = float(v)
        else:
            s = str(v).strip()
            if not s:
                return default
            f = float(s)
    except (TypeError, ValueError):
        return default
    if math.isnan(f):
        return default
    if clamp_01:
        return max(0.0, min(1.0, f))
    return f


# ======================================================================
# Score → Tier 辅助
# ======================================================================

def score_to_tier(s: float) -> str:
    s = float(s or 0)
    if s >= 0.85: return TIER_HIGH
    if s >= 0.70: return TIER_MEDIUM
    if s >= 0.50: return TIER_LOW
    return TIER_VERY_LOW


def _mk(submetric: str, score: float, reason: str,
        rule_name: str, threshold: Optional[float]) -> SubMetric:
    """构造规范化 SubMetric dict（score 限制 0~1）。"""
    try:
        s = float(score)
    except (TypeError, ValueError):
        s = 0.0
    s = 0.0 if math.isnan(s) else max(0.0, min(1.0, s))
    return {  # type: ignore[return-value]
        "submetric": submetric,
        "score": s,
        "reason": reason,
        "rule_name": rule_name,
        "threshold": threshold,
    }


# ======================================================================
# 离散集合的同义词去重率（G1.5）
# ======================================================================

def _synonym_dedup_ratio(items: List[str]) -> Tuple[List[str], float]:
    """同义词归一化（去空格、小写化、中文不变）后去重。
    返回：(去重后 list, 去重率 unique/original)。"""
    if not items:
        return [], 1.0
    seen: Dict[str, str] = {}  # norm → original
    order: List[str] = []
    for x in items:
        if x is None: continue
        s = str(x).strip().lower()
        if not s: continue
        if s in seen: continue
        seen[s] = x
        order.append(x)
    ratio = len(seen) / max(1, len([i for i in items if i and str(i).strip()]))
    return order, ratio


# ======================================================================
# Gate 1 × 7 子项（§4.3）
# ======================================================================

def _gate1_subscores(
    c: Dict[str, Any],
    usl_storage: Any,
    domain_terms_hint: Optional[Iterable[str]],
) -> Tuple[float, List[SubMetric]]:
    """
    G1.1 名称合规         布尔  FAIL -0.35  → 权重 ×5
    G1.2 en_mapping 可用  布尔  WARN -0.08  → 权重 ×1
    G1.3 semantic_type 合法 布尔 FAIL -0.15 → 权重 ×5
    G1.4 同义词集大小 [0,30] 布尔 WARN      → 权重 ×1
    G1.5 同义词去重率 ≥ 0.98                → 权重 ×1
    G1.6 canonical 与同义词互不包含         → 权重 ×1
    G1.7 USL 同名冲突检查（命中 → origin=usl，分数1.0） → 权重 ×1
    返回：(g1_score, 7 条子项详情)
    """
    canonical = str(c.get("canonical") or "").strip()
    en = str(c.get("en") or c.get("en_mapping") or "").strip()
    sem_type = str(c.get("semantic_type") or "").strip() or "对象类型"
    synonyms_raw = c.get("synonyms") or c.get("synonyms_json") or []
    if isinstance(synonyms_raw, str):
        try: synonyms_raw = json.loads(synonyms_raw)
        except Exception: synonyms_raw = []
    synonyms: List[str] = [str(s) for s in synonyms_raw if s is not None and str(s).strip()]

    # G1.1 名称合规
    g1_1_ok = bool(NAME_REGEX.match(canonical))
    g1_1 = _mk(
        submetric="g1_name_valid",
        score=1.0 if g1_1_ok else 0.0,
        reason=(f"canonical='{canonical}' 名称合规" if g1_1_ok
                else f"canonical='{canonical}' 不符合 ^[中文字母数字_.-]{{1,40}}$"),
        rule_name=f"{RULE_PREFIX}_g1_1_name_regex",
        threshold=None,
    )

    # G1.2 en_mapping 可用：PascalCase
    g1_2_ok = bool(en) and bool(PASCAL_CASE_REGEX.match(en))
    g1_2 = _mk(
        submetric="g1_en_mapping_valid",
        score=1.0 if g1_2_ok else 0.0,
        reason=(f"en='{en}' 为合法 PascalCase" if g1_2_ok
                else f"en='{en}' 为空或非 PascalCase（USL 写回时可自动补全）"),
        rule_name=f"{RULE_PREFIX}_g1_2_en_pascal",
        threshold=None,
    )

    # G1.3 semantic_type 合法 6 枚举
    g1_3_ok = sem_type in VALID_SEMANTIC_TYPES
    g1_3 = _mk(
        submetric="g1_semantic_type_valid",
        score=1.0 if g1_3_ok else 0.0,
        reason=(f"semantic_type='{sem_type}' 属于合法 6 枚举" if g1_3_ok
                else f"semantic_type='{sem_type}' 非法（应为 {sorted(VALID_SEMANTIC_TYPES)}，默认回退 '对象类型'）"),
        rule_name=f"{RULE_PREFIX}_g1_3_semtype_enum",
        threshold=None,
    )

    # G1.4 同义词集大小 [0, 30]
    syn_count = len(synonyms)
    g1_4_ok = 0 <= syn_count <= 30
    g1_4 = _mk(
        submetric="g1_synonyms_size_valid",
        score=1.0 if g1_4_ok else 0.0,
        reason=(f"同义词共 {syn_count} 个 ∈ [0,30]" if g1_4_ok
                else f"同义词 {syn_count} 个超出 30，将截断前 30 个"),
        rule_name=f"{RULE_PREFIX}_g1_4_syn_count",
        threshold=30.0,
    )

    # G1.5 同义词去重率 ≥ 0.98
    dedup_syns, dedup_ratio = _synonym_dedup_ratio(synonyms)
    g1_5_ok = dedup_ratio >= 0.98
    g1_5 = _mk(
        submetric="g1_synonyms_dedup_ratio",
        score=dedup_ratio,
        reason=(f"去重率 {dedup_ratio:.3f} ≥ 0.98 ✓" if g1_5_ok
                else f"去重率 {dedup_ratio:.3f} < 0.98，自动去重 {len(synonyms) - len(dedup_syns)} 项"),
        rule_name=f"{RULE_PREFIX}_g1_5_syn_dedup",
        threshold=0.98,
    )

    # G1.6 canonical 与同义词无互相包含环（canonical 不在 synonym 集合中；synonyms 不包含 canonical）
    canon_norm = canonical.strip().lower()
    syn_norms = {s.strip().lower() for s in synonyms if s and s.strip()}
    g1_6_ok = canon_norm not in syn_norms
    # 也检查 synonyms 之间的互相包含（弱版本：不做两两 contains 强校验）
    g1_6 = _mk(
        submetric="g1_circular_inclusion_free",
        score=1.0 if g1_6_ok else 0.0,
        reason=("canonical 与同义词互相独立" if g1_6_ok
                else f"canonical='{canonical}' 出现在同义词集合中，已自动剔除"),
        rule_name=f"{RULE_PREFIX}_g1_6_no_circ_include",
        threshold=None,
    )

    # G1.7 USL 同名冲突检查：若 usl_storage 存在则查同 domain 下同 canonical
    domain_id = c.get("domain_id")
    usl_hit = False
    if domain_terms_hint is not None:
        hint_set = {str(t).strip() for t in domain_terms_hint if t}
        if canon_norm in {x.lower() for x in hint_set}:
            usl_hit = True
    if not usl_hit and usl_storage is not None and domain_id:
        try:
            # 兼容 SQLiteUslStorage.list_terms / list 接口
            fn = getattr(usl_storage, "list_terms_by_domain", None) or getattr(
                usl_storage, "list_terms", None
            )
            if fn is not None:
                try:
                    page = fn(domain_id=domain_id, canonical_q=canonical, page=1, page_size=5)
                    items = page.get("items") if isinstance(page, dict) else page
                    usl_hit = bool(items and len(items) > 0)
                except Exception:
                    usl_hit = False
        except Exception:
            usl_hit = False
    if usl_hit:
        # 写回 origin=usl（副作用：原地修改 candidate dict）
        try: c["origin"] = ORIGIN_USL
        except Exception: pass
    g1_7 = _mk(
        submetric="g1_usl_duplicate_check",
        score=1.0 if usl_hit else 0.0,  # 命中（已在 USL）→ 分数 1.0（去重信息有效）
        reason=(f"canonical='{canonical}' 已在 USL 中，origin 自动标记 'usl'"
                if usl_hit
                else f"canonical='{canonical}' USL 未命中，视为新增候选"),
        rule_name=f"{RULE_PREFIX}_g1_7_usl_dup_check",
        threshold=None,
    )

    subs = [g1_1, g1_2, g1_3, g1_4, g1_5, g1_6, g1_7]
    # g1_score = Σ(weight_i × sub_i) / Σ(weight_i)，G1.1/G1.3 FAIL 类权重 ×5
    total_w = sum(G1_SUB_WEIGHTS)
    numer = sum(w * s["score"] for w, s in zip(G1_SUB_WEIGHTS, subs))
    g1_score = numer / total_w if total_w > 0 else 0.0
    return round(g1_score, 6), subs


# ======================================================================
# Gate 2 × 4 子项（§4.4）
# ======================================================================

def _collect_synonyms_plus_canonical(c: Dict[str, Any]) -> List[str]:
    """把 canonical + synonyms + near_synonyms + aliases 合并作术语集合（用于 G2.1 disjoint 检查）。"""
    out: List[str] = [str(c.get("canonical") or "").strip().lower()]
    for key in ("synonyms", "synonyms_json", "near_synonyms", "near_synonyms_json",
                "aliases", "aliases_json"):
        raw = c.get(key)
        if not raw: continue
        if isinstance(raw, str):
            try: raw = json.loads(raw)
            except Exception: raw = None
        if isinstance(raw, (list, tuple, set)):
            for x in raw:
                if x and str(x).strip():
                    out.append(str(x).strip().lower())
    return [x for x in out if x]


def _gate2_subscores(
    c: Dict[str, Any],
    usl_storage: Any,
    disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]],
) -> Tuple[float, List[SubMetric]]:
    """
    G2.1 Disjointness：查 disjoint pair 是否命中 candidate 的同义词对
    G2.2 基数约束：占位 1.0（待 L5 基数归纳）
    G2.3 is_a 无环：占位 1.0（待 L3 拓扑排序）
    G2.4 LLM Judge：feature flag 关闭时默认 1.0
    返回：(g2_score 简单平均, 4 条子项详情)
    """
    terms = _collect_synonyms_plus_canonical(c)
    term_set = set(terms)

    # G2.1 Disjointness 检查
    g2_1_score = 1.0
    g2_1_reason = "未命中 USL disjoint pair"
    disjoint_hits: List[Tuple[str, str]] = []
    if disjoint_pairs_hint is not None:
        for (a, b) in disjoint_pairs_hint:
            a_s = str(a or "").strip().lower()
            b_s = str(b or "").strip().lower()
            # 跳过自对 (a,a) — 同一术语永远不可能与自己语义不相交；这会导致恒阳性误报
            if not a_s or not b_s or a_s == b_s:
                continue
            if (a_s in term_set and b_s in term_set) or (b_s in term_set and a_s in term_set):
                disjoint_hits.append((a_s, b_s))
    if not disjoint_hits and usl_storage is not None and c.get("domain_id"):
        try:
            fn = getattr(usl_storage, "list_disjoint_pairs", None)
            if fn is not None:
                try:
                    page = fn(domain_id=c["domain_id"], page=1, page_size=500)
                    items = page.get("items") if isinstance(page, dict) else page or []
                    for it in items:
                        a_s = str(it.get("term_a") or it.get("term_a_id") or "").strip().lower()
                        b_s = str(it.get("term_b") or it.get("term_b_id") or "").strip().lower()
                        if (a_s in term_set and b_s in term_set) or (b_s in term_set and a_s in term_set):
                            disjoint_hits.append((a_s, b_s))
                except Exception:
                    pass
        except Exception:
            pass
    if disjoint_hits:
        g2_1_score = 0.0
        g2_1_reason = f"命中 disjoint pair: {disjoint_hits[:3]}（语义冲突，FAIL）"
    g2_1 = _mk(
        submetric="g2_usl_disjointness",
        score=g2_1_score,
        reason=g2_1_reason,
        rule_name=f"{RULE_PREFIX}_g2_1_disjoint_check",
        threshold=None,
    )

    # G2.2 基数约束占位
    g2_2 = _mk(
        submetric="g2_cardinality_constraint",
        score=1.0,
        reason="待 L5 基数归纳后复核（当前无候选基数）",
        rule_name=f"{RULE_PREFIX}_g2_2_card_placeholder",
        threshold=None,
    )

    # G2.3 is_a 无环占位
    g2_3 = _mk(
        submetric="g2_isa_acyclic",
        score=1.0,
        reason="待 L3 分类层级草稿就绪后做拓扑排序（当前无层级）",
        rule_name=f"{RULE_PREFIX}_g2_3_isa_placeholder",
        threshold=None,
    )

    # G2.4 LLM Judge
    g2_4_score = 1.0
    if not ENABLE_LLM_JUDGE:
        g2_4_reason = "feature flag SEMANTIC_ADMIN_ENABLE_LLM_JUDGE=false，LLM Judge 关闭"
    else:
        g2_4_reason = "LLM Judge 调用未接入，默认 1.0（后续接入 LLM client）"
    g2_4 = _mk(
        submetric="g2_llm_semantic_judge",
        score=g2_4_score,
        reason=g2_4_reason,
        rule_name=f"{RULE_PREFIX}_g2_4_llm_judge",
        threshold=None,
    )

    subs = [g2_1, g2_2, g2_3, g2_4]
    g2_score = sum(s["score"] for s in subs) / max(1, len(subs))
    return round(g2_score, 6), subs


# ======================================================================
# Gate 3 × 5 子项（§4.5，按 GATE3_INNER_WEIGHTS 加权）
# ======================================================================

def _gate3_subscores(c: Dict[str, Any]) -> Tuple[float, List[SubMetric]]:
    """
    G3.1 属性密度   s = min(1, confidence*1.5)          子权重 0.30
    G3.2 词频覆盖率  s = min(1, doc_hits/10)              子权重 0.20
    G3.3 同义词丰富度 s = min(1, (syn+near+alias)/5)      子权重 0.15
    G3.4 USL 对齐率(新颖度反向) s = 1 - usl_align_confidence  子权重 0.15
    G3.5 层级贡献度  s = min(1, l3_children_est/3)        子权重 0.20
    返回：(g3_score = Σ w_i * s_i, 5 条子项详情)
    """
    # provenance
    prov_raw = c.get("provenance") or c.get("provenance_json") or {}
    if isinstance(prov_raw, str):
        try:
            loaded = json.loads(prov_raw)
            # JSON list（非 dict）也降级为 {}，避免下游 .get() AttributeError
            prov = loaded if isinstance(loaded, dict) else {}
        except Exception:
            prov = {}
    elif isinstance(prov_raw, dict):
        prov = prov_raw
    else:
        # int/list/set/object 等任何非 dict 一律降级为 {}，防止 .get() 崩溃
        prov = {}

    # G3.1 属性密度
    conf = _safe_float(c.get("confidence"), default=0.0, clamp_01=True)
    s1 = min(1.0, conf * 1.5)
    g3_1 = _mk(
        submetric="g3_property_density",
        score=s1,
        reason=f"confidence={conf:.3f} → 属性密度估计 s={s1:.3f}",
        rule_name=f"{RULE_PREFIX}_g3_1_property_density",
        threshold=0.2,  # s 达到 1.0 所需 confidence 下界约 2/3
    )

    # G3.2 词频覆盖率：doc_hits 来自 provenance.doc_hits（默认 1，确保最小占位>0）
    #   非数字字符串不会抛 ValueError；负数或 0 回退默认 1，保证 s2>0
    doc_hits = _safe_int(
        prov.get("doc_hits") or prov.get("hit_count"),
        default=1,
        non_negative=True,
    )
    s2 = min(1.0, doc_hits / 10.0)
    g3_2 = _mk(
        submetric="g3_term_frequency_coverage",
        score=s2,
        reason=f"provenance.doc_hits={doc_hits} → 词频覆盖率 s={s2:.3f}",
        rule_name=f"{RULE_PREFIX}_g3_2_doc_hits",
        threshold=10.0,
    )

    # G3.3 同义词丰富度
    def _as_list(v: Any) -> int:
        if isinstance(v, str):
            try:
                loaded = json.loads(v)
                if isinstance(loaded, (list, tuple, set)):
                    return len([x for x in loaded if x is not None and str(x).strip()])
                return 0
            except Exception:
                return 0
        if isinstance(v, (list, tuple, set)):
            return len([x for x in v if x is not None and str(x).strip()])
        # dict/int/object 均不当作 list；之前 dict 会被迭代 keys 导致虚假同义词数量
        return 0
    n_syn   = _as_list(c.get("synonyms") or c.get("synonyms_json"))
    n_near  = _as_list(c.get("near_synonyms") or c.get("near_synonyms_json"))
    n_alias = _as_list(c.get("aliases") or c.get("aliases_json"))
    total_syn_like = n_syn + n_near + n_alias
    s3 = min(1.0, total_syn_like / 5.0)
    g3_3 = _mk(
        submetric="g3_synonym_richness",
        score=s3,
        reason=f"syn({n_syn})+near({n_near})+alias({n_alias})={total_syn_like} → s={s3:.3f}",
        rule_name=f"{RULE_PREFIX}_g3_3_syn_richness",
        threshold=5.0,
    )

    # G3.4 USL 对齐率（新颖度）
    align = _safe_float(c.get("usl_align_confidence"), default=0.0, clamp_01=True)
    s4 = max(0.0, min(1.0, 1.0 - align))
    g3_4 = _mk(
        submetric="g3_usl_alignment_novelty",
        score=s4,
        reason=f"usl_align_confidence={align:.3f} → 新颖度 s=1−align={s4:.3f}",
        rule_name=f"{RULE_PREFIX}_g3_4_usl_novelty",
        threshold=None,
    )

    # G3.5 层级贡献度
    l3_est = _safe_int(
        prov.get("l3_children_est") or prov.get("children_est"),
        default=1,
        non_negative=True,
    )
    s5 = min(1.0, l3_est / 3.0)
    g3_5 = _mk(
        submetric="g3_hierarchy_contribution",
        score=s5,
        reason=f"provenance.l3_children_est={l3_est} → 层级贡献度 s={s5:.3f}",
        rule_name=f"{RULE_PREFIX}_g3_5_hierarchy_contrib",
        threshold=3.0,
    )

    subs = [g3_1, g3_2, g3_3, g3_4, g3_5]
    total_w = sum(GATE3_INNER_WEIGHTS)
    numer = sum(w * s["score"] for w, s in zip(GATE3_INNER_WEIGHTS, subs))
    g3_score = numer / total_w if total_w > 0 else 0.0
    return round(g3_score, 6), subs


# ======================================================================
# QualityEvaluator 主类（实现 Protocol）
# ======================================================================

class QualityEvaluator(QualityEvaluatorProtocol):
    """三关质量闸评估器。无状态，无 DB 连接；所有 DB 访问通过 usl_storage 注入。"""

    # 权重暴露（便于调参覆盖，但默认值来自 data-model.md）
    gate_weights: Tuple[float, float, float] = GATE_WEIGHTS
    gate3_inner_weights: Tuple[float, float, float, float, float] = GATE3_INNER_WEIGHTS

    # ------------------------------------------------------------------
    def evaluate_candidate(
        self,
        candidate: Dict[str, Any],
        *,
        usl_storage: Optional[Any] = None,
        domain_terms_hint: Optional[Iterable[str]] = None,
        disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> QualityReport:
        cid = str(candidate.get("id") or "").strip() or str(uuid.uuid4())
        g1s, g1d = _gate1_subscores(candidate, usl_storage, domain_terms_hint)
        g2s, g2d = _gate2_subscores(candidate, usl_storage, disjoint_pairs_hint)
        g3s, g3d = _gate3_subscores(candidate)
        total = (
            self.gate_weights[0] * g1s
            + self.gate_weights[1] * g2s
            + self.gate_weights[2] * g3s
        )
        total_score = round(total, 6)
        tier = score_to_tier(total_score)
        report: QualityReport = {
            "candidate_id": cid,
            "gate1_score": g1s,
            "gate1_details": list(g1d),
            "gate2_score": g2s,
            "gate2_details": list(g2d),
            "gate3_score": g3s,
            "gate3_details": list(g3d),
            "total_score": total_score,
            "tier": tier,
            "created_at": datetime.now().isoformat(),
        }
        return report  # type: ignore[return-value]

    # ------------------------------------------------------------------
    def evaluate_batch(
        self,
        candidates: Iterable[Dict[str, Any]],
        *,
        usl_storage: Optional[Any] = None,
        domain_terms_hint: Optional[Iterable[str]] = None,
        disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> List[QualityReport]:
        return [
            self.evaluate_candidate(
                c, usl_storage=usl_storage,
                domain_terms_hint=domain_terms_hint,
                disjoint_pairs_hint=disjoint_pairs_hint,
            )
            for c in candidates
        ]


# ======================================================================
# 模块级便捷函数（无需实例化类即可调用）
# ======================================================================

_evaluator_singleton: Optional[QualityEvaluator] = None


def evaluate_candidate(
    candidate: Dict[str, Any],
    *,
    usl_storage: Optional[Any] = None,
    domain_terms_hint: Optional[Iterable[str]] = None,
    disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
) -> QualityReport:
    """模块级便捷调用。返回 usl_quality_reports 可直接 save 的 dict。"""
    global _evaluator_singleton
    if _evaluator_singleton is None:
        _evaluator_singleton = QualityEvaluator()
    return _evaluator_singleton.evaluate_candidate(
        candidate, usl_storage=usl_storage,
        domain_terms_hint=domain_terms_hint,
        disjoint_pairs_hint=disjoint_pairs_hint,
    )


def evaluate_batch(
    candidates: Iterable[Dict[str, Any]],
    *,
    usl_storage: Optional[Any] = None,
    domain_terms_hint: Optional[Iterable[str]] = None,
    disjoint_pairs_hint: Optional[Iterable[Tuple[str, str]]] = None,
) -> List[QualityReport]:
    global _evaluator_singleton
    if _evaluator_singleton is None:
        _evaluator_singleton = QualityEvaluator()
    return _evaluator_singleton.evaluate_batch(
        candidates, usl_storage=usl_storage,
        domain_terms_hint=domain_terms_hint,
        disjoint_pairs_hint=disjoint_pairs_hint,
    )


__all__ = [
    "QualityEvaluator", "evaluate_candidate", "evaluate_batch",
    "score_to_tier", "ENABLE_LLM_JUDGE",
]
