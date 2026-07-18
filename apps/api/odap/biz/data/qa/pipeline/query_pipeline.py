"""QueryPipeline - 五阶段查询管线主编排器"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from odap.biz.data.qa.models import (
    FusionStrategy, QueryAuditRecord, QueryPlan, QueryRequest, QueryResponse,
    QueryUnderstanding, RetrievalResultSet
)
from odap.biz.data.qa.pipeline.execution.query_executor import ExecutionContext, ExecutionStage
from odap.biz.data.qa.pipeline.fusion.result_fuser import FusionStage
from odap.biz.data.qa.pipeline.generation.response_generator import GenerationStage
from odap.biz.data.qa.pipeline.planning.query_planner import PlanningStage
from odap.biz.data.qa.pipeline.understanding.intent_recognizer import UnderstandingStage
from odap.biz.data.qa.retrieval.unified_retriever import UnifiedRetriever
from odap.biz.data.qa.evaluation.audit_storage import QueryAuditStorage

logger = logging.getLogger(__name__)


class QueryPipeline:
    """五阶段查询管线 - 替代 QAEngineV2 的核心逻辑"""

    def __init__(self, llm_client=None, graph_manager=None):
        # 自动创建 LLM 客户端
        if llm_client is None:
            try:
                from odap.biz.data.qa.pipeline.llm_client import create_llm_client
                llm_client = create_llm_client()
            except Exception:
                pass
        self.understanding = UnderstandingStage(llm_client)
        self.planning = PlanningStage()
        self.execution = ExecutionStage(UnifiedRetriever(
            vector_retriever=self._create_vector_retriever(llm_client, graph_manager),
            graph_retriever=self._create_graph_retriever(llm_client, graph_manager),
        ))
        self.fusion = FusionStage()
        self.generation = GenerationStage(llm_client)
        self.audit_storage = QueryAuditStorage()
        self._llm_client = llm_client
        self._graph_manager = graph_manager

    def _create_vector_retriever(self, llm_client, graph_manager):
        from odap.biz.data.qa.retrieval.vector_retriever import VectorRetriever, QueryRewriter
        return VectorRetriever(graph_manager, QueryRewriter(llm_client))

    def _create_graph_retriever(self, llm_client, graph_manager):
        from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever, CypherGenerator
        return GraphRetriever(graph_manager, CypherGenerator(llm_client))

    async def query(self, request: QueryRequest) -> QueryResponse:
        """五阶段查询: Understanding → Planning → Execution → Fusion → Generation"""
        start_time = time.time()
        audit = QueryAuditRecord(
            user_id=request.user_id,
            workspace_id=request.workspace_id or "",
            scenario_id=request.scenario_id,
            original_query=request.query,
        )

        try:
            # Stage 1: Understanding
            understanding = self.understanding.analyze(
                request.query, request.context
            )
            audit.intent = understanding.intent.value
            audit.extracted_entities = understanding.extracted_entities
            audit.rewritten_queries = understanding.rewritten_queries

            # 澄清检测
            if understanding.needs_clarification:
                return self._clarification_response(understanding, audit, start_time)

            # Stage 2: Planning
            constraints = {
                "top_k": request.top_k,
                "mode": request.mode,
            }
            plan = self.planning.create_plan(understanding, constraints)
            audit.query_plan = plan.model_dump()
            audit.selected_pillars = plan.pillars

            # Stage 3: Execution
            context = ExecutionContext(
                workspace_id=request.workspace_id or "",
                scenario_id=request.scenario_id,
                user_id=request.user_id,
            )
            raw_results = await self.execution.execute(plan, context)
            audit.pillar_results_count = raw_results.pillar_scores
            audit.execution_time_ms = raw_results.metadata.get("execution_time_ms", {})
            audit.total_results_before_fusion = len(raw_results.results)

            # Stage 4: Fusion
            fused = self.fusion.merge_and_rerank(
                raw_results, request.query, understanding,
                plan.fusion_strategy, plan.top_k
            )
            audit.total_results_after_fusion = len(fused.results)

            # Stage 5: Generation
            response = await self.generation.generate(
                fused, understanding, request.query, stream=request.stream
            )
            response.understanding = understanding
            response.plan = plan
            response.total_time_ms = (time.time() - start_time) * 1000

            # 审计
            audit.response_length = len(response.answer)
            audit.source_count = len(response.sources)
            audit.total_time_ms = response.total_time_ms
            self._save_audit(audit)

            return response

        except Exception as e:
            logger.error(f"QueryPipeline error: {e}")
            audit.total_time_ms = (time.time() - start_time) * 1000
            self._save_audit(audit)
            return QueryResponse(
                answer=f"查询处理出错: {str(e)}",
                total_time_ms=audit.total_time_ms,
                metadata={"error": str(e)},
            )

    async def search(self, request: QueryRequest) -> RetrievalResultSet:
        """纯检索 - 不生成回答，仅返回检索结果"""
        understanding = self.understanding.analyze(request.query, request.context)
        constraints = {"top_k": request.top_k, "mode": request.mode}
        plan = self.planning.create_plan(understanding, constraints)
        context = ExecutionContext(
            workspace_id=request.workspace_id or "",
            scenario_id=request.scenario_id,
            user_id=request.user_id,
        )
        raw_results = await self.execution.execute(plan, context)
        return self.fusion.merge_and_rerank(
            raw_results, request.query, understanding,
            plan.fusion_strategy, plan.top_k
        )

    def explain(self, request: QueryRequest) -> Dict[str, Any]:
        """查询解释 - 展示 NL 如何被理解和转换为查询"""
        understanding = self.understanding.analyze(request.query, request.context)
        constraints = {"top_k": request.top_k, "mode": request.mode}
        plan = self.planning.create_plan(understanding, constraints)

        return {
            "original_query": request.query,
            "understanding": understanding.model_dump(),
            "plan": plan.model_dump(),
            "explanation": self._build_explanation(understanding, plan),
        }

    def _clarification_response(self, understanding: QueryUnderstanding,
                                audit: QueryAuditRecord,
                                start_time: float) -> QueryResponse:
        """生成澄清响应"""
        reason_map = {
            "ambiguous_pronoun": "问题中包含模糊代词，请明确指代对象",
            "too_short": "问题描述过于简短，请提供更多细节",
            "low_confidence": "无法确定查询意图，请更详细地描述您的问题",
        }
        reason = reason_map.get(
            understanding.clarification_reason or "", "请提供更多信息"
        )
        audit.total_time_ms = (time.time() - start_time) * 1000
        self._save_audit(audit)

        return QueryResponse(
            answer=f"抱歉，{reason}。您可以尝试：\n1. 使用更具体的实体名称\n2. 说明查询的关联方向\n3. 提供更多上下文信息",
            understanding=understanding,
            total_time_ms=audit.total_time_ms,
        )

    def _build_explanation(self, understanding: QueryUnderstanding,
                           plan: QueryPlan) -> str:
        """构建查询解释文本"""
        parts = [
            f"1. 意图识别: {understanding.intent.value} (置信度: {understanding.confidence:.2f})",
        ]
        if understanding.extracted_entities:
            parts.append(f"2. 提取实体: {', '.join(understanding.extracted_entities)}")
        if understanding.rewritten_queries:
            parts.append(f"3. 查询改写: {understanding.rewritten_queries[0]}")
        parts.append(f"4. 检索支柱: {', '.join(plan.pillars)}")
        parts.append(f"5. 融合策略: {plan.fusion_strategy.value}")
        for sq in plan.sub_queries:
            mode_str = f" (mode={sq.mode})" if sq.mode else ""
            parts.append(f"   - {sq.pillar}: {sq.query[:50]}{mode_str}")
        return "\n".join(parts)

    def _save_audit(self, audit: QueryAuditRecord) -> None:
        """异步保存审计记录"""
        try:
            self.audit_storage.save(audit)
        except Exception as e:
            logger.error(f"Failed to save audit: {e}")
