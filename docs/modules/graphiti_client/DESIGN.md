# Graphiti 客户端模块设计文档

## 1. 模块概述

### 1.1 模块定位

`graphiti_client` 是系统与 Graphiti 双时态知识图谱交互的核心客户端模块。Graphiti 提供了传统知识图谱不具备的双时态（Bi-Temporal）能力，支持"当时是什么状态"、"何时发生变化"和"历史版本对比"的查询。

### 1.2 核心能力

| 能力 | 描述 |
|------|------|
| 双时态存储 | 支持 valid_time（有效时间）和 transaction_time（记录时间） |
| Episode 管理 | 战场事件的时序记录 |
| 实体关系图谱 | Target、Unit、IntelligenceReport 等实体及其关系 |
| RAG 增强推理 | 语义向量检索 + 图遍历 |
| 时序推理 | 历史状态快照、时间窗口查询 |

### 1.3 Graphiti 在架构中的位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Graphiti 双时态知识图谱                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      GraphitiClient                                  │    │
│  │  • 连接管理                                                         │    │
│  │  • 会话管理                                                         │    │
│  │  • 错误处理                                                         │    │
│  │  • 重试机制                                                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      BiTemporalStore                                 │    │
│  │  ┌─────────────────┐           ┌─────────────────┐                   │    │
│  │  │   valid_time   │           │ transaction_time │                   │    │
│  │  │   (有效时间)    │           │   (记录时间)      │                   │    │
│  │  └─────────────────┘           └─────────────────┘                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Neo4j Backend                                   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         消费者                                              │
│  • OpenHarness Bridge (记忆系统)                                          │
│  • Intelligence Agent (情报存储)                                          │
│  • Commander Agent (决策推理)                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 接口设计

### 2.1 GraphitiClient 主接口

```python
# core/graphiti_client/client.py
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel, Field

class GraphitiConfig(BaseModel):
    """Graphiti 配置"""
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(...)
    graphiti_url: str = Field(default="http://localhost:7474")
    embedder_name: str = Field(default="openai")

class GraphitiClient:
    """Graphiti 双时态知识图谱客户端"""

    async def initialize(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...

    # Episode 操作
    async def add_episode(
        self,
        name: str,
        episode_body: str,
        source: str,
        categories: List[str],
        invalid_at: Optional[datetime] = None
    ) -> str: ...

    async def add_entity(
        self,
        name: str,
        entity_type: str,
        properties: Dict[str, Any],
        categories: List[str] = None
    ) -> str: ...

    # 查询操作
    async def search_episodes(
        self,
        query: str,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]: ...

    async def get_entity_history(
        self,
        entity_id: str,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> List[Dict[str, Any]]: ...

    async def get_temporal_facts(
        self,
        entity_id: str,
        valid_time: Optional[datetime] = None
    ) -> Dict[str, Any]: ...

    # RAG 增强
    async def rag_search(
        self,
        query: str,
        context_entities: Optional[List[str]] = None,
        limit: int = 5
    ) -> Dict[str, Any]: ...

    async def generate_reasoning_context(
        self,
        question: str,
        max_episodes: int = 10
    ) -> str: ...
```

### 2.2 BattlefieldGraphitiClient 扩展接口

```python
# core/graphiti_client/battlefield_extension.py
from enum import Enum

class TargetType(str, Enum):
    RADAR = "radar"
    COMMAND_CENTER = "command_center"
    SUPPLY_DEPOT = "supply_depot"
    LAUNCHER = "launcher"
    AIR_DEFENSE = "air_defense"

class ThreatLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class StrikeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"

class BattlefieldGraphitiClient(GraphitiClient):
    """战场领域扩展的 Graphiti 客户端"""

    async def add_target(
        self,
        name: str,
        target_type: TargetType,
        location: Dict[str, float],
        threat_level: ThreatLevel,
        properties: Dict[str, Any] = None
    ) -> str: ...

    async def update_target_status(
        self,
        target_id: str,
        status: str,
        reason: str = None
    ) -> bool: ...

    async def add_intelligence_report(
        self,
        source: str,
        content: str,
        confidence: float,
        detected_targets: List[str] = None
    ) -> str: ...

    async def add_strike_order(
        self,
        target_id: str,
        weapon_type: str,
        issued_by: str,
        priority: int = 1
    ) -> str: ...

    async def update_strike_status(
        self,
        strike_id: str,
        status: StrikeStatus,
        result: Dict[str, Any] = None
    ) -> bool: ...
```

