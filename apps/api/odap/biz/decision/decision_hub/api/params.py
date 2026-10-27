"""台账 / 队列的查询参数对象（FastAPI 类依赖）

把参数校验与 `DecisionQuery` 构造放在这里，路由函数只保留"校验 -> 调服务 ->
返回"三步，避免单函数被 15 个参数撑到 40 行以上。

契约要点：
- 全部端点**不提供任何 workspace 入参**，`workspace_id` 只从 JWT 声明解析
- `page` 上限 100：估算态下"跳末页"本无意义，深翻页 `SKIP` 是 O(n)
- 排序枚举不含 `evidence_count`：契约 v1.2.0 已物理删除（需写时派生 + M3 回填，
  降 P1）。留着会让前端拿到"枚举接受但行为未定义"的结果，比 422 更难排查
"""

from datetime import datetime
from typing import List, Literal, Optional

from fastapi import HTTPException, Query

from odap.biz.decision.decision_record.interfaces import DecisionQuery
from odap.biz.decision.decision_record.models import (
    DecisionEntrySource,
    DecisionOutcome,
    DecisionStatus,
)
from odap.biz.decision.decision_record.models.timestamps import iso_utc

LedgerSort = Literal["created_at", "updated_at", "confidence"]
QueueSort = Literal["waited_desc", "created_asc", "confidence_asc"]
SortOrder = Literal["asc", "desc"]
QueueGroupParam = Literal["all", "to_resolve", "to_execute"]


class LedgerParams:
    """`GET /api/decisions` 查询参数。"""

    def __init__(
        self,
        page: int = Query(1, ge=1, le=100),
        page_size: int = Query(20, ge=1, le=100),
        status: Optional[List[DecisionStatus]] = Query(None, description="可重复传入以多选"),
        outcome: Optional[List[DecisionOutcome]] = Query(None, description="可重复传入以多选"),
        entry_source: Optional[DecisionEntrySource] = Query(None),
        decision_type: Optional[str] = Query(None, max_length=64),
        agent_id: Optional[str] = Query(None, max_length=64),
        min_confidence: Optional[float] = Query(None, ge=0, le=1),
        max_confidence: Optional[float] = Query(None, ge=0, le=1),
        q: Optional[str] = Query(None, max_length=100),
        created_from: Optional[datetime] = Query(None),
        created_to: Optional[datetime] = Query(None),
        sort: LedgerSort = Query("created_at"),
        order: SortOrder = Query("desc"),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.status = status or []
        self.outcome = outcome or []
        self.entry_source = entry_source
        self.decision_type = decision_type
        self.agent_id = agent_id
        self.min_confidence = min_confidence
        self.max_confidence = max_confidence
        self.q = q
        self.created_from = created_from
        self.created_to = created_to
        self.sort = sort
        self.order = order

    def to_query(self, workspace_id: str) -> DecisionQuery:
        """构造查询对象；`min > max` 返回 422（静默空集会让人以为"没数据"）。"""
        if (
            self.min_confidence is not None
            and self.max_confidence is not None
            and self.min_confidence > self.max_confidence
        ):
            raise HTTPException(status_code=422, detail="min_confidence 不得大于 max_confidence")
        return DecisionQuery(
            workspace_id=workspace_id,
            statuses=tuple(item.value for item in self.status),
            outcomes=tuple(item.value for item in self.outcome),
            entry_source=self.entry_source.value if self.entry_source else None,
            decision_type=self.decision_type,
            agent_id=self.agent_id,
            min_confidence=self.min_confidence,
            max_confidence=self.max_confidence,
            text_query=self.q,
            created_from=iso_utc(self.created_from),
            created_to=iso_utc(self.created_to),
            exclude_assumed=False,  # 台账要看全量（含历史推定记录）
            sort_by=self.sort,
            order=self.order,
        )


class QueueParams:
    """`GET /api/decisions/pending` 查询参数。

    刻意**不存在** `status` / `outcome` / `sla_minutes` 字段：
    队列的待办域与 SLA 口径都由服务端定，客户端无法收窄成别的语义。
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, le=100),
        page_size: int = Query(20, ge=1, le=100),
        group: QueueGroupParam = Query("all"),
        entry_source: Optional[DecisionEntrySource] = Query(None),
        decision_type: Optional[str] = Query(None, max_length=64),
        sort_by: QueueSort = Query("waited_desc"),
    ) -> None:
        self.page = page
        self.page_size = page_size
        self.group = group
        self.entry_source = entry_source
        self.decision_type = decision_type
        self.sort_by = sort_by

    def to_query(self, workspace_id: str) -> DecisionQuery:
        return DecisionQuery(
            workspace_id=workspace_id,
            entry_source=self.entry_source.value if self.entry_source else None,
            decision_type=self.decision_type,
            exclude_assumed=True,
        )
