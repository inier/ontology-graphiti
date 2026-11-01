"""决策台账与待决策队列端点（ADR-101 §3.1 / §3.2，本期 2 个只读端点）

隔离（ADR-076 §7）：
- 两个端点都不接受任何 workspace 入参，一律 `Depends(get_current_workspace)` 从 JWT 解析
- 声明缺失 -> 422（fail-closed，不做 user_id 兜底、不回落 default 空间）
- 跨空间"命中"不存在于本层：列表类端点没有可枚举的单条 ID，隔离由存储层
  `MATCH (n:Decision {group_id: $ws})` 强制，跨空间数据不会出现在任何响应中
- 本 router 不引入单段 `/{decision_id}` 路由，避免遮蔽既有 `/{id}/chain` 等端点
"""

from fastapi import APIRouter, Depends

from odap.infra.security.workspace_access import get_current_workspace

from odap.biz.decision.decision_hub.api.params import LedgerParams, QueueParams
from odap.biz.decision.decision_hub.models import DecisionLedgerPage, PendingQueuePage
from odap.biz.decision.decision_hub.services.ledger_service import (
    LedgerService,
    get_ledger_service,
)

decision_hub_router = APIRouter(prefix="/api/decisions", tags=["决策台账"])


@decision_hub_router.get("", response_model=DecisionLedgerPage)
async def list_decision_ledger(
    params: LedgerParams = Depends(),
    workspace_id: str = Depends(get_current_workspace),
    service: LedgerService = Depends(get_ledger_service),
) -> DecisionLedgerPage:
    """决策台账：分页 + 筛选 + 排序，含 `total_is_estimate` 估算标记。"""
    return await service.list_ledger(params.to_query(workspace_id), params.page, params.page_size)


@decision_hub_router.get("/pending", response_model=PendingQueuePage)
async def list_pending_decisions(
    params: QueueParams = Depends(),
    workspace_id: str = Depends(get_current_workspace),
    service: LedgerService = Depends(get_ledger_service),
) -> PendingQueuePage:
    """待决策队列：待办域（pending|decided|executing）按 group 二分 + 四计数 + SLA。"""
    return await service.list_pending(
        params.to_query(workspace_id),
        group=params.group,
        sort_by=params.sort_by,
        page=params.page,
        page_size=params.page_size,
    )
