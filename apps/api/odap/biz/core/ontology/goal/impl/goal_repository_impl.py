"""GoalRepositoryImpl (T422)

实现 GoalRepository 抽象基类，依赖 SQLiteGoalStorage 持久化。
Domain Object ↔ dict 转换在这里完成。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..interfaces import GoalRepository
from ..models import ChangeProposal, Goal, ImpactAnalysis
from ..storage import SQLiteGoalStorage
from ..storage.sqlite_goal_storage import _parse_dt_iso


class GoalRepositoryImpl(GoalRepository):
    """OntoFlow Goal 仓储实现（基于 SQLite）"""

    def __init__(self, storage: SQLiteGoalStorage = None):
        self.storage = storage or SQLiteGoalStorage()

    # ---------- Goal CRUD ----------

    def save_goal(self, goal: Goal) -> Goal:
        """保存或更新 Goal (upsert)"""
        goal.updated_at = datetime.now()
        self.storage.save_goal(self._goal_to_dict(goal))
        return goal

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """根据 ID 获取 Goal；不存在返回 None"""
        row = self.storage.get_goal(goal_id)
        return self._dict_to_goal(row) if row else None

    def list_goals(
        self,
        workspace_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页列出 Goal；可按 status / workspace_id 过滤"""
        rows = self.storage.list_goals(
            workspace_id=workspace_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return {
            "goals": [self._dict_to_goal(r) for r in rows.get("goals", [])],
            "total": int(rows.get("total", 0)),
            "page": int(rows.get("page", page)),
            "page_size": int(rows.get("page_size", page_size)),
        }

    def update_goal(self, goal: Goal) -> Goal:
        """更新 Goal 整体 (upsert)"""
        return self.save_goal(goal)

    def delete_goal(self, goal_id: str) -> bool:
        """删除 Goal；级联删除其下的 ChangeProposal/ImpactAnalysis"""
        ok = self.storage.delete_goal(goal_id)
        if ok:
            # 级联清理
            self.storage.delete_proposals_by_goal(goal_id)
        return ok

    # ---------- ChangeProposal CRUD ----------

    def save_proposal(self, proposal: ChangeProposal) -> ChangeProposal:
        """保存或更新 ChangeProposal (upsert)"""
        self.storage.save_proposal(self._proposal_to_dict(proposal))
        return proposal

    def get_proposal(self, proposal_id: str) -> Optional[ChangeProposal]:
        """根据 ID 获取 ChangeProposal；不存在返回 None"""
        row = self.storage.get_proposal(proposal_id)
        return self._dict_to_proposal(row) if row else None

    def list_proposals(
        self,
        goal_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ChangeProposal]:
        """列出 ChangeProposal；可按 goal_id / status 过滤"""
        rows = self.storage.list_proposals(goal_id=goal_id, status=status)
        return [self._dict_to_proposal(r) for r in rows]

    def update_proposal(self, proposal: ChangeProposal) -> ChangeProposal:
        """更新 ChangeProposal (upsert)"""
        return self.save_proposal(proposal)

    # ---------- ImpactAnalysis CRUD ----------

    def save_impact(self, impact: ImpactAnalysis) -> ImpactAnalysis:
        """保存或更新 ImpactAnalysis (upsert)"""
        self.storage.save_impact(self._impact_to_dict(impact))
        return impact

    def get_impact(self, impact_id: str) -> Optional[ImpactAnalysis]:
        """根据 ID 获取 ImpactAnalysis；不存在返回 None"""
        row = self.storage.get_impact(impact_id)
        return self._dict_to_impact(row) if row else None

    # ---------- Lineage ----------

    def get_goal_lineage(self, goal_id: str) -> Dict[str, Any]:
        """获取 Goal 的血缘树（祖先链 + 子 Goal + 关联 Proposal）"""
        goal = self.get_goal(goal_id)
        if not goal:
            return {
                "goal": None,
                "ancestors": [],
                "children": [],
                "proposals": [],
            }

        ancestors: List[Goal] = []
        current = goal
        # 防止循环引用
        seen: set = {goal_id}
        while current.parent_goal_id and current.parent_goal_id not in seen:
            parent = self.get_goal(current.parent_goal_id)
            if not parent:
                break
            ancestors.append(parent)
            seen.add(parent.id)
            current = parent

        children_rows = self.storage.list_goals_by_parent(goal_id)
        children = [self._dict_to_goal(r) for r in children_rows]

        proposals = self.list_proposals(goal_id=goal_id)

        return {
            "goal": goal,
            "ancestors": ancestors,
            "children": children,
            "proposals": proposals,
        }

    # ---------- 内部转换工具 ----------

    @staticmethod
    def _goal_to_dict(goal: Goal) -> Dict[str, Any]:
        """Goal → 持久化 dict"""
        return {
            "id": goal.id,
            "title": goal.title,
            "description": goal.description,
            "business_objective": goal.business_objective,
            "rationale": goal.rationale,
            "status": goal.status.value,
            "parent_goal_id": goal.parent_goal_id,
            "workspace_id": goal.workspace_id,
            "created_by": goal.created_by,
            "created_at": goal.created_at.isoformat(),
            "updated_at": goal.updated_at.isoformat(),
            "tags": list(goal.tags or []),
            "metadata": dict(goal.metadata or {}),
        }

    @staticmethod
    def _dict_to_goal(row: Dict[str, Any]) -> Goal:
        """持久化 dict → Goal"""
        return Goal(
            id=row.get("id", ""),
            title=row.get("title", ""),
            description=row.get("description", "") or "",
            business_objective=row.get("business_objective", ""),
            rationale=row.get("rationale") or None,
            status=row.get("status", "proposed"),
            parent_goal_id=row.get("parent_goal_id") or None,
            workspace_id=row.get("workspace_id", ""),
            created_by=row.get("created_by", ""),
            created_at=_parse_dt_iso(row.get("created_at")) or datetime.now(),
            updated_at=_parse_dt_iso(row.get("updated_at")) or datetime.now(),
            tags=row.get("tags", []) or [],
            metadata=row.get("metadata", {}) or {},
        )

    @staticmethod
    def _proposal_to_dict(proposal: ChangeProposal) -> Dict[str, Any]:
        """ChangeProposal → 持久化 dict"""
        reviewed = proposal.reviewed_at
        return {
            "id": proposal.id,
            "goal_id": proposal.goal_id,
            "title": proposal.title,
            "description": proposal.description,
            "changes": list(proposal.changes or []),
            "impact_analysis_id": proposal.impact_analysis_id,
            "estimated_benefit": proposal.estimated_benefit,
            "estimated_cost": proposal.estimated_cost,
            "status": proposal.status.value,
            "proposed_by": proposal.proposed_by,
            "created_at": proposal.created_at.isoformat(),
            "reviewed_at": reviewed.isoformat() if reviewed else None,
            "reviewer_notes": proposal.reviewer_notes,
        }

    @staticmethod
    def _dict_to_proposal(row: Dict[str, Any]) -> ChangeProposal:
        """持久化 dict → ChangeProposal"""
        reviewed_raw = row.get("reviewed_at")
        reviewed = _parse_dt_iso(reviewed_raw) if reviewed_raw else None
        return ChangeProposal(
            id=row.get("id", ""),
            goal_id=row.get("goal_id", ""),
            title=row.get("title", ""),
            description=row.get("description", "") or "",
            changes=row.get("changes", []) or [],
            impact_analysis_id=row.get("impact_analysis_id") or None,
            estimated_benefit=row.get("estimated_benefit", "") or "",
            estimated_cost=row.get("estimated_cost") or None,
            status=row.get("status", "draft"),
            proposed_by=row.get("proposed_by", ""),
            created_at=_parse_dt_iso(row.get("created_at")) or datetime.now(),
            reviewed_at=reviewed,
            reviewer_notes=row.get("reviewer_notes") or None,
        )

    @staticmethod
    def _impact_to_dict(impact: ImpactAnalysis) -> Dict[str, Any]:
        """ImpactAnalysis → 持久化 dict"""
        return {
            "id": impact.id,
            "proposal_id": impact.proposal_id,
            "affected_object_types": list(impact.affected_object_types or []),
            "affected_action_types": list(impact.affected_action_types or []),
            "affected_instances_count": int(impact.affected_instances_count),
            "breaking_changes": list(impact.breaking_changes or []),
            "estimated_migration_cost": impact.estimated_migration_cost.value,
            "risk_level": impact.risk_level.value,
            "analysis_metadata": dict(impact.analysis_metadata or {}),
            "created_at": impact.created_at.isoformat(),
        }

    @staticmethod
    def _dict_to_impact(row: Dict[str, Any]) -> ImpactAnalysis:
        """持久化 dict → ImpactAnalysis"""
        from ..models import ImpactCost, RiskLevel
        try:
            cost = ImpactCost(row.get("estimated_migration_cost", "low"))
        except ValueError:
            cost = ImpactCost.LOW
        try:
            risk = RiskLevel(row.get("risk_level", "low"))
        except ValueError:
            risk = RiskLevel.LOW
        return ImpactAnalysis(
            id=row.get("id", ""),
            proposal_id=row.get("proposal_id", ""),
            affected_object_types=row.get("affected_object_types", []) or [],
            affected_action_types=row.get("affected_action_types", []) or [],
            affected_instances_count=int(
                row.get("affected_instances_count", 0) or 0
            ),
            breaking_changes=row.get("breaking_changes", []) or [],
            estimated_migration_cost=cost,
            risk_level=risk,
            analysis_metadata=row.get("analysis_metadata", {}) or {},
            created_at=_parse_dt_iso(row.get("created_at")) or datetime.now(),
        )


__all__ = ["GoalRepositoryImpl"]
