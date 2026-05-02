"""
本体构建管道服务

实现完整的处理链路，包含6个阶段：
1. 数据采集 (collection): 调用现有摄入服务
2. 数据清洗 (cleaning): 实现去重、标准化、缺失值处理
3. LLM归纳 (llm): 实现实体/关系/事件提取
4. 本体构建 (ontology): 生成 OntologyDocument
5. 版本管理 (version): 创建版本记录
6. 图谱生成 (graph): 构建 Neo4j 图谱

每个阶段记录完整的处理日志，支持异步执行和状态查询。
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..models.audit import (
    PipelineStage, ProcessLog, ProcessingStatus,
    DataIngestRecord, DataSource
)
from ..models.version import OntologyVersion, VersionStatus
from ..ingestion import OntologyDocument
from ..storage.sqlite_ingest_storage import SQLiteIngestStorage
from odap.infra.security.audit_logger import audit_info, audit_error
from odap.infra.security.audit_models import AuditEventType, AuditSeverity
from .ingest_service import IngestService, get_ingest_service
from .build_service import OntologyBuilderService, get_builder_service
from .version_service import VersionManagementService, get_version_service
from .transform_service import OntologyTransformService as TransformService

logger = logging.getLogger("ontology_pipeline")


def get_local_time():
    """获取本地时间"""
    return datetime.now(timezone.utc).astimezone()


@dataclass
class PipelineContext:
    """管道执行上下文"""
    ingest_id: str
    scenario_id: str
    workspace_id: str = "default"
    source: str = "manual"
    source_details: Dict[str, Any] = field(default_factory=dict)
    original_content: Optional[str] = None
    current_stage: PipelineStage = PipelineStage.COLLECTION
    logs: List[ProcessLog] = field(default_factory=list)
    stage_results: Dict[str, Any] = field(default_factory=dict)
    version_id: Optional[str] = None
    document_id: Optional[str] = None
    error: Optional[str] = None
    success: bool = False
    _storage: SQLiteIngestStorage = field(default_factory=lambda: SQLiteIngestStorage())

    def add_log(self, stage: PipelineStage, operation: str, details: Dict[str, Any],
                status: ProcessingStatus = ProcessingStatus.PROCESSING,
                error_message: Optional[str] = None):
        """添加处理日志（同时保存到数据库和 Graphiti 审计）"""
        log = ProcessLog(
            timestamp=get_local_time(),
            stage=stage,
            operation=operation,
            details=details,
            status=status,
            error_message=error_message
        )
        self.logs.append(log)
        
        # 保存到数据库
        log_dict = {
            'id': log.id,
            'ingest_id': self.ingest_id,
            'stage': stage.value,
            'operation': operation,
            'details': details,
            'status': status.value,
            'error_message': error_message,
            'duration_ms': log.duration_ms,
            'timestamp': log.timestamp.isoformat()
        }
        self._storage.save_process_log(log_dict)
        
        # 调用统一审计日志（保存到 Graphiti）
        try:
            event_type_map = {
                PipelineStage.COLLECTION: AuditEventType.DATA_INGESTION,
                PipelineStage.CLEANING: AuditEventType.DATA_TRANSFORMATION,
                PipelineStage.LLM_EXTRACTION: AuditEventType.MODEL_INFERENCE,
                PipelineStage.ONTOLOGY_BUILD: AuditEventType.ONTOLOGY_BUILD,
                PipelineStage.VERSION_MANAGE: AuditEventType.VERSION_CREATE,
                PipelineStage.GRAPH_BUILD: AuditEventType.GRAPH_UPDATE,
            }
            event_type = event_type_map.get(stage, AuditEventType.SYSTEM_UPDATE)
            severity = AuditSeverity.INFO if status == ProcessingStatus.COMPLETED else AuditSeverity.WARNING if status == ProcessingStatus.PROCESSING else AuditSeverity.HIGH
            
            audit_info(
                event_type=event_type,
                actor={"actor_id": "system", "actor_type": "pipeline", "roles": []},
                action=f"pipeline.{stage.value}.{operation}",
                resource={"resource_id": self.ingest_id, "resource_type": "ingest", "attributes": details},
                result={"success": status == ProcessingStatus.COMPLETED, "message": operation},
                workspace_id=self.workspace_id,
                context={"stage": stage.value, "details": details, "duration_ms": log.duration_ms},
                trace_id=self.ingest_id,
                source="ontology_pipeline"
            )
        except Exception as e:
            logger.warning(f"审计日志记录失败: {e}")
        
        return log

    def save_build_history(self, status: str = "completed"):
        """保存构建历史记录（同时写入 Graphiti 审计日志）"""
        build_history = {
            'id': str(uuid.uuid4()),
            'ingest_id': self.ingest_id,
            'build_id': f"build-{uuid.uuid4().hex[:8]}",
            'version_id': self.version_id,
            'document_id': self.document_id,
            'entity_count': self.stage_results.get('ontology', {}).get('entity_count', 0),
            'relation_count': self.stage_results.get('ontology', {}).get('relation_count', 0),
            'event_count': self.stage_results.get('llm', {}).get('events_count', 0),
            'status': status,
            'start_time': self.logs[0].timestamp.isoformat() if self.logs else get_local_time().isoformat(),
            'end_time': get_local_time().isoformat(),
            'duration_seconds': sum(log.duration_ms or 0 for log in self.logs) / 1000
        }
        self._storage.save_build_history(build_history)
        
        # 调用统一审计日志记录构建完成事件
        try:
            if status == "completed":
                audit_info(
                    event_type=AuditEventType.ONTOLOGY_BUILD,
                    actor={"actor_id": "system", "actor_type": "pipeline", "roles": []},
                    action="ontology.build.completed",
                    resource={
                        "resource_id": build_history['build_id'],
                        "resource_type": "ontology_build",
                        "attributes": {
                            "version_id": self.version_id,
                            "document_id": self.document_id,
                            "entity_count": build_history['entity_count'],
                            "relation_count": build_history['relation_count'],
                            "event_count": build_history['event_count']
                        }
                    },
                    result={"success": True, "message": f"构建完成，版本: {self.version_id}"},
                    workspace_id=self.workspace_id,
                    context={"ingest_id": self.ingest_id, "stage_results": self.stage_results},
                    trace_id=self.ingest_id,
                    source="ontology_pipeline"
                )
            else:
                audit_error(
                    event_type=AuditEventType.ONTOLOGY_BUILD,
                    actor={"actor_id": "system", "actor_type": "pipeline", "roles": []},
                    action="ontology.build.failed",
                    resource={
                        "resource_id": self.ingest_id,
                        "resource_type": "ontology_build",
                        "attributes": {"error": self.error}
                    },
                    result={"success": False, "message": f"构建失败: {self.error}"},
                    workspace_id=self.workspace_id,
                    context={"ingest_id": self.ingest_id, "error": self.error},
                    trace_id=self.ingest_id,
                    source="ontology_pipeline"
                )
        except Exception as e:
            logger.warning(f"构建历史审计日志记录失败: {e}")
        
        return build_history


class PipelineStageHandler:
    """管道阶段处理器基类"""

    def __init__(self, stage: PipelineStage):
        self.stage = stage
        self.service = None

    async def execute(self, context: PipelineContext) -> bool:
        """执行阶段处理，返回是否成功"""
        raise NotImplementedError

    def _log(self, context: PipelineContext, operation: str, details: Dict[str, Any],
             status: ProcessingStatus = ProcessingStatus.PROCESSING,
             error_message: Optional[str] = None):
        """记录日志"""
        context.add_log(
            stage=self.stage,
            operation=operation,
            details=details,
            status=status,
            error_message=error_message
        )
        logger.info(f"[{self.stage.value}] {operation}: {details}")


class CollectionStageHandler(PipelineStageHandler):
    """数据采集阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.COLLECTION)
        self.ingest_service = get_ingest_service()

    async def execute(self, context: PipelineContext) -> bool:
        """执行数据采集 - 从已有的 ingest record 获取数据"""
        try:
            self._log(context, "开始数据采集", {
                "source": context.source,
                "source_details": context.source_details,
                "ingest_id": context.ingest_id
            })

            # 从已有的 ingest record 获取数据，而不是重新采集
            ingest_status = self.ingest_service.get_ingest_status(context.ingest_id)
            
            if not ingest_status:
                raise ValueError(f"无法找到 ingest record: {context.ingest_id}")

            result = {
                "record_count": ingest_status.get("record_count", 1),
                "original_content": ingest_status.get("original_content", ""),
                "source": ingest_status.get("source", "manual"),
                "source_details": ingest_status.get("source_details", {})
            }

            context.stage_results["collection"] = result
            context.original_content = result.get("original_content", "")

            self._log(context, "数据采集完成", {
                "record_count": result.get("record_count", 0),
                "original_length": len(context.original_content) if context.original_content else 0,
                "input": {
                    "source": context.source, 
                    "source_details": context.source_details,
                    "ingest_id": context.ingest_id
                },
                "output": {
                    "original_content": context.original_content[:500] if context.original_content else "",
                    "record_count": result.get("record_count", 1)
                }
            }, ProcessingStatus.COMPLETED)

            return True

        except Exception as e:
            logger.error(f"数据采集失败: {e}")
            self._log(context, "数据采集失败", {"error": str(e)},
                     ProcessingStatus.FAILED, str(e))
            context.error = str(e)
            return False

    async def _ingest_news(self, context: PipelineContext) -> Dict[str, Any]:
        """新闻摄入"""
        url = context.source_details.get("url", "")
        result = await self.ingest_service.ingest_news(
            url=url,
            scenario_id=context.scenario_id
        )
        return {
            "record_count": 1,
            "original_content": f"News from {url}",
            "ingest_id": result.get("ingest_id")
        }

    async def _ingest_json(self, context: PipelineContext) -> Dict[str, Any]:
        """JSON摄入"""
        json_data = context.source_details.get("data", {})
        result = await self.ingest_service.ingest_json(
            json_data=json_data,
            scenario_id=context.scenario_id
        )
        return {
            "record_count": 1,
            "original_content": str(json_data)[:500],
            "ingest_id": result.get("ingest_id")
        }

    async def _ingest_nl(self, context: PipelineContext) -> Dict[str, Any]:
        """自然语言摄入"""
        text = context.source_details.get("text", "")
        result = await self.ingest_service.ingest_text(
            text=text,
            scenario_id=context.scenario_id
        )
        return {
            "record_count": 1,
            "original_content": text,
            "ingest_id": result.get("ingest_id")
        }

    async def _ingest_random(self, context: PipelineContext) -> Dict[str, Any]:
        """随机事件摄入"""
        parties = context.source_details.get("parties", ["红方", "蓝方"])
        result = await self.ingest_service.ingest_random(
            parties=parties,
            scenario_id=context.scenario_id
        )
        return {
            "record_count": result.get("record_count", 1),
            "original_content": f"Random event with parties: {parties}",
            "ingest_id": result.get("ingest_id")
        }

    async def _ingest_qa(self, context: PipelineContext) -> Dict[str, Any]:
        """QA查询摄入"""
        query = context.source_details.get("query", "")
        return {
            "record_count": 1,
            "original_content": f"QA Query: {query}",
            "ingest_id": None
        }

    async def _ingest_manual(self, context: PipelineContext) -> Dict[str, Any]:
        """手动录入"""
        content = context.source_details.get("content", "")
        result = await self.ingest_service.ingest_from_manual(
            form_data=content,
            scenario_id=context.scenario_id
        )
        return {
            "record_count": 1,
            "original_content": content,
            "ingest_id": result
        }


