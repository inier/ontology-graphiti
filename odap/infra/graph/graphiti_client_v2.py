"""
Graphiti 客户端 v2 - 时序知识图谱增强版
基于 Neo4j 的双时态知识图谱，支持混合检索和连接治理

三层降级：
1. Neo4j Driver 直连（无需 graphiti-core，直接 Cypher 操作）
2. Graphiti（双时态知识图谱，需要 graphiti-core + Neo4j）
3. NetworkX fallback（纯内存，无外部依赖）
"""

import sys
import os
import json
import asyncio
import time
import threading
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.biz.ontology.mock_data.data_generator import load_simulation_data

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EntityNode, EpisodicNode
    from graphiti_core.edges import Edge, EntityEdge
    from graphiti_core.embedder.client import EmbedderClient
    GRAPHITI_AVAILABLE = True
except ImportError as e:
    GRAPHITI_AVAILABLE = False
    print(f"提示: graphiti-core 未安装 ({e})，Graphiti 模式不可用")

try:
    from neo4j import GraphDatabase
    NEO4J_DRIVER_AVAILABLE = True
except ImportError as e:
    NEO4J_DRIVER_AVAILABLE = False
    print(f"提示: neo4j driver 未安装 ({e})，Neo4j 直连模式不可用")


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ConnectionConfig:
    """连接配置"""
    max_pool_size: int = 20
    pool_timeout: int = 30
    idle_timeout: int = 300
    connection_timeout: int = 10


@dataclass
class CircuitBreakerConfig:
    """断路器配置"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3


@dataclass
class EpisodeConfig:
    """Episode 配置"""
    batch_size: int = 10
    max_batch_wait_ms: int = 100
    deduplicate: bool = True
    retry_attempts: int = 3


@dataclass
class GraphitiClientMetrics:
    """Graphiti 客户端指标"""
    query_times: List[float] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    connection_pool_size: int = 0
    circuit_state: str = "closed"
    failure_count: int = 0
    episode_batch_count: int = 0
    episode_success_count: int = 0
    episode_failure_count: int = 0


class ConnectionPool:
    """连接池管理器"""

    def __init__(self, uri: str, user: str, password: str, config: ConnectionConfig):
        self.uri = uri
        self.user = user
        self.password = password
        self.config = config
        self.pool: List = []
        self.pool_creation_times: List[float] = []
        self.lock = threading.Lock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = True
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        """启动清理线程"""
        def cleanup_loop():
            while self._running:
                time.sleep(60)
                self._cleanup_expired()
                if not self._running:
                    break

        self._cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
        self._cleanup_thread.start()

    def _cleanup_expired(self):
        """清理过期连接"""
        with self.lock:
            current_time = time.time()
            valid_indices = []
            for i, creation_time in enumerate(self.pool_creation_times):
                if current_time - creation_time < self.config.idle_timeout:
                    valid_indices.append(i)
                else:
                    try:
                        self.pool[i].close()
                    except Exception:
                        pass

            self.pool = [self.pool[i] for i in valid_indices]
            self.pool_creation_times = [self.pool_creation_times[i] for i in valid_indices]

    def get_connection(self):
        """获取连接"""
        with self.lock:
            if self.pool:
                conn = self.pool.pop(0)
                self.pool_creation_times.pop(0)
                return conn

            if len(self.pool) < self.config.max_pool_size:
                try:
                    conn = GraphDatabase.driver(
                        self.uri,
                        auth=(self.user, self.password),
                        max_connection_lifetime=self.config.idle_timeout
                    )
                    conn.verify_connectivity()
                    return conn
                except Exception as e:
                    raise ConnectionError(f"Failed to create connection: {e}")

        raise ConnectionError("Connection pool exhausted")

    def return_connection(self, conn):
        """归还连接"""
        with self.lock:
            if len(self.pool) < self.config.max_pool_size:
                self.pool.append(conn)
                self.pool_creation_times.append(time.time())

    def close_all(self):
        """关闭所有连接"""
        self._running = False
        with self.lock:
            for conn in self.pool:
                try:
                    conn.close()
                except Exception:
                    pass
            self.pool.clear()
            self.pool_creation_times.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计"""
        with self.lock:
            return {
                "current_size": len(self.pool),
                "max_size": self.config.max_pool_size,
                "pool_timeout": self.config.pool_timeout
            }


