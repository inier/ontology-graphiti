"""结构变更提案工厂（ADR-090 子项目 D D-D4/D-D5）。

背景：concept_gap 的 `schema` 层缺口（object_type / relation_type / property 缺）
promote 时需落一条 `ChangeProposal`（RFC 6902 JSON Patch）。`semantic_admin` 受 C3
契约约束不得直连 `ontology.goal.*` 内部实现，故此处提供**唯一的公共工厂**，由
`odap.biz.core.ontology.public` 门面再导出（消费者：
`gap_pool/services/gap_service.py::_route_to_proposal`）。

设计要点：
- `goal_id` 由缺口 id 派生（`gap:<gap_id>`），保证「缺口 → 提案」双向可溯源；不伪造
  Goal 行（缺口本身即该结构性变更的动因锚点）。
- 复用 `ChangeProposal` 的 RFC 6902 严格校验（op/path 静态校验，D-D9 不跑 Impact）。
- 提案落 `draft` 态（D-D7 门控归人：不自动实施）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models.proposal import ChangeProposal
from ..storage import SQLiteGoalStorage

# 缺口驱动的提案：goal_id 前缀（可据此识别「非人工 Goal」来源）
GAP_GOAL_PREFIX = "gap:"


def gap_goal_id(gap_id: str) -> str:
    """由缺口 id 派生稳定的 goal_id。"""
    return f"{GAP_GOAL_PREFIX}{gap_id}"


def _error(code: str, message: str) -> Dict[str, Any]:
    """统一失败返回（规则 2 dict + 规则 14 显式 code）。"""
    return {"status": "error", "code": code, "message": message}


def _default_description(origin_gap_id: str, scope_key, workspace_id,
                         domain_id) -> str:
    return (f"由概念缺口 {origin_gap_id} 归因至 schema 层自动衍生；"
            f"scope={scope_key or '-'} workspace={workspace_id or '-'} "
            f"domain={domain_id or '-'}")


def _build_proposal(*, origin_gap_id: str, expression: str,
                    changes: List[Dict[str, Any]], proposed_by: str,
                    title, description, scope_key, workspace_id,
                    domain_id) -> ChangeProposal:
    """构造并校验 ChangeProposal（RFC 6902 静态校验由模型承担）。"""
    return ChangeProposal(
        goal_id=gap_goal_id(origin_gap_id),
        title=title or f"补齐本体结构：{expression}",
        description=description or _default_description(
            origin_gap_id, scope_key, workspace_id, domain_id),
        changes=list(changes),
        proposed_by=proposed_by or "system",
    )


def _to_row(proposal: ChangeProposal) -> Dict[str, Any]:
    """ChangeProposal → change_proposals 表行（datetime/Enum 落 ISO / .value）。"""
    return {
        "id": proposal.id,
        "goal_id": proposal.goal_id,
        "title": proposal.title,
        "description": proposal.description,
        "changes": proposal.changes,
        "impact_analysis_id": None,
        "estimated_benefit": proposal.estimated_benefit,
        "estimated_cost": proposal.estimated_cost,
        "status": proposal.status.value,
        "proposed_by": proposal.proposed_by,
        "created_at": proposal.created_at.isoformat(),
        "reviewed_at": None,
        "reviewer_notes": None,
    }


def create_schema_proposal(
    *,
    origin_gap_id: str,
    expression: str,
    changes: List[Dict[str, Any]],
    proposed_by: str,
    title: Optional[str] = None,
    description: str = "",
    scope_key: Optional[str] = None,
    workspace_id: Optional[str] = None,
    domain_id: Optional[str] = None,
    storage: Optional[SQLiteGoalStorage] = None,
) -> Dict[str, Any]:
    """构造并持久化由缺口推导的结构变更提案（失败显式 code，规则 14）。

    成功 → {"status":"ok","proposal_id","goal_id","proposal_status","changes_count"}
    """
    if not changes:
        return _error("SCHEMA_PATCH_EMPTY",
                      "changes 为空：无法从该缺口推导结构变更（缺归因 target_kind）")
    try:
        proposal = _build_proposal(
            origin_gap_id=origin_gap_id, expression=expression, changes=changes,
            proposed_by=proposed_by, title=title, description=description,
            scope_key=scope_key, workspace_id=workspace_id, domain_id=domain_id,
        )
    except ValueError as e:  # RFC 6902 校验失败（非法 op / 缺 path）
        return _error("INVALID_SCHEMA_PATCH", f"结构变更补丁非法: {e}")
    (storage or SQLiteGoalStorage()).save_proposal(_to_row(proposal))
    return {
        "status": "ok",
        "proposal_id": proposal.id,
        "goal_id": proposal.goal_id,
        "proposal_status": proposal.status.value,
        "changes_count": len(proposal.changes),
    }


__all__ = ["create_schema_proposal", "gap_goal_id", "GAP_GOAL_PREFIX"]