class CleaningStageHandler(PipelineStageHandler):
    """数据清洗阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.CLEANING)
        self.transform_service = TransformService()

    async def execute(self, context: PipelineContext) -> bool:
        """执行数据清洗"""
        try:
            self._log(context, "开始数据清洗", {})

            original = context.original_content or ""
            cleaned = original

            # 1. 去除特殊字符
            cleaned = self._clean_special_chars(cleaned)

            # 2. 标准化空白字符
            cleaned = self._normalize_whitespace(cleaned)

            # 3. 去重检测
            duplicates = self._detect_duplicates(cleaned, context)

            # 4. 缺失值检测
            missing_info = self._check_missing_values(cleaned, context)

            result = {
                "original_length": len(original),
                "cleaned_length": len(cleaned),
                "duplicates_found": duplicates,
                "missing_values": missing_info,
                "input": {"original_content": original[:200] if original else ""},
                "output": {"cleaned_content": cleaned[:200] if cleaned else ""}
            }

            context.stage_results["cleaning"] = result
            context.original_content = cleaned

            self._log(context, "数据清洗完成", result, ProcessingStatus.COMPLETED)
            return True

        except Exception as e:
            logger.error(f"数据清洗失败: {e}")
            self._log(context, "数据清洗失败", {"error": str(e)},
                     ProcessingStatus.FAILED, str(e))
            context.error = str(e)
            return False

    def _clean_special_chars(self, text: str) -> str:
        """去除特殊字符"""
        import re
        # 保留中文、英文、数字、常用标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s,.:;!?()（）《》【】""'']', '', text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """标准化空白字符"""
        import re
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _detect_duplicates(self, text: str, context: PipelineContext) -> Dict[str, Any]:
        """检测重复内容"""
        # 简单的重复检测逻辑
        words = text.split()
        unique_words = set(words)
        duplicate_ratio = 1 - (len(unique_words) / len(words)) if words else 0

        return {
            "total_words": len(words),
            "unique_words": len(unique_words),
            "duplicate_ratio": duplicate_ratio,
            "has_duplicates": duplicate_ratio > 0.3
        }

    def _check_missing_values(self, text: str, context: PipelineContext) -> Dict[str, Any]:
        """检测缺失值"""
        missing = []

        # 检查基本字段是否存在
        if not text or len(text) < 10:
            missing.append("内容过短")

        # 检查是否包含关键信息
        required_patterns = ["红方", "蓝方", "位置", "时间"]
        for pattern in required_patterns:
            if pattern not in text:
                missing.append(f"缺少关键信息: {pattern}")

        return {
            "missing_fields": missing,
            "has_missing": len(missing) > 0
        }


class LLMExtractionStageHandler(PipelineStageHandler):
    """LLM归纳阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.LLM_EXTRACTION)

    async def execute(self, context: PipelineContext) -> bool:
        """执行LLM归纳"""
        try:
            self._log(context, "开始LLM归纳", {})

            text = context.original_content or ""

            # 调用LLM提取实体、关系、事件
            entities, relations, events = await self._extract_with_llm(text, context)

            result = {
                "entities_count": len(entities),
                "relations_count": len(relations),
                "events_count": len(events),
                "entities": entities,
                "relations": relations,
                "events": events
            }

            context.stage_results["llm"] = result

            self._log(context, "LLM归纳完成", {
                "entities": len(entities),
                "relations": len(relations),
                "events": len(events),
                "input": {"cleaned_content": text[:200] if text else ""},
                "output": {"entities": entities, "relations": relations, "events": events}
            }, ProcessingStatus.COMPLETED)

            return True

        except Exception as e:
            logger.error(f"LLM归纳失败: {e}")
            self._log(context, "LLM归纳失败", {"error": str(e)},
                     ProcessingStatus.FAILED, str(e))
            context.error = str(e)
            return False

    async def _extract_with_llm(self, text: str, context: PipelineContext) -> Tuple[List, List, List]:
        """使用LLM提取信息"""
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            import os

            entities = []
            relations = []
            events = []

            api_key = os.getenv('OPENAI_API_KEY', '')
            api_base = os.getenv('OPENAI_API_BASE', 'https://open.bigmodel.cn/api/paas/v4')
            model = os.getenv('OPENAI_MODEL', 'glm-4')

            if not api_key:
                logger.warning("未配置 OPENAI_API_KEY，使用基于规则的简单提取")
                return self._extract_with_rule(text)

            config = LLMConfig(
                model=model,
                api_key=api_key,
                base_url=api_base,
                temperature=0.7
            )
            llm_client = ZhipuAIClient(config=config)

            prompt = f"""从以下文本中提取实体、关系和事件，并以JSON格式返回。

文本内容：
{text}

请提取：
1. 实体（entities）：包括军事单位、位置、装备等，每个实体包含 entity_id, entity_type, name
2. 关系（relations）：实体之间的关系，包含 relation_id, relation_type, source_entity, target_entity
3. 事件（events）：发生的事情，包含 event_id, event_type, location, description

请以以下JSON格式返回（只需返回JSON，不要其他内容）：
{{
    "entities": [
        {{"entity_id": "实体ID", "entity_type": "类型", "name": "名称"}}
    ],
    "relations": [
        {{"relation_id": "关系ID", "relation_type": "关系类型", "source_entity": "源实体ID", "target_entity": "目标实体ID"}}
    ],
    "events": [
        {{"event_id": "事件ID", "event_type": "事件类型", "location": "地点", "description": "描述"}}
    ]
}}
"""

            import asyncio
            from graphiti_core.prompts.models import Message

            messages = [Message(role="user", content=prompt)]
            result, _, _ = await asyncio.wait_for(
                llm_client._generate_response(messages),
                timeout=30.0
            )

            if result and 'entities' in result:
                entities = result.get('entities', [])
            if result and 'relations' in result:
                relations = result.get('relations', [])
            if result and 'events' in result:
                events = result.get('events', [])

            logger.info(f"LLM提取完成: {len(entities)}个实体, {len(relations)}个关系, {len(events)}个事件")
            return entities, relations, events

        except Exception as e:
            logger.error(f"LLM提取失败: {e}，使用基于规则的提取")
            return self._extract_with_rule(text)

    def _extract_with_rule(self, text: str) -> Tuple[List, List, List]:
        """使用基于规则的提取作为回退"""
        entities = []
        relations = []
        events = []

        import re

        unit_pattern = r'(红方|蓝方)[^，。,\s]+'
        units = re.findall(unit_pattern, text)
        for i, unit in enumerate(set(units)):
            entities.append({
                "entity_id": f"unit-{i}",
                "entity_type": "Unit",
                "name": unit,
                "side": "red" if "红方" in unit else "blue"
            })

        location_pattern = r'([A-Z]区[^，。,\s]+|B区高地|C区城镇)'
        locations = re.findall(location_pattern, text)
        for i, loc in enumerate(set(locations)):
            entities.append({
                "entity_id": f"location-{i}",
                "entity_type": "Location",
                "name": loc
            })

        event_keywords = ["交火", "攻击", "撤退", "增援", "巡逻"]
        for keyword in event_keywords:
            if keyword in text:
                events.append({
                    "event_id": f"event-{len(events)}",
                    "event_type": keyword,
                    "location": "未知",
                    "description": f"发生{keyword}事件"
                })

        if len(entities) >= 2:
            relations.append({
                "relation_id": "rel-1",
                "relation_type": "engaged_with",
                "source_entity": entities[0]["entity_id"] if entities else None,
                "target_entity": entities[1]["entity_id"] if len(entities) > 1 else None,
                "description": "交战关系"
            })

        return entities, relations, events


