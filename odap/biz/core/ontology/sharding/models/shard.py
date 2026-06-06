"""
本体分片 - 领域模型 (T324)

定义分片策略 + 分片键 + 分片查询结果。
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field


class ShardingStrategy(str, Enum):
    """分片策略"""
    HASH = "hash"           # 按主键 hash 分片
    RANGE = "range"         # 按主键范围分片
    ROUND_ROBIN = "round_robin"  # 轮询


class ShardKey(BaseModel):
    """分片键标识（(object_type_id, primary_key) → 哪个 shard）"""
    object_type_id: str
    primary_key: str
    shard_id: int

    @classmethod
    def from_hash(cls, object_type_id: str, primary_key: str, shard_count: int) -> "ShardKey":
        """按 hash 决定 shard_id"""
        h = hash((object_type_id, primary_key))
        return cls(object_type_id=object_type_id, primary_key=primary_key, shard_id=h % shard_count)


class Shard(BaseModel):
    """单个分片"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    object_type_id: str
    shard_index: int                           # 0..N-1
    instance_count: int = 0
    storage_backend: str = "sqlite"            # sqlite / neo4j / memory
    storage_path: str = ""                     # sqlite: db path / neo4j: label


class ShardQueryResult(BaseModel):
    """分片查询结果（含合并信息）"""
    object_type_id: str
    shard_results: List[Dict[str, Any]] = Field(default_factory=list)
    total_count: int = 0
    shards_queried: int = 0
    duration_ms: float = 0.0
