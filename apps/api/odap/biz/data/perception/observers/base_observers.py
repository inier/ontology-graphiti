import logging
import os
import shutil
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from ..schemas import PerceptionEvent, PerceptionSourceType

logger = logging.getLogger(__name__)


class BaseObserver(ABC):
    def __init__(self, name: str, source_type: PerceptionSourceType, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.source_type = source_type
        self.config = config or {}
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    @abstractmethod
    async def observe(self) -> List[PerceptionEvent]:
        pass

    @abstractmethod
    async def acknowledge(self, event_id: str) -> bool:
        pass


class MCPObserver(BaseObserver):
    def __init__(self, name: str = "mcp_observer", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, PerceptionSourceType.MCP, config)
        self._acknowledged_ids: set = set()

    async def observe(self) -> List[PerceptionEvent]:
        events = []
        try:
            from odap.biz.integration.mcp_adapter.mcp_client import MCPClient
            client = MCPClient()
            messages = await client.poll_messages()
            for msg in messages:
                events.append(PerceptionEvent(
                    source_type=PerceptionSourceType.MCP,
                    source_name=self.name,
                    raw_content=msg.get('content', ''),
                    structured_data=msg,
                    metadata={'mcp_source': msg.get('source', '')},
                    workspace_id=msg.get('workspace_id'),
                ))
        except Exception as e:
            logger.warning(f"MCPObserver observe failed: {e}")
        return events

    async def acknowledge(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._acknowledged_ids:
            logger.debug(f"MCPObserver: event {event_id} already acknowledged")
            return True
        try:
            from odap.biz.integration.mcp_adapter.mcp_client import MCPClient
            client = MCPClient()
            ack_result = await client.acknowledge_message(event_id)
            if ack_result:
                self._acknowledged_ids.add(event_id)
                logger.debug(f"MCPObserver: acknowledged event {event_id}")
                return True
            else:
                logger.warning(f"MCPObserver: MCP server rejected ack for {event_id}")
                return False
        except ImportError:
            logger.debug("MCPObserver: MCPClient not available, marking as acknowledged locally")
            self._acknowledged_ids.add(event_id)
            return True
        except Exception as e:
            logger.warning(f"MCPObserver: acknowledge failed for {event_id}: {e}")
            return False


class FileObserver(BaseObserver):
    def __init__(self, name: str = "file_observer", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, PerceptionSourceType.FILE, config)
        self._watch_dir = (config or {}).get('watch_dir', 'data/incoming')
        self._processed_dir = (config or {}).get('processed_dir', os.path.join(self._watch_dir, '..', 'processed'))
        self._processed = set()
        self._event_file_map: Dict[str, str] = {}

    async def observe(self) -> List[PerceptionEvent]:
        import uuid
        events = []
        watch_dir = self._watch_dir
        if not os.path.exists(watch_dir):
            return events
        for fname in os.listdir(watch_dir):
            fpath = os.path.join(watch_dir, fname)
            if not os.path.isfile(fpath):
                continue
            if fpath in self._processed:
                continue
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read(10000)
                ext = os.path.splitext(fname)[1].lower()
                event_id = f"file_{uuid.uuid4().hex[:12]}"
                self._event_file_map[event_id] = fpath
                events.append(PerceptionEvent(
                    event_id=event_id,
                    source_type=PerceptionSourceType.FILE,
                    source_name=self.name,
                    raw_content=content,
                    metadata={'filename': fname, 'extension': ext, 'path': fpath},
                ))
                self._processed.add(fpath)
            except Exception as e:
                logger.warning(f"FileObserver failed to read {fpath}: {e}")
        return events

    async def acknowledge(self, event_id: str) -> bool:
        if not event_id:
            return False
        fpath = self._event_file_map.get(event_id)
        if not fpath:
            logger.warning(f"FileObserver: no file mapping for event {event_id}")
            return False
        if not os.path.exists(fpath):
            logger.debug(f"FileObserver: file {fpath} already removed")
            self._event_file_map.pop(event_id, None)
            return True
        try:
            os.makedirs(self._processed_dir, exist_ok=True)
            dest = os.path.join(self._processed_dir, os.path.basename(fpath))
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(fpath))
                dest = os.path.join(self._processed_dir, f"{base}_{event_id}{ext}")
            shutil.move(fpath, dest)
            self._event_file_map.pop(event_id, None)
            logger.debug(f"FileObserver: moved {fpath} -> {dest}")
            return True
        except Exception as e:
            logger.warning(f"FileObserver: acknowledge failed for {event_id}: {e}")
            return False


class APIObserver(BaseObserver):
    def __init__(self, name: str = "api_observer", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, PerceptionSourceType.API, config)
        self._queue: List[PerceptionEvent] = []
        self._acknowledged_ids: set = set()

    def enqueue(self, event: PerceptionEvent) -> None:
        self._queue.append(event)

    async def observe(self) -> List[PerceptionEvent]:
        events = list(self._queue)
        self._queue.clear()
        return events

    async def acknowledge(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._acknowledged_ids:
            logger.debug(f"APIObserver: event {event_id} already acknowledged")
            return True
        self._acknowledged_ids.add(event_id)
        logger.debug(f"APIObserver: acknowledged event {event_id}")
        return True


class SensorObserver(BaseObserver):
    def __init__(self, name: str = "sensor_observer", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, PerceptionSourceType.SENSOR, config)
        self._queue: List[PerceptionEvent] = []
        self._acknowledged_ids: set = set()

    def ingest_reading(self, sensor_id: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        self._queue.append(PerceptionEvent(
            source_type=PerceptionSourceType.SENSOR,
            source_name=self.name,
            raw_content=str(value),
            structured_data={'sensor_id': sensor_id, 'value': value},
            metadata=metadata or {},
        ))

    async def observe(self) -> List[PerceptionEvent]:
        events = list(self._queue)
        self._queue.clear()
        return events

    async def acknowledge(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._acknowledged_ids:
            logger.debug(f"SensorObserver: event {event_id} already acknowledged")
            return True
        self._acknowledged_ids.add(event_id)
        logger.debug(f"SensorObserver: acknowledged event {event_id}")
        return True


class NewsObserver(BaseObserver):
    def __init__(self, name: str = "news_observer", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, PerceptionSourceType.NEWS, config)
        self._acknowledged_ids: set = set()

    async def observe(self) -> List[PerceptionEvent]:
        events = []
        try:
            from odap.biz.core.ontology.ingestion_split.ingestion import NewsIngester
            ingester = NewsIngester()
            articles = ingester.fetch_latest()
            for article in articles[:10]:
                events.append(PerceptionEvent(
                    source_type=PerceptionSourceType.NEWS,
                    source_name=self.name,
                    raw_content=article.get('content', ''),
                    structured_data=article,
                    metadata={'url': article.get('url', ''), 'title': article.get('title', '')},
                ))
        except Exception as e:
            logger.warning(f"NewsObserver observe failed: {e}")
        return events

    async def acknowledge(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._acknowledged_ids:
            logger.debug(f"NewsObserver: event {event_id} already acknowledged")
            return True
        try:
            from odap.biz.core.ontology.ingestion_split.ingestion import NewsIngester
            ingester = NewsIngester()
            ingester.mark_processed(event_id)
            self._acknowledged_ids.add(event_id)
            logger.debug(f"NewsObserver: acknowledged event {event_id}")
            return True
        except ImportError:
            logger.debug("NewsObserver: NewsIngester not available, marking as acknowledged locally")
            self._acknowledged_ids.add(event_id)
            return True
        except Exception as e:
            logger.warning(f"NewsObserver: acknowledge failed for {event_id}: {e}")
            return False


class WebhookObserver(BaseObserver):
    def __init__(self, name: str = "webhook_observer", config: Optional[Dict[str, Any]] = None):
        super().__init__(name, PerceptionSourceType.WEBHOOK, config)
        self._queue: List[PerceptionEvent] = []
        self._acknowledged_ids: set = set()

    def receive_webhook(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> str:
        import uuid
        event_id = f"wh_{uuid.uuid4().hex[:12]}"
        self._queue.append(PerceptionEvent(
            event_id=event_id,
            source_type=PerceptionSourceType.WEBHOOK,
            source_name=self.name,
            raw_content=str(payload),
            structured_data=payload,
            metadata={'headers': headers or {}},
        ))
        return event_id

    async def observe(self) -> List[PerceptionEvent]:
        events = list(self._queue)
        self._queue.clear()
        return events

    async def acknowledge(self, event_id: str) -> bool:
        if not event_id:
            return False
        if event_id in self._acknowledged_ids:
            logger.debug(f"WebhookObserver: event {event_id} already acknowledged")
            return True
        self._acknowledged_ids.add(event_id)
        logger.debug(f"WebhookObserver: acknowledged event {event_id}")
        return True