from typing import Tuple


class OntologyBuildStageHandler(PipelineStageHandler):
    """本体构建阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.ONTOLOGY_BUILD)
        self.builder_service = get_builder_service()

    async def execute(self, context: PipelineContext) -> bool:
        """执行本体构建"""
        try:
            self._log(context, "开始本体构建", {})

            # 获取LLM阶段的结果
            llm_result = context.stage_results.get("llm", {})
            entities = llm_result.get("entities", [])
            relations = llm_result.get("relations", [])
            events = llm_result.get("events", [])

            # 构建OntologyDocument
            document = self._build_ontology_document(context, entities, relations, events)

            # 保存document_id到上下文
            context.document_id = document.doc_id
            context.stage_results["ontology"] = {
                "document_id": document.doc_id,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "event_count": len(events)
            }

            self._log(context, "本体构建完成", {
                "document_id": document.doc_id,
                "entity_count": len(entities),
                "relation_count": len(relations),
                "input": {"entities": entities, "relations": relations, "events": events},
                "output": {"document": document.to_dict() if hasattr(document, 'to_dict') else {"doc_id": document.doc_id}}
            }, ProcessingStatus.COMPLETED)

            return True

        except Exception as e:
            logger.error(f"本体构建失败: {e}")
            self._log(context, "本体构建失败", {"error": str(e)},
                     ProcessingStatus.FAILED, str(e))
            context.error = str(e)
            return False

    def _build_ontology_document(
        self,
        context: PipelineContext,
        entities: List[Dict],
        relations: List[Dict],
        events: List[Dict]
    ) -> OntologyDocument:
        """构建OntologyDocument"""
        from ..schema.document import OntologyEntity, OntologyRelation, OntologyEvent, DataSource

        doc_entities = [
            OntologyEntity(
                entity_id=e["entity_id"],
                entity_type=e["entity_type"],
                name=e["name"],
                name_en=e.get("name_en", ""),
                basic_properties=e
            )
            for e in entities
        ]

        doc_relations = [
            OntologyRelation(
                relation_id=r["relation_id"],
                relation_type=r["relation_type"],
                source_entity=r["source_entity"],
                target_entity=r["target_entity"],
                temporal={}
            )
            for r in relations
        ]

        doc_events = [
            OntologyEvent(
                event_id=ev["event_id"],
                event_type=ev["event_type"],
                timestamp=get_local_time().isoformat(),
                location=ev.get("location", ""),
                participants=[],
                outcome={}
            )
            for ev in events
        ]

        document = OntologyDocument(
            doc_type="event",
            source=DataSource(
                type=context.source
            ),
            entities=doc_entities,
            relations=doc_relations,
            events=doc_events
        )

        return document


class VersionManageStageHandler(PipelineStageHandler):
    """版本管理阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.VERSION_MANAGE)
        self.version_service = get_version_service()

    async def execute(self, context: PipelineContext) -> bool:
        """执行版本管理"""
        try:
            self._log(context, "开始版本管理", {})

            # 获取本体文档信息
            ontology_result = context.stage_results.get("ontology", {})
            document_id = ontology_result.get("document_id", context.document_id)

            # 创建新版本
            version = await self._create_version(context, document_id)

            context.version_id = version.get("version_id")
            context.stage_results["version"] = version

            self._log(context, "版本管理完成", {
                "version_id": version.get("version_id"),
                "version_number": version.get("version_number"),
                "input": {"document_id": document_id, "scenario_id": context.scenario_id},
                "output": {"version": version}
            }, ProcessingStatus.COMPLETED)

            return True

        except Exception as e:
            logger.error(f"版本管理失败: {e}")
            self._log(context, "版本管理失败", {"error": str(e)},
                     ProcessingStatus.FAILED, str(e))
            context.error = str(e)
            return False

    async def _create_version(self, context: PipelineContext, document_id: str) -> Dict[str, Any]:
        """创建新版本（全局唯一，持久化到数据库）"""
        # 使用时间戳生成全局唯一版本号
        timestamp = int(time.time())
        version_number = f"1.0.{timestamp}"
        version_id = f"v{version_number}"
        
        # 调用版本服务进行持久化（全局版本，不绑定场景）
        saved_version = self.version_service.create_version(
            ontology_id=None,  # 全局版本，不绑定场景
            version_number=version_number,
            parent_version_id=None,
            change_summary=f"Auto-generated from ingest {context.ingest_id}"
        )
        
        # 如果有场景ID，进行绑定
        if context.scenario_id:
            self.version_service.bind_version_to_scenario(
                version_id=saved_version.get("version_id", version_id),
                scenario_id=context.scenario_id,
                is_current=True
            )
        
        version_info = {
            "version_id": saved_version.get("version_id", version_id),
            "version_number": saved_version.get("version_number", version_number),
            "ontology_id": None,  # 全局版本
            "document_id": document_id,
            "ingest_id": context.ingest_id,
            "status": saved_version.get("status", "released"),
            "is_current": True,
            "created_at": saved_version.get("created_at", get_local_time().isoformat()),
            "entity_count": context.stage_results.get("ontology", {}).get("entity_count", 0),
            "relation_count": context.stage_results.get("ontology", {}).get("relation_count", 0),
            "scenario_id": context.scenario_id  # 记录绑定的场景
        }
        
        return version_info


