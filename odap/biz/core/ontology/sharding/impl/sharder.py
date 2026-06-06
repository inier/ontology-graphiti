"""
本体分片器 (T324)

当 ObjectType > 10000 实例时按主键 hash 自动分片。
查询时并行扫描各分片并合并结果。

Sharding 阈值与并行度可配置。
"""
from __future__ import annotations

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from ..models import Shard, ShardKey, ShardQueryResult, ShardingStrategy


# 默认阈值与并行度
DEFAULT_SHARDING_THRESHOLD = 10_000
DEFAULT_SHARD_COUNT = 4
DEFAULT_MAX_PARALLEL = 4


class Sharder:
    """本体分片器"""

    def __init__(
        self,
        shard_count: int = DEFAULT_SHARD_COUNT,
        threshold: int = DEFAULT_SHARDING_THRESHOLD,
        max_parallel: int = DEFAULT_MAX_PARALLEL,
        shard_query_fn: Optional[Callable[[str, str, int], List[Dict[str, Any]]]] = None,
    ):
        """
        Args:
            shard_count: 分片数
            threshold: 触发分片的实例数阈值
            max_parallel: 查询时最大并行度
            shard_query_fn: (object_type_id, primary_key_range, shard_index) -> List[dict]
                           注入式分片查询函数（默认 None，使用本地内存 mock）
        """
        if shard_count < 1:
            raise ValueError("shard_count must be >= 1")
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        if max_parallel < 1:
            raise ValueError("max_parallel must be >= 1")
        self.shard_count = shard_count
        self.threshold = threshold
        self.max_parallel = max_parallel
        self._shard_query_fn = shard_query_fn

    def should_shard(self, instance_count: int) -> bool:
        """判断是否需要分片"""
        return instance_count >= self.threshold

    def shard_for_key(self, object_type_id: str, primary_key: str) -> int:
        """决定主键属于哪个分片（hash 策略）"""
        return self._hash(object_type_id, primary_key) % self.shard_count

    def create_shards(self, object_type_id: str) -> List[Shard]:
        """为某 ObjectType 创建 N 个分片"""
        return [
            Shard(
                object_type_id=object_type_id,
                shard_index=i,
                storage_backend="sqlite",
                storage_path=f"shards/{object_type_id}_shard_{i}.db",
            )
            for i in range(self.shard_count)
        ]

    def query_all_shards(
        self,
        object_type_id: str,
        primary_key_range: Optional[tuple] = None,
    ) -> ShardQueryResult:
        """
        并行查询所有分片并合并。

        primary_key_range: (start, end) 限定主键范围；None 表示全量。
        """
        start = time.perf_counter()
        shard_results = self._dispatch_parallel_queries(object_type_id, primary_key_range)
        total = sum(r.get("count", 0) for r in shard_results)
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ShardQueryResult(
            object_type_id=object_type_id,
            shard_results=shard_results,
            total_count=total,
            shards_queried=len(shard_results),
            duration_ms=duration_ms,
        )

    def _dispatch_parallel_queries(
        self,
        object_type_id: str,
        primary_key_range: Optional[tuple],
    ) -> List[Dict[str, Any]]:
        """派发并行查询并收集结果"""
        shard_results: List[Dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            future_to_idx = {
                executor.submit(
                    self._query_one_shard,
                    object_type_id,
                    shard_idx,
                    primary_key_range,
                ): shard_idx
                for shard_idx in range(self.shard_count)
            }
            for future in as_completed(future_to_idx):
                shard_idx = future_to_idx[future]
                shard_results.append(self._collect_future_result(future, shard_idx))
        return shard_results

    @staticmethod
    def _collect_future_result(future, shard_idx: int) -> Dict[str, Any]:
        try:
            data = future.result()
            return {"shard_index": shard_idx, "instances": data, "count": len(data)}
        except Exception as exc:
            return {"shard_index": shard_idx, "error": str(exc), "count": 0}

    # ---------- 内部 ----------

    @staticmethod
    def _hash(object_type_id: str, primary_key: str) -> int:
        """稳定 hash"""
        h = hashlib.md5(f"{object_type_id}::{primary_key}".encode("utf-8")).hexdigest()
        return int(h, 16)

    def _query_one_shard(
        self,
        object_type_id: str,
        shard_idx: int,
        primary_key_range: Optional[tuple],
    ) -> List[Dict[str, Any]]:
        """查询单个分片（注入式）"""
        if self._shard_query_fn is None:
            return []
        return self._shard_query_fn(object_type_id, primary_key_range or ("", ""), shard_idx)
