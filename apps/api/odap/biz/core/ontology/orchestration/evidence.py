"""证据解析器（AC-37 的实现，供运行时自检与 `scripts/verify_provenance.py` 共用）。

逐类解析规则（全部确定性，无 LLM、无网络模糊判断）：
    tbox_node     `ObjectType:Order` / `RelationType:placedBy` → 查 TBox 索引（真读 SQLite）
    metric        `metric:order_return_rate@2026Q3` → 去时间后缀查指标定义（TBox indicator）
    opa_decision  `policies/xxx.rego#allow` → rego 文件存在且规则名可命中
    doc           `doc:<id>` / `repo:docs/...` → 查纳管文档/条目（knowledge 域，真读 SQLite）
    dict_hit      `USL:term:<canonical>` → 查 USL 术语表
    decision      `decision:<name>` → 必须是编排层已知决策枚举（防拼写错漏导致假证据）
    graph_edge    查 Neo4j 真实边/节点（`impl/graph_evidence.py`，AC-37）；图后端不可用时
                  **显式不可解析**（返回 `GRAPH_UNAVAILABLE`，绝不假通过）
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Optional, Set, Tuple

from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

logger = logging.getLogger(__name__)

#: 编排层决策枚举（只允许这些 ref，防止「随便写个 decision 就声称已决」）
DECISION_REFS: Set[str] = {
    "decision:clarify_required",
    "decision:clarify_no_dictionary_hit",
    "decision:clarify_dictionary_unavailable",
    "decision:unmapped_to_gap_pool",
    "decision:guard_degraded_opa_unavailable",
    "decision:retrieval_degraded",
    "decision:no_evidence",
    "decision:no_answer_accepted",
    "decision:contract_ok",
    "decision:contract_violation",
    "decision:blocked_by_guard",
    "decision:skipped_after_block",
    "decision:intent_l3_used",
    "decision:intent_l3_unavailable",
}

#: 意图类别枚举（`intent_cue` 证据只允许这些值）
INTENT_CLASSES: Set[str] = {
    "metric_query",
    "concept_lookup",
    "relation_lookup",
    "property_lookup",
    "process_lookup",
    "rule_lookup",
    "action_request",
}


class DefaultEvidenceResolver:
    """默认证据解析器。"""

    def __init__(
        self,
        catalog: Optional[TBoxCatalog] = None,
        graph_verifier: Optional[Callable[[str], Tuple[bool, str]]] = None,
        doc_verifier: Optional[Callable[[str], Tuple[bool, str]]] = None,
        usl_verifier: Optional[Callable[[str], Tuple[bool, str]]] = None,
    ) -> None:
        self.catalog = catalog or TBoxCatalog()
        self._graph_verifier = graph_verifier
        self._doc_verifier = doc_verifier
        self._usl_verifier = usl_verifier

    def resolve(self, kind: str, ref: str) -> Tuple[bool, str]:
        value = (ref or "").strip()
        if not value:
            return False, "ref 为空"
        try:
            if kind == "tbox_node":
                return self._resolve_tbox(value)
            if kind == "metric":
                return self._resolve_metric(value)
            if kind == "opa_decision":
                return self._resolve_policy(value)
            if kind == "doc":
                return self._resolve_doc(value)
            if kind == "dict_hit":
                return self._resolve_usl(value)
            if kind == "decision":
                return (True, "") if value in DECISION_REFS else (False, "未知决策枚举")
            if kind == "graph_edge":
                return self._resolve_graph(value)
            if kind == "intent_cue":
                return self._resolve_intent_cue(value)
        except Exception as exc:  # noqa: BLE001 - 解析失败必须显式返回原因
            logger.warning("evidence resolve error: kind=%s ref=%s error=%s", kind, value, exc)
            return False, f"{type(exc).__name__}: {exc}"
        return False, f"未知证据种类：{kind}"

    # ── 分类解析 ──────────────────────────────────────────────────────────
    def _resolve_tbox(self, ref: str) -> Tuple[bool, str]:
        kind, _, element_id = ref.partition(":")
        if not kind or not element_id:
            return False, "tbox_node ref 必须是 <Kind>:<ID>"
        return (True, "") if self.catalog.exists(kind, element_id) else (
            False, f"TBox 中不存在 {ref}"
        )

    def _resolve_metric(self, ref: str) -> Tuple[bool, str]:
        name = ref.split(":", 1)[-1].split("@", 1)[0]
        hit = self.catalog.lookup(name)
        if hit is None:
            return False, f"指标定义不存在：{name}"
        return (True, "") if hit[1]["kind"] == "metric" else (
            False, f"{name} 不是指标类型（实际 {hit[1]['kind']}）"
        )

    def _resolve_policy(self, ref: str) -> Tuple[bool, str]:
        from odap.biz.core.ontology.orchestration.impl.rule_guard import policy_ref_exists

        return (True, "") if policy_ref_exists(ref) else (False, f"策略规则不存在：{ref}")

    def _resolve_doc(self, ref: str) -> Tuple[bool, str]:
        if self._doc_verifier is not None:
            return self._doc_verifier(ref)
        return _default_doc_verifier(ref)

    def _resolve_usl(self, ref: str) -> Tuple[bool, str]:
        if self._usl_verifier is not None:
            return self._usl_verifier(ref)
        return _default_usl_verifier(ref)

    def _resolve_graph(self, ref: str) -> Tuple[bool, str]:
        """图证据：默认走 Neo4j 存在性校验；注入 verifier 时以注入者为准。"""
        if self._graph_verifier is not None:
            return self._graph_verifier(ref)
        from odap.biz.core.ontology.orchestration.impl.graph_evidence import (
            verify_graph_ref,
        )

        return verify_graph_ref(ref)

    def _resolve_intent_cue(self, ref: str) -> Tuple[bool, str]:
        """形态学意图证据：`cue:<intent>:<surface>`，意图类别合法且后缀可解释才算。

        校验口径：surface 必须以该类别的注册后缀结尾，或本身是 USL 已登记术语——
        防止「随便写个 cue 就声称某段文字是某个意图」（与 graph_edge 同一条纪律）。
        """
        from odap.biz.core.ontology.orchestration.impl.intent_cues import (
            PROCESS_CUES,
            PROPERTY_CUES,
            RULE_CUES,
            METRIC_CUES,
        )

        parts = ref.split(":", 2)
        if len(parts) != 3 or parts[0] != "cue":
            return False, "intent_cue ref 必须形如 cue:<intent>:<surface>"
        intent, surface = parts[1], parts[2].strip()
        if intent not in INTENT_CLASSES:
            return False, f"未知意图类别：{intent}"
        if not surface:
            return False, "intent_cue 的 surface 为空"
        cue_table = {
            "metric_query": METRIC_CUES,
            "property_lookup": PROPERTY_CUES,
            "process_lookup": PROCESS_CUES,
            "rule_lookup": RULE_CUES,
        }.get(intent, ())
        if cue_table and surface.endswith(tuple(cue_table)):
            return True, ""
        if _usl_has_term(surface):
            return True, ""
        return False, f"{surface} 既不以 {intent} 的注册后缀结尾，也不是 USL 术语"


def _usl_has_term(surface: str) -> bool:
    from odap.biz.core.ontology.orchestration.impl.intent_router import UslDictionary

    mapping = UslDictionary().load()
    return surface in mapping


def _default_doc_verifier(ref: str) -> Tuple[bool, str]:
    """文档类证据：查纳管文档与 Wiki 条目（knowledge 域，真读 SQLite）。"""
    from odap.biz.knowledge.governance.public import get_doc_repository
    from odap.biz.knowledge.wiki.public import get_entry_repository

    target = ref
    for prefix in ("doc:", "entry:", "wiki:"):
        if target.lower().startswith(prefix):
            target = target[len(prefix):]
            break
    target = target.split("#", 1)[0]

    if get_entry_repository().get(target) is not None:
        return True, ""
    if get_entry_repository().get_by_source_ref(f"repo:{target}") is not None:
        return True, ""
    if get_doc_repository().get(target) is not None:
        return True, ""
    if get_doc_repository().get_by_source_ref(f"repo:{target}") is not None:
        return True, ""
    return False, f"文档/条目不存在：{ref}"


def _default_usl_verifier(ref: str) -> Tuple[bool, str]:
    from odap.biz.core.ontology.orchestration.impl.intent_router import UslDictionary

    canonical = ref.split("USL:term:", 1)[-1] if "USL:term:" in ref else ref
    mapping: Dict[str, dict] = UslDictionary().load()
    if any(entry.get("canonical") == canonical for entry in mapping.values()):
        return True, ""
    return False, f"USL 术语不存在：{canonical}"


__all__ = ["DefaultEvidenceResolver", "DECISION_REFS"]