class CircuitBreaker:
    """断路器实现"""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.half_open_calls = 0
        self.lock = threading.Lock()

    def record_success(self):
        """记录成功"""
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
                if self.half_open_calls >= self.config.half_open_max_calls:
                    self._transition_to(CircuitState.CLOSED)
            elif self.failure_count > 0:
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self):
        """记录失败"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)

    def can_execute(self) -> bool:
        """检查是否可以执行"""
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time > self.config.recovery_timeout:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return self.half_open_calls < self.config.half_open_max_calls

            return False

    def _transition_to(self, new_state: CircuitState):
        """状态转换"""
        self.state = new_state
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.half_open_calls = 0

    def get_state(self) -> str:
        """获取状态"""
        return self.state.value


class EpisodeManager:
    """Episode 管理器 - 批量写入 + 去重"""

    def __init__(self, graphiti, config: EpisodeConfig):
        self.graphiti = graphiti
        self.config = config
        self.pending_episodes: List[Dict] = []
        self.last_batch_time = time.time()
        self.lock = threading.Lock()
        self.seen_names: set = set()
        self._flush_thread: Optional[threading.Thread] = None
        self._running = True
        self._start_flush_thread()

    def _start_flush_thread(self):
        """启动批量刷新线程"""
        def flush_loop():
            while self._running:
                time.sleep(self.config.max_batch_wait_ms / 1000.0)
                self._check_flush()
                if not self._running:
                    break

        self._flush_thread = threading.Thread(target=flush_loop, daemon=True)
        self._flush_thread.start()

    def _check_flush(self):
        """检查是否需要刷新"""
        with self.lock:
            if not self.pending_episodes:
                return

            time_since_last = (time.time() - self.last_batch_time) * 1000
            if (len(self.pending_episodes) >= self.config.batch_size or
                time_since_last >= self.config.max_batch_wait_ms):
                self._flush_batch()

    def _flush_batch(self):
        """刷新批量 episodes"""
        if not self.pending_episodes:
            return

        episodes_to_process = self.pending_episodes.copy()
        self.pending_episodes.clear()
        self.last_batch_time = time.time()

        asyncio.run(self._add_episodes_async(episodes_to_process))

    async def _add_episodes_async(self, episodes: List[Dict]):
        """异步添加 episodes"""
        success_count = 0
        failure_count = 0

        for episode in episodes:
            try:
                await self.graphiti.add_episode(
                    name=episode.get('name'),
                    content=episode.get('content'),
                    source_description=episode.get('source_description', ''),
                    reference_time=episode.get('reference_time', datetime.now(timezone.utc)),
                    update_communities=False
                )
                success_count += 1
            except Exception as e:
                failure_count += 1
                print(f"添加 Episode 失败 {episode.get('name')}: {e}")

        self.graphiti._metrics.episode_success_count += success_count
        self.graphiti._metrics.episode_failure_count += failure_count
        self.graphiti._metrics.episode_batch_count += 1

    def add(self, name: str, content: str, source_description: str = "",
            reference_time=None) -> bool:
        """添加 episode（批量处理）"""
        if self.config.deduplicate:
            if name in self.seen_names:
                return False
            self.seen_names.add(name)

        with self.lock:
            self.pending_episodes.append({
                'name': name,
                'content': content,
                'source_description': source_description,
                'reference_time': reference_time or datetime.now(timezone.utc)
            })

            if len(self.pending_episodes) >= self.config.batch_size:
                self._flush_batch()

            return True

    def flush(self):
        """强制刷新"""
        with self.lock:
            self._flush_batch()

    def stop(self):
        """停止管理器"""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)
        self.flush()

    def get_pending_count(self) -> int:
        """获取待处理数量"""
        with self.lock:
            return len(self.pending_episodes)


class GraphitiClientV2:
    """
    Graphiti 客户端 v2
    增强版图谱管理器，支持：
    - 三层降级（Neo4j Driver → Graphiti → NetworkX fallback）
    - 连接池管理
    - 断路器模式
    - 批量 Episode 写入 + 去重
    - 性能监控
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, neo4j_uri: str = None, neo4j_user: str = None, neo4j_password: str = None):
        if GraphitiClientV2._initialized:
            return

        from odap.infra.security import security_config
        self.neo4j_uri = neo4j_uri or security_config.NEO4J_URI
        self.neo4j_user = neo4j_user or security_config.NEO4J_USER
        self.neo4j_password = neo4j_password or security_config.NEO4J_PASSWORD

        self.graph = None
        self._connected = False
        self._mode = "fallback"

        self._connection_pool: Optional[ConnectionPool] = None
        self._circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        self._episode_manager: Optional[EpisodeManager] = None

        self._metrics = GraphitiClientMetrics()

        self._connection_config = ConnectionConfig()
        self._episode_config = EpisodeConfig()

        self.reserved_tasks = []

        self._connect()
        GraphitiClientV2._initialized = True

    def _connect(self):
        """三层降级连接"""
        if NEO4J_DRIVER_AVAILABLE:
            try:
                self._connection_pool = ConnectionPool(
                    self.neo4j_uri, self.neo4j_user, self.neo4j_password,
                    self._connection_config
                )
                test_driver = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password)
                )
                test_driver.verify_connectivity()
                test_driver.close()

                self._connected = True
                self._mode = "neo4j_driver"
                print(f"Neo4j Driver 直连成功: {self.neo4j_uri}")
                self._load_data_to_neo4j()
                return
            except Exception as e:
                print(f"Neo4j Driver 连接失败: {e}")

        if GRAPHITI_AVAILABLE:
            if self._init_graphiti_sync():
                self._mode = "graphiti"
                return

        self._use_fallback_mode()

    def _use_fallback_mode(self):
        """使用回退模式"""
        self._connected = False
        self._mode = "fallback"
        print("切换到回退模式（基于内存图谱）")
        import networkx as nx
        self.fallback_graph = nx.DiGraph()
        self._load_data_to_fallback()

    def _load_data_to_neo4j(self):
        """加载数据到 Neo4j"""
        data = load_simulation_data()
        all_entities = []
        all_entities.extend(data.get("locations", []))
        all_entities.extend(data.get("military_units", []))
        all_entities.extend(data.get("weapon_systems", []))
        all_entities.extend(data.get("civilian_infrastructure", []))

        with self._connection_pool.get_connection().session() as session:
            for entity in all_entities[:50]:
                try:
                    entity_id = entity["id"]
                    entity_type = entity.get("type", "Unknown").replace(' ', '_')
                    props = entity.get("properties", {})
                    labels = f"Entity:{entity_type}"
                    cypher = f"MERGE (n:{labels} {{id: $eid}}) SET n += $props"
                    session.run(cypher, eid=entity_id, props=props)
                except Exception as e:
                    print(f"加载实体失败 {entity_id}: {e}")

        print(f"Neo4j 数据加载完成: {len(all_entities[:50])} 个实体")

    def _load_data_to_fallback(self):
        """加载数据到回退模式"""
        data = load_simulation_data()
        for location in data.get("locations", []):
            self.fallback_graph.add_node(
                location["id"],
                entity_type=location["type"],
                **location["properties"]
            )
        for unit in data.get("military_units", []):
            self.fallback_graph.add_node(
                unit["id"],
                entity_type=unit["type"],
                **unit["properties"]
            )

    def _init_graphiti_sync(self) -> bool:
        """同步初始化 graphiti"""
        async def init_all():
            try:
                llm_client = self._create_llm_client()
                embedder = self._create_embedder()
                if not embedder:
                    return False

                self.graph = Graphiti(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                    llm_client=llm_client,
                    embedder=embedder,
                )

                await asyncio.wait_for(
                    self.graph.build_indices_and_constraints(delete_existing=False),
                    timeout=15.0
                )

                self._episode_manager = EpisodeManager(self.graph, self._episode_config)
                self._connected = True
                return True
            except Exception as e:
                print(f"Graphiti 初始化失败: {e}")
                return False

        try:
            return asyncio.run(init_all())
        except Exception as e:
            print(f"初始化失败: {e}")
            return False

    def _create_llm_client(self):
        """创建 LLM 客户端"""
        from graphiti_core.llm_client.config import LLMConfig
        from odap.infra.llm import ZhipuAIClient
        config = LLMConfig(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            temperature=0.7
        )
        return ZhipuAIClient(config=config)

    def _create_embedder(self):
        """创建 Embedder"""
        try:
            from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
            raw_base = OPENAI_API_BASE.rstrip('/')
            if '/chat/completions' in raw_base:
                embed_base = raw_base.split('/chat/completions')[0]
            else:
                embed_base = raw_base
            config = OpenAIEmbedderConfig(
                api_key=OPENAI_API_KEY,
                base_url=embed_base,
                embedding_model="Pro/BAAI/bge-m3"
            )
            return OpenAIEmbedder(config=config)
        except Exception as e:
            print(f"创建 Embedder 失败: {e}")
            return None

    def query_entities(self, entity_type=None, area=None):
        """查询实体"""
        start_time = time.time()
        try:
            if not self._circuit_breaker.can_execute():
                raise Exception("Circuit breaker is open")

            if self._mode == "neo4j_driver" and self._connection_pool:
                result = self._query_entities_neo4j(entity_type, area)
            elif self._mode == "graphiti" and self._connected:
                result = self._query_entities_graphiti(entity_type, area)
            else:
                result = self._query_entities_fallback(entity_type, area)

            self._circuit_breaker.record_success()
            self._metrics.query_times.append(time.time() - start_time)
            if len(self._metrics.query_times) > 100:
                self._metrics.query_times.pop(0)
            return result
        except Exception as e:
            self._circuit_breaker.record_failure()
            print(f"Query entities failed: {e}")
            return self._query_entities_fallback(entity_type, area)

    def _query_entities_neo4j(self, entity_type=None, area=None):
        """Neo4j 模式查询"""
        label = entity_type.replace(" ", "_") if entity_type else "Entity"
        cypher = f"MATCH (n:{label}) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"
        params = {"area": area} if area else {}

        conn = self._connection_pool.get_connection()
        try:
            with conn.session() as session:
                result = session.run(cypher, **params)
                return [
                    {
                        "id": record["id"],
                        "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                        "properties": record["props"]
                    }
                    for record in result
                ]
        finally:
            self._connection_pool.return_connection(conn)

    def _query_entities_fallback(self, entity_type=None, area=None):
        """回退模式查询"""
        result = []
        for node_id, node_data in self.fallback_graph.nodes(data=True):
            if entity_type and node_data.get("entity_type") != entity_type:
                continue
            if area and node_data.get("area") != area:
                continue
            result.append({
                "id": node_id,
                "type": node_data.get("entity_type"),
                "properties": {k: v for k, v in node_data.items() if k != "entity_type"}
            })
        return result

    def _query_entities_graphiti(self, entity_type=None, area=None):
        """Graphiti 模式查询"""
        async def query():
            episodes = await self.graph.retrieve_episodes(reference_time=datetime.now())
            result = []
            for episode in episodes:
                if entity_type and episode.name and entity_type.lower() not in episode.name.lower():
                    continue
                result.append({
                    "id": episode.name or str(episode.uuid),
                    "type": "Entity",
                    "properties": {"body": episode.content}
                })
            return result

        return asyncio.run(query())

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索实体"""
        if self._mode == "neo4j_driver" and self._connection_pool:
            return self._search_neo4j(query, limit)
        if self._mode == "graphiti" and self._connected:
            return self._search_graphiti(query, limit)
        return self._search_fallback(query, limit)

    def _search_neo4j(self, query: str, limit: int) -> List[Dict]:
        """Neo4j 搜索"""
        cypher = (
            "MATCH (n) WHERE n.id CONTAINS $q OR n.name CONTAINS $q "
            "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props LIMIT $lmt"
        )

        conn = self._connection_pool.get_connection()
        try:
            with conn.session() as session:
                result = session.run(cypher, q=query, lmt=limit)
                return [
                    {
                        "id": record["id"],
                        "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                        "properties": record["props"],
                    }
                    for record in result
                ]
        finally:
            self._connection_pool.return_connection(conn)

    def _search_fallback(self, query: str, limit: int) -> List[Dict]:
        """回退模式搜索"""
        if self.fallback_graph is None:
            return []
        results = []
        query_lower = query.lower()
        for node_id, data in self.fallback_graph.nodes(data=True):
            text = f"{node_id} {data.get('name', '')} {data.get('entity_type', '')}".lower()
            if query_lower in text:
                results.append({
                    "id": node_id,
                    "type": data.get("entity_type"),
                    "properties": {k: v for k, v in data.items() if k != "entity_type"}
                })
                if len(results) >= limit:
                    break
        return results

    def _search_graphiti(self, query: str, limit: int) -> List[Dict]:
        """Graphiti 搜索"""
        async def search():
            results = await self.graph.search(query=query, num_results=limit)
            return [
                {
                    "id": r.name or str(r.uuid),
                    "type": "EntityEdge",
                    "properties": {"fact": r.fact}
                }
                for r in results
            ]

        return asyncio.run(search())

    def search_hybrid(self, query_text: str, top_k: int = 5,
                     vector_weight: float = 0.7, keyword_weight: float = 0.3) -> List[Dict]:
        """混合检索（向量 + 关键词）"""
        if self._mode == "neo4j_driver" and self._connection_pool:
            return self._search_hybrid_neo4j(query_text, top_k, vector_weight, keyword_weight)
        if self._mode == "graphiti" and self._connected:
            return self._search_hybrid_graphiti(query_text, top_k, vector_weight, keyword_weight)
        return self._search_fallback(query_text, limit=top_k)

    def _search_hybrid_neo4j(self, query_text: str, top_k: int,
                            vector_weight: float, keyword_weight: float) -> List[Dict]:
        """Neo4j 混合检索"""
        vector_results = self._search_graphiti(query_text, top_k)
        keyword_results = self._search_neo4j(query_text, top_k)

        result_map = {}
        for i, r in enumerate(vector_results):
            result_id = r["id"]
            score = (top_k - i) / top_k * vector_weight
            result_map[result_id] = {**r, "score": score}

        for i, r in enumerate(keyword_results):
            result_id = r["id"]
            score = (top_k - i) / top_k * keyword_weight
            if result_id in result_map:
                result_map[result_id]["score"] += score
            else:
                result_map[result_id] = {**r, "score": score}

        sorted_results = sorted(result_map.values(), key=lambda x: x["score"], reverse=True)[:top_k]
        return sorted_results

    def _search_hybrid_graphiti(self, query_text: str, top_k: int,
                               vector_weight: float, keyword_weight: float) -> List[Dict]:
        """Graphiti 混合检索"""
        return self._search_hybrid_neo4j(query_text, top_k, vector_weight, keyword_weight)

    def query_temporal(self, valid_time=None, transaction_time=None, entity_type=None) -> List[Dict]:
        """双时态查询"""
        if self._use_fallback or not self._connected:
            return self.query_entities(entity_type)

        async def temporal_query():
            episodes = await self.graph.retrieve_episodes(
                reference_time=datetime.now(),
                valid_time=valid_time,
                transaction_time=transaction_time
            )
            result = []
            for episode in episodes:
                if entity_type and episode.name and entity_type.lower() not in episode.name.lower():
                    continue
                result.append({
                    "id": episode.name or str(episode.uuid),
                    "type": "Entity",
                    "properties": {"body": episode.content},
                    "valid_time": str(episode.created_at),
                    "transaction_time": str(episode.created_at)
                })
            return result

        return asyncio.run(temporal_query())

    async def add_episode(self, name: str, content: str,
                         source_description: str = "", reference_time=None) -> bool:
        """添加 Episode"""
        if self._mode == "graphiti" and self._connected and self._episode_manager:
            return self._episode_manager.add(name, content, source_description, reference_time)
        return False

    def add_episodes_batch(self, episodes: List[Dict]) -> Dict[str, Any]:
        """批量添加 Episodes"""
        if self._mode == "graphiti" and self._connected and self._episode_manager:
            for ep in episodes:
                self._episode_manager.add(
                    ep.get('name'),
                    ep.get('content'),
                    ep.get('source_description', ''),
                    ep.get('reference_time')
                )
            self._episode_manager.flush()
            return {
                "success": len(episodes),
                "failed": 0,
                "pending": self._episode_manager.get_pending_count()
            }
        return {"success": 0, "failed": len(episodes), "error": "Not in graphiti mode"}

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._mode == "neo4j_driver" and self._connection_pool:
            return self._get_statistics_neo4j()
        if self._mode == "graphiti" and self._connected:
            return self._get_statistics_graphiti()
        return self._get_statistics_fallback()

    def _get_statistics_fallback(self) -> Dict[str, Any]:
        return {
            "total_entities": self.fallback_graph.number_of_nodes(),
            "total_relationships": self.fallback_graph.number_of_edges(),
            "mode": "fallback"
        }

    def _get_statistics_neo4j(self) -> Dict[str, Any]:
        conn = self._connection_pool.get_connection()
        try:
            with conn.session() as session:
                total = session.run("MATCH (n:Entity) RETURN count(n) AS cnt").single()["cnt"]
                return {
                    "total_entities": total,
                    "mode": "neo4j_driver",
                    "connection_pool": self._connection_pool.get_stats(),
                    "circuit_breaker": self._circuit_breaker.get_state()
                }
        finally:
            self._connection_pool.return_connection(conn)

    def _get_statistics_graphiti(self) -> Dict[str, Any]:
        return {
            "mode": "graphiti",
            "circuit_breaker": self._circuit_breaker.get_state()
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        query_times = self._metrics.query_times
        return {
            "query_times": {
                "average": sum(query_times) / len(query_times) if query_times else 0,
                "max": max(query_times) if query_times else 0,
                "count": len(query_times)
            },
            "cache": {
                "hits": self._metrics.cache_hits,
                "misses": self._metrics.cache_misses,
            },
            "circuit_breaker": {
                "state": self._circuit_breaker.get_state(),
                "failure_count": self._circuit_breaker.failure_count
            },
            "episode_manager": {
                "batch_count": self._metrics.episode_batch_count,
                "success_count": self._metrics.episode_success_count,
                "failure_count": self._metrics.episode_failure_count,
                "pending": self._episode_manager.get_pending_count() if self._episode_manager else 0
            }
        }

    def reserve_task(self, task_data: Dict) -> str:
        """预留任务"""
        import uuid
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        task_data["id"] = task_id
        task_data["status"] = "reserved"
        task_data["created_at"] = datetime.now().isoformat()
        self.reserved_tasks.append(task_data)
        return task_id

    def close(self):
        """关闭客户端"""
        if self._connection_pool:
            self._connection_pool.close_all()
        if self._episode_manager:
            self._episode_manager.stop()
