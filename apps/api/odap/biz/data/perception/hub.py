import logging
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from .schemas import (
    PerceptionEvent, PerceptionOutput, ExtractionResult,
    PerceptionSourceType, PerceptionStatus, PerceptionPriority,
)
from .observers.base_observers import (
    BaseObserver, MCPObserver, FileObserver, APIObserver,
    SensorObserver, NewsObserver, WebhookObserver,
)

logger = logging.getLogger(__name__)


class PerceptionHub:
    def __init__(self):
        self._observers: Dict[str, BaseObserver] = {}
        self._write_proxy = None
        self._query_service = None
        self._oms = None
        self._pipeline = None
        self._event_buffer: List[PerceptionEvent] = []
        self._register_default_observers()

    def _register_default_observers(self):
        for observer_cls in (MCPObserver, FileObserver, APIObserver, SensorObserver, NewsObserver, WebhookObserver):
            obs = observer_cls()
            self._observers[obs.name] = obs

    def register_observer(self, observer: BaseObserver):
        self._observers[observer.name] = observer

    def remove_observer(self, name: str):
        self._observers.pop(name, None)

    @property
    def write_proxy(self):
        """获取 GraphWriteProxy 单例（用于写操作）。"""
        if self._write_proxy is None:
            from odap.infra.query import get_graph_write_proxy
            self._write_proxy = get_graph_write_proxy()
        return self._write_proxy

    @property
    def query_service(self):
        """获取 QueryService 单例（用于读操作）。"""
        if self._query_service is None:
            from odap.infra.query import get_query_service
            self._query_service = get_query_service()
        return self._query_service

    @property
    def oms(self):
        if self._oms is None:
            # 必须走 public 门面：ontology/__init__._legacy_map 的 OMSStorage 条目是坏映射
            # （指向模块路径但取不存在的类名别名），实测抛 ImportError；且原先构造的
            # SQLiteOMSStorage 从未被导入，即使 import 成功也是 NameError。
            from odap.biz.core.ontology.public import OMSStorage
            self._oms = OMSStorage()
        return self._oms

    @property
    def type_registry(self):
        """获取 TypeRegistry 单例（统一类型定义读写入口）"""
        if not hasattr(self, '_type_registry') or self._type_registry is None:
            from odap.biz.core.ontology.public import get_type_registry
            self._type_registry = get_type_registry()
        return self._type_registry

    @property
    def pipeline(self):
        if self._pipeline is None:
            try:
                # Stage E 修复：原路径 odap.biz.core.ontology.services.pipeline_service
                # 在 flat→3+1 迁移后已不存在，真实实现位于 design.services.pipeline_service，
                # 现统一经 public 门面访问（C3 契约要求）。
                from odap.biz.core.ontology.public import OntologyPipeline
                self._pipeline = OntologyPipeline()
            except Exception as e:
                logger.warning(f"PerceptionHub: OntologyPipeline import failed: {e}")
                self._pipeline = None
        return self._pipeline

    async def observe_all(self) -> List[PerceptionEvent]:
        all_events = []
        for name, observer in self._observers.items():
            if not observer.enabled:
                continue
            try:
                events = await observer.observe()
                for event in events:
                    if not event.event_id:
                        event.event_id = f"pe_{uuid.uuid4().hex[:12]}"
                    if not event.timestamp:
                        event.timestamp = datetime.now(timezone.utc).isoformat()
                    event.status = PerceptionStatus.RECEIVED
                all_events.extend(events)
                logger.info(f"PerceptionHub: {name} observed {len(events)} events")
            except Exception as e:
                logger.warning(f"PerceptionHub: observer {name} failed: {e}")
        return all_events

    async def process_event(self, event: PerceptionEvent, ontology_id: str = None) -> PerceptionOutput:
        event.status = PerceptionStatus.PROCESSING
        try:
            extraction = await self._extract(event)
            event.status = PerceptionStatus.EXTRACTED

            self._map_to_oms(extraction, ontology_id=ontology_id)
            event.status = PerceptionStatus.MAPPED

            episode_id = await self._store_to_graphiti(event, extraction)
            event.status = PerceptionStatus.STORED

            return PerceptionOutput(
                event_id=event.event_id,
                extraction=extraction,
                graphiti_episode_id=episode_id,
                oms_registered_types=[e.get('entity_type', '') for e in extraction.entities if e.get('entity_type')],
                status=PerceptionStatus.STORED,
            )
        except Exception as e:
            logger.error(f"PerceptionHub: process_event failed for {event.event_id}: {e}")
            event.status = PerceptionStatus.FAILED
            return PerceptionOutput(
                event_id=event.event_id,
                extraction=ExtractionResult(),
                status=PerceptionStatus.FAILED,
                error=str(e),
            )

    async def process_batch(self, events: List[PerceptionEvent]) -> List[PerceptionOutput]:
        results = []
        for event in events:
            result = await self.process_event(event)
            results.append(result)
        return results

    async def observe_and_process(self) -> List[PerceptionOutput]:
        events = await self.observe_all()
        if not events:
            return []
        return await self.process_batch(events)

    def ingest_manual(self, content: str, source_type: PerceptionSourceType = PerceptionSourceType.MANUAL,
                      metadata: Optional[Dict[str, Any]] = None) -> PerceptionEvent:
        event = PerceptionEvent(
            event_id=f"pe_{uuid.uuid4().hex[:12]}",
            source_type=source_type,
            source_name="manual",
            raw_content=content,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._event_buffer.append(event)
        return event

    def ingest_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        webhook_obs = self._observers.get('webhook_observer')
        if isinstance(webhook_obs, WebhookObserver):
            return webhook_obs.receive_webhook(payload, headers)
        return ""

    def ingest_sensor(self, sensor_id: str, value: Any, metadata: Optional[Dict[str, Any]] = None):
        sensor_obs = self._observers.get('sensor_observer')
        if isinstance(sensor_obs, SensorObserver):
            sensor_obs.ingest_reading(sensor_id, value, metadata)

    async def _extract(self, event: PerceptionEvent) -> ExtractionResult:
        text = event.raw_content
        if not text:
            return ExtractionResult()

        # 抽取失败必须向上抛（规则 14）：process_event 已将其记为 FAILED + error 字段并
        # 打 error 日志。原先此处 except 后降级到 NewsIngester.extract_ontology —— 该方法
        # 不存在（NewsIngester 只有 ingest，语义是"联网检索"而非"抽取给定文本"），异常被吞后
        # 落到 return ExtractionResult(confidence=0.0)，把"抽取链路坏了"伪装成"这段文本没有
        # 可抽取内容"，下游 _map_to_oms / _store_to_graphiti 拿到空结果照常走完并报成功。
        # Stage E 修复：原路径 odap.biz.core.ontology.services.pipeline_service 已死，
        # 真实实现在 design.services.pipeline_service，经 public 门面统一暴露。
        from odap.biz.core.ontology.public import LLMExtractionStageHandler, PipelineContext
        handler = LLMExtractionStageHandler()
        # PipelineContext 的 ingest_id / scenario_id 是必填位置参数，原先的 PipelineContext()
        # 每次调用都抛 TypeError —— 正是被上面那个 except Exception 吞掉、导致整条感知抽取
        # 链路"看起来在跑、实际恒返回空"的根因。字段全部取自 PerceptionEvent 自身，不做反推。
        context = PipelineContext(
            ingest_id=event.event_id,
            scenario_id=event.scenario_id or "",
            workspace_id=event.workspace_id or "default",
            source=event.source_type.value,
            source_details={"source_name": event.source_name},
            original_content=text,
        )
        # 注：_extract_with_llm 当前并不读取 context（仅 execute() 用它写流水线审计日志）。
        # 若将来它开始使用 scenario_id/workspace_id，上面的接线即成为真实语义，需同步复核。
        entities, relations, events_list = await handler._extract_with_llm(text, context)
        return ExtractionResult(
            entities=entities,
            relations=relations,
            events=events_list,
            actions=[],
            confidence=0.8,
        )

    def _map_to_oms(self, extraction: ExtractionResult, ontology_id: str = None) -> List[str]:
        """将抽取结果中的实体类型注册到 TypeRegistry

        如果提供了 ontology_id，通过 TypeRegistry → OntologyService 注册（推荐）。
        否则降级为直接写入 OMS（向后兼容）。
        """
        registered = []
        for entity in extraction.entities:
            etype = entity.get('entity_type', '')
            if not etype:
                continue
            # 先检查 OMS 缓存是否已存在
            if self.oms.get_object_type(etype):
                continue
            try:
                props = []
                for prop_group in ('basic_properties', 'statistical_properties', 'capabilities', 'constraints'):
                    group = entity.get(prop_group, {})
                    if isinstance(group, dict):
                        for pname, pval in group.items():
                            props.append({
                                'name': pname,
                                'display_name': pname.replace('_', ' ').title(),
                                'property_type': 'string',
                                'category': prop_group,
                            })

                if ontology_id:
                    # 通过 TypeRegistry 注册（推荐路径）
                    result = self.type_registry.create_object_type(ontology_id, {
                        'name': etype,
                        'display_name': etype,
                        'description': f'Auto-registered by PerceptionHub',
                        'properties': props,
                    })
                    if result.get("status") != "error":
                        registered.append(etype)
                    else:
                        # 规则 14「兜底需可观测」：原先是 debug 级，生产默认 INFO 下不可见，
                        # 整批类型注册失败也会被 process_event 报成 STORED。
                        logger.warning(
                            "PerceptionHub: TypeRegistry 自动注册 %s 失败: %s",
                            etype, result.get('message'),
                        )
                else:
                    # 降级：直接写入 OMS（向后兼容）
                    self.oms.create_object_type({
                        'type_id': etype,
                        'name': etype,
                        'display_name': etype,
                        'description': f'Auto-registered by PerceptionHub',
                        'properties': props,
                    })
                    registered.append(etype)
            except Exception as e:
                logger.warning("PerceptionHub: OMS 自动注册 %s 失败: %s", etype, e)
        return registered

    async def _store_to_graphiti(self, event: PerceptionEvent, extraction: ExtractionResult) -> Optional[str]:
        try:
            episode_text = event.raw_content[:2000]
            if extraction.entities:
                entity_summary = ", ".join(
                    f"{e.get('entity_type', '?')}:{e.get('name', e.get('entity_id', '?'))}"
                    for e in extraction.entities[:10]
                )
                episode_text += f"\n[Extracted: {entity_summary}]"

            result = await self.write_proxy.add_episode(
                name=f"perception_{event.event_id}",
                content=episode_text,
                source_description="PerceptionHub auto-ingest",
                reference_time=event.timestamp or datetime.now(timezone.utc).isoformat(),
            )
            if result.get("status") == "error":
                logger.warning(f"PerceptionHub add_episode failed: {result.get('message', '')}")
                return None
            return f"ep_{event.event_id}"
        except Exception as e:
            logger.warning(f"PerceptionHub store to Graphiti failed: {e}")
            return None

    def get_status(self) -> Dict[str, Any]:
        return {
            'observers': {
                name: {
                    'type': obs.source_type.value,
                    'enabled': obs.enabled,
                }
                for name, obs in self._observers.items()
            },
            'buffer_size': len(self._event_buffer),
        }


_hub_instance = None


def get_perception_hub() -> PerceptionHub:
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = PerceptionHub()
    return _hub_instance
