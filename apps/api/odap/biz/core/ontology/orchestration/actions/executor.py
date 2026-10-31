"""动作执行器 —— 每个 `action_type` 的真实副作用（AC-42）。

纪律：
- **不伪造执行结果**：拿不到证据就抛 `ACTION_EXECUTION_FAILED`，返回 200 但什么都没做
  属禁用的「假成功」；
- 本轮未建执行路径的动作（`spec.executable is False`）抛
  `501 ACTION_EXECUTION_NOT_IMPLEMENTED` 并指向 SPEC 编号，不做「看起来能跑」的空壳；
- 只读动作（`open_provenance` / `view_citations`）真实读 `qa_traces`/`qa_provenance`。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from odap.common import api_errors as E
from odap.common.api_errors import ApiError
from odap.biz.core.ontology.orchestration.actions.catalog import spec_for
from odap.biz.core.ontology.orchestration.repositories.trace_repo import QaTraceRepository

logger = logging.getLogger(__name__)


class ActionExecutor:
    """把一条已落库的动作变成真实结果。"""

    def __init__(self, trace_repo: Optional[QaTraceRepository] = None) -> None:
        self.trace_repo = trace_repo or QaTraceRepository()

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("action_type") or "")
        spec = spec_for(action_type)
        if spec is None:
            raise ApiError(
                E.ACTION_EXECUTION_NOT_IMPLEMENTED,
                f"动作类型未在目录登记，拒绝执行：{action_type}",
                status_code=501,
                detail={"action_type": action_type},
            )
        if not spec.executable:
            raise ApiError(
                E.ACTION_EXECUTION_NOT_IMPLEMENTED,
                f"动作 {action_type} 的执行路径本轮未实现（SPEC-v2 AC-42 后续波次）",
                status_code=501,
                detail={"action_type": action_type, "spec_ref": "SPEC-v2 AC-42"},
            )
        handler = _HANDLERS.get(action_type)
        if handler is None:  # 目录说能执行但没接执行器 = 装配错误，必须暴露
            raise ApiError(
                E.ACTION_EXECUTION_NOT_IMPLEMENTED,
                f"动作 {action_type} 缺失执行器装配",
                status_code=501,
                detail={"action_type": action_type},
            )
        payload = action.get("payload") or {}
        result = handler(self, action.get("trace_id", ""), payload)
        return {"action_type": action_type, "result": result}

    # ── 只读动作 ──────────────────────────────────────────────────────────
    def _open_provenance(self, trace_id: str, _payload: Dict[str, Any]) -> Dict[str, Any]:
        provenance = self.trace_repo.get_provenance(trace_id)
        if provenance is None:
            raise ApiError(
                E.ACTION_EXECUTION_FAILED,
                f"执行失败：溯源记录不存在 trace_id={trace_id}",
                status_code=409,
                detail={"trace_id": trace_id, "reason": "trace_missing"},
            )
        return {
            "trace_id": trace_id,
            "tbox_version": provenance.tbox_version,
            "contract_ok": provenance.contract_ok,
            "step_count": len(provenance.steps),
            "steps": [s.model_dump(mode="json") for s in provenance.steps],
        }

    def _view_citations(self, trace_id: str, _payload: Dict[str, Any]) -> Dict[str, Any]:
        trace = self.trace_repo.get_trace(trace_id)
        if trace is None:
            raise ApiError(
                E.ACTION_EXECUTION_FAILED,
                f"执行失败：问答记录不存在 trace_id={trace_id}",
                status_code=409,
                detail={"trace_id": trace_id, "reason": "trace_missing"},
            )
        return {"trace_id": trace_id, "citations": trace.get("citations") or []}

    # ── 写动作（高风险，必经 HITL）────────────────────────────────────────
    def _submit_gap_fill(self, trace_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        slots = payload.get("slots") or []
        if not slots:
            raise ApiError(
                E.ACTION_EXECUTION_FAILED,
                "执行失败：payload.slots 为空，无从提交本体缺口",
                status_code=422,
                detail={"trace_id": trace_id, "reason": "empty_slots"},
            )
        gap_service = _gap_service()
        written = 0
        gap_ids = []
        for slot in slots:
            raw = str(slot.get("raw") or slot.get("slot") or "")
            if not raw:
                continue
            outcome = gap_service.record_signal(
                _gap_source(),
                raw,
                workspace_id=payload.get("workspace_id") or None,
                ref=f"qa_action:{trace_id}",
                detail=f"本体约束问答未映射槽位：{slot.get('slot')}",
            )
            if outcome.get("status") != "ok":
                raise ApiError(
                    E.ACTION_EXECUTION_FAILED,
                    f"执行失败：写入 gap_pool 未成功（slot={slot.get('slot')}）",
                    status_code=502,
                    detail={"trace_id": trace_id, "outcome": outcome},
                )
            written += 1
            gap_id = (outcome.get("gap") or {}).get("gap_id")
            if gap_id:
                gap_ids.append(str(gap_id))
        if written == 0:
            raise ApiError(
                E.ACTION_EXECUTION_FAILED,
                "执行失败：所有槽位的 raw 均为空，未写入任何缺口",
                status_code=422,
                detail={"trace_id": trace_id, "reason": "no_writable_slot"},
            )
        return {"trace_id": trace_id, "written": written, "gap_ids": gap_ids}


def _gap_service() -> Any:
    """惰性导入（gap_pool 属 semantic_admin 域，避免编排层启动期循环依赖）。"""
    from odap.biz.semantic_admin.gap_pool.services.gap_service import GapService

    return GapService()


def _gap_source() -> Any:
    from odap.biz.semantic_admin.gap_pool.models.gap import GapSignalSource

    return GapSignalSource.MAPPING_FAILURE


_HANDLERS = {
    "open_provenance": ActionExecutor._open_provenance,
    "view_citations": ActionExecutor._view_citations,
    "submit_gap_fill": ActionExecutor._submit_gap_fill,
}


__all__ = ["ActionExecutor"]
