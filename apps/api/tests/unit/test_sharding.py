"""
Sharder 单元测试 (T325, TDD)

按 AGENTS.md 规则 9 必测。
"""
from __future__ import annotations

import time
import unittest
from typing import Any, Dict, List

from odap.biz.core.ontology.sharding.impl import Sharder
from odap.biz.core.ontology.sharding.models import (
    Shard,
    ShardKey,
    ShardQueryResult,
    ShardingStrategy,
)


def _mock_query_fn(object_type_id: str, pk_range: tuple, shard_idx: int) -> List[Dict[str, Any]]:
    """Mock 分片查询：按 shard_idx 返回不同数量的实例"""
    return [{"id": f"{object_type_id}-{shard_idx}-{i}", "shard": shard_idx} for i in range(shard_idx + 1)]


def _slow_query_fn(object_type_id: str, pk_range: tuple, shard_idx: int) -> List[Dict[str, Any]]:
    """慢查询（用于测试并行）"""
    time.sleep(0.05)
    return [{"id": f"s{shard_idx}-{i}"} for i in range(3)]


def _failing_query_fn(object_type_id: str, pk_range: tuple, shard_idx: int) -> List[Dict[str, Any]]:
    """总是失败的查询"""
    raise RuntimeError(f"shard {shard_idx} down")


class TestSharderBasics(unittest.TestCase):
    """分片器基础测试"""

    def test_default_construction(self):
        s = Sharder()
        self.assertEqual(s.shard_count, 4)
        self.assertEqual(s.threshold, 10_000)
        self.assertEqual(s.max_parallel, 4)

    def test_custom_construction(self):
        s = Sharder(shard_count=8, threshold=5_000, max_parallel=2)
        self.assertEqual(s.shard_count, 8)
        self.assertEqual(s.threshold, 5_000)
        self.assertEqual(s.max_parallel, 2)

    def test_invalid_shard_count(self):
        with self.assertRaises(ValueError):
            Sharder(shard_count=0)

    def test_invalid_threshold(self):
        with self.assertRaises(ValueError):
            Sharder(threshold=0)

    def test_invalid_max_parallel(self):
        with self.assertRaises(ValueError):
            Sharder(max_parallel=0)


class TestSharderDecision(unittest.TestCase):
    """分片决策测试"""

    def test_should_shard_below_threshold(self):
        s = Sharder(threshold=10_000)
        self.assertFalse(s.should_shard(0))
        self.assertFalse(s.should_shard(5_000))
        self.assertFalse(s.should_shard(9_999))

    def test_should_shard_above_threshold(self):
        s = Sharder(threshold=10_000)
        self.assertTrue(s.should_shard(10_000))
        self.assertTrue(s.should_shard(50_000))

    def test_shard_for_key_deterministic(self):
        s = Sharder(shard_count=4)
        shard1 = s.shard_for_key("Customer", "C001")
        shard2 = s.shard_for_key("Customer", "C001")
        self.assertEqual(shard1, shard2)

    def test_shard_for_key_in_range(self):
        s = Sharder(shard_count=4)
        for i in range(100):
            shard = s.shard_for_key("Customer", f"C{i:03d}")
            self.assertGreaterEqual(shard, 0)
            self.assertLess(shard, 4)

    def test_shard_for_key_distribution(self):
        """验证分片分布大致均匀（每个分片至少 1 个）"""
        s = Sharder(shard_count=4)
        distribution = {0: 0, 1: 0, 2: 0, 3: 0}
        for i in range(1000):
            shard = s.shard_for_key("Customer", f"C{i:04d}")
            distribution[shard] += 1
        # 4 个分片都应有实例
        for count in distribution.values():
            self.assertGreater(count, 0)


