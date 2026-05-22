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
        self._graph_manager = None
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
    def graph(self):
        if self._graph_manager is None:
            from odap.infra.graph.graph_service import GraphManager
            self._graph_manager = GraphManager()
        return self._graph_manager

    @property
    def oms(self):
        if self._oms is None:
            from odap.biz.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
            self._oms = SQLiteOMSStorage()
        return self._oms

    @property
    def pipeline(self):
        if self._pipeline is None:
            try:
                from odap.biz.ontology.services.pipeline_service import OntologyPipeline
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

    async def process_event(self, event: PerceptionEvent) -> PerceptionOutput:
        event.status = PerceptionStatus.PROCESSING
        try:
            extraction = await self._extract(event)
            event.status = PerceptionStatus.EXTRACTED

            self._map_to_oms(extraction)
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

        try:
            from odap.biz.ontology.services.pipeline_service import LLMExtractionStageHandler, PipelineContext
            handler = LLMExtractionStageHandler()
            context = PipelineContext()
            context.original_content = text
            entities, relations, events_list = await handler._extract_with_llm(text, context)
            return ExtractionResult(
                entities=entities,
                relations=relations,
                events=events_list,
                actions=[],
                confidence=0.8,
            )
        except ImportError as e:
            logger.warning(f"PerceptionHub: LLMExtractionStageHandler import failed: {e}")
            pass
        except Exception as e:
            logger.warning(f"PerceptionHub LLM extraction failed: {e}")

        try:
            from odap.biz.ontology.ingestion_split.ingestion import NewsIngester
            ingester = NewsIngester()
            doc = ingester.extract_ontology(text)
            if doc:
                return ExtractionResult(
                    entities=[e.__dict__ if hasattr(e, '__dict__') else dict(e) for e in doc.get('entities', [])],
                    relations=[r.__dict__ if hasattr(r, '__dict__') else dict(r) for r in doc.get('relations', [])],
                    events=[ev.__dict__ if hasattr(ev, '__dict__') else dict(ev) for ev in doc.get('events', [])],
                    confidence=0.6,
                )
        except Exception as e:
            logger.warning(f"PerceptionHub NewsIngester fallback failed: {e}")

        return ExtractionResult(confidence=0.0)

    def _map_to_oms(self, extraction: ExtractionResult) -> List[str]:
        registered = []
        for entity in extraction.entities:
            etype = entity.get('entity_type', '')
            if etype and not self.oms.get_object_type(etype):
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
                    self.oms.create_object_type({
                        'type_id': etype,
                        'name': etype,
                        'display_name': etype,
                        'description': f'Auto-registered by PerceptionHub',
                        'properties': props,
                    })
                    registered.append(etype)
                except Exception as e:
                    logger.debug(f"OMS auto-register failed for {etype}: {e}")
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

            self.graph.add_episode(
                episode_text=episode_text,
                reference_time=event.timestamp or datetime.now(timezone.utc).isoformat(),
            )
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
