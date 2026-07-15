"""
基于graphiti的图谱管理模块
使用Neo4j作为图数据库，支持时序知识图谱特性

三层模式降级：
1. Neo4j Driver 直连（无需 graphiti-core，直接 Cypher 操作）
2. Graphiti（双时态知识图谱，需要 graphiti-core + Neo4j）
3. NetworkX fallback（纯内存，无外部依赖）

解决方案：在单个 asyncio.run() 中完成所有 graphiti 操作
"""

import sys
import os
import json
import asyncio
import time
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import deque

from odap.infra.config_composer import get_config
from odap.infra.security.audit_helper import graph_audit
from ._utils import _run_async
from .cache_mixin import CacheMixin
from .entity_ops import EntityOpsMixin
from .relationship_ops import RelationshipOpsMixin
from .temporal_ops import TemporalOpsMixin
from .search_ops import SearchOpsMixin

from odap.infra.observability.instruments import graphiti_span


import logging

logger = logging.getLogger(__name__)
# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# 获取配置
OPENAI_API_KEY = get_config("llm.api_key", "")
OPENAI_API_BASE = get_config("llm.api_base", "https://api.openai.com/v1")
OPENAI_MODEL = get_config("llm.model", "gpt-4")

# 然后再添加项目路径并导入其他模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# P0-3 fix (R-P0-006): do NOT import from `odap.biz.core.ontology.design.*`
# (the design subsystem is upper-layer). `load_simulation_data` is a simple
# file reader for a local test fixture; inline the implementation here.
def _load_simulation_data_local():
    """Local copy of the simulation data loader. Reads a JSON fixture from
    the infra/graph directory (originally bundled in design/mock_data/).

    This is a pure file read with no dependencies on the ontology design
    subsystem, so it can live here safely.
    """
    try:
        fixture_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "simulation_data.json",
        )
        with open(fixture_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        # Fixture not present: return an empty dict so callers can degrade gracefully
        logger.warning(
            "simulation_data.json not found at %s — returning empty dict. "
            "Graph service will operate on an empty graph.",
            fixture_path,
        )
        return {}


# Public alias used throughout this module (replaces the design import)
load_simulation_data = _load_simulation_data_local

# 尝试导入 graphiti-core（可选）
try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EntityNode, EpisodicNode
    from graphiti_core.edges import Edge, EntityEdge
    from graphiti_core.embedder.client import EmbedderClient
    GRAPHITI_AVAILABLE = True
except ImportError as e:
    GRAPHITI_AVAILABLE = False
    logger.info(f'提示: graphiti-core 未安装 ({e})，Graphiti 模式不可用')

# 尝试导入 neo4j driver（可选）
try:
    from neo4j import GraphDatabase
    NEO4J_DRIVER_AVAILABLE = True
except ImportError as e:
    NEO4J_DRIVER_AVAILABLE = False
    logger.info(f'提示: neo4j driver 未安装 ({e})，Neo4j 直连模式不可用')


class GraphManager(CacheMixin, EntityOpsMixin, RelationshipOpsMixin, TemporalOpsMixin, SearchOpsMixin):
    """
    图谱管理器
    基于graphiti的时序知识图谱，支持动态更新和混合检索
    使用单例模式确保所有实例共享同一个图谱

    操作方法通过 Mixin 类提供：
    - CacheMixin: 缓存管理 (_cache_get, _cache_set, invalidate_cache 等)
    - EntityOpsMixin: 实体 CRUD (add_entity, query_entities, update_entity 等)
    - RelationshipOpsMixin: 关系操作 (add_relationship, get_all_relations 等)
    - TemporalOpsMixin: 时态查询 (query_temporal 等)
    - SearchOpsMixin: 搜索与遍历 (search, traverse, get_neighbors 等)
    """

    _instance = None
    _initialized = False
    _test_mode = False  # 仅在单元测试中允许 NetworkX fallback

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, neo4j_uri: str = None,
                 neo4j_user: str = None,
                 neo4j_password: str = None):
        """
        初始化图谱管理器

        两层连接策略：
        1. Graphiti — 双时态知识图谱，需要 graphiti-core + Neo4j
        2. Neo4j Driver 直连 — 无需 graphiti-core，Cypher 直接操作

        当 Neo4j 不可用时，不再自动降级到 NetworkX，
        而是返回明确的错误信息。仅在 _test_mode=True 时允许 NetworkX fallback。
        """
        if GraphManager._initialized:
            return

        self.graph: Optional[Graphiti] = None
        # 从安全配置模块读取，确保能够正确获取值
        from odap.infra.security import security_config
        self.neo4j_uri = neo4j_uri or security_config.NEO4J_URI
        self.neo4j_user = neo4j_user or security_config.NEO4J_USER
        # P0-8 fix: use lazy-validated method that raises on placeholder in prod
        self.neo4j_password = neo4j_password or security_config.get_neo4j_password()
        self.neo4j_driver = None
        self.fallback_graph = None
        self.reserved_tasks = []
        self._connected = False
        self._use_fallback = True
        self._mode = "fallback"
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_interval = 10

        # 连接池配置
        self.max_pool_size = 20
        self.pool_timeout = 30  # 秒
        self.idle_timeout = 300  # 秒
        self.pool = []
        self.pool_creation_times = []

        # 断路器配置
        self.failure_threshold = 5
        self.recovery_timeout = 60  # 秒
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = 0

        # 性能监控
        self.query_times = deque(maxlen=100)
        self.cache_hits = 0
        self.cache_misses = 0

        # LRU 查询缓存
        self._query_cache: Dict[str, Any] = {}
        self._query_cache_timestamps: Dict[str, float] = {}
        self._cache_max_size = 256
        self._cache_ttl = 300  # 秒

        # 时间索引（用于加速双时态查询）
        self._temporal_index: Dict[str, List[Dict]] = {}
        self._temporal_index_built = False

        # 尝试三层降级
        self._connect()

        GraphManager._initialized = True

    def _connect(self):
        """
        两层连接策略：Graphiti → Neo4j Driver

        Graphiti 是核心功能（双时态知识图谱），必须优先尝试。
        仅当 graphiti-core 未安装或 Neo4j 不可用时尝试 Neo4j Driver。
        当两者都不可用时，不再自动降级到 NetworkX（除非 _test_mode=True）。
        """
        # 第一层：Graphiti（双时态知识图谱，核心功能）
        if GRAPHITI_AVAILABLE:
            if self._init_graphiti_sync():
                self._mode = "graphiti"
                return
            logger.info('Graphiti 初始化失败，尝试下一层')

        # 第二层：Neo4j Driver 直连（无 graphiti-core，Cypher 直接操作）
        if NEO4J_DRIVER_AVAILABLE:
            try:
                self.neo4j_driver = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password),
                    connection_timeout=5.0
                )
                import socket
                socket.setdefaulttimeout(10)
                self.neo4j_driver.verify_connectivity()
                self._connected = True
                self._use_fallback = False
                self._mode = "neo4j_driver"
                logger.info(f'Neo4j Driver 直连成功: {self.neo4j_uri}')
                self._load_data_to_neo4j()
                self._migrate_entities()
                return
            except Exception as e:
                logger.info(f'Neo4j Driver 连接失败: {e}')
                if self.neo4j_driver:
                    self.neo4j_driver.close()
                    self.neo4j_driver = None

        # Neo4j 不可用：仅在测试模式下使用 NetworkX fallback
        if self._test_mode:
            self._use_fallback_mode()
        else:
            logger.info('图数据库服务不可用，所有查询操作将返回错误')
            self._connected = False
            self._use_fallback = False
            self._mode = "unavailable"

    def _try_reconnect(self):
        if self._mode != "fallback":
            return True
        if getattr(self, '_reconnect_attempts', 0) >= getattr(self, '_max_reconnect_attempts', 3):
            return False
        if not NEO4J_DRIVER_AVAILABLE:
            return False
        self._reconnect_attempts = getattr(self, '_reconnect_attempts', 0) + 1
        max_attempts = getattr(self, '_max_reconnect_attempts', 3)
        logger.info(f'尝试重连 Neo4j ({self._reconnect_attempts}/{max_attempts})...')
        try:
            driver = GraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
                connection_timeout=5.0
            )
            driver.verify_connectivity()
            self.neo4j_driver = driver
            self._connected = True
            self._use_fallback = False
            self._mode = "neo4j_driver"
            self.fallback_graph = None
            logger.info(f'Neo4j 重连成功，模式: neo4j_driver')
            return True
        except Exception as e:
            logger.info(f'Neo4j 重连失败: {e}')
            return False

    from odap.infra.monitoring import monitor_performance

    @monitor_performance('database_queries', 'load_data_to_neo4j')
    def _load_data_to_neo4j(self):
        """将模拟数据加载到 Neo4j（通过 Cypher）"""
        if not self.neo4j_driver:
            return
        data = load_simulation_data()

        with self.neo4j_driver.session() as session:
            # 创建唯一性约束
            try:
                session.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
            except Exception:
                pass  # 约束可能已存在

            all_entities = []
            all_entities.extend(data.get("locations", []))
            all_entities.extend(data.get("units", []))
            all_entities.extend(data.get("equipment", []))
            all_entities.extend(data.get("civilian_infrastructure", []))

            # 批量加载数据，提高性能
            batch_size = 100
            batches = [all_entities[i:i+batch_size] for i in range(0, len(all_entities), batch_size)]
            count = 0

            for batch in batches:
                try:
                    # 为每个实体类型生成单独的批量操作
                    # 按实体类型分组
                    entities_by_type = {}
                    for entity in batch:
                        entity_type = entity.get("type", "Unknown").replace(' ', '_')
                        if entity_type not in entities_by_type:
                            entities_by_type[entity_type] = []
                        entities_by_type[entity_type].append(entity)

                    # 对每种类型执行批量操作
                    for entity_type, entities in entities_by_type.items():
                        safe_type = entity_type.replace(' ', '_')
                        self._validate_label(safe_type)
                        entity_type_id = entity_type.lower().replace(' ', '_')
                        if re.search(r'[\u4e00-\u9fff]', entity_type_id):
                            entity_type_id = "zh_type"
                        self._validate_label(entity_type_id)
                        labels = f"Entity:{safe_type}:EntityType:{entity_type_id}"
                        cypher = f"""
                        UNWIND $entities AS entity
                        MERGE (n:{labels} {{id: entity.id}})
                        SET n += entity.properties
                        """
                        params = {
                            "entities": [
                                {
                                    "id": entity["id"],
                                    "properties": {
                                        **entity.get("properties", {}),
                                        "workspace_id": entity.get("properties", {}).get("workspace_id", "default"),
                                        "entity_type_id": entity_type_id,
                                    }
                                }
                                for entity in entities
                            ]
                        }
                        result = session.run(cypher, **params)
                        count += len(entities)
                except Exception as e:
                    logger.info(f'  Neo4j 批量加载失败: {e}')
                    # 批量失败后尝试单个加载
                    for entity in batch:
                        try:
                            entity_id = entity["id"]
                            entity_type = entity.get("type", "Unknown")
                            props = entity.get("properties", {})
                            if "workspace_id" not in props:
                                props["workspace_id"] = "default"
                            safe_type = entity_type.replace(' ', '_')
                            self._validate_label(safe_type)
                            entity_type_id = entity_type.lower().replace(' ', '_')
                            if re.search(r'[\u4e00-\u9fff]', entity_type_id):
                                entity_type_id = "zh_type"
                            self._validate_label(entity_type_id)
                            labels = f"Entity:{safe_type}:EntityType:{entity_type_id}"
                            cypher = f"MERGE (n:{labels} {{id: $eid}}) SET n += $props"
                            props["entity_type_id"] = entity_type_id
                            session.run(cypher, eid=entity_id, props=props)
                            count += 1
                        except Exception as e2:
                            logger.info(f'  Neo4j 加载实体失败 {entity_id}: {e2}')

            logger.info(f'Neo4j 数据加载完成: {count} 个实体')

    def _close_neo4j(self):
        """关闭 Neo4j Driver"""
        if self.neo4j_driver:
            try:
                self.neo4j_driver.close()
            except Exception:
                pass

    def _get_connection(self):
        """
        从连接池获取连接
        实现断路器逻辑
        """
        # 检查断路器状态
        if self._check_circuit():
            raise Exception("Circuit is open, please try again later")

        # 清理过期连接
        self._cleanup_pool()

        # 从池获取连接
        if self.pool:
            conn = self.pool.pop(0)
            self.pool_creation_times.pop(0)
            return conn

        # 池为空且未达到最大连接数，创建新连接
        if len(self.pool) < self.max_pool_size:
            try:
                conn = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password)
                )
                conn.verify_connectivity()
                return conn
            except Exception as e:
                self._record_failure()
                raise e

        # 池已满，等待
        start_time = time.time()
        while time.time() - start_time < self.pool_timeout:
            self._cleanup_pool()
            if self.pool:
                conn = self.pool.pop(0)
                self.pool_creation_times.pop(0)
                return conn
            time.sleep(0.1)

        raise Exception(f"Connection pool timeout after {self.pool_timeout} seconds")

    def _return_connection(self, conn):
        """
        将连接返回连接池
        """
        if conn:
            self.pool.append(conn)
            self.pool_creation_times.append(time.time())

    def _cleanup_pool(self):
        """
        清理过期的连接
        """
        current_time = time.time()
        valid_indices = []
        for i, creation_time in enumerate(self.pool_creation_times):
            if current_time - creation_time < self.idle_timeout:
                valid_indices.append(i)
            else:
                # 关闭过期连接
                try:
                    self.pool[i].close()
                except Exception:
                    pass

        # 保留有效的连接
        self.pool = [self.pool[i] for i in valid_indices]
        self.pool_creation_times = [self.pool_creation_times[i] for i in valid_indices]

    def _check_circuit(self):
        """
        检查断路器状态
        """
        if not self.circuit_open:
            return False

        # 检查是否可以恢复
        if time.time() - self.last_failure_time > self.recovery_timeout:
            self.circuit_open = False
            self.failure_count = 0
            return False

        return True

    def _record_failure(self):
        """
        记录失败，更新断路器状态
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.circuit_open = True
            logger.info(f'Circuit opened after {self.failure_count} failures')

    def _record_success(self):
        """
        记录成功，重置失败计数
        """
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
        if self.circuit_open:
            # 尝试半开状态
            self.circuit_open = False
            logger.info('Circuit closed, trying to recover')

    def get_performance_metrics(self):
        """
        获取性能监控指标
        """
        if self.query_times:
            avg_query_time = sum(self.query_times) / len(self.query_times)
            max_query_time = max(self.query_times)
            min_query_time = min(self.query_times)
        else:
            avg_query_time = 0
            max_query_time = 0
            min_query_time = 0

        total_cache = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / total_cache if total_cache > 0 else 0

        return {
            "query_times": {
                "average": avg_query_time,
                "max": max_query_time,
                "min": min_query_time,
                "count": len(self.query_times)
            },
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": cache_hit_rate
            },
            "connection_pool": {
                "current_size": len(self.pool),
                "max_size": self.max_pool_size
            },
            "circuit_breaker": {
                "is_open": self.circuit_open,
                "failure_count": self.failure_count,
                "failure_threshold": self.failure_threshold
            }
        }

    def _create_llm_client(self):
        """创建LLM客户端（使用智谱AI适配器）"""
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
        """创建 Embedder（兼容 SiliconFlow 等 OpenAI 兼容 API）"""
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
            logger.info(f'创建 Embedder 失败: {e}')
            return None

    def _use_fallback_mode(self):
        """
        使用回退模式（仅测试模式下允许）

        生产环境下，当 Neo4j 不可用时不再静默降级到 NetworkX，
        而是返回明确的错误信息。
        """
        if not self._test_mode:
            logger.info('图数据库服务不可用，拒绝降级到 NetworkX 回退模式')
            self._connected = False
            self._use_fallback = False
            self._mode = "unavailable"
            return

        self._connected = False
        self._use_fallback = True
        logger.info('测试模式：切换到回退模式（基于内存图谱）')
        import networkx as nx
        self.fallback_graph = nx.DiGraph()
        self._load_data_to_fallback()

    @staticmethod
    def _unavailable_error() -> Dict[str, Any]:
        """返回图数据库不可用的标准错误"""
        return {"status": "error", "message": "图数据库服务不可用，请稍后重试"}

    def _load_data_to_fallback(self):
        """
        将模拟数据加载到回退模式的图谱中
        """
        data = load_simulation_data()
        for location in data.get("locations", []):
            self.fallback_graph.add_node(
                location["id"],
                entity_type=location["type"],
                **location["properties"]
            )
        for unit in data.get("units", []):
            self.fallback_graph.add_node(
                unit["id"],
                entity_type=unit["type"],
                **unit["properties"]
            )
        for weapon in data.get("equipment", []):
            self.fallback_graph.add_node(
                weapon["id"],
                entity_type=weapon["type"],
                **weapon["properties"]
            )
        for infra in data.get("civilian_infrastructure", []):
            self.fallback_graph.add_node(
                infra["id"],
                entity_type=infra["type"],
                **infra["properties"]
            )

    def init_graphiti_async(self):
        """
        异步初始化 graphiti（在后台线程中运行）
        """
        import threading

        def run_init():
            success = self._init_graphiti_sync()
            if success:
                logger.info('Graphiti + Neo4j 初始化成功！')
            else:
                logger.info('Graphiti + Neo4j 初始化失败，使用回退模式')

        thread = threading.Thread(target=run_init, daemon=True)
        thread.start()

    def initialize_graph(self):
        """
        同步初始化图谱（回退模式）
        """
        pass

    def _init_graphiti_sync(self) -> bool:
        """
        初始化 Graphiti：快速验证连接，同时建立 Neo4j Driver 用于直接操作
        """
        async def init_core():
            try:
                logger.info('创建LLM客户端...')
                llm_client = self._create_llm_client()
                embedder = self._create_embedder()
                if not embedder:
                    logger.info('Embedder 创建失败，Graphiti 模式不可用')
                    return False

                logger.info(f'创建Graphiti实例连接到 {self.neo4j_uri}...')
                self.graph = Graphiti(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                    llm_client=llm_client,
                    embedder=embedder,
                )

                logger.info('验证 Neo4j 连接...')
                try:
                    await asyncio.wait_for(
                        self.graph.build_indices_and_constraints(delete_existing=False),
                        timeout=15.0
                    )
                except asyncio.TimeoutError:
                    logger.info('Neo4j 连接超时（15s），Graphiti 模式不可用')
                    return False

                logger.info('索引和约束构建完成')

                if NEO4J_DRIVER_AVAILABLE:
                    try:
                        self.neo4j_driver = GraphDatabase.driver(
                            self.neo4j_uri,
                            auth=(self.neo4j_user, self.neo4j_password),
                            connection_timeout=5.0
                        )
                        self.neo4j_driver.verify_connectivity()
                        logger.info('Graphiti 模式: Neo4j Driver 辅助连接已建立')
                    except Exception as e:
                        logger.info(f'Graphiti 模式: Neo4j Driver 辅助连接失败: {e}')

                self._load_data_to_neo4j()
                self._migrate_entities()

                self._connected = True
                self._use_fallback = False

                return True

            except Exception as e:
                logger.info(f'Graphiti初始化失败: {e}')
                return False

        try:
            return _run_async(init_core())
        except Exception as e:
            logger.info(f'初始化失败: {e}')
            return False

    def _create_episode_text(self, entity_data: Dict) -> str:
        """将实体数据转换为自然语言描述"""
        entity_id = entity_data.get("id", "")
        entity_type = entity_data.get("type", "")
        props = entity_data.get("properties", {})

        parts = [f"{entity_id} 是一个 {entity_type}"]
        for key, value in props.items():
            if key not in ["name", "type"]:
                parts.append(f"它的 {key} 是 {value}")

        return "。".join(parts)

    async def _add_episodes_to_graphiti(self):
        """将数据添加到 graphiti"""
        data = load_simulation_data()
        reference_time = datetime.now(timezone.utc)

        all_entities = []
        all_entities.extend(data.get("locations", []))
        all_entities.extend(data.get("units", []))
        all_entities.extend(data.get("equipment", []))
        all_entities.extend(data.get("civilian_infrastructure", []))

        success_count = 0
        error_count = 0

        for entity in all_entities[:20]:
            episode_text = self._create_episode_text(entity)
            try:
                await self.graph.add_episode(
                    name=entity.get("id", "unknown"),
                    episode_body=episode_text,
                    source_description=f"数据: {entity.get('type')}",
                    reference_time=reference_time,
                    update_communities=False
                )
                logger.info(f"  添加实体: {entity.get('id')}")
                success_count += 1
            except Exception as e:
                logger.info(f"  添加实体失败 {entity.get('id')}: {e}")
                error_count += 1

        logger.info(f'实体添加完成: 成功 {success_count}, 失败 {error_count}')

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息

        Returns:
            统计信息字典
        """
        try:
            if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
                result = self._get_statistics_neo4j()
            elif self._test_mode and self._use_fallback:
                result = self._get_statistics_fallback()
            else:
                result = self._unavailable_error()
            if isinstance(result, dict):
                graph_audit(
                    "graph_get_statistics_success",
                    resource="graph_engine",
                    details={
                        "total_entities": result.get("total_entities", 0),
                        "total_relationships": result.get("total_relationships", 0),
                        "mode": result.get("mode", str(self._mode)),
                        "entity_type_count": len(result.get("entity_types", {})) if isinstance(result.get("entity_types"), dict) else 0,
                    },
                )
            return result
        except Exception as e:
            graph_audit(
                "graph_get_statistics_failed",
                result_status="failure",
                result_message=str(e),
                resource="graph_engine",
                details={},
            )
            raise

    def get_graph_statistics(self) -> Dict[str, Any]:
        """别名，保持向后兼容"""
        return self.get_statistics()

    def _get_statistics_fallback(self) -> Dict[str, Any]:
        """回退模式：获取统计信息"""
        return {
            "total_entities": self.fallback_graph.number_of_nodes(),
            "total_relationships": self.fallback_graph.number_of_edges(),
            "entity_types": self._count_entity_types(),
            "mode": "fallback"
        }

    def _get_statistics_neo4j(self) -> Dict[str, Any]:
        """Neo4j Driver 模式：获取统计信息"""
        try:
            with self.neo4j_driver.session() as session:
                total = session.run("MATCH (n:Entity) RETURN count(n) AS cnt").single()["cnt"]
                type_result = session.run(
                    "MATCH (n:Entity) "
                    "UNWIND labels(n) AS lbl "
                    "WITH lbl, count(n) AS cnt "
                    "WHERE lbl <> 'Entity' "
                    "RETURN lbl AS type, cnt"
                )
                entity_types = {record["type"]: record["cnt"] for record in type_result}
                return {
                    "total_entities": total,
                    "total_relationships": 0,
                    "entity_types": entity_types,
                    "mode": self._mode,
                }
        except Exception as e:
            logger.info(f'Neo4j 统计失败: {e}')
            if self._test_mode and self._use_fallback:
                return self._get_statistics_fallback()
            return self._unavailable_error()

    def _get_statistics_graphiti(self) -> Dict[str, Any]:
        """Graphiti模式：获取统计信息"""
        async def get_stats():
            try:
                episodes = await self.graph.retrieve_episodes(
                    reference_time=datetime.now()
                )
                return {
                    "total_entities": len(episodes),
                    "total_relationships": 0,
                    "entity_types": {"EpisodicNode": len(episodes)},
                    "mode": "graphiti"
                }
            except Exception as e:
                logger.info(f'获取统计信息失败: {e}')
                if self._test_mode and self._use_fallback:
                    return self._get_statistics_fallback()
                return self._unavailable_error()

        return _run_async(get_stats())

    def _count_entity_types(self) -> Dict[str, int]:
        """统计各类型实体数量"""
        counts = {}
        for _, data in self.fallback_graph.nodes(data=True):
            entity_type = data.get("entity_type", "Unknown")
            counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts

    def _migrate_entities(self):
        """补齐存量实体缺失的 workspace_id 和 name 属性"""
        if not self.neo4j_driver:
            return
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (n:AuditLog)
                    WHERE n.name IS NULL OR n.name = ''
                    SET n.name = coalesce('审计日志_' + n.action, '审计日志')
                    RETURN count(n) AS updated
                """)
                record = result.single()
                if record and record["updated"] > 0:
                    logger.info(f"审计实体迁移完成: {record['updated']} 个实体已补齐 name")

                result = session.run("""
                    MATCH (n:Entity)
                    WHERE n.workspace_id IS NULL
                    SET n.workspace_id = 'default'
                    RETURN count(n) AS updated
                """)
                record = result.single()
                if record and record["updated"] > 0:
                    logger.info(f"实体 workspace_id 迁移完成: {record['updated']} 个实体已补齐 workspace_id")

                result = session.run("""
                    MATCH (n:AuditUser)
                    WHERE n.workspace_id IS NULL
                    SET n.workspace_id = 'default'
                    RETURN count(n) AS updated
                """)
                record = result.single()
                if record and record["updated"] > 0:
                    logger.info(f"审计用户 workspace_id 迁移完成: {record['updated']} 个实体已补齐 workspace_id")

                result = session.run("""
                    MATCH (n:AuditResource)
                    WHERE n.workspace_id IS NULL
                    SET n.workspace_id = 'default'
                    RETURN count(n) AS updated
                """)
                record = result.single()
                if record and record["updated"] > 0:
                    logger.info(f"审计资源 workspace_id 迁移完成: {record['updated']} 个实体已补齐 workspace_id")

                result = session.run("""
                    MATCH (n:AuditService)
                    WHERE n.workspace_id IS NULL
                    SET n.workspace_id = 'default'
                    RETURN count(n) AS updated
                """)
                record = result.single()
                if record and record["updated"] > 0:
                    logger.info(f"审计服务 workspace_id 迁移完成: {record['updated']} 个实体已补齐 workspace_id")
        except Exception as e:
            logger.info(f'实体迁移失败: {e}')

    @staticmethod
    def _validate_label(label: str) -> str:
        """Validate Neo4j label against injection. Only allow alphanumeric + underscore."""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', label):
            raise ValueError(f"Invalid Neo4j label: {label}")
        return label

    @staticmethod
    def _validate_property_key(key: str) -> str:
        """Validate Neo4j property key against injection. Only allow alphanumeric + underscore."""
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
            raise ValueError(f"Invalid Neo4j property key: {key}")
        return key

    @staticmethod
    def _sanitize_neo4j_properties(properties: Dict[str, Any]) -> Dict[str, Any]:
        """清洗属性值，确保仅包含 Neo4j 兼容类型 (str, int, float, bool, list of primitives)"""
        result = {}
        for key, value in properties.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                result[key] = value
            elif isinstance(value, (list, tuple)):
                sane_list = []
                for item in value:
                    if isinstance(item, (str, int, float, bool)):
                        sane_list.append(item)
                    else:
                        sane_list.append(str(item))
                if sane_list:
                    result[key] = sane_list
            elif isinstance(value, dict):
                for sub_k, sub_v in value.items():
                    if isinstance(sub_v, (str, int, float, bool)):
                        result[f"{key}_{sub_k}"] = sub_v
                    elif sub_v is not None:
                        result[f"{key}_{sub_k}"] = str(sub_v)
            else:
                result[key] = str(value)
        return result

    def reserve_task(self, task_data: Dict) -> str:
        """
        预留任务，分配唯一任务ID

        Args:
            task_data: 任务数据字典

        Returns:
            任务ID
        """
        import uuid

        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        task_data["id"] = task_id
        task_data["status"] = "reserved"
        task_data["created_at"] = datetime.now().isoformat()
        self.reserved_tasks.append(task_data)
        logger.info(f'任务已预留: {task_id}')
        graph_audit(
            "graph_reserve_task_success",
            resource=task_id,
            details={
                "task_id": task_id,
                "task_keys": list(task_data.keys())[:20],
                "total_reserved": len(self.reserved_tasks),
            },
        )
        return task_id

    def get_reserved_tasks(self) -> List[Dict]:
        """
        获取所有预留任务

        Returns:
            预留任务列表
        """
        return list(self.reserved_tasks)

    def clear_reserved_tasks(self) -> None:
        """
        清空所有预留任务
        """
        self.reserved_tasks.clear()
        logger.info('所有预留任务已清空')

    def clear_graph(self) -> Dict[str, Any]:
        """
        清空图谱中的所有数据（仅 Neo4j 模式）

        Returns:
            清空结果统计
        """
        if not self.neo4j_driver:
            graph_audit(
                "graph_clear_graph_failed",
                result_status="failure",
                result_message="no neo4j driver",
                resource="graph_engine",
                details={},
            )
            return {"status": "no_neo4j", "cleared": 0}

        try:
            with self.neo4j_driver.session() as session:
                before_nodes = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
                before_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]

                session.run("MATCH (n) DETACH DELETE n")

                after_nodes = session.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
                after_rels = session.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]

                cleared_nodes = before_nodes - after_nodes
                cleared_rels = before_rels - after_rels

                logger.info(f'图谱清空完成: 删除了 {cleared_nodes} 个节点和 {cleared_rels} 条关系')
                result = {
                    "status": "success",
                    "cleared_nodes": cleared_nodes,
                    "cleared_relationships": cleared_rels,
                    "remaining_nodes": after_nodes,
                    "remaining_relationships": after_rels
                }
                graph_audit(
                    "graph_clear_graph_success",
                    resource="graph_engine",
                    details={
                        "cleared_nodes": cleared_nodes,
                        "cleared_relationships": cleared_rels,
                        "remaining_nodes": after_nodes,
                        "remaining_relationships": after_rels,
                    },
                )
                return result

        except Exception as e:
            logger.info(f'图谱清空失败: {e}')
            graph_audit(
                "graph_clear_graph_failed",
                result_status="failure",
                result_message=str(e),
                resource="graph_engine",
                details={},
            )
            return {"status": "error", "error": str(e), "cleared": 0}

    async def add_episode(self, name: str, content: str,
                    source_description: str = "",
                    reference_time=None) -> bool:
        try:
            if self._use_fallback or not self._connected:
                graph_audit(
                    "graph_add_episode_failed",
                    result_status="failure",
                    result_message="fallback or not connected",
                    resource=name[:100],
                    details={"name_len": len(name), "content_len": len(content)},
                )
                return False

            if reference_time is None:
                reference_time = datetime.now(timezone.utc)

            if self.graph is None:
                logger.info('Graphiti 未初始化，无法添加 Episode')
                graph_audit(
                    "graph_add_episode_failed",
                    result_status="failure",
                    result_message="graph not initialized",
                    resource=name[:100],
                    details={"name_len": len(name), "content_len": len(content)},
                )
                return False

            with graphiti_span("add_episode", "graphiti",
                              attributes={"graphiti.entity_name": name[:100]}):
                await self.graph.add_episode(
                    name=name,
                    episode_body=content,
                    source_description=source_description,
                    reference_time=reference_time,
                    update_communities=False,
                )
            graph_audit(
                "graph_add_episode_success",
                resource=name[:100],
                details={
                    "name_len": len(name),
                    "content_len": len(content),
                    "has_source_description": bool(source_description),
                    "has_reference_time": bool(reference_time),
                },
            )
            return True
        except Exception as e:
            logger.info(f'Graphiti 添加 Episode 失败: {e}')
            graph_audit(
                "graph_add_episode_failed",
                result_status="failure",
                result_message=str(e),
                resource=name[:100],
                details={"name_len": len(name), "content_len": len(content)},
            )
            return False

    def add_episodes_batch(self, episodes: List[Dict], batch_size: int = 10) -> Dict[str, Any]:
        """
        批量添加 Episode 到 Graphiti

        Args:
            episodes: Episode 列表，每个元素包含 name, content, source_description, reference_time
            batch_size: 批处理大小

        Returns:
            处理结果，包含成功和失败的数量
        """
        if self._use_fallback or not self._connected:
            graph_audit(
                "graph_add_episodes_batch_failed",
                result_status="failure",
                result_message="fallback or not connected",
                resource="graph_engine",
                details={"total_episodes": len(episodes), "batch_size": batch_size},
            )
            return {"success": 0, "failed": len(episodes), "error": "Fallback mode not supported"}

        async def add_batch():
            success_count = 0
            failed_count = 0
            failed_episodes = []

            # 去重处理
            seen_names = set()
            unique_episodes = []
            for episode in episodes:
                name = episode.get('name')
                if name and name not in seen_names:
                    seen_names.add(name)
                    unique_episodes.append(episode)

            # 批量处理
            for i in range(0, len(unique_episodes), batch_size):
                batch = unique_episodes[i:i + batch_size]
                for episode in batch:
                    try:
                        name = episode.get('name')
                        content = episode.get('content')
                        source_description = episode.get('source_description', '')
                        reference_time = episode.get('reference_time', datetime.now(timezone.utc))

                        await self.graph.add_episode(
                            name=name,
                            episode_body=content,
                            source_description=source_description,
                            reference_time=reference_time,
                            update_communities=False,
                        )
                        success_count += 1
                    except Exception as e:
                        logger.info(f"Graphiti 添加 Episode 失败 {episode.get('name')}: {e}")
                        failed_count += 1
                        failed_episodes.append({"episode": episode, "error": str(e)})

            result = {
                "success": success_count,
                "failed": failed_count,
                "failed_episodes": failed_episodes
            }
            graph_audit(
                "graph_add_episodes_batch_success",
                resource="graph_engine",
                details={
                    "total_episodes": len(episodes),
                    "unique_episodes": len(unique_episodes),
                    "success": success_count,
                    "failed": failed_count,
                    "batch_size": batch_size,
                },
            )
            return result

        return _run_async(add_batch())
