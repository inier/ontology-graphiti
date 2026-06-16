import logging
import json
import hashlib
import hmac
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class WritebackResult:
    def __init__(self, success: bool, message: str = "", data: Optional[Dict[str, Any]] = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()


class WritebackConnector(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', self.__class__.__name__)

    @abstractmethod
    async def execute(self, action_record: Dict[str, Any], execution_result: Dict[str, Any]) -> WritebackResult:
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        pass


class WebhookConnector(WritebackConnector):
    async def execute(self, action_record: Dict[str, Any], execution_result: Dict[str, Any]) -> WritebackResult:
        url = self.config.get('url', '')
        method = self.config.get('method', 'POST').upper()
        headers = self.config.get('headers', {})
        timeout = self.config.get('timeout', 30)
        secret = self.config.get('secret', '')

        if not url:
            return WritebackResult(False, "Webhook URL not configured")

        payload = {
            'action_record_id': action_record.get('action_record_id', ''),
            'action_type_id': action_record.get('action_type_id', ''),
            'target_object_id': action_record.get('target_object_id', ''),
            'target_object_type': action_record.get('target_object_type', ''),
            'parameters': action_record.get('parameters', {}),
            'execution_result': execution_result,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        if secret:
            signature = hmac.new(
                secret.encode('utf-8'),
                json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                hashlib.sha256,
            ).hexdigest()
            headers['X-Signature-256'] = f"sha256={signature}"

        try:
            import httpx
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == 'POST':
                    response = await client.post(url, json=payload, headers=headers)
                elif method == 'PUT':
                    response = await client.put(url, json=payload, headers=headers)
                else:
                    response = await client.post(url, json=payload, headers=headers)

                if 200 <= response.status_code < 300:
                    return WritebackResult(
                        True,
                        f"Webhook delivered: {response.status_code}",
                        {'status_code': response.status_code, 'response': response.text[:500]},
                    )
                else:
                    return WritebackResult(
                        False,
                        f"Webhook failed: {response.status_code}",
                        {'status_code': response.status_code, 'response': response.text[:500]},
                    )
        except ImportError:
            logger.warning("httpx not available, webhook writeback skipped")
            return WritebackResult(False, "httpx library not installed")
        except Exception as e:
            return WritebackResult(False, f"Webhook error: {str(e)}")

    def validate_config(self) -> bool:
        return bool(self.config.get('url'))


class GraphWritebackConnector(WritebackConnector):
    async def execute(self, action_record: Dict[str, Any], execution_result: Dict[str, Any]) -> WritebackResult:
        target_id = action_record.get('target_object_id', '')
        target_type = action_record.get('target_object_type', '')
        data = execution_result.get('data', {})

        if not target_id:
            return WritebackResult(False, "No target_object_id provided")

        try:
            from odap.infra.query import get_graph_write_proxy
            write_proxy = get_graph_write_proxy()

            properties_to_update = {}
            if isinstance(data, dict):
                for key in ('status', 'state', 'phase', 'outcome'):
                    if key in data and data[key] is not None:
                        properties_to_update[key] = data[key]

            if properties_to_update:
                result = write_proxy.update_entity(target_id, properties_to_update)
                if result.get("status") == "success":
                    return WritebackResult(
                        True,
                        f"Graph updated: {target_id} with {list(properties_to_update.keys())}",
                        {'updated_properties': list(properties_to_update.keys())},
                    )
                else:
                    return WritebackResult(False, f"Graph update failed: {result.get('message', 'unknown')}")
            else:
                return WritebackResult(True, "No properties to update in graph")

        except Exception as e:
            return WritebackResult(False, f"Graph update error: {str(e)}")

    def validate_config(self) -> bool:
        return True


class WritebackManager:
    _connector_registry: Dict[str, type] = {
        'webhook': WebhookConnector,
        'graph': GraphWritebackConnector,
    }

    def __init__(self):
        self._connectors: Dict[str, WritebackConnector] = {}

    def register_connector(self, name: str, connector: WritebackConnector):
        self._connectors[name] = connector

    def get_connector(self, name: str) -> Optional[WritebackConnector]:
        return self._connectors.get(name)

    def create_connector_from_config(self, config: Dict[str, Any]) -> Optional[WritebackConnector]:
        wb_type = config.get('type', '')
        connector_cls = self._connector_registry.get(wb_type)
        if not connector_cls:
            logger.warning(f"Unknown writeback type: {wb_type}")
            return None
        connector = connector_cls(config)
        if not connector.validate_config():
            logger.warning(f"Invalid config for {wb_type} connector")
            return None
        return connector

    async def execute_writeback(
        self,
        action_record: Dict[str, Any],
        execution_result: Dict[str, Any],
        writeback_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[WritebackResult]:
        if not writeback_config:
            return None

        wb_type = writeback_config.get('type', '')

        connector = self._connectors.get(wb_type)
        if not connector:
            connector = self.create_connector_from_config(writeback_config)
            if connector:
                self._connectors[wb_type] = connector

        if not connector:
            return WritebackResult(False, f"No connector for type: {wb_type}")

        return await connector.execute(action_record, execution_result)


_manager_instance = None


def get_writeback_manager() -> WritebackManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = WritebackManager()
        _manager_instance.register_connector('graph', GraphWritebackConnector({}))
    return _manager_instance