---

## 3. 数据模型

### 3.1 核心实体定义

```python
# core/graphiti_client/models.py
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class GeoLocation(BaseModel):
    """地理坐标"""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    region: Optional[str] = None

class TargetEntity(BaseModel):
    """打击目标"""
    entity_id: str
    name: str
    target_type: str
    location: GeoLocation
    threat_level: str
    status: str  # active/damaged/destroyed/unknown
    discovered_at: datetime
    destroyed_at: Optional[datetime] = None

class IntelligenceEpisode(BaseModel):
    """情报报告"""
    episode_id: str
    source: str
    confidence: float = Field(..., ge=0, le=1)
    content: str
    time_window: Dict[str, datetime]
    categories: List[str]

class StrikeEpisode(BaseModel):
    """打击命令"""
    episode_id: str
    target_id: str
    weapon_type: str
    status: str
    issued_by: str
    issued_at: datetime
    executed_at: Optional[datetime] = None

class RelationTypes:
    """预定义关系类型"""
    DETECTED_AT = "DETECTED_AT"
    THREATENED_BY = "THREATENED_BY"
    EVIDENCE_FOR = "EVIDENCE_FOR"
    ATTACKED_BY = "ATTACKED_BY"
    PART_OF = "PART_OF"
    LOCATED_AT = "LOCATED_AT"
```

---

## 4. 核心实现

### 4.1 客户端初始化

```python
# core/graphiti_client/client.py
import logging

logger = logging.getLogger(__name__)

class GraphitiClientImpl(GraphitiClient):
    """Graphiti 客户端实现"""

    async def initialize(self) -> None:
        """初始化 Graphiti 连接"""
        logger.info(f"Initializing Graphiti: {self.config.neo4j_uri}")

        from graphiti_core.graphiti import Graphiti

        self._graphiti = Graphiti(
            graph_name=self.config.graph_name or "battlefield_graph",
            index_name=self.config.index_name or "battlefield_index",
            neo4j_uri=self.config.neo4j_uri,
            neo4j_user=self.config.neo4j_user,
            neo4j_password=self.config.neo4j_password,
            neo4j_database=self.config.neo4j_database or "neo4j",
        )

        # 设置嵌入器
        await self._setup_embedder()

        self._initialized = True
        logger.info("Graphiti client initialized")

    async def _setup_embedder(self) -> None:
        """设置嵌入器"""
        if self.config.embedder_name == "openai":
            from graphiti_core.embedders.openai import OpenAIEmbedder
            self._graphiti.embedder = OpenAIEmbedder(
                api_key=os.environ.get("OPENAI_API_KEY"),
                model="text-embedding-3-small",
                dimension=1536
            )

    async def add_episode(
        self,
        name: str,
        episode_body: str,
        source: str,
        categories: List[str],
        invalid_at: Optional[datetime] = None,
        episode_id: Optional[str] = None
    ) -> str:
        """添加 Episode"""
        episode = await self._graphiti.add_episode(
            name=name,
            episode_body=episode_body,
            source=source,
            categories=categories,
            invalid_at=invalid_at,
            episode_id=episode_id
        )
        return episode.uuid

    async def search_episodes(
        self,
        query: str,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        categories: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """语义搜索 Episodes"""
        results = await self._graphiti.search(
            query=query,
            time_range=time_range,
            categories=categories,
            limit=limit
        )
        return [self._serialize_episode(r) for r in results]
```

---

## 5. 配置示例

```yaml
# config/graphiti_client.yaml
graphiti:
  neo4j:
    uri: "bolt://localhost:7687"
    user: "neo4j"
    password: "${NEO4J_PASSWORD}"
    database: "neo4j"

  graphiti_url: "http://localhost:7474"

  embedder:
    name: "openai"
    model: "text-embedding-3-small"
    dimension: 1536

  graph_name: "BattlefieldGraph"
  index_name: "battlefield_index"

  query:
    default_limit: 10
    timeout_seconds: 30
```

---

## 6. 错误处理

```python
# core/graphiti_client/exceptions.py

class GraphitiError(Exception):
    """Graphiti 基础异常"""
    pass

class ConnectionError(GraphitiError):
    """连接错误"""
    pass

class EntityNotFoundError(GraphitiError):
    """实体未找到"""
    pass

class QueryTimeoutError(GraphitiError):
    """查询超时"""
    pass
```

---

## 7. 性能优化与缓存策略

