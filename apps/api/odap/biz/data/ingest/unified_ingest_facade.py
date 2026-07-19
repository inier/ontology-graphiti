"""数据摄入统一门面

UnifiedIngestFacade 是所有数据摄入的统一入口，
根据 source_type 路由到 PerceptionHub（事件驱动）或 IngestService（文档驱动）。

摄入契约（Phase 2）：
- ontology_id: 约束性抽取时必填，指定数据归属的本体
- extraction_mode: constrained（约束性）| exploratory（探索性）
  - constrained: entity_type 必须在本体类型定义中已存在
  - exploratory: 允许推断新类型结构，生成 draft 候选
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SourceCategory:
    """数据源分类常量"""
    DOCUMENT_DRIVEN = frozenset({
        "url", "news", "tavily", "manual", "json",
        "natural_language", "random_events", "database",
        "kb_upload", "ontology_document",
    })
    EVENT_DRIVEN = frozenset({
        "webhook", "sensor", "mcp", "file", "api",
    })


class ExtractionMode:
    """抽取模式常量"""
    CONSTRAINED = "constrained"    # 约束性：entity_type 必须已定义
    EXPLORATORY = "exploratory"    # 探索性：允许推断新类型结构


class UnifiedIngestFacade:
    """统一摄入门面 — 所有数据摄入的单一入口。

    路由规则:
    - 文档驱动源 (url/news/tavily/manual/json/natural_language/random_events/database)
      → IngestService
    - 事件驱动源 (webhook/sensor/mcp/file/api)
      → PerceptionHub

    摄入契约:
    - constrained 模式: ontology_id 必填，entity_type 必须在本体中已定义
    - exploratory 模式: 允许推断新类型，自动生成 draft 候选
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> "UnifiedIngestFacade":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._ingest_service = None
        self._perception_hub = None
        self._type_registry = None

    @property
    def ingest_service(self):
        """延迟加载 IngestService"""
        if self._ingest_service is None:
            from odap.biz.core.ontology.construction.pipeline.services import get_ingest_service
            self._ingest_service = get_ingest_service()
        return self._ingest_service

    @property
    def perception_hub(self):
        """延迟加载 PerceptionHub"""
        if self._perception_hub is None:
            from odap.biz.data.perception.hub import get_perception_hub
            self._perception_hub = get_perception_hub()
        return self._perception_hub

    @property
    def type_registry(self):
        """延迟加载 TypeRegistry"""
        if self._type_registry is None:
            from odap.biz.core.ontology.registry import get_type_registry
            self._type_registry = get_type_registry()
        return self._type_registry

    async def ingest(self, source_type: str, **kwargs) -> Dict[str, Any]:
        """统一摄入入口。

        Args:
            source_type: 数据源类型
            ontology_id: 所属本体 ID（约束性抽取时必填）
            extraction_mode: constrained | exploratory
            **kwargs: 各源类型所需的参数

        Returns:
            Dict[str, Any]: 摄入结果
        """
        ontology_id = kwargs.get("ontology_id")
        extraction_mode = kwargs.get("extraction_mode", ExtractionMode.CONSTRAINED)

        # 约束性抽取契约校验
        if extraction_mode == ExtractionMode.CONSTRAINED and ontology_id:
            validation = self._validate_ingest_contract(ontology_id)
            if validation.get("status") == "error":
                return validation

        if source_type in SourceCategory.DOCUMENT_DRIVEN:
            return await self._ingest_document(source_type, **kwargs)
        elif source_type in SourceCategory.EVENT_DRIVEN:
            return await self._ingest_event(source_type, **kwargs)
        else:
            return {"status": "error", "message": f"Unknown source type: {source_type}"}

    def _validate_ingest_contract(self, ontology_id: str) -> Dict[str, Any]:
        """摄入契约校验：验证本体存在且有类型定义

        Returns:
            {"status": "ok"} 或 {"status": "error", "message": "..."}
        """
        try:
            ontology = self.type_registry.ontology_service.get_ontology(ontology_id)
            if ontology.get("status") == "error":
                return {"status": "error", "message": f"本体不存在: {ontology_id}"}

            types = self.type_registry.list_object_types(ontology_id)
            type_count = types.get("count", 0)
            if type_count == 0:
                return {
                    "status": "error",
                    "message": f"本体 {ontology_id} 尚无类型定义，请先定义对象类型或使用 exploratory 模式",
                }
            return {"status": "ok", "type_count": type_count}
        except Exception as exc:
            logger.warning("Ingest contract validation failed: %s", exc)
            return {"status": "ok"}  # 校验失败不阻塞摄入

    def validate_entity_type(self, ontology_id: str, entity_type: str) -> Dict[str, Any]:
        """验证 entity_type 是否在本体类型定义中已存在

        用于约束性抽取时，逐条验证抽取结果的 entity_type。

        Returns:
            {"valid": True/False, "type_id": "...", "message": "..."}
        """
        try:
            types = self.type_registry.list_object_types(ontology_id)
            for obj_type in types.get("object_types", []):
                if obj_type.get("name") == entity_type or obj_type.get("type_id") == entity_type:
                    return {"valid": True, "type_id": obj_type["type_id"]}
            return {"valid": False, "message": f"entity_type '{entity_type}' 未在本体 {ontology_id} 中定义"}
        except Exception as exc:
            logger.warning("Entity type validation failed: %s", exc)
            return {"valid": True}  # 校验失败不阻塞

    async def _ingest_document(self, source_type: str, **kwargs) -> Dict[str, Any]:
        """路由到 IngestService（文档驱动源）"""
        try:
            # 知识库文档摄入 — 路由到 KB 服务
            if source_type == "kb_upload":
                return await self._ingest_kb_document(source_type, **kwargs)

            # 本体文档摄入 — 路由到本体文档处理
            if source_type == "ontology_document":
                return await self._ingest_ontology_document(source_type, **kwargs)

            if source_type == "url":
                record_id = await self.ingest_service.ingest_from_url(
                    url=kwargs.get("url", ""),
                    event_context=kwargs.get("event_context", ""),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "news":
                record_id = await self.ingest_service.ingest_from_news(
                    query=kwargs.get("query", ""),
                    event_context=kwargs.get("event_context", ""),
                    max_sources=kwargs.get("max_sources", 5),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "tavily":
                record_id = await self.ingest_service.ingest_from_tavily(
                    query=kwargs.get("query", ""),
                    event_context=kwargs.get("event_context", ""),
                    max_sources=kwargs.get("max_sources", 5),
                    search_depth=kwargs.get("search_depth", "basic"),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "manual":
                record_id = await self.ingest_service.ingest_from_manual(
                    form_data=kwargs.get("form_data", ""),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "json":
                record_id = await self.ingest_service.ingest_from_json(
                    raw_json=kwargs.get("raw_json", ""),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "natural_language":
                record_id = await self.ingest_service.ingest_from_natural_language(
                    text=kwargs.get("text", ""),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "random_events":
                record_id = await self.ingest_service.generate_random_events(
                    parties=kwargs.get("parties", ["Red", "Blue"]),
                    scenario_context=kwargs.get("scenario_context"),
                    count=kwargs.get("count", 1),
                    scenario_id=kwargs.get("scenario_id"),
                    generator_type=kwargs.get("generator_type", "military"),
                    workspace_id=kwargs.get("workspace_id", "default"),
                )
            elif source_type == "database":
                record_id = await self.ingest_service.ingest_from_database(
                    connection_id=kwargs.get("connection_id", ""),
                    table_patterns=kwargs.get("table_patterns"),
                    scenario_id=kwargs.get("scenario_id"),
                    workspace_id=kwargs.get("workspace_id", "default"),
                )
            else:
                return {"status": "error", "message": f"Unsupported document source: {source_type}"}

            return {
                "status": "ok",
                "source_type": source_type,
                "record_id": record_id,
                "routed_to": "IngestService",
            }
        except Exception as e:
            logger.error(f"UnifiedIngestFacade document ingest failed ({source_type}): {e}")
            return {"status": "error", "message": str(e)}

    async def _ingest_event(self, source_type: str, **kwargs) -> Dict[str, Any]:
        """路由到 PerceptionHub（事件驱动源）"""
        try:
            from odap.biz.data.perception.schemas import (
                PerceptionEvent, PerceptionSourceType,
            )

            # 映射 source_type 字符串到 PerceptionSourceType
            source_type_map = {
                "webhook": PerceptionSourceType.WEBHOOK,
                "sensor": PerceptionSourceType.SENSOR,
                "mcp": PerceptionSourceType.MCP,
                "file": PerceptionSourceType.FILE,
                "api": PerceptionSourceType.API,
            }
            perception_source = source_type_map.get(source_type, PerceptionSourceType.API)

            if source_type == "webhook":
                event_id = self.perception_hub.ingest_webhook(
                    payload=kwargs.get("payload", {}),
                    headers=kwargs.get("headers"),
                )
                event = PerceptionEvent(
                    event_id=event_id,
                    source_type=perception_source,
                    source_name="webhook",
                    raw_content=str(kwargs.get("payload", {})),
                    structured_data=kwargs.get("payload"),
                    scenario_id=kwargs.get("scenario_id"),
                )
            elif source_type == "sensor":
                self.perception_hub.ingest_sensor(
                    sensor_id=kwargs.get("sensor_id", ""),
                    value=kwargs.get("value"),
                    metadata=kwargs.get("metadata"),
                )
                return {
                    "status": "ok",
                    "source_type": source_type,
                    "routed_to": "PerceptionHub",
                    "message": "Sensor reading queued",
                }
            else:
                # mcp / file / api — 通用事件处理
                event = PerceptionEvent(
                    source_type=perception_source,
                    source_name=source_type,
                    raw_content=kwargs.get("content", ""),
                    structured_data=kwargs.get("structured_data"),
                    metadata=kwargs.get("metadata", {}),
                    scenario_id=kwargs.get("scenario_id"),
                )

            output = await self.perception_hub.process_event(
                event, ontology_id=kwargs.get("ontology_id")
            )

            return {
                "status": "ok",
                "source_type": source_type,
                "event_id": output.event_id,
                "routed_to": "PerceptionHub",
                "extraction_confidence": output.extraction.confidence,
            }
        except Exception as e:
            logger.error(f"UnifiedIngestFacade event ingest failed ({source_type}): {e}")
            return {"status": "error", "message": str(e)}

    async def _ingest_kb_document(self, source_type: str = "kb_upload", **kwargs) -> Dict[str, Any]:
        """统一入口 — 知识库文档摄入。

        将 KB 文档上传/创建操作统一路由到这里，执行：
        1. 创建文档记录（SQLite）— 仅当未提供 doc_id 时
        2. 文本清洗
        3. 实体关系提取
        4. 写入 Neo4j 图谱

        Args:
            kb_id: 目标知识库 ID
            doc_id: 已有文档 ID（由 routes 层传入时跳过创建）
            title: 文档标题
            content: 文档内容
            content_type: 内容类型 (text/file/web)
            category_id: 分类 ID（可选）
            extraction_method: 提取方式 (auto/regex/llm)
            entity_types: 目标实体类型列表（可选）
            workspace_id: 工作空间 ID

        Returns:
            Dict[str, Any]: 摄入结果
        """
        try:
            from odap.biz.data.knowledge_base.services.knowledge_base_service import KnowledgeBaseService

            kb_id = kwargs.get("kb_id", "")
            if not kb_id:
                return {"status": "error", "message": "kb_id is required for KB document ingestion"}

            kb_service = KnowledgeBaseService.get_instance()
            kb = kb_service.get_knowledge_base(kb_id)
            if isinstance(kb, dict) and kb.get("status") == "error":
                return {"status": "error", "message": f"知识库不存在: {kb_id}"}

            existing_doc_id = kwargs.get("doc_id", "")
            if existing_doc_id:
                # 文档已由 routes 层创建，直接使用已有 doc_id
                doc_id = existing_doc_id
            else:
                # 创建文档记录
                data = {
                    "title": kwargs.get("title", "未命名文档"),
                    "content_type": kwargs.get("content_type", "text"),
                    "content": kwargs.get("content", ""),
                    "category_id": kwargs.get("category_id"),
                }
                doc_result = kb_service.create_document(kb_id, data)
                if isinstance(doc_result, dict) and doc_result.get("status") == "error":
                    return {"status": "error", "message": doc_result.get("message", "文档创建失败")}
                doc_id = doc_result.get("doc_id", "")
                if not doc_id:
                    return {"status": "error", "message": "文档 ID 获取失败"}

            # 触发实体提取和图谱构建
            extraction_method = kwargs.get("extraction_method", "auto")
            entity_types = kwargs.get("entity_types")

            graph_result = await kb_service.build_graph(
                doc_id,
                extraction_method=extraction_method,
                entity_types=entity_types,
            )

            return {
                "status": "ok",
                "source_type": source_type,
                "kb_id": kb_id,
                "doc_id": doc_id,
                "routed_to": "UnifiedIngestFacade→KnowledgeBaseService",
                "graph_build": graph_result,
            }
        except Exception as e:
            logger.error(f"UnifiedIngestFacade kb_document ingest failed: {e}")
            return {"status": "error", "message": str(e)}

    async def _ingest_ontology_document(self, source_type: str = "ontology_document", **kwargs) -> Dict[str, Any]:
        """统一入口 — 本体文档摄入。

        处理本体相关的文档摄入，将文档内容与本体类型定义关联。

        Args:
            ontology_id: 所属本体 ID
            title: 文档标题
            content: 文档内容
            extraction_mode: constrained | exploratory
            workspace_id: 工作空间 ID

        Returns:
            Dict[str, Any]: 摄入结果
        """
        try:
            ontology_id = kwargs.get("ontology_id")
            if not ontology_id:
                return {"status": "error", "message": "ontology_id is required for ontology document ingestion"}

            # 验证本体存在
            validation = self._validate_ingest_contract(ontology_id)
            if validation.get("status") == "error":
                return validation

            # 文本内容确认
            content = kwargs.get("content", "")
            title = kwargs.get("title", f"Ontology Doc – {ontology_id}")
            if not content or not content.strip():
                return {"status": "error", "message": "文档内容为空"}

            # 路由到 IngestService 处理
            record_id = await self.ingest_service.ingest_from_manual(
                form_data={
                    "title": title,
                    "content": content,
                    "ontology_id": ontology_id,
                    "extraction_mode": kwargs.get("extraction_mode", ExtractionMode.CONSTRAINED),
                    "workspace_id": kwargs.get("workspace_id", "default"),
                },
                scenario_id=kwargs.get("scenario_id"),
            )

            return {
                "status": "ok",
                "source_type": source_type,
                "ontology_id": ontology_id,
                "record_id": record_id,
                "routed_to": "UnifiedIngestFacade→IngestService",
            }
        except Exception as e:
            logger.error(f"UnifiedIngestFacade ontology document ingest failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_supported_source_types(self) -> Dict[str, List[str]]:
        """返回所有支持的源类型分类"""
        return {
            "document_driven": sorted(SourceCategory.DOCUMENT_DRIVEN),
            "event_driven": sorted(SourceCategory.EVENT_DRIVEN),
        }

    async def scan_conflicts(self, ontology_id: str = None) -> Dict[str, Any]:
        """扫描指定本体的数据冲突

        Args:
            ontology_id: 本体 ID（可选，不指定则扫描全部）

        Returns:
            Dict[str, Any]: 冲突扫描结果
        """
        try:
            service = self.ingest_service
            return service.scan_data_conflicts()
        except Exception as e:
            logger.error(f"UnifiedIngestFacade scan_conflicts failed: {e}")
            return {"status": "error", "message": f"IngestService unavailable: {e}"}

    async def repair_conflicts(self, ontology_id: str = None,
                                conflict_ids: List[str] = None,
                                dry_run: bool = True) -> Dict[str, Any]:
        """修复指定本体的数据冲突

        Args:
            ontology_id: 本体 ID（可选）
            conflict_ids: 指定修复的冲突 ID 列表（可选）
            dry_run: 是否仅模拟运行（默认 True）

        Returns:
            Dict[str, Any]: 修复结果
        """
        try:
            service = self.ingest_service
            return service.repair_data_conflicts(dry_run=dry_run)
        except Exception as e:
            logger.error(f"UnifiedIngestFacade repair_conflicts failed: {e}")
            return {"status": "error", "message": f"IngestService unavailable: {e}"}

    def list_generator_types(self) -> List[str]:
        """列出可用的随机事件生成器类型

        Returns:
            List[str]: 生成器类型名称列表
        """
        try:
            service = self.ingest_service
            types_info = service.get_random_generator_types()
            return [t.get("type", t.get("name", "")) for t in types_info if t.get("type") or t.get("name")]
        except Exception as e:
            logger.error(f"UnifiedIngestFacade list_generator_types failed: {e}")
            return []


_facade_instance = None


def get_unified_ingest_facade() -> UnifiedIngestFacade:
    """获取统一摄入门面实例（单例）"""
    global _facade_instance
    if _facade_instance is None:
        _facade_instance = UnifiedIngestFacade()
    return _facade_instance
