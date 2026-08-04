"""Iter 3.2: Graphiti audit writer — zero-LLM fact-evolution audit.

ADR-074 §2.2: 事实演化审计使用 ``EpisodicNode.save`` 写入 Graphiti，
覆盖三项审计需求：
    #1 数据采集审计：何时从哪个数据源采集了什么
    #2 抽取过程审计：用了哪个 HE 模板、LLM 参数、置信度评分
    #4 推理过程审计：推理路径、用了哪些事实

This writer delegates to ``GraphManager.save_audit_episode()`` (implemented
in Iter 1.1), which uses ``EpisodicNode.save(driver)`` directly — bypassing
``add_episode`` and its 3-9 LLM calls per invocation.

Distinction from existing ``GraphitiAuditChannel``:
    - ``GraphitiAuditChannel`` (audit_graphiti_channel.py): writes audit
      events as Neo4j *entities* (AuditLog/AuditUser/AuditResource nodes)
      via ``add_entity``/``add_relationship``. Used for operational audit
      graph traversal.
    - ``GraphitiAuditWriter`` (this module): writes audit events as
      Graphiti *Episodes* via ``EpisodicNode.save``. Used for fact-evolution
      audit with dual-temporal tracking (valid_time + transaction_time),
      edge invalidation, and point-in-time queries.

Design rules (AGENTS.md):
    - Never raises — all errors are caught and logged
    - Returns bool: True on success, False on failure (degradation)
    - Lazy imports to avoid circular dependencies
    - All audit data is JSON-serializable
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger("graphiti_audit_writer")


class GraphitiAuditWriter:
    """Writes fact-evolution audit events to Graphiti via EpisodicNode.save.

    This is the canonical writer for ADR-074 §2.2 fact-evolution audit:
        #1 数据采集审计, #2 抽取过程审计, #4 推理过程审计.

    Usage:
        writer = GraphitiAuditWriter()
        writer.log_ingestion_audit(...)
        writer.log_extraction_audit(...)
        writer.log_reasoning_audit(...)
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, graph_manager=None):
        if hasattr(self, "_initialized"):
            return
        self._graph_manager = graph_manager
        self._initialized = True

    def _get_graph_manager(self):
        """Lazily resolve the GraphManager singleton."""
        if self._graph_manager is not None:
            return self._graph_manager
        try:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        except Exception as exc:
            logger.debug("GraphManager init failed: %s", exc)
            self._graph_manager = None
        return self._graph_manager

    # ------------------------------------------------------------------
    # #1 数据采集审计
    # ------------------------------------------------------------------

    def log_ingestion_audit(
        self,
        workspace_id: str,
        doc_id: str,
        source_type: str,
        source_url: str = "",
        raw_data_ref: str = "",
        query: str = "",
        text_length: int = 0,
        collected_at: Optional[datetime] = None,
    ) -> bool:
        """#1 数据采集审计：记录何时从哪个数据源采集了什么。

        Args:
            workspace_id: 工作空间 ID.
            doc_id: OntologyDocument ID.
            source_type: 采集器类型 (news_ingest / manual_input / file_upload).
            source_url: 数据源 URL.
            raw_data_ref: MinIO 原始数据引用 (Iter 3.1).
            query: 检索关键词或采集上下文.
            text_length: 采集文本长度.
            collected_at: 采集时间（默认当前 UTC）.

        Returns:
            True if audit episode saved, False on failure.
        """
        audit_data = {
            "audit_layer": "fact_evolution",
            "audit_type": "#1_ingestion",
            "event_type": "data.ingest",
            "workspace_id": workspace_id,
            "doc_id": doc_id,
            "source_type": source_type,
            "source_url": source_url,
            "raw_data_ref": raw_data_ref,
            "query": query,
            "text_length": text_length,
            "collected_at": (collected_at or datetime.now(timezone.utc)).isoformat(),
            "audit_id": str(uuid.uuid4()),
        }
        return self._write_episode(audit_data, valid_at=collected_at, source_desc="ingestion_audit")

    # ------------------------------------------------------------------
    # #2 抽取过程审计
    # ------------------------------------------------------------------

    def log_extraction_audit(
        self,
        workspace_id: str,
        ontology_id: str,
        session_id: str,
        source_doc_id: str = "",
        template_id: str = "",
        extraction_method: str = "",
        entity_count: int = 0,
        relation_count: int = 0,
        confidence_score: Optional[float] = None,
        validation_report: Optional[Dict[str, Any]] = None,
        llm_params: Optional[Dict[str, Any]] = None,
        degradation_flags: Optional[list] = None,
        extracted_at: Optional[datetime] = None,
    ) -> bool:
        """#2 抽取过程审计：记录 HE 模板、方法、LLM 参数、置信度、校验结果。

        Args:
            workspace_id: 工作空间 ID.
            ontology_id: 目标本体 ID.
            session_id: 抽取会话 ID.
            source_doc_id: 源文档 ID.
            template_id: HE 模板名/路径.
            extraction_method: 抽取方法 (he_feed / trial_extract / custom).
            entity_count: 抽取实体数.
            relation_count: 抽取关系数.
            confidence_score: 置信度评分 (0.0-1.0).
            validation_report: 4维校验报告.
            llm_params: LLM 调用参数 (model, temperature, etc.).
            degradation_flags: 降级标志列表.
            extracted_at: 抽取时间.

        Returns:
            True if audit episode saved, False on failure.
        """
        audit_data = {
            "audit_layer": "fact_evolution",
            "audit_type": "#2_extraction",
            "event_type": "data.extract",
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
            "session_id": session_id,
            "source_doc_id": source_doc_id,
            "template_id": template_id,
            "extraction_method": extraction_method,
            "entity_count": entity_count,
            "relation_count": relation_count,
            "confidence_score": confidence_score,
            "validation_report": validation_report or {},
            "llm_params": llm_params or {},
            "degradation_flags": degradation_flags or [],
            "extracted_at": (extracted_at or datetime.now(timezone.utc)).isoformat(),
            "audit_id": str(uuid.uuid4()),
        }
        return self._write_episode(audit_data, valid_at=extracted_at, source_desc="extraction_audit")

    # ------------------------------------------------------------------
    # #4 推理过程审计
    # ------------------------------------------------------------------

    def log_reasoning_audit(
        self,
        workspace_id: str,
        reasoning_engine: str,
        input_facts: Optional[list] = None,
        reasoning_path: Optional[list] = None,
        output_conclusion: str = "",
        confidence: Optional[float] = None,
        trace_id: str = "",
        reasoned_at: Optional[datetime] = None,
    ) -> bool:
        """#4 推理过程审计：记录推理引擎、输入事实、推理路径、输出结论。

        Args:
            workspace_id: 工作空间 ID.
            reasoning_engine: 推理引擎名称.
            input_facts: 输入事实列表 (entity_id / relation_id references).
            reasoning_path: 推理路径 (step-by-step chain).
            output_conclusion: 推理结论.
            confidence: 置信度 (0.0-1.0).
            trace_id: 追踪 ID.
            reasoned_at: 推理时间.

        Returns:
            True if audit episode saved, False on failure.
        """
        audit_data = {
            "audit_layer": "fact_evolution",
            "audit_type": "#4_reasoning",
            "event_type": "reasoning.execute",
            "workspace_id": workspace_id,
            "reasoning_engine": reasoning_engine,
            "input_facts": input_facts or [],
            "reasoning_path": reasoning_path or [],
            "output_conclusion": output_conclusion,
            "confidence": confidence,
            "trace_id": trace_id or str(uuid.uuid4()),
            "reasoned_at": (reasoned_at or datetime.now(timezone.utc)).isoformat(),
            "audit_id": str(uuid.uuid4()),
        }
        return self._write_episode(audit_data, valid_at=reasoned_at, source_desc="reasoning_audit")

    # ------------------------------------------------------------------
    # Generic episode writer
    # ------------------------------------------------------------------

    def _write_episode(
        self,
        audit_data: Dict[str, Any],
        valid_at: Optional[datetime] = None,
        source_desc: str = "audit_layer",
    ) -> bool:
        """Write an audit episode to Graphiti via save_audit_episode.

        This delegates to GraphManager.save_audit_episode(), which uses
        EpisodicNode.save(driver) — zero LLM calls.

        Args:
            audit_data: 审计数据 dict (JSON-serializable).
            valid_at: 事实生效时间（双时态的 valid_time）.
            source_desc: 来源描述 (episode sourceDescription 字段).

        Returns:
            True on success, False on failure or when Graphiti is unavailable.
        """
        gm = self._get_graph_manager()
        if gm is None:
            logger.debug("GraphManager unavailable, audit episode skipped: %s",
                         audit_data.get("audit_type"))
            return False

        try:
            # save_audit_episode is an async method — check if we're in an
            # async context. If not, run via asyncio.
            import asyncio
            coro = gm.save_audit_episode(
                audit_data=audit_data,
                valid_at=valid_at,
                source_description=source_desc,
            )
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context — schedule the coroutine
                # but can't await it here. Use ensure_future + callback.
                # For simplicity, we create a task and return True optimistically.
                # The caller in async context should use the async method directly.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=30)
            except RuntimeError:
                # No running loop — safe to use asyncio.run
                return asyncio.run(coro)
        except Exception as exc:
            logger.warning("Audit episode write failed (%s): %s",
                           audit_data.get("audit_type"), exc)
            return False

    # ------------------------------------------------------------------
    # Async interface (for use within async services)
    # ------------------------------------------------------------------

    async def log_ingestion_audit_async(
        self,
        workspace_id: str,
        doc_id: str,
        source_type: str,
        **kwargs: Any,
    ) -> bool:
        """Async version of log_ingestion_audit for use in async services."""
        audit_data = {
            "audit_layer": "fact_evolution",
            "audit_type": "#1_ingestion",
            "event_type": "data.ingest",
            "workspace_id": workspace_id,
            "doc_id": doc_id,
            "source_type": source_type,
            "audit_id": str(uuid.uuid4()),
            **kwargs,
        }
        collected_at = kwargs.get("collected_at")
        if isinstance(collected_at, str):
            collected_at = None
        return await self._write_episode_async(
            audit_data, valid_at=collected_at, source_desc="ingestion_audit",
        )

    async def log_extraction_audit_async(
        self,
        workspace_id: str,
        ontology_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> bool:
        """Async version of log_extraction_audit for use in async services."""
        audit_data = {
            "audit_layer": "fact_evolution",
            "audit_type": "#2_extraction",
            "event_type": "data.extract",
            "workspace_id": workspace_id,
            "ontology_id": ontology_id,
            "session_id": session_id,
            "audit_id": str(uuid.uuid4()),
            **kwargs,
        }
        extracted_at = kwargs.get("extracted_at")
        if isinstance(extracted_at, str):
            extracted_at = None
        return await self._write_episode_async(
            audit_data, valid_at=extracted_at, source_desc="extraction_audit",
        )

    async def _write_episode_async(
        self,
        audit_data: Dict[str, Any],
        valid_at: Optional[datetime] = None,
        source_desc: str = "audit_layer",
    ) -> bool:
        """Async episode writer — awaits save_audit_episode directly.

        Args:
            audit_data: 审计数据 dict (JSON-serializable).
            valid_at: 事实生效时间（双时态的 valid_time）.
            source_desc: 来源描述 (episode sourceDescription 字段).
        """
        gm = self._get_graph_manager()
        if gm is None:
            logger.debug("GraphManager unavailable, audit episode skipped: %s",
                         audit_data.get("audit_type"))
            return False
        try:
            return await gm.save_audit_episode(
                audit_data=audit_data,
                valid_at=valid_at,
                source_description=source_desc,
            )
        except Exception as exc:
            logger.warning("Async audit episode write failed (%s): %s",
                           audit_data.get("audit_type"), exc)
            return False


# Module-level singleton accessor
def get_graphiti_audit_writer() -> GraphitiAuditWriter:
    """Return the singleton GraphitiAuditWriter instance."""
    return GraphitiAuditWriter()