### 7.1 三级缓存架构
```python
# core/graphiti_client/cache_manager.py
from typing import Optional, Any
import redis.asyncio as redis
from dataclasses import dataclass
import asyncio
import json
import os
import pickle

@dataclass
class CacheConfig:
    """缓存配置"""
    memory_max_size: int = 1000  # L1缓存最大条目数
    memory_ttl: int = 60  # L1缓存TTL（秒）
    redis_ttl: int = 3600  # L2缓存TTL（秒）
    disk_ttl: int = 86400  # L3缓存TTL（秒）
    enable_persistence: bool = True

class ThreeLevelCache:
    """三级缓存架构：内存 → Redis → 磁盘"""
    
    def __init__(self, config: CacheConfig):
        self.config = config
        self.memory_cache = {}  # L1: 内存缓存（字典）
        self.redis_client = None  # L2: Redis缓存
        self.disk_base_path = "/tmp/graphiti_cache"  # L3: 磁盘缓存
        
        # 初始化缓存目录
        if self.config.enable_persistence:
            os.makedirs(self.disk_base_path, exist_ok=True)
        
    async def initialize(self, redis_url: Optional[str] = None):
        """初始化缓存系统"""
        # 初始化Redis连接
        if redis_url:
            self.redis_client = redis.from_url(redis_url)
            await self.redis_client.ping()
            print("L2 Redis缓存已连接")
        
        # 清理过期缓存
        await self._cleanup_expired()
        
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存数据（三级缓存查找）"""
        # L1: 检查内存缓存
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not self._is_expired(entry):
                print(f"L1缓存命中: {key}")
                return entry["data"]
            else:
                del self.memory_cache[key]
        
        # L2: 检查Redis缓存
        if self.redis_client:
            try:
                redis_data = await self.redis_client.get(f"graphiti:{key}")
                if redis_data:
                    data = pickle.loads(redis_data)
                    # 回填到L1缓存
                    await self._set_memory_cache(key, data, self.config.redis_ttl)
                    print(f"L2 Redis缓存命中: {key}")
                    return data
            except Exception as e:
                print(f"Redis缓存读取失败: {e}")
        
        # L3: 检查磁盘缓存
        if self.config.enable_persistence:
            disk_path = f"{self.disk_base_path}/{key}.pkl"
            if os.path.exists(disk_path):
                try:
                    with open(disk_path, 'rb') as f:
                        data = pickle.load(f)
                        # 检查磁盘缓存是否过期
                        mtime = os.path.getmtime(disk_path)
                        if time.time() - mtime < self.config.disk_ttl:
                            # 回填到L1和L2缓存
                            await self.set(key, data)
                            print(f"L3磁盘缓存命中: {key}")
                            return data
                        else:
                            os.remove(disk_path)
                except Exception as e:
                    print(f"磁盘缓存读取失败: {e}")
        
        return None
    
    async def set(self, key: str, data: Any, ttl: Optional[int] = None):
        """设置缓存数据（三级缓存写入）"""
        if ttl is None:
            ttl = self.config.memory_ttl
        
        # L1: 内存缓存
        await self._set_memory_cache(key, data, ttl)
        
        # L2: Redis缓存
        if self.redis_client:
            try:
                serialized = pickle.dumps(data)
                await self.redis_client.setex(
                    f"graphiti:{key}",
                    ttl if ttl <= self.config.redis_ttl else self.config.redis_ttl,
                    serialized
                )
            except Exception as e:
                print(f"Redis缓存写入失败: {e}")
        
        # L3: 磁盘缓存
        if self.config.enable_persistence and ttl <= self.config.disk_ttl:
            try:
                disk_path = f"{self.disk_base_path}/{key}.pkl"
                with open(disk_path, 'wb') as f:
                    pickle.dump(data, f)
            except Exception as e:
                print(f"磁盘缓存写入失败: {e}")
    
    async def _set_memory_cache(self, key: str, data: Any, ttl: int):
        """设置L1内存缓存"""
        self.memory_cache[key] = {
            "data": data,
            "expires_at": time.time() + ttl
        }
        
        # 如果缓存超过最大大小，清理最旧的条目
        if len(self.memory_cache) > self.config.memory_max_size:
            # 按过期时间排序，移除最早过期的
            sorted_items = sorted(
                self.memory_cache.items(),
                key=lambda x: x[1]["expires_at"]
            )
            for i in range(len(sorted_items) // 2):  # 移除一半
                del self.memory_cache[sorted_items[i][0]]
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """检查缓存是否过期"""
        return time.time() > cache_entry["expires_at"]
    
    async def _cleanup_expired(self):
        """清理过期缓存"""
        # 清理L1内存缓存
        expired_keys = []
        for key, entry in self.memory_cache.items():
            if self._is_expired(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.memory_cache[key]
        
        # 清理L3磁盘缓存
        if self.config.enable_persistence:
            cutoff_time = time.time() - self.config.disk_ttl
            for filename in os.listdir(self.disk_base_path):
                filepath = os.path.join(self.disk_base_path, filename)
                if os.path.isfile(filepath):
                    mtime = os.path.getmtime(filepath)
                    if mtime < cutoff_time:
                        os.remove(filepath)
```

