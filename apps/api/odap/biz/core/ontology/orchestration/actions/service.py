"""F9 动作业务逻辑（AC-40~AC-42）。

三条铁律：
1. **高风险动作禁止自动执行**（AC-41）：`execute` 见到 `risk_level=high` 且
   `status != approved` 时直接 409 `ACTION_HITL_REQUIRED`，绝不放行。
2. **动作必须与 trace_id 关联**（AC-42）：`propose` 只接受已落库的 trace，
   否则 404 `QA_TRACE_NOT_FOUND`，避免产生孤儿动作。
3. **审批失败即拒绝**：审批门 fail-closed，异常上抛，不做「降级放行」。

本层不 import fastapi（分层铁律），HTTP 语义由 `ApiError.status_code` 承载。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.common.ids import new_doc_id
from odap.biz.core.ontology.orchestration.actions.approval import OpaApprovalGate
from odap.biz.core.ontology.orchestration.actions.catalog import RISK_HIGH, spec_for
from odap.biz.core.ontology.orchestration.actions.executor import ActionExecutor
from odap.biz.core.ontology.orchestration.actions.repository import QaActionRepository
from odap.biz.core.ontology.orchestration.contracts import SuggestedAction
from odap.biz.core.ontology.orchestration.repositories.trace_repo import QaTraceRepository

_OPEN_STATUSES = ("proposed", "approved")


class ActionService:
    """建议 → 审批 → 执行 的唯一入口。"""

    def __init__(
        self,
        repo: Optional[QaActionRepository] = None,
        executor: Optional[ActionExecutor] = None,
        approval_gate: Optional[OpaApprovalGate] = None,
        trace_repo: Optional[QaTraceRepository] = None,
    ) -> None:
        self.trace_repo = trace_repo or QaTraceRepository()
        self.repo = repo or QaActionRepository(getattr(self.trace_repo, "db_path", None))
        self.executor = executor or ActionExecutor(self.trace_repo)
        self.approval_gate = approval_gate or OpaApprovalGate()

    # ── 建议 ──────────────────────────────────────────────────────────────
    def propose(self, trace_id: str, actions: List[SuggestedAction]) -> List[SuggestedAction]:
        """把派生出的动作落库为 `proposed`，回填 `action_id`。"""
        if not actions:
            return []
        if not self.trace_repo.exists(trace_id):
            raise ApiError(
                E.QA_TRACE_NOT_FOUND,
                f"问答记录不存在，无法挂载动作：{trace_id}",
                status_code=404,
                detail={"trace_id": trace_id},
            )
        rows = []
        for action in actions:
            spec = spec_for(action.action_type)
            if spec is None:
                raise ApiError(
                    E.ACTION_EXECUTION_NOT_IMPLEMENTED,
                    f"动作类型未在目录登记，拒绝下发：{action.action_type}",
                    status_code=501,
                    detail={"action_type": action.action_type},
                )
            rows.append({
                "id": new_doc_id("act"),
                "action_type": spec.action_type,
                "risk_level": spec.risk_level,
                "payload": dict(action.payload or {}),
                "status": "proposed",
            })
        ids = self.repo.insert_many(trace_id, rows)
        enriched: List[SuggestedAction] = []
        for action, action_id in zip(actions, ids):
            spec = spec_for(action.action_type)
            enriched.append(action.model_copy(update={
                "action_id": action_id,
                "risk_level": spec.risk_level if spec else action.risk_level,
                "requires_hitl": spec.requires_hitl if spec else action.requires_hitl,
                "executable": spec.executable if spec else action.executable,
                "status": "proposed",
            }))
        return enriched

    def list(self, trace_id: str) -> List[Dict[str, Any]]:
        """按 trace 列出动作（按创建时间升序）。"""
        if not self.trace_repo.exists(trace_id):
            raise ApiError(
                E.QA_TRACE_NOT_FOUND,
                f"问答记录不存在：{trace_id}",
                status_code=404,
                detail={"trace_id": trace_id},
            )
        return self.repo.list_by_trace(trace_id)

    # ── HITL 审批 ─────────────────────────────────────────────────────────
    def decide(self, action_id: str, *, approved: bool,
               user_ctx: Dict[str, Any]) -> Dict[str, Any]:
        """HITL 决策：批准 / 驳回高风险动作（低风险动作无 HITL 环节）。"""
        action = self._require(action_id)
        if action["risk_level"] != RISK_HIGH:
            raise ApiError(
                E.ACTION_HITL_NOT_APPLICABLE,
                f"动作 {action['action_type']} 为低风险（只读），无需 HITL 审批",
                status_code=409,
                detail={"action_id": action_id, "risk_level": action["risk_level"]},
            )
        if action["status"] not in _OPEN_STATUSES:
            raise ApiError(
                E.ACTION_ALREADY_SETTLED,
                f"动作状态为 {action['status']}，不可再审批",
                status_code=409,
                detail={"action_id": action_id, "status": action["status"]},
            )
        operator = str(user_ctx.get("sub") or user_ctx.get("user_id") or "")
        if approved:
            self.approval_gate.authorize(user_ctx, action)
            if not self.repo.mark_approved(action_id, operator):
                raise ApiError(
                    E.ACTION_ALREADY_SETTLED,
                    "动作状态已变更，审批未生效（并发冲突）",
                    status_code=409,
                    detail={"action_id": action_id},
                )
        else:
            if not self.repo.mark_rejected(action_id, operator):
                raise ApiError(
                    E.ACTION_ALREADY_SETTLED,
                    "动作状态已变更，驳回未生效（并发冲突）",
                    status_code=409,
                    detail={"action_id": action_id},
                )
        return self._require(action_id)

    # ── 执行 ──────────────────────────────────────────────────────────────
    def execute(self, action_id: str) -> Dict[str, Any]:
        """执行动作（高风险必须已 `approved`，否则 409）。"""
        action = self._require(action_id)
        if action["status"] == "executed":
            raise ApiError(
                E.ACTION_ALREADY_SETTLED,
                "动作已执行，禁止重复执行",
                status_code=409,
                detail={"action_id": action_id, "status": "executed"},
            )
        if action["status"] == "rejected":
            raise ApiError(
                E.ACTION_REJECTED,
                "动作已被驳回，不可执行",
                status_code=409,
                detail={"action_id": action_id, "status": "rejected"},
            )
        if action["risk_level"] == RISK_HIGH and action["status"] != "approved":
            raise ApiError(
                E.ACTION_HITL_REQUIRED,
                f"高风险动作 {action['action_type']} 必须经 HITL 确认后才能执行（AC-41）",
                status_code=409,
                detail={"action_id": action_id, "status": action["status"],
                        "risk_level": action["risk_level"]},
            )
        outcome = self.executor.execute(action)
        if not self.repo.mark_executed(action_id):
            raise ApiError(
                E.ACTION_ALREADY_SETTLED,
                "动作状态已变更，执行结果未能落库（并发冲突）",
                status_code=409,
                detail={"action_id": action_id},
            )
        return {"action": self._require(action_id), **outcome}

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _require(self, action_id: str) -> Dict[str, Any]:
        action = self.repo.get(action_id)
        if action is None:
            raise ApiError(
                E.ACTION_NOT_FOUND, f"动作不存在：{action_id}", status_code=404,
                detail={"action_id": action_id},
            )
        return action


__all__ = ["ActionService"]
