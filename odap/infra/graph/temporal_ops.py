"""
时态查询操作 Mixin

提供 GraphManager 的双时态查询功能（valid_time / transaction_time）。
"""

from datetime import datetime, timezone
from typing import List, Dict, Any

from ._utils import _run_async



import logging

logger = logging.getLogger(__name__)
class TemporalOpsMixin:
    """时态查询：query_temporal, query_at_valid_time, query_at_transaction_time"""

    def query_temporal(self, valid_time=None, transaction_time=None, entity_type=None) -> List[Dict]:
        cache_key = self._cache_key("qt", valid_time=str(valid_time), transaction_time=str(transaction_time), entity_type=entity_type)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        if self._mode == "unavailable" and not self._test_mode:
            return self._unavailable_error()

        if self._use_fallback or not self._connected:
            if self._test_mode:
                logger.info('警告: 回退模式不支持时态查询，返回所有实体')
                return self.query_entities(entity_type)
            return self._unavailable_error()

        self._build_temporal_index()

        if self._temporal_index and valid_time:
            try:
                vt_str = valid_time if isinstance(valid_time, str) else valid_time.isoformat()
                result = []
                for idx_vt, entries in self._temporal_index.items():
                    if idx_vt <= vt_str:
                        for entry in entries:
                            if entity_type and entry.get("type", "").lower() != entity_type.lower():
                                continue
                            if transaction_time:
                                tt_str = transaction_time if isinstance(transaction_time, str) else transaction_time.isoformat()
                                if entry.get("transaction_time", "") > tt_str:
                                    continue
                            result.append(entry)
                self._cache_set(cache_key, result)
                return result
            except Exception as e:
                logger.info(f'时间索引查询失败，降级到 Graphiti 查询: {e}')

        async def temporal_query():
            try:
                reference_time = None
                if valid_time:
                    if isinstance(valid_time, str):
                        reference_time = datetime.fromisoformat(valid_time.replace('Z', '+00:00'))
                    else:
                        reference_time = valid_time
                else:
                    reference_time = datetime.now(timezone.utc)

                episodes = await self.graph.retrieve_episodes(
                    reference_time=reference_time,
                )

                result = []
                for episode in episodes:
                    if entity_type and episode.name and entity_type.lower() not in episode.name.lower():
                        continue

                    ep_valid_time = str(episode.reference_time) if hasattr(episode, 'reference_time') and episode.reference_time else str(episode.created_at)
                    ep_transaction_time = str(episode.created_at)

                    if transaction_time:
                        if isinstance(transaction_time, str):
                            if ep_transaction_time > transaction_time:
                                continue

                    result.append({
                        "id": episode.name or str(episode.uuid),
                        "type": "Entity",
                        "properties": {"body": episode.content},
                        "valid_time": ep_valid_time,
                        "transaction_time": ep_transaction_time,
                    })

                return result
            except Exception as e:
                logger.info(f'Graphiti时态查询失败，降级到普通查询: {e}')
                return self.query_entities(entity_type)

        result = _run_async(temporal_query())
        self._cache_set(cache_key, result)
        return result

    def query_at_valid_time(self, entity_type=None, valid_time=None) -> List[Dict]:
        return self.query_temporal(valid_time=valid_time, entity_type=entity_type)

    def query_at_transaction_time(self, entity_type=None, transaction_time=None) -> List[Dict]:
        return self.query_temporal(transaction_time=transaction_time, entity_type=entity_type)
