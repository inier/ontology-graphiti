"""
缓存管理 Mixin

提供 GraphManager 的 LRU 查询缓存和时间索引功能。
"""

import time
from typing import Optional, Any, Dict, List



import logging

logger = logging.getLogger(__name__)
class CacheMixin:
    """缓存管理：LRU 查询缓存 + 时间索引"""

    def _cache_get(self, key: str) -> Optional[Any]:
        if key not in self._query_cache:
            self.cache_misses += 1
            return None
        ts = self._query_cache_timestamps.get(key, 0)
        if time.time() - ts > self._cache_ttl:
            del self._query_cache[key]
            del self._query_cache_timestamps[key]
            self.cache_misses += 1
            return None
        self.cache_hits += 1
        return self._query_cache[key]

    def _cache_set(self, key: str, value: Any):
        if len(self._query_cache) >= self._cache_max_size:
            oldest_key = min(self._query_cache_timestamps, key=self._query_cache_timestamps.get)
            del self._query_cache[oldest_key]
            del self._query_cache_timestamps[oldest_key]
        self._query_cache[key] = value
        self._query_cache_timestamps[key] = time.time()

    def _cache_key(self, prefix: str, **kwargs) -> str:
        parts = [prefix]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                parts.append(f"{k}={v}")
        return "|".join(parts)

    def invalidate_cache(self):
        self._query_cache.clear()
        self._query_cache_timestamps.clear()
        self._temporal_index.clear()
        self._temporal_index_built = False

    def _build_temporal_index(self):
        if self._temporal_index_built:
            return
        if self._use_fallback or not self._connected:
            self._temporal_index_built = True
            return
        try:
            if self.neo4j_driver:
                with self.neo4j_driver.session() as session:
                    result = session.run(
                        "MATCH (n:Entity) WHERE n.valid_time IS NOT NULL "
                        "RETURN n.id AS id, n.valid_time AS valid_time, "
                        "n.transaction_time AS transaction_time, labels(n) AS labels, properties(n) AS props "
                        "ORDER BY n.valid_time"
                    )
                    for record in result:
                        vt = str(record.get("valid_time", ""))
                        if vt not in self._temporal_index:
                            self._temporal_index[vt] = []
                        self._temporal_index[vt].append({
                            "id": record["id"],
                            "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                            "properties": record["props"],
                            "valid_time": vt,
                            "transaction_time": str(record.get("transaction_time", "")),
                        })
            self._temporal_index_built = True
        except Exception as e:
            logger.info(f'构建时间索引失败: {e}')
            self._temporal_index_built = True
