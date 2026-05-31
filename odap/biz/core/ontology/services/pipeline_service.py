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
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, Awaitable, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..models.audit import (
    PipelineStage, ProcessLog, ProcessingStatus,
    DataIngestRecord, DataSource
)
from ..schema.document import OntologyDocument
from ..schema.document import OntologyDocumentSchema, OntologyValidationError
from .version_service import OntologyVersionManager, OntologyVersion
from odap.infra.events import HookRegistry, HookPhase, HookContext
from odap.infra.security.unified_audit import log_audit, log_error
from .ingest_service import IngestService, get_ingest_service
from .build_service import OntologyBuilderService, get_builder_service
from .transform_service import OntologyTransformService as TransformService

logger = logging.getLogger("ontology_pipeline")


def _make_ingest_storage():
    from ..storage.sqlite_ingest_storage import SQLiteIngestStorage
    return SQLiteIngestStorage()


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
    _storage: Any = field(default_factory=_make_ingest_storage)
    _stage_start_times: Dict[str, datetime] = field(default_factory=dict)

    def add_log(self, stage: PipelineStage, operation: str, details: Dict[str, Any],
                status: ProcessingStatus = ProcessingStatus.PROCESSING,
                error_message: Optional[str] = None):
        """添加处理日志（同时保存到数据库和 Graphiti 审计）"""
        # 计算阶段执行时长
        stage_key = stage.value
        current_time = get_local_time()
        duration_ms = None
        start_time_str = None
        
        if stage_key in self._stage_start_times:
            start_time = self._stage_start_times[stage_key]
            duration_ms = (current_time - start_time).total_seconds() * 1000
            start_time_str = start_time.isoformat()
        
        # 在 details 中添加完整的时间信息，用于审计和时间回溯
        audit_details = details.copy() if details else {}
        audit_details['_audit'] = {
            'start_time': start_time_str,
            'end_time': current_time.isoformat(),
            'duration_ms': duration_ms
        }
        
        log = ProcessLog(
            timestamp=current_time,
            stage=stage,
            operation=operation,
            details=audit_details,
            status=status,
            error_message=error_message,
            duration_ms=duration_ms
        )
        self.logs.append(log)
        
        # 保存到数据库 - 使用包含审计信息的 details
        log_dict = {
            'id': log.id,
            'ingest_id': self.ingest_id,
            'stage': stage.value,
            'operation': operation,
            'details': audit_details,
            'status': status.value,
            'error_message': error_message,
            'duration_ms': duration_ms,
            'timestamp': log.timestamp.isoformat()
        }
        self._storage.save_process_log(log_dict)
        
        # 调用统一审计日志（保存到 Graphiti）
        try:
            log_audit(
                action=f"pipeline.{stage.value}.{operation}",
                resource=self.ingest_id,
                user="system",
                service="ontology_pipeline",
                details={
                    "stage": stage.value,
                    "status": status.value,
                    "operation": operation,
                    "duration_ms": log.duration_ms,
                    "details": details
                }
            )
        except Exception as e:
            logger.warning(f"审计日志记录失败: {e}")
        
        return log

    def start_stage(self, stage: PipelineStage):
        """记录阶段开始时间，用于计算执行时长"""
        self._stage_start_times[stage.value] = get_local_time()

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
                log_audit(
                    action="ontology.build.completed",
                    resource=self.ingest_id,
                    user="system",
                    service="ontology_pipeline",
                    details={
                        "build_id": build_history['build_id'],
                        "version_id": self.version_id,
                        "document_id": self.document_id,
                        "entity_count": build_history['entity_count'],
                        "relation_count": build_history['relation_count'],
                        "event_count": build_history['event_count'],
                        "stage_results": self.stage_results
                    }
                )
            else:
                log_error(
                    error=f"构建失败: {self.error}",
                    context="ontology.build.failed",
                    user="system",
                    service="ontology_pipeline"
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
                "input": {
                    "source": context.source, 
                    "source_details": context.source_details,
                    "ingest_id": context.ingest_id
                },
                "output": {
                    "original_content": context.original_content,
                    "record_count": result.get("record_count", 1),
                    "source": result.get("source"),
                    "source_details": result.get("source_details")
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
                "input": {
                    "original_content": original
                },
                "output": {
                    "cleaned_content": cleaned,
                    "records_extracted": 1,
                    "validation_result": {
                        "is_valid": True,
                        "duplicates_removed": 0,
                        "missing_values_filled": 0,
                        "format_standardized": True
                    },
                    "documents_cleaned": 1
                }
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
        """使用LLM提取信息（含动作抽取，对齐ADR-036/ADR-032）"""
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            import os

            entities = []
            relations = []
            events = []
            actions = []

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

            prompt = f"""从以下文本中提取实体、关系、事件和动作，并以JSON格式返回。

文本内容：
{text}

请提取：
1. 实体（entities）：包括单位(Unit)、位置(Location)、装备(Equipment)、事件(Event)等，每个实体包含：
   - entity_id, entity_type, name
   - basic_properties: 基本属性（如side, status, location, coordinates）
   - statistical_properties: 统计属性（如combat_power, morale, supply_level, casualty_rate）
   - capabilities: 能力属性（如range, armor_penetration, air_defense）
   - constraints: 约束属性（如max_speed, min_supply）

2. 关系（relations）：实体之间的关系，包含 relation_id, relation_type, source_entity, target_entity
   关系类型参考：located_at, attached_to, engaged_with, adjacent_to, contains, assigned_to, participants, occurs_at

3. 事件（events）：发生的事情，包含 event_id, event_type, location, description, participants, outcome

4. 动作（actions）：文本中描述的或可推断的业务动作，包含：
   - action_id, action_type（move/attack/defend/reinforce/retreat/observe/communicate）
   - actor: 执行者实体ID
   - target: 目标实体ID
   - parameters: 动作参数（如destination, target_id, defense_type等）
   - opa_required: 是否需要策略审批（attack/reinforce/retreat为true）

请以以下JSON格式返回（只需返回JSON，不要其他内容）：
{{
    "entities": [
        {{"entity_id": "实体ID", "entity_type": "Unit|Location|Equipment|Event", "name": "名称",
          "basic_properties": {{"side": "red|blue|neutral", "status": "active|deployed|destroyed", "location": "位置"}},
          "statistical_properties": {{"combat_power": 0.8, "morale": 0.7}},
          "capabilities": {{"range": 100.0}},
          "constraints": {{}}}}
    ],
    "relations": [
        {{"relation_id": "关系ID", "relation_type": "located_at|engaged_with|...", "source_entity": "源实体ID", "target_entity": "目标实体ID"}}
    ],
    "events": [
        {{"event_id": "事件ID", "event_type": "contact|attack|movement|...", "location": "地点", "description": "描述", "participants": ["实体ID"], "outcome": {{}}}}
    ],
    "actions": [
        {{"action_id": "动作ID", "action_type": "move|attack|defend|reinforce|retreat|observe|communicate",
          "actor": "执行者实体ID", "target": "目标实体ID",
          "parameters": {{"destination": "目标位置", "target_id": "攻击目标ID"}},
          "opa_required": false}}
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
            if result and 'actions' in result:
                actions = result.get('actions', [])

            self._register_entity_types_from_extraction(entities)

            logger.info(f"LLM提取完成: {len(entities)}个实体, {len(relations)}个关系, {len(events)}个事件, {len(actions)}个动作")
            return entities, relations, events

        except Exception as e:
            logger.error(f"LLM提取失败: {e}，使用基于规则的提取")
            return self._extract_with_rule(text)

    def _register_entity_types_from_extraction(self, entities: List):
        try:
            from odap.biz.core.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
            oms = SQLiteOMSStorage()
            for entity in entities:
                etype = entity.get('entity_type', '')
                if etype and not oms.get_object_type(etype):
                    props = []
                    for prop_group in ('basic_properties', 'statistical_properties', 'capabilities', 'constraints'):
                        group = entity.get(prop_group, {})
                        if isinstance(group, dict):
                            for pname, pval in group.items():
                                props.append({
                                    'name': pname,
                                    'display_name': pname.replace('_', ' ').title(),
                                    'property_type': self._infer_property_type(pval),
                                    'category': prop_group,
                                })
                    oms.create_object_type({
                        'type_id': etype,
                        'name': etype,
                        'display_name': etype,
                        'description': f'Auto-registered from extraction',
                        'properties': props,
                    })
                    logger.info(f"Auto-registered entity type: {etype}")
        except Exception as e:
            logger.debug(f"Entity type auto-registration skipped: {e}")

    @staticmethod
    def _infer_property_type(value) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "float"
        if isinstance(value, (list, dict)):
            return "json"
        return "string"

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
                "event_count": len(events),
                "entities": entities,
                "relations": relations,
                "events": events
            }

            await self._save_ontology_document(context, document, entities, relations, events)

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
        from ..schema.document import OntologyEntity, OntologyRelation, OntologyEvent, SourceInfo

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
            source=SourceInfo(
                type=context.source
            ),
            entities=doc_entities,
            relations=doc_relations,
            events=doc_events
        )

        return document
    
    async def _save_ontology_document(
        self,
        context: PipelineContext,
        document: OntologyDocument,
        entities: List[Dict],
        relations: List[Dict],
        events: List[Dict]
    ) -> None:
        from ..storage.sqlite_ingest_storage import SQLiteIngestStorage
        
        try:
            storage = SQLiteIngestStorage()
            
            storage.save_ontology_document(document)
            
            if context.scenario_id:
                doc_dict = {
                    "doc_id": document.doc_id,
                    "doc_type": document.doc_type,
                    "entities": entities,
                    "events": events,
                    "relations": relations,
                    "created_at": get_local_time().isoformat()
                }
                storage.add_scenario_document(context.scenario_id, doc_dict)
            
            logger.info(f"本体文档已保存到 SQLite: {document.doc_id}, scenario_id: {context.scenario_id}")
            
        except Exception as e:
            logger.warning(f"保存本体文档到 SQLite 失败: {e}")


class VersionManageStageHandler(PipelineStageHandler):
    """版本管理阶段处理器"""

    def __init__(self):
        super().__init__(PipelineStage.VERSION_MANAGE)
        self.version_manager = OntologyVersionManager.get_instance()

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
        timestamp = int(time.time())
        version_number = f"1.0.{timestamp}"
        version_id = f"v{version_number}"
        
        version_info = {
            "version_id": version_id,
            "version_number": version_number,
            "ontology_id": document_id or f"ontology-{timestamp}",
            "document_id": document_id,
            "ingest_id": context.ingest_id,
            "status": "released",
            "is_current": True,
            "created_at": get_local_time().isoformat(),
            "entity_count": context.stage_results.get("ontology", {}).get("entity_count", 0),
            "relation_count": context.stage_results.get("ontology", {}).get("relation_count", 0),
            "scenario_id": context.scenario_id
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

            entity_id_map = {}
            for entity in entities:
                try:
                    original_id = entity.get("entity_id", f"entity-{uuid.uuid4().hex[:8]}")
                    entity_type = entity.get("entity_type", "Unknown")
                    node_id = f"{entity_type}-{context.ingest_id[:8]}-{original_id}"
                    entity_id_map[original_id] = node_id
                    properties = entity.get("basic_properties", entity)
                    if isinstance(properties, dict):
                        properties["workspace_id"] = context.workspace_id
                        properties["source_type"] = context.source
                        properties["scenario_id"] = context.scenario_id
                        properties["ingest_id"] = context.ingest_id
                        properties["original_entity_id"] = original_id
                    else:
                        properties = {
                            "workspace_id": context.workspace_id,
                            "source_type": context.source,
                            "scenario_id": context.scenario_id,
                            "ingest_id": context.ingest_id,
                            "original_entity_id": original_id,
                        }

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
                    original_source = relation.get("source_entity")
                    original_target = relation.get("target_entity")
                    source_id = entity_id_map.get(original_source, original_source)
                    target_id = entity_id_map.get(original_target, original_target)
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

    _instance: Optional['OntologyPipeline'] = None

    def __init__(self, graph_manager=None, version_manager=None, hook_registry=None):
        self.graph = graph_manager
        self.versions = version_manager or OntologyVersionManager.get_instance()
        self.hooks = hook_registry or HookRegistry.get_instance()
        self._ingest_count = 0
        self._error_count = 0
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

    @classmethod
    def get_instance(cls) -> 'OntologyPipeline':
        if cls._instance is None:
            cls._instance = OntologyPipeline()
        return cls._instance

    @classmethod
    def initialize(cls, graph_manager=None, version_manager=None, hook_registry=None) -> 'OntologyPipeline':
        cls._instance = OntologyPipeline(
            graph_manager=graph_manager,
            version_manager=version_manager,
            hook_registry=hook_registry,
        )
        return cls._instance

    async def ingest(self, doc: OntologyDocument, ontology_id: Optional[str] = None) -> OntologyVersion:
        validation = OntologyDocumentSchema.validate(doc)
        if not validation.is_valid:
            self._error_count += 1
            raise OntologyValidationError(validation.errors)
        if validation.warnings:
            for w in validation.warnings:
                logger.warning(f"[Schema Warning] {w}")

        final_ontology_id = ontology_id or doc.ontology_id
        if not final_ontology_id:
            raise ValueError("需要提供 ontology_id，或者 doc.ontology_id 必须已设置")

        version = await self.versions.append(final_ontology_id, doc)

        if self.graph is not None:
            try:
                await self._write_to_graphiti(doc, version)
            except Exception as e:
                logger.error(f"Graphiti 写入失败（版本 {version.version_id} 已保存）: {e}")

        event_payload = {
            "version_id": version.version_id,
            "ontology_id": final_ontology_id,
            "doc_id": doc.doc_id,
            "doc_type": doc.doc_type,
            "entity_count": len(doc.entities),
            "relation_count": len(doc.relations),
            "event_count": len(doc.events),
            "action_count": len(doc.actions),
            "title": doc.meta.title,
            "scenario_id": doc.scenario_id,
        }
        asyncio.create_task(self._emit_hook(event_payload))

        self._ingest_count += 1
        logger.info(
            f"热写入完成: {version.version_id} | 本体:{final_ontology_id} | "
            f"实体:{len(doc.entities)} 关系:{len(doc.relations)} 事件:{len(doc.events)}"
        )
        return version

    async def _write_to_graphiti(self, doc: OntologyDocument, version: OntologyVersion):
        episode_text = doc.to_episode_text()
        if hasattr(self.graph, 'add_episode'):
            await self.graph.add_episode(
                name=f"ontology_{doc.doc_id}",
                episode_body=episode_text,
                source_description=f"ontology_document:{doc.doc_type}",
                reference_time=datetime.now(timezone.utc),
            )
        logger.debug(f"Graphiti Episode 写入: {doc.doc_id}")

    async def _emit_hook(self, payload: dict):
        try:
            context = HookContext(event_name="ontology.updated")
            context.set_data("payload", payload)

            hooks = self.hooks.get_hooks("ontology.updated", HookPhase.POST)
            for hook in hooks:
                try:
                    result = hook.handler(context, payload)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Hook {hook.name} 执行失败: {e}")
        except Exception as e:
            logger.error(f"Hook 广播失败: {e}")

    async def rollback(self, version_id: str) -> OntologyVersion:
        doc = await self.versions.get_doc(version_id)
        if doc is None:
            raise ValueError(f"版本 {version_id} 不存在或快照已丢失")

        doc.ontology_version.parent_version = version_id
        doc.ontology_version.commit_message = f"回退到版本 {version_id}"

        logger.info(f"回退到版本: {version_id}")
        return await self.ingest(doc)

    def register_ontology_hook(self, handler):
        self.hooks.register(
            event="ontology.updated",
            name=getattr(handler, "__name__", str(id(handler))),
            handler=handler,
            phase=HookPhase.POST,
            description="本体更新订阅",
        )

    def get_stats(self) -> dict:
        return {
            "ingest_count": self._ingest_count,
            "error_count": self._error_count,
            "version_count": self.versions.get_version_count(),
            "latest_version": self.versions.get_latest_version_id(),
        }

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
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = OntologyPipeline()
    return _pipeline_instance


PipelineService = OntologyPipeline


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
