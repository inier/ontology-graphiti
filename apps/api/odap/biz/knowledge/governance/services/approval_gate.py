"""导出审批门禁（F3，AC-17）。

规则（fail-closed）：`approval_id` 必须在审批工作流里存在且 `decision=APPROVE`；
审批服务异常/查询失败一律 503，绝不因审批系统故障放行仓库写入。
"""

from __future__ import annotations

from odap.common.api_errors import ApiError

APPROVAL_UNAVAILABLE = "APPROVAL_SERVICE_UNAVAILABLE"


def default_approval_checker(approval_id: str) -> bool:
    """默认审批核验：查 semantic_admin 审批日志，decision=APPROVE 即视为通过。"""
    try:
        from odap.biz.semantic_admin.approval_workflow.services import ApprovalService

        result = ApprovalService().list_approvals(candidate_id=approval_id)
    except Exception as exc:  # noqa: BLE001 - 审批系统故障必须显式拒绝
        raise ApiError(
            APPROVAL_UNAVAILABLE,
            f"审批服务不可用，按 fail-closed 拒绝回写仓库：{type(exc).__name__}: {exc}",
            status_code=503, detail={"approval_id": approval_id},
        ) from exc
    if not isinstance(result, dict) or result.get("status") == "error":
        raise ApiError(
            APPROVAL_UNAVAILABLE,
            f"审批日志查询失败：{(result or {}).get('message', 'unknown')}",
            status_code=503, detail={"approval_id": approval_id},
        )
    items = result.get("items") or []
    return any(str(i.get("decision", "")).upper() == "APPROVE" for i in items)


__all__ = ["default_approval_checker", "APPROVAL_UNAVAILABLE"]