### 7.2 缓存策略配置
```yaml
# config/graphiti_client.yaml
graphiti_client:
  cache:
    enabled: true
    levels:
      memory:
        max_size: 1000
        ttl_seconds: 60
      redis:
        enabled: true
        url: "redis://localhost:6379"
        ttl_seconds: 3600
        connection_pool_size: 10
      disk:
        enabled: true
        base_path: "/tmp/graphiti_cache"
        ttl_seconds: 86400
        max_size_mb: 1024
  
  query_cache:
    enabled: true
    default_ttl_seconds: 300
    max_cached_queries: 1000
    
  result_cache:
    enabled: true
    strategy: "adaptive"  # adaptive/fixed/time_based
    default_ttl_seconds: 600
    max_items: 5000
```

### 7.3 性能监控
```python
# core/graphiti_client/performance_monitor.py
from datetime import datetime, timedelta
from typing import Dict, Any, List
from collections import defaultdict
import time as time_module

class PerformanceMonitor:
    """Graphiti客户端性能监控器"""
    
    def __init__(self):
        self.query_times = defaultdict(list)
        self.cache_stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "disk_hits": 0,
            "disk_misses": 0
        }
        self.error_count = defaultdict(int)
        self.start_time = datetime.now()
    
    def record_query(self, query_type: str, execution_time_ms: float):
        """记录查询性能"""
        self.query_times[query_type].append(execution_time_ms)
        
        # 保持最近1000个记录
        if len(self.query_times[query_type]) > 1000:
            self.query_times[query_type] = self.query_times[query_type][-1000:]
    
    def record_cache_hit(self, cache_level: str):
        """记录缓存命中"""
        if cache_level == "memory":
            self.cache_stats["memory_hits"] += 1
        elif cache_level == "redis":
            self.cache_stats["redis_hits"] += 1
        elif cache_level == "disk":
            self.cache_stats["disk_hits"] += 1
    
    def record_cache_miss(self, cache_level: str):
        """记录缓存未命中"""
        if cache_level == "memory":
            self.cache_stats["memory_misses"] += 1
        elif cache_level == "redis":
            self.cache_stats["redis_misses"] += 1
        elif cache_level == "disk":
            self.cache_stats["disk_misses"] += 1
    
    def record_error(self, error_type: str):
        """记录错误"""
        self.error_count[error_type] += 1
    
    def get_performance_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        report = {
            "uptime_hours": (datetime.now() - self.start_time).total_seconds() / 3600,
            "query_performance": {},
            "cache_efficiency": {},
            "error_summary": dict(self.error_count)
        }
        
        # 查询性能统计
        for query_type, times in self.query_times.items():
            if times:
                report["query_performance"][query_type] = {
                    "count": len(times),
                    "avg_ms": sum(times) / len(times),
                    "p95_ms": sorted(times)[int(len(times) * 0.95)],
                    "p99_ms": sorted(times)[int(len(times) * 0.99)],
                    "max_ms": max(times)
                }
        
        # 缓存效率统计
        total_memory_access = self.cache_stats["memory_hits"] + self.cache_stats["memory_misses"]
        total_redis_access = self.cache_stats["redis_hits"] + self.cache_stats["redis_misses"]
        total_disk_access = self.cache_stats["disk_hits"] + self.cache_stats["disk_misses"]
        
        report["cache_efficiency"] = {
            "memory_hit_rate": self.cache_stats["memory_hits"] / total_memory_access if total_memory_access > 0 else 0,
            "redis_hit_rate": self.cache_stats["redis_hits"] / total_redis_access if total_redis_access > 0 else 0,
            "disk_hit_rate": self.cache_stats["disk_hits"] / total_disk_access if total_disk_access > 0 else 0,
            "overall_hit_rate": (
                (self.cache_stats["memory_hits"] + self.cache_stats["redis_hits"] + self.cache_stats["disk_hits"]) /
                (total_memory_access + total_redis_access + total_disk_access)
                if (total_memory_access + total_redis_access + total_disk_access) > 0 else 0
            )
        }
        
        return report
```