class GraphBuildStageHandler(PipelineStageHandler):
    """图谱生成阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.GRAPH_BUILD)
        self.builder_service = get_builder_service()

    async def execute(self, context: PipelineContext) -> bool:
        """执行图谱生成"""
        try:
            self._log(context, "开始图谱生成", {})

            # 获取本体文档
            ontology_result = context.stage_results.get("ontology", {})
            document_id = ontology_result.get("document_id", context.document_id)

            # 构建图谱
            graph_result = await self._build_graph(context, document_id)

            context.stage_results["graph"] = graph_result

            self._log(context, "图谱生成完成", {
                "nodes_created": graph_result.get("nodes_created", 0),
                "edges_created": graph_result.get("edges_created", 0),
                "input": {"document_id": document_id, "version_id": context.version_id},
                "output": {"graph_result": graph_result}
            }, ProcessingStatus.COMPLETED)

            return True

        except Exception as e:
            logger.error(f"图谱生成失败: {e}")
            self._log(context, "图谱生成失败", {"error": str(e)},
                     ProcessingStatus.FAILED, str(e))
            context.error = str(e)
            return False

    async def _build_graph(self, context: PipelineContext, document_id: str) -> Dict[str, Any]:
        """构建图谱"""
        try:
            from odap.infra.graph.graph_service import GraphManager
            from datetime import datetime, timezone

            llm_result = context.stage_results.get("llm", {})
            entities = llm_result.get("entities", [])
            relations = llm_result.get("relations", [])

            graph_manager = GraphManager()

            nodes_created = 0
            edges_created = 0

            for entity in entities:
                try:
                    node_id = entity.get("entity_id", f"entity-{uuid.uuid4().hex[:8]}")
                    entity_type = entity.get("entity_type", "Unknown")
                    properties = entity.get("basic_properties", entity)

                    success = graph_manager.add_entity(
                        entity_id=node_id,
                        entity_type=entity_type,
                        properties=properties
                    )
                    if success:
                        nodes_created += 1
                except Exception as e:
                    logger.warning(f"创建节点失败 {entity.get('entity_id')}: {e}")

            for relation in relations:
                try:
                    source_id = relation.get("source_entity")
                    target_id = relation.get("target_entity")
                    rel_type = relation.get("relation_type", "related_to")
                    properties = relation.get("properties", {})

                    if source_id and target_id:
                        success = graph_manager.add_relationship(
                            source_id=source_id,
                            target_id=target_id,
                            relationship=rel_type,
                            properties=properties
                        )
                        if success:
                            edges_created += 1
                except Exception as e:
                    logger.warning(f"创建边失败 {relation.get('relation_id')}: {e}")

            graph_id = f"graph-{uuid.uuid4().hex[:8]}"

            return {
                "nodes_created": nodes_created,
                "edges_created": edges_created,
                "graph_id": graph_id,
                "status": "completed",
                "mode": graph_manager._mode,
                "document_id": document_id,
                "version_id": context.version_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"图谱构建失败: {e}")
            return {
                "nodes_created": 0,
                "edges_created": 0,
                "graph_id": f"graph-error-{uuid.uuid4().hex[:8]}",
                "status": "failed",
                "error": str(e)
            }


class OntologyPipeline:
    """
    本体构建管道

    协调6个阶段的执行，记录完整处理日志
    """

    def __init__(self):
        self.handlers: Dict[PipelineStage, PipelineStageHandler] = {
            PipelineStage.COLLECTION: CollectionStageHandler(),
            PipelineStage.CLEANING: CleaningStageHandler(),
            PipelineStage.LLM_EXTRACTION: LLMExtractionStageHandler(),
            PipelineStage.ONTOLOGY_BUILD: OntologyBuildStageHandler(),
            PipelineStage.VERSION_MANAGE: VersionManageStageHandler(),
            PipelineStage.GRAPH_BUILD: GraphBuildStageHandler(),
        }
        self._execution_order = [
            PipelineStage.COLLECTION,
            PipelineStage.CLEANING,
            PipelineStage.LLM_EXTRACTION,
            PipelineStage.ONTOLOGY_BUILD,
            PipelineStage.VERSION_MANAGE,
            PipelineStage.GRAPH_BUILD,
        ]

    async def run(
        self,
        ingest_id: str,
        scenario_id: str,
        source: str = "manual",
        source_details: Dict[str, Any] = None,
        workspace_id: str = "default",
        progress_callback: Optional[Callable[[PipelineStage, float, str], Awaitable]] = None
    ) -> PipelineContext:
        """
        运行完整管道

        Args:
            ingest_id: 摄入记录ID
            scenario_id: 场景ID
            source: 数据来源
            source_details: 数据详情
            workspace_id: 工作空间ID
            progress_callback: 进度回调函数

        Returns:
            PipelineContext: 管道执行上下文
        """
        context = PipelineContext(
            ingest_id=ingest_id,
            scenario_id=scenario_id,
            workspace_id=workspace_id,
            source=source,
            source_details=source_details or {},
            original_content=source_details.get("content", "") if source_details else ""
        )

        logger.info(f"开始执行本体构建管道: ingest_id={ingest_id}, source={source}")

        total_stages = len(self._execution_order)

        for i, stage in enumerate(self._execution_order):
            context.current_stage = stage

            # 进度回调
            if progress_callback:
                progress = (i / total_stages) * 100
                await progress_callback(stage, progress, f"执行中: {stage.value}")

            # 执行阶段
            handler = self.handlers[stage]
            success = await handler.execute(context)

            if not success:
                logger.error(f"管道执行失败 at stage: {stage.value}")
                break

        # 最终进度回调
        if progress_callback:
            await progress_callback(context.current_stage, 100.0, "完成")

        # 检查是否所有阶段都成功完成
        all_stages_completed = context.error is None and context.current_stage == self._execution_order[-1]
        context.success = all_stages_completed
        
        # 保存构建历史
        status = "completed" if context.success else "failed"
        context.save_build_history(status)

        logger.info(f"管道执行完成: ingest_id={ingest_id}, version_id={context.version_id}")

        return context

    def get_context(self, ingest_id: str) -> Optional[PipelineContext]:
        """获取管道上下文（从存储中）"""
        # TODO: 从存储中恢复上下文
        pass

    def get_stage_logs(self, ingest_id: str) -> List[ProcessLog]:
        """获取某次执行的阶段日志"""
        # TODO: 从存储中获取日志
        return []


# 全局管道实例
_pipeline_instance: Optional[OntologyPipeline] = None


def get_pipeline_service() -> OntologyPipeline:
    """获取管道服务单例"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = OntologyPipeline()
    return _pipeline_instance


async def run_ontology_pipeline(
    ingest_id: str,
    scenario_id: str,
    source: str = "manual",
    source_details: Dict[str, Any] = None,
    workspace_id: str = "default",
    progress_callback: Optional[Callable[[PipelineStage, float, str], Awaitable]] = None
) -> PipelineContext:
    """
    运行本体构建管道的便捷函数

    Args:
        ingest_id: 摄入记录ID
        scenario_id: 场景ID
        source: 数据来源
        source_details: 数据详情
        workspace_id: 工作空间ID
        progress_callback: 进度回调函数

    Returns:
        PipelineContext: 管道执行上下文
    """
    pipeline = get_pipeline_service()
    return await pipeline.run(
        ingest_id=ingest_id,
        scenario_id=scenario_id,
        source=source,
        source_details=source_details,
        workspace_id=workspace_id,
        progress_callback=progress_callback
    )
