"""从管线结果派生执行建议（AC-40）。

派生规则是**确定性**的（可审计、可回归），不调用 LLM：
- 任何回答都可「看溯源」→ `open_provenance`（low）
- 有证据 → 可「看引用」→ `view_citations`（low）
- 存在未映射槽位 → 可「提交本体缺口」→ `submit_gap_fill`（high）
- 给出了答案 → 可「导出为 Wiki」→ `export_answer_wiki`（high）

`allow_actions=False`（默认）时只提供只读动作，写类动作不下发，
避免把「有副作用的能力」默认塞给前端。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from odap.biz.core.ontology.orchestration.actions.catalog import spec_for
from odap.biz.core.ontology.orchestration.contracts import SuggestedAction


def _build(action_type: str, payload: Dict[str, Any]) -> Optional[SuggestedAction]:
    spec = spec_for(action_type)
    if spec is None:  # 目录未登记 → 不派生（fail-closed）
        return None
    return SuggestedAction(
        action_type=spec.action_type,
        risk_level=spec.risk_level,  # type: ignore[arg-type]
        requires_hitl=spec.requires_hitl,
        executable=spec.executable,
        status="proposed",
        summary=spec.summary,
        payload=payload,
    )


def _slots(unmapped: Sequence[Any]) -> List[Dict[str, str]]:
    """把 `UnmappedSlot` / dict 统一成 `{slot, raw}`，供缺口回写消费。"""
    out: List[Dict[str, str]] = []
    for item in unmapped:
        if isinstance(item, dict):
            slot, raw = item.get("slot", ""), item.get("raw", "")
        else:
            slot, raw = getattr(item, "slot", ""), getattr(item, "raw", "")
        if slot:
            out.append({"slot": str(slot), "raw": str(raw)})
    return out


def derive_actions(
    *,
    trace_id: str,
    query: str,
    workspace_id: str = "",
    citation_count: int = 0,
    unmapped: Optional[Sequence[Any]] = None,
    no_answer: bool = False,
    allow_actions: bool = False,
) -> List[SuggestedAction]:
    """按确定性规则产出建议动作列表（可能为空）。"""
    actions: List[SuggestedAction] = []

    readonly = _build("open_provenance", {"trace_id": trace_id})
    if readonly:
        actions.append(readonly)

    if citation_count > 0:
        cite = _build(
            "view_citations",
            {"trace_id": trace_id, "citation_count": citation_count},
        )
        if cite:
            actions.append(cite)

    if not allow_actions:
        return actions

    if slots_ := _slots(unmapped or []):
        gap = _build(
            "submit_gap_fill",
            {"trace_id": trace_id, "workspace_id": workspace_id, "slots": slots_},
        )
        if gap:
            actions.append(gap)

    if not no_answer:
        export = _build(
            "export_answer_wiki",
            {"trace_id": trace_id, "workspace_id": workspace_id,
             "title_suggestion": (query or "").strip()[:60]},
        )
        if export:
            actions.append(export)

    return actions


__all__ = ["derive_actions"]