## 8. 连接池与资源管理

### 8.1 连接池设计
```python
# core/graphiti_client/connection_pool.py
import asyncio
from typing import List, Optional
from contextlib import asynccontextmanager
from neo4j import AsyncGraphDatabase

class GraphitiConnectionPool:
    """Graphiti连接池管理器"""
    
    def __init__(self, 
                 uri: str, 
                 auth: tuple,
                 max_connections: int = 20,
                 idle_timeout_seconds: int = 300):
        self.uri = uri
        self.auth = auth
        self.max_connections = max_connections
        self.idle_timeout = idle_timeout_seconds
        
        self.active_connections = []
        self.idle_connections = []
        self.waiting_tasks = []
        self.stats = {
            "total_created": 0,
            "total_destroyed": 0,
            "peak_usage": 0,
            "avg_wait_time_ms": 0
        }
    
    @asynccontextmanager
    async def acquire(self):
        """获取数据库连接"""
        start_time = time_module.time()
        
        # 尝试从空闲连接获取
        if self.idle_connections:
            driver = self.idle_connections.pop()
        # 创建新连接
        elif len(self.active_connections) + len(self.idle_connections) < self.max_connections:
            driver = AsyncGraphDatabase.driver(self.uri, auth=self.auth)
            self.stats["total_created"] += 1
        # 等待可用连接
        else:
            future = asyncio.Future()
            self.waiting_tasks.append(future)
            driver = await future
        
        self.active_connections.append(driver)
        
        if len(self.active_connections) > self.stats["peak_usage"]:
            self.stats["peak_usage"] = len(self.active_connections)
        
        try:
            yield driver
        finally:
            # 归还连接
            self.active_connections.remove(driver)
            
            # 如果连接超过空闲超时，关闭它
            if len(self.idle_connections) >= self.max_connections // 2:
                await driver.close()
                self.stats["total_destroyed"] += 1
            else:
                self.idle_connections.append(driver)
            
            # 如果有等待任务，分配连接
            if self.waiting_tasks:
                future = self.waiting_tasks.pop(0)
                if self.idle_connections:
                    next_driver = self.idle_connections.pop()
                else:
                    next_driver = AsyncGraphDatabase.driver(self.uri, auth=self.auth)
                    self.stats["total_created"] += 1
                future.set_result(next_driver)
            
            # 更新统计
            wait_time = (time_module.time() - start_time) * 1000
            self.stats["avg_wait_time_ms"] = (
                (self.stats["avg_wait_time_ms"] * self.stats["total_created"] + wait_time) /
                (self.stats["total_created"] + 1)
            )
```

## 9. 错误处理增强

```python
# core/graphiti_client/error_handler.py
from typing import Optional, Type
import asyncio
from datetime import datetime

class GraphitiErrorHandler:
    """Graphiti错误处理器"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.retry_delays = [0.1, 1, 5]  # 指数退避延迟
        
    async def execute_with_retry(self, func, *args, **kwargs):
        """带重试的执行"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                # 检查是否为可重试错误
                if not self._should_retry(e):
                    raise
                
                # 如果是最后一次尝试，直接抛出
                if attempt >= self.max_retries:
                    break
                
                # 等待重试延迟
                delay = self.retry_delays[attempt] if attempt < len(self.retry_delays) else 10
                print(f"重试尝试 {attempt + 1}/{self.max_retries}，延迟 {delay}秒")
                await asyncio.sleep(delay)
        
        # 重试次数用尽，抛出最后一个错误
        raise last_error
    
    def _should_retry(self, error: Exception) -> bool:
        """判断错误是否应该重试"""
        error_str = str(error).lower()
        
        # 可重试的错误类型
        retryable_errors = [
            "connection",
            "timeout",
            "network",
            "socket",
            "deadlock",
            "resource",
            "temporarily"
        ]
        
        return any(retryable in error_str for retryable in retryable_errors)
```

## 10. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|---------|
| 1.0.0 | 2026-04-11 | 初始版本 |
| 1.1.0 | 2026-04-12 | 新增三级缓存架构、性能监控、连接池管理和错误重试机制 |