class TestSharderCreateShards(unittest.TestCase):
    """分片创建测试"""

    def test_create_shards_returns_correct_count(self):
        s = Sharder(shard_count=4)
        shards = s.create_shards("Customer")
        self.assertEqual(len(shards), 4)

    def test_shards_have_distinct_indices(self):
        s = Sharder(shard_count=4)
        shards = s.create_shards("Customer")
        indices = [sh.shard_index for sh in shards]
        self.assertEqual(sorted(indices), [0, 1, 2, 3])

    def test_shards_have_unique_ids(self):
        s = Sharder(shard_count=4)
        shards = s.create_shards("Customer")
        ids = [sh.id for sh in shards]
        self.assertEqual(len(set(ids)), 4)

    def test_shards_have_storage_path(self):
        s = Sharder(shard_count=4)
        shards = s.create_shards("Customer")
        for i, sh in enumerate(shards):
            self.assertIn("Customer", sh.storage_path)
            self.assertIn(str(i), sh.storage_path)


class TestSharderQueryParallel(unittest.TestCase):
    """并行查询测试"""

    def test_query_all_shards_aggregates_results(self):
        s = Sharder(shard_count=4, shard_query_fn=_mock_query_fn)
        result = s.query_all_shards("Customer")
        self.assertIsInstance(result, ShardQueryResult)
        # shard 0: 1, shard 1: 2, shard 2: 3, shard 3: 4 = 10
        self.assertEqual(result.total_count, 10)
        self.assertEqual(result.shards_queried, 4)

    def test_query_all_shards_with_range(self):
        s = Sharder(shard_count=4, shard_query_fn=_mock_query_fn)
        result = s.query_all_shards("Customer", primary_key_range=("C0", "C9"))
        self.assertEqual(result.total_count, 10)

    def test_query_with_no_injected_fn(self):
        """未注入 query_fn 时返回空（占位实现）"""
        s = Sharder(shard_count=4)
        result = s.query_all_shards("Customer")
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.shards_queried, 4)

    def test_parallel_execution_is_faster(self):
        """4 个分片 × 50ms 慢查询，并行应快于串行（4*50=200ms）"""
        s = Sharder(shard_count=4, max_parallel=4, shard_query_fn=_slow_query_fn)
        start = time.perf_counter()
        result = s.query_all_shards("Customer")
        elapsed = time.perf_counter() - start
        # 4 个分片 × 3 实例 = 12
        self.assertEqual(result.total_count, 12)
        # 串行需要 200ms，并行应 < 200ms（保留 buffer）
        self.assertLess(elapsed, 0.18)

    def test_query_with_failing_shard(self):
        """单个分片失败时，其他分片仍应返回结果"""
        s = Sharder(shard_count=4, shard_query_fn=_failing_query_fn)
        result = s.query_all_shards("Customer")
        # 4 个分片都失败，但聚合不应崩溃
        self.assertEqual(result.total_count, 0)
        self.assertEqual(result.shards_queried, 4)
        # 验证每个 shard 都有 error 字段
        for sr in result.shard_results:
            self.assertIn("error", sr)


class TestShardKeyAndSchemas(unittest.TestCase):
    """分片键与 schema 测试"""

    def test_shard_key_from_hash(self):
        sk = ShardKey.from_hash("Customer", "C001", shard_count=4)
        self.assertEqual(sk.object_type_id, "Customer")
        self.assertEqual(sk.primary_key, "C001")
        self.assertGreaterEqual(sk.shard_id, 0)
        self.assertLess(sk.shard_id, 4)

    def test_sharding_strategy_str_enum(self):
        self.assertEqual(ShardingStrategy.HASH.value, "hash")
        self.assertEqual(ShardingStrategy.HASH, "hash")  # str 兼容

    def test_shard_default_factory(self):
        """容器字段必须 Field(default_factory=...)"""
        from odap.biz.core.ontology.sharding.models.shard import Shard
        sh = Shard(object_type_id="X", shard_index=0)
        self.assertTrue(len(sh.id) > 0)
        self.assertEqual(sh.instance_count, 0)
        self.assertEqual(sh.storage_backend, "sqlite")

    def test_shard_query_result_default_factory(self):
        res = ShardQueryResult(object_type_id="X")
        self.assertEqual(res.shard_results, [])
        self.assertEqual(res.total_count, 0)
        self.assertEqual(res.duration_ms, 0.0)


if __name__ == "__main__":
    unittest.main()
