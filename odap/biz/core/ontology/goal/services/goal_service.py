"""GoalService 编排层 (T425)

服务层规范 (AGENTS.md 规则 2):
- 必须返回 Dict[str, Any]，禁止抛 HTTPException
- 错误格式: {"status": "error", "message": "..."}
- 成功格式: 扁平 dict
- 类型转换: Enum→.value, datetime→.isoformat(), BaseModel→扁平 dict

主要职责:
- 依赖注入: repository, rationale_generator, impact_analyzer
- 业务编排: 创建 Goal 自动生成 rationale; 创建 Proposal 自动跑 ImpactAnalyzer
- 状态机: change_status 校验合法转换
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from odap.infra.security.audit_helper import storage_audit

from ..impl import (
    GoalRepositoryImpl,
    ImpactAnalyzerImpl,
    RationaleGenerator,
)
from ..interfaces import GoalRepository, ImpactAnalyzer
from ..models import (
    ChangeProposal,
    Goal,
    GoalStatus,
    ImpactAnalysis,
    ProposalStatus,
)
from ..models.goal import is_valid_goal_transition
from ..storage import SQLiteGoalStorage

logger = logging.getLogger(__name__)

_AUDIT_SERVICE = "ontology_design"


def _audit_success(action: str, resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="success",
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _audit_failure(action: str, msg: str = "", resource: str = None, details: Dict[str, Any] = None) -> None:
    try:
        storage_audit(
            action=action,
            result_status="failure",
            result_message=(msg or "")[:200],
            resource=resource,
            details=details or {},
            service=_AUDIT_SERVICE,
        )
    except Exception as e:
        logger.warning(f"audit failed: {e}")


def _new_id() -> str:
    return str(uuid.uuid4())


class GoalService:
    """OntoFlow Goal 编排服务"""

    def __init__(
        self,
        repository: GoalRepository = None,
        rationale_generator: RationaleGenerator = None,
        impact_analyzer: ImpactAnalyzer = None,
        storage: SQLiteGoalStorage = None,
    ):
        self.storage = storage or SQLiteGoalStorage()
        self.repository = repository or GoalRepositoryImpl(storage=self.storage)
        self.rationale_generator = rationale_generator or RationaleGenerator()
        self.impact_analyzer = impact_analyzer or ImpactAnalyzerImpl()

    # ---------- Goal CRUD ----------

    async def create_goal(
        self,
        title: str,
        description: str,
        business_objective: str,
        workspace_id: str,
        created_by: str,
        parent_goal_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_rationale: bool = True,
    ) -> Dict[str, Any]:
        """创建 Goal；可选自动生成 rationale"""
        action = "goal.create_goal"
        try:
            self._validate_create_goal_inputs(
                title, business_objective, workspace_id, parent_goal_id
            )
            goal = self._build_new_goal(
                title, description, business_objective,
                workspace_id, created_by, parent_goal_id, tags, metadata,
            )
            rationale_generated = False
            if auto_rationale:
                generated = await self._safe_generate_rationale(goal)
                goal.rationale = generated
                rationale_generated = bool(generated)
            saved = self.repository.save_goal(goal)
            _audit_success(action, resource=saved.id,
                            details={"goal_id": saved.id,
                                     "workspace_id_len": len(workspace_id or ""),
                                     "has_parent": bool(parent_goal_id),
                                     "tags_count": len(tags or []),
                                     "rationale_generated": rationale_generated,
                                     "status": saved.status.value})
            return self._goal_to_dict(saved)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc),
                            details={"workspace_id_len": len(workspace_id or ""),
                                     "has_parent": bool(parent_goal_id)})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"create_goal failed: {exc}"}

    def _validate_create_goal_inputs(
        self, title, business_objective, workspace_id, parent_goal_id,
    ) -> None:
        if not title or not str(title).strip():
            raise ValueError("title is required and must be non-empty")
        if not business_objective or not str(business_objective).strip():
            raise ValueError(
                "business_objective is required and must be non-empty"
            )
        if not workspace_id or not str(workspace_id).strip():
            raise ValueError("workspace_id is required and must be non-empty")
        if parent_goal_id and not self.repository.get_goal(parent_goal_id):
            raise ValueError(f"parent_goal not found: {parent_goal_id}")

    def _build_new_goal(
        self, title, description, business_objective,
        workspace_id, created_by, parent_goal_id, tags, metadata,
    ) -> Goal:
        return Goal(
            title=title,
            description=description or "",
            business_objective=business_objective,
            parent_goal_id=parent_goal_id,
            workspace_id=workspace_id,
            created_by=created_by,
            tags=list(tags or []),
            metadata=dict(metadata or {}),
        )

    async def _safe_generate_rationale(self, goal: Goal) -> Optional[str]:
        try:
            return await self.rationale_generator.generate(goal)
        except Exception as exc:
            logger.warning("auto_rationale failed: %s", exc)
            return None

    def get_goal(self, goal_id: str) -> Dict[str, Any]:
        """获取 Goal"""
        action = "goal.get_goal"
        try:
            goal = self.repository.get_goal(goal_id)
            if not goal:
                _audit_failure(action, msg="goal not found", resource=goal_id,
                                details={"goal_id": goal_id})
                return {"status": "error", "message": f"goal not found: {goal_id}"}
            _audit_success(action, resource=goal_id,
                            details={"goal_id": goal_id,
                                     "status": goal.status.value,
                                     "has_parent": bool(goal.parent_goal_id)})
            return self._goal_to_dict(goal)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": f"get_goal failed: {exc}"}

    def list_goals(
        self,
        workspace_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页列出 Goal"""
        action = "goal.list_goals"
        try:
            if not workspace_id or not str(workspace_id).strip():
                raise ValueError("workspace_id is required")
            data = self.repository.list_goals(
                workspace_id=workspace_id,
                status=status,
                page=page,
                page_size=page_size,
            )
            _audit_success(action,
                            details={"workspace_id_len": len(workspace_id or ""),
                                     "has_status_filter": bool(status),
                                     "count": len(data.get("goals", []) or []),
                                     "total": int(data.get("total", 0)),
                                     "page": page})
            return {
                "goals": [self._goal_to_dict(g) for g in data["goals"]],
                "total": data["total"],
                "page": data["page"],
                "page_size": data["page_size"],
                "count": len(data["goals"]),
            }
        except ValueError as exc:
            _audit_failure(action, msg=str(exc),
                            details={"workspace_id_len": len(workspace_id or "")})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_goals failed: {exc}"}

    def update_goal(
        self, goal_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """更新 Goal（部分字段）"""
        action = "goal.update_goal"
        try:
            existing = self.repository.get_goal(goal_id)
            if not existing:
                _audit_failure(action, msg="goal not found", resource=goal_id,
                                details={"goal_id": goal_id})
                return {"status": "error", "message": f"goal not found: {goal_id}"}
            merged = self._merge_goal(existing, payload)
            merged.updated_at = datetime.now()
            saved = self.repository.save_goal(merged)
            _audit_success(action, resource=goal_id,
                            details={"goal_id": goal_id,
                                     "status": saved.status.value,
                                     "tags_count": len(saved.tags or [])})
            return self._goal_to_dict(saved)
        except ValueError as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": f"update_goal failed: {exc}"}

    def delete_goal(self, goal_id: str) -> Dict[str, Any]:
        """删除 Goal"""
        action = "goal.delete_goal"
        try:
            ok = self.repository.delete_goal(goal_id)
            if not ok:
                _audit_failure(action, msg="goal not found", resource=goal_id,
                                details={"goal_id": goal_id})
                return {"status": "error", "message": f"goal not found: {goal_id}"}
            _audit_success(action, resource=goal_id,
                            details={"goal_id": goal_id, "deleted": True})
            return {"goal_id": goal_id, "deleted": True}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": f"delete_goal failed: {exc}"}

    # ---------- 状态机 ----------

    def change_status(
        self, goal_id: str, new_status: str
    ) -> Dict[str, Any]:
        """转换 Goal 状态 (校验合法状态机)"""
        action = "goal.change_status"
        try:
            existing = self.repository.get_goal(goal_id)
            if not existing:
                _audit_failure(action, msg="goal not found", resource=goal_id,
                                details={"goal_id": goal_id})
                return {"status": "error", "message": f"goal not found: {goal_id}"}
            try:
                target = GoalStatus(new_status)
            except ValueError:
                _audit_failure(action, msg=f"invalid new_status: {new_status}",
                                resource=goal_id, details={"goal_id": goal_id,
                                                             "new_status": str(new_status)})
                return {
                    "status": "error",
                    "message": f"invalid new_status: {new_status}",
                }
            if not is_valid_goal_transition(existing.status, target):
                _audit_failure(action, msg=f"invalid transition {existing.status.value}->{target.value}",
                                resource=goal_id, details={"goal_id": goal_id,
                                                             "from_status": existing.status.value,
                                                             "to_status": target.value})
                return {
                    "status": "error",
                    "message": (
                        f"invalid transition: {existing.status.value} -> "
                        f"{target.value}"
                    ),
                }
            existing.status = target
            existing.updated_at = datetime.now()
            saved = self.repository.save_goal(existing)
            _audit_success(action, resource=goal_id,
                            details={"goal_id": goal_id,
                                     "from_status": existing.status.value,  # already updated - use target
                                     "to_status": target.value})
            return self._goal_to_dict(saved)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": f"change_status failed: {exc}"}

    # ---------- Proposal + Impact ----------

    def propose_change(
        self,
        goal_id: str,
        title: str,
        description: str,
        changes: List[Dict[str, Any]],
        proposed_by: str,
        estimated_benefit: str = "",
        estimated_cost: Optional[str] = None,
    ) -> Dict[str, Any]:
        """创建 ChangeProposal 并自动运行 ImpactAnalyzer"""
        action = "goal.propose_change"
        try:
            goal = self.repository.get_goal(goal_id)
            if not goal:
                _audit_failure(action, msg="goal not found", resource=goal_id,
                                details={"goal_id": goal_id})
                return {"status": "error", "message": f"goal not found: {goal_id}"}
            self._validate_proposal_inputs(title, proposed_by)
            proposal = self._build_proposal(
                goal_id, title, description, changes,
                proposed_by, estimated_benefit, estimated_cost,
            )
            impact = self._analyze_and_persist(proposal)
            _audit_success(action, resource=proposal.id,
                            details={"proposal_id": proposal.id,
                                     "goal_id": goal_id,
                                     "changes_count": len(changes or []),
                                     "impact_affected_count": int(impact.affected_instances_count),
                                     "risk_level": impact.risk_level.value})
            return {
                "proposal": self._proposal_to_dict(proposal),
                "impact": self._impact_to_dict(impact),
            }
        except ValueError as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": str(exc)}
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {"status": "error", "message": f"propose_change failed: {exc}"}

    @staticmethod
    def _validate_proposal_inputs(title: str, proposed_by: str) -> None:
        if not title or not str(title).strip():
            raise ValueError("title is required and must be non-empty")
        if not proposed_by or not str(proposed_by).strip():
            raise ValueError("proposed_by is required and must be non-empty")

    def _build_proposal(
        self, goal_id, title, description, changes,
        proposed_by, estimated_benefit, estimated_cost,
    ) -> ChangeProposal:
        return ChangeProposal(
            goal_id=goal_id,
            title=title,
            description=description or "",
            changes=list(changes or []),
            estimated_benefit=estimated_benefit or "",
            estimated_cost=estimated_cost,
            status=ProposalStatus.DRAFT,
            proposed_by=proposed_by,
        )

    def _analyze_and_persist(self, proposal: ChangeProposal) -> ImpactAnalysis:
        impact = self.impact_analyzer.analyze(
            changes=proposal.changes,
            proposal_id=proposal.id,
        )
        impact.proposal_id = proposal.id
        self.repository.save_impact(impact)
        proposal.impact_analysis_id = impact.id
        self.repository.save_proposal(proposal)
        return impact

    def list_proposals(
        self,
        goal_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """列出 ChangeProposal"""
        action = "goal.list_proposals"
        try:
            items = self.repository.list_proposals(goal_id=goal_id, status=status)
            _audit_success(action,
                            details={"has_goal_filter": bool(goal_id),
                                     "has_status_filter": bool(status),
                                     "count": len(items or [])})
            return {
                "proposals": [self._proposal_to_dict(p) for p in items],
                "count": len(items),
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc))
            return {"status": "error", "message": f"list_proposals failed: {exc}"}

    def review_proposal(
        self,
        proposal_id: str,
        decision: str,
        reviewer_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """审批 ChangeProposal (approve/reject/...)"""
        action = "goal.review_proposal"
        try:
            proposal = self.repository.get_proposal(proposal_id)
            if not proposal:
                _audit_failure(action, msg="proposal not found", resource=proposal_id,
                                details={"proposal_id": proposal_id})
                return {
                    "status": "error",
                    "message": f"proposal not found: {proposal_id}",
                }
            new_status = self._map_decision_to_status(decision)
            if new_status is None:
                _audit_failure(action, msg=f"invalid decision: {decision}",
                                resource=proposal_id,
                                details={"proposal_id": proposal_id,
                                         "decision": str(decision)})
                return {
                    "status": "error",
                    "message": f"invalid decision: {decision}",
                }
            proposal.status = new_status
            proposal.reviewed_at = datetime.now()
            proposal.reviewer_notes = reviewer_notes
            self.repository.update_proposal(proposal)
            _audit_success(action, resource=proposal_id,
                            details={"proposal_id": proposal_id,
                                     "new_status": new_status.value,
                                     "has_notes": bool(reviewer_notes)})
            return self._proposal_to_dict(proposal)
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=proposal_id,
                            details={"proposal_id": proposal_id})
            return {
                "status": "error",
                "message": f"review_proposal failed: {exc}",
            }

    @staticmethod
    def _map_decision_to_status(decision: str) -> Optional[ProposalStatus]:
        decision_lower = (decision or "").lower()
        if decision_lower in {"approve", "approved"}:
            return ProposalStatus.APPROVED
        if decision_lower in {"reject", "rejected"}:
            return ProposalStatus.REJECTED
        if decision_lower in {"submit", "submitted"}:
            return ProposalStatus.SUBMITTED
        if decision_lower in {"under-review", "review"}:
            return ProposalStatus.UNDER_REVIEW
        if decision_lower in {"implement", "implemented"}:
            return ProposalStatus.IMPLEMENTED
        return None

    # ---------- Lineage ----------

    def get_goal_lineage(self, goal_id: str) -> Dict[str, Any]:
        """获取 Goal 血缘"""
        action = "goal.get_goal_lineage"
        try:
            data = self.repository.get_goal_lineage(goal_id)
            if data.get("goal") is None:
                _audit_failure(action, msg="goal not found", resource=goal_id,
                                details={"goal_id": goal_id})
                return {"status": "error", "message": f"goal not found: {goal_id}"}
            _audit_success(action, resource=goal_id,
                            details={"goal_id": goal_id,
                                     "ancestors_count": len(data.get("ancestors", []) or []),
                                     "children_count": len(data.get("children", []) or []),
                                     "proposals_count": len(data.get("proposals", []) or [])})
            return {
                "goal": self._goal_to_dict(data["goal"]),
                "ancestors": [self._goal_to_dict(g) for g in data["ancestors"]],
                "children": [self._goal_to_dict(g) for g in data["children"]],
                "proposals": [
                    self._proposal_to_dict(p) for p in data["proposals"]
                ],
            }
        except Exception as exc:
            _audit_failure(action, msg=str(exc), resource=goal_id,
                            details={"goal_id": goal_id})
            return {
                "status": "error",
                "message": f"get_goal_lineage failed: {exc}",
            }

    # ---------- 内部工具 ----------

    @staticmethod
    def _merge_goal(
        existing: Goal, payload: Dict[str, Any]
    ) -> Goal:
        """合并更新字段；不传则保留原值"""
        merged_payload = {
            "id": existing.id,
            "title": payload.get("title", existing.title),
            "description": payload.get("description", existing.description),
            "business_objective": payload.get(
                "business_objective", existing.business_objective
            ),
            "rationale": payload.get("rationale", existing.rationale),
            "status": existing.status.value,
            "parent_goal_id": payload.get(
                "parent_goal_id", existing.parent_goal_id
            ),
            "workspace_id": existing.workspace_id,
            "created_by": existing.created_by,
            "created_at": existing.created_at,
            "updated_at": datetime.now(),
            "tags": payload.get("tags", existing.tags),
            "metadata": payload.get("metadata", existing.metadata),
        }
        return Goal(**merged_payload)

    @staticmethod
    def _goal_to_dict(goal: Goal) -> Dict[str, Any]:
        """Goal → 扁平 dict"""
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
    def _proposal_to_dict(proposal: ChangeProposal) -> Dict[str, Any]:
        """ChangeProposal → 扁平 dict"""
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
    def _impact_to_dict(impact: ImpactAnalysis) -> Dict[str, Any]:
        """ImpactAnalysis → 扁平 dict"""
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


__all__ = ["GoalService"]
