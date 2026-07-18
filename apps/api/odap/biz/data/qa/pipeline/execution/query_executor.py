"""Stage 3: 查询执行 - 并行执行子查询"""

import logging
from typing import Any, Dict, Optional

from odap.biz.data.qa.models import QueryPlan, RetrievalResultSet
from odap.biz.data.qa.retrieval.unified_retriever import UnifiedRetriever

logger = logging.getLogger(__name__)


class ExecutionContext:
    """执行上下文"""

    def __init__(self, workspace_id: str = "", scenario_id: Optional[str] = None,
                 user_id: str = "", auth_context: Optional[Dict] = None):
        self.workspace_id = workspace_id
        self.scenario_id = scenario_id
        self.user_id = user_id
        self.auth_context = auth_context or {}


class ExecutionStage:
    """Stage 3: 查询执行"""

    def __init__(self, retriever: Optional[UnifiedRetriever] = None):
        self.retriever = retriever or UnifiedRetriever()

    async def execute(self, plan: QueryPlan,
                      context: Optional[ExecutionContext] = None) -> RetrievalResultSet:
        """执行查询计划"""
        context = context or ExecutionContext()

        result_set = await self.retriever.search(
            plan=plan,
            workspace_id=context.workspace_id,
            scenario_id=context.scenario_id,
        )

        return result_set
