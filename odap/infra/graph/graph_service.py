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
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from collections import deque

# 尝试加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# 获取配置
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_API_BASE = os.getenv('OPENAI_API_BASE', 'https://api.openai.com/v1')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')

# 然后再添加项目路径并导入其他模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.biz.ontology.mock_data.data_generator import load_simulation_data

# 尝试导入 graphiti-core（可选）
try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EntityNode, EpisodicNode
    from graphiti_core.edges import Edge, EntityEdge
    from graphiti_core.embedder.client import EmbedderClient
    GRAPHITI_AVAILABLE = True
except ImportError as e:
    GRAPHITI_AVAILABLE = False
    print(f"提示: graphiti-core 未安装 ({e})，Graphiti 模式不可用")

# 尝试导入 neo4j driver（可选）
try:
    from neo4j import GraphDatabase
    NEO4J_DRIVER_AVAILABLE = True
except ImportError as e:
    NEO4J_DRIVER_AVAILABLE = False
    print(f"提示: neo4j driver 未安装 ({e})，Neo4j 直连模式不可用")


class GraphManager:
    """
    图谱管理器
    基于graphiti的时序知识图谱，支持动态更新和混合检索
    使用单例模式确保所有实例共享同一个图谱
    """

    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, neo4j_uri: str = None,
                 neo4j_user: str = None,
                 neo4j_password: str = None):
        """
        初始化图谱管理器

        三层降级策略：
        1. Neo4j Driver 直连 — 无需 graphiti-core，Cypher 直接操作
        2. Graphiti — 双时态知识图谱，需要 graphiti-core + Neo4j
        3. NetworkX fallback — 纯内存，零外部依赖

        Args:
            neo4j_uri: Neo4j连接URI (默认从环境变量读取)
            neo4j_user: Neo4j用户名 (默认从环境变量读取)
            neo4j_password: Neo4j密码 (默认从环境变量读取)
        """
        if GraphManager._initialized:
            return

        self.graph: Optional[Graphiti] = None
        self.neo4j_uri = neo4j_uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = neo4j_user or os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = neo4j_password or os.getenv('NEO4J_PASSWORD', 'neo4j123456')
        self.neo4j_driver = None  # Neo4j Driver 直连
        self.fallback_graph = None  # networkx 内存图（fallback 模式时创建）
        self.reserved_tasks = []
        self._connected = False
        self._use_fallback = True
        self._mode = "fallback"   # "neo4j_driver" | "graphiti" | "fallback"
        
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

        # 尝试三层降级
        self._connect()

        GraphManager._initialized = True

    def _connect(self):
        """
        三层降级连接：Neo4j Driver → Graphiti → NetworkX fallback
        """
        # 第一层：Neo4j Driver 直连
        if NEO4J_DRIVER_AVAILABLE:
            try:
                self.neo4j_driver = GraphDatabase.driver(
                    self.neo4j_uri,
                    auth=(self.neo4j_user, self.neo4j_password)
                )
                # 验证连接
                self.neo4j_driver.verify_connectivity()
                self._connected = True
                self._use_fallback = False
                self._mode = "neo4j_driver"
                print(f"Neo4j Driver 直连成功: {self.neo4j_uri}")
                # 尝试加载模拟数据到 Neo4j
                self._load_data_to_neo4j()
                return
            except Exception as e:
                print(f"Neo4j Driver 连接失败: {e}，尝试下一层")
                if self.neo4j_driver:
                    self.neo4j_driver.close()
                    self.neo4j_driver = None

        # 第二层：Graphiti（需要 graphiti-core + Neo4j）
        if GRAPHITI_AVAILABLE:
            if self._init_graphiti_sync():
                self._mode = "graphiti"
                return

        # 第三层：NetworkX fallback
        self._use_fallback_mode()

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
            all_entities.extend(data.get("military_units", []))
            all_entities.extend(data.get("weapon_systems", []))
            all_entities.extend(data.get("civilian_infrastructure", []))

            count = 0
            for entity in all_entities:
                entity_id = entity["id"]
                entity_type = entity.get("type", "Unknown")
                props = entity.get("properties", {})
                # MERGE 避免重复
                props_str = ", ".join(f"{k}: ${k}" for k in props.keys())
                labels = f"Entity:{entity_type.replace(' ', '_')}"
                cypher = f"MERGE (n:{labels} {{id: $eid}}) SET n += {{{props_str}}}"
                try:
                    params = {"eid": entity_id}
                    params.update(props)
                    session.run(cypher, **params)
                    count += 1
                except Exception as e:
                    print(f"  Neo4j 加载实体失败 {entity_id}: {e}")

            print(f"Neo4j 数据加载完成: {count} 个实体")

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
            print(f"Circuit opened after {self.failure_count} failures")

    def _record_success(self):
        """
        记录成功，重置失败计数
        """
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
        if self.circuit_open:
            # 尝试半开状态
            self.circuit_open = False
            print("Circuit closed, trying to recover")

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
            print(f"创建 Embedder 失败: {e}")
            return None

    def _use_fallback_mode(self):
        """
        使用回退模式（当Neo4j不可用时）
        """
        self._connected = False
        self._use_fallback = True
        print("切换到回退模式（基于内存图谱）")
        import networkx as nx
        self.fallback_graph = nx.DiGraph()
        self._load_data_to_fallback()

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
        for unit in data.get("military_units", []):
            self.fallback_graph.add_node(
                unit["id"],
                entity_type=unit["type"],
                **unit["properties"]
            )
        for weapon in data.get("weapon_systems", []):
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
                print("Graphiti + Neo4j 初始化成功！")
            else:
                print("Graphiti + Neo4j 初始化失败，使用回退模式")

        thread = threading.Thread(target=run_init, daemon=True)
        thread.start()

    def initialize_graph(self):
        """
        同步初始化图谱（回退模式）
        """
        pass

    def _init_graphiti_sync(self) -> bool:
        """
        在单个 asyncio.run() 中初始化 graphiti
        """
        async def init_all():
            try:
                print("创建LLM客户端...")
                llm_client = self._create_llm_client()
                embedder = self._create_embedder()
                if not embedder:
                    print("Embedder 创建失败，Graphiti 模式不可用")
                    return False

                print(f"创建Graphiti实例连接到 {self.neo4j_uri}...")
                self.graph = Graphiti(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                    llm_client=llm_client,
                    embedder=embedder,
                )

                # 先验证 Neo4j 连接可用性（快速失败）
                print("验证 Neo4j 连接...")
                try:
                    await asyncio.wait_for(
                        self.graph.build_indices_and_constraints(delete_existing=False),
                        timeout=15.0
                    )
                except asyncio.TimeoutError:
                    print("Neo4j 连接超时（15s），Graphiti 模式不可用")
                    return False

                print("索引和约束构建完成")

                print("加载数据到 Neo4j...")
                await self._add_episodes_to_graphiti()
                print("Graphiti图谱初始化完成")

                self._connected = True
                self._use_fallback = False
                return True

            except Exception as e:
                print(f"Graphiti初始化失败: {e}")
                return False

        try:
            return asyncio.run(init_all())
        except Exception as e:
            print(f"初始化失败: {e}")
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
        all_entities.extend(data.get("military_units", []))
        all_entities.extend(data.get("weapon_systems", []))
        all_entities.extend(data.get("civilian_infrastructure", []))

        success_count = 0
        error_count = 0

        for entity in all_entities[:20]:
            episode_text = self._create_episode_text(entity)
            try:
                await self.graph.add_episode(
                    name=entity.get("id", "unknown"),
                    content=episode_text,
                    source_description=f"数据: {entity.get('type')}",
                    reference_time=reference_time,
                    update_communities=False
                )
                print(f"  添加实体: {entity.get('id')}")
                success_count += 1
            except Exception as e:
                print(f"  添加实体失败 {entity.get('id')}: {e}")
                error_count += 1

        print(f"实体添加完成: 成功 {success_count}, 失败 {error_count}")

    def query_entities(self, entity_type=None, area=None):
        """
        查询实体

        Args:
            entity_type: 实体类型
            area: 区域

        Returns:
            实体列表
        """
        start_time = time.time()
        try:
            if self._mode == "neo4j_driver" and self.neo4j_driver:
                result = self._query_entities_neo4j(entity_type, area)
            elif self._mode == "graphiti" and self._connected:
                result = self._query_entities_graphiti(entity_type, area)
            else:
                result = self._query_entities_fallback(entity_type, area)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            print(f"Query entities failed: {e}")
            return self._query_entities_fallback(entity_type, area)
        finally:
            # 记录查询时间
            query_time = time.time() - start_time
            self.query_times.append(query_time)
            print(f"Query entities took {query_time:.4f} seconds")

    def _query_entities_neo4j(self, entity_type=None, area=None):
        """Neo4j Driver 模式：查询实体"""
        label = entity_type.replace(" ", "_") if entity_type else "Entity"
        if area:
            cypher = f"MATCH (n:{label}) WHERE n.area = $area RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"
            params = {"area": area}
        else:
            cypher = f"MATCH (n:{label}) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"
            params = {}

        try:
            with self.neo4j_driver.session() as session:
                result = session.run(cypher, **params)
                return [
                    {
                        "id": record["id"],
                        "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                        "properties": record["props"]
                    }
                    for record in result
                ]
        except Exception as e:
            print(f"Neo4j 查询失败: {e}")
            return self._query_entities_fallback(entity_type, area)

    def _query_entities_fallback(self, entity_type=None, area=None):
        """
        回退模式：查询实体
        """
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
        """
        Graphiti模式：查询实体
        """
        async def query():
            try:
                episodes = await self.graph.retrieve_episodes(
                    reference_time=datetime.now()
                )
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
            except Exception as e:
                print(f"Graphiti查询失败，降级到 fallback: {e}")
                return self._query_entities_fallback(entity_type, area)

        return asyncio.run(query())

    def update_entity(self, entity_id, properties):
        """
        更新实体属性

        Args:
            entity_id: 实体ID
            properties: 新属性

        Returns:
            是否成功
        """
        if self._mode == "neo4j_driver" and self.neo4j_driver:
            return self._update_entity_neo4j(entity_id, properties)
        if self._mode == "graphiti" and self._connected:
            return self._update_entity_graphiti(entity_id, properties)
        return self._update_entity_fallback(entity_id, properties)

    def _update_entity_neo4j(self, entity_id: str, properties: Dict) -> bool:
        """Neo4j Driver 模式：更新实体"""
        try:
            props_str = ", ".join(f"n.{k} = ${k}" for k in properties.keys())
            cypher = f"MATCH (n:Entity {{id: $eid}}) SET {props_str}"
            params = {"eid": entity_id}
            params.update(properties)
            with self.neo4j_driver.session() as session:
                result = session.run(cypher, **params)
                summary = result.consume()
                return summary.counters.properties_set > 0
        except Exception as e:
            print(f"Neo4j 更新实体失败: {e}")
            return False

    def _update_entity_fallback(self, entity_id, properties):
        """回退模式：更新实体"""
        if entity_id in self.fallback_graph:
            for key, value in properties.items():
                self.fallback_graph.nodes[entity_id][key] = value
            return True
        return False

    def _update_entity_graphiti(self, entity_id, properties):
        """Graphiti模式：更新实体"""
        return False

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取图谱统计信息

        Returns:
            统计信息字典
        """
        if self._mode == "neo4j_driver" and self.neo4j_driver:
            return self._get_statistics_neo4j()
        if self._mode == "graphiti" and self._connected:
            return self._get_statistics_graphiti()
        return self._get_statistics_fallback()

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
                    "mode": "neo4j_driver",
                }
        except Exception as e:
            print(f"Neo4j 统计失败: {e}")
            return self._get_statistics_fallback()

    def cleanup_self_loops(self) -> Dict[str, int]:
        """
        清理自环关系（source_node_uuid = target_node_uuid）

        Returns:
            清理结果统计
        """
        if not self.neo4j_driver:
            return {"status": "no_neo4j", "cleaned": 0}

        try:
            with self.neo4j_driver.session() as session:
                before = session.run(
                    "MATCH (a)-[r:RELATES_TO]->(b) "
                    "WHERE r.source_node_uuid = r.target_node_uuid "
                    "RETURN count(r) as cnt"
                ).single()["cnt"]

                session.run(
                    "MATCH (a)-[r:RELATES_TO]->(b) "
                    "WHERE r.source_node_uuid = r.target_node_uuid "
                    "DELETE r"
                )

                after = session.run(
                    "MATCH (a)-[r:RELATES_TO]->(b) "
                    "WHERE r.source_node_uuid = r.target_node_uuid "
                    "RETURN count(r) as cnt"
                ).single()["cnt"]

                cleaned = before - after
                print(f"自环关系清理完成: 清理了 {cleaned} 条自环关系")

                return {"status": "success", "cleaned": cleaned, "remaining": after}

        except Exception as e:
            print(f"自环关系清理失败: {e}")
            return {"status": "error", "error": str(e), "cleaned": 0}

    def get_relationship_stats(self) -> Dict[str, Any]:
        """获取关系统计信息"""
        if not self.neo4j_driver:
            return {"status": "no_neo4j"}

        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (a)-[r]->(b)
                    WITH type(r) as rel_type,
                         r.source_node_uuid IS NOT NULL as has_src,
                         r.target_node_uuid IS NOT NULL as has_tgt,
                         count(r) as cnt
                    RETURN rel_type, has_src, has_tgt, sum(cnt) as total
                    ORDER BY rel_type
                """)

                stats = {}
                for record in result:
                    rel_type = record["rel_type"]
                    if rel_type not in stats:
                        stats[rel_type] = {"total": 0, "with_uuid": 0, "without_uuid": 0}
                    stats[rel_type]["total"] += record["total"]
                    if record["has_src"] and record["has_tgt"]:
                        stats[rel_type]["with_uuid"] += record["total"]
                    else:
                        stats[rel_type]["without_uuid"] += record["total"]

                self_loops = session.run("""
                    MATCH (a)-[r:RELATES_TO]->(b)
                    WHERE r.source_node_uuid = r.target_node_uuid
                    RETURN count(r) as cnt
                """).single()["cnt"]

                return {"status": "success", "relationships": stats, "self_loops": self_loops}

        except Exception as e:
            print(f"关系统计获取失败: {e}")
            return {"status": "error", "error": str(e)}

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
                print(f"获取统计信息失败，降级到 fallback: {e}")
                return self._get_statistics_fallback()

        return asyncio.run(get_stats())

    def _count_entity_types(self) -> Dict[str, int]:
        """统计各类型实体数量"""
        counts = {}
        for _, data in self.fallback_graph.nodes(data=True):
            entity_type = data.get("entity_type", "Unknown")
            counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts

    def add_relationship(self, source_id: str, target_id: str,
                         relationship: str, properties: Dict = None):
        """
        添加关系

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relationship: 关系类型
            properties: 关系属性

        Returns:
            是否成功
        """
        if self._use_fallback or not self._connected:
            return self._add_relationship_fallback(source_id, target_id, relationship, properties)

        return self._add_relationship_graphiti(source_id, target_id, relationship, properties)

    def _add_relationship_fallback(self, source_id: str, target_id: str,
                                   relationship: str, properties: Dict = None):
        """回退模式：添加关系"""
        if source_id in self.fallback_graph and target_id in self.fallback_graph:
            self.fallback_graph.add_edge(
                source_id, target_id,
                relationship=relationship,
                **(properties or {})
            )
            return True
        return False

    def _add_relationship_graphiti(self, source_id: str, target_id: str,
                                   relationship: str, properties: Dict = None):
        """Graphiti模式：添加关系"""
        return False

    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索实体

        Args:
            query: 搜索查询
            limit: 返回结果数量限制

        Returns:
            匹配的实体列表
        """
        if self._mode == "neo4j_driver" and self.neo4j_driver:
            return self._search_neo4j(query, limit)
        if self._mode == "graphiti" and self._connected:
            return self._search_graphiti(query, limit)
        return self._search_fallback(query, limit)

    def _search_neo4j(self, query: str, limit: int = 10) -> List[Dict]:
        """Neo4j Driver 模式：全文搜索"""
        try:
            with self.neo4j_driver.session() as session:
                cypher = (
                    "MATCH (n) WHERE n.id CONTAINS $q OR n.name CONTAINS $q "
                    "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props LIMIT $lmt"
                )
                result = session.run(cypher, q=query, lmt=limit)
                return [
                    {
                        "id": record["id"],
                        "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                        "properties": record["props"],
                    }
                    for record in result
                ]
        except Exception as e:
            print(f"Neo4j 搜索失败: {e}")
            return self._search_fallback(query, limit)

    def _search_fallback(self, query: str, limit: int = 10) -> List[Dict]:
        """回退模式：搜索"""
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

    def _search_graphiti(self, query: str, limit: int = 10) -> List[Dict]:
        """Graphiti模式：搜索（返回 EntityEdge 列表）"""
        async def search():
            try:
                results = await self.graph.search(query=query, num_results=limit)
                return [
                    {
                        "id": r.name or str(r.uuid),
                        "type": "EntityEdge",
                        "properties": {
                            "fact": r.fact,
                            "source_node": r.source_node_uuid,
                            "target_node": r.target_node_uuid,
                        }
                    }
                    for r in results
                ]
            except Exception as e:
                print(f"Graphiti搜索失败，降级到 fallback: {e}")
                return self._search_fallback(query, limit)

        return asyncio.run(search())

    def add_entity(self, entity_id: str, entity_type: str, properties: Dict[str, Any]) -> bool:
        """
        添加实体到图谱

        Args:
            entity_id: 实体ID
            entity_type: 实体类型
            properties: 实体属性

        Returns:
            是否添加成功
        """
        if self._mode == "neo4j_driver" and self.neo4j_driver:
            return self._add_entity_neo4j(entity_id, entity_type, properties)
        if self._mode == "graphiti" and self._connected:
            return self._add_entity_graphiti(entity_id, entity_type, properties)
        return self._add_entity_fallback(entity_id, entity_type, properties)

    def _add_entity_neo4j(self, entity_id: str, entity_type: str,
                           properties: Dict[str, Any]) -> bool:
        """Neo4j Driver 模式：添加实体"""
        try:
            label = f"Entity:{entity_type.replace(' ', '_')}"
            props_str = ", ".join(f"{k}: ${k}" for k in properties.keys())
            cypher = f"MERGE (n:{label} {{id: $eid}}) SET n += {{{props_str}}}"
            params = {"eid": entity_id}
            params.update(properties)
            with self.neo4j_driver.session() as session:
                session.run(cypher, **params)
            return True
        except Exception as e:
            print(f"Neo4j 添加实体失败: {e}")
            return False

    def _add_entity_fallback(self, entity_id: str, entity_type: str,
                              properties: Dict[str, Any]) -> bool:
        """回退模式：添加实体"""
        if entity_id in self.fallback_graph:
            # 实体已存在，更新属性
            self.fallback_graph.nodes[entity_id]["entity_type"] = entity_type
            for k, v in properties.items():
                self.fallback_graph.nodes[entity_id][k] = v
        else:
            self.fallback_graph.add_node(
                entity_id,
                entity_type=entity_type,
                **properties
            )
        return True

    def _add_entity_graphiti(self, entity_id: str, entity_type: str,
                              properties: Dict[str, Any]) -> bool:
        """Graphiti模式：添加实体（通过 Episode）"""
        async def add():
            try:
                parts = [f"{entity_id} 是一个 {entity_type}"]
                for key, value in properties.items():
                    parts.append(f"它的 {key} 是 {value}")
                episode_text = "。".join(parts)

                await self.graph.add_episode(
                    name=entity_id,
                    content=episode_text,
                    source_description=f"数据: {entity_type}",
                    reference_time=datetime.now(timezone.utc),
                    update_communities=False
                )
                return True
            except Exception as e:
                print(f"Graphiti添加实体失败: {e}")
                return self._add_entity_fallback(entity_id, entity_type, properties)

        return asyncio.run(add())

    def get_entity_history(self, entity_id: str) -> List[Dict]:
        """
        获取实体的历史变更记录

        Args:
            entity_id: 实体ID

        Returns:
            历史记录列表（回退模式返回空列表）
        """
        if self._use_fallback or not self._connected:
            # 回退模式不支持时态查询，返回空列表
            print(f"警告: 回退模式不支持时态查询 (entity_id={entity_id})")
            return []

        # Graphiti模式：查询 episode 历史
        async def get_history():
            try:
                episodes = await self.graph.retrieve_episodes(
                    reference_time=datetime.now()
                )
                return [
                    {
                        "entity_id": e.name or str(e.uuid),
                        "timestamp": str(e.created_at),
                        "body": e.content
                    }
                    for e in episodes
                    if e.name == entity_id or str(e.uuid) == entity_id
                ]
            except Exception as e:
                print(f"Graphiti查询实体历史失败，降级到 fallback: {e}")
                return []

        return asyncio.run(get_history())

    def query_temporal(self, valid_time=None, transaction_time=None, entity_type=None) -> List[Dict]:
        """
        双时态查询 API

        Args:
            valid_time: 有效时间，实体状态有效的时间点或范围
            transaction_time: 事务时间，数据被记录到系统的时间点或范围
            entity_type: 实体类型（可选）

        Returns:
            符合时态条件的实体列表
        """
        if self._use_fallback or not self._connected:
            # 回退模式不支持时态查询，返回所有实体
            print("警告: 回退模式不支持时态查询，返回所有实体")
            return self.query_entities(entity_type)

        # Graphiti模式：使用时态参数查询
        async def temporal_query():
            try:
                # 构建查询参数
                query_params = {}
                if valid_time:
                    query_params['valid_time'] = valid_time
                if transaction_time:
                    query_params['transaction_time'] = transaction_time

                # 调用Graphiti的时态查询
                episodes = await self.graph.retrieve_episodes(
                    reference_time=datetime.now(),
                    **query_params
                )

                # 过滤实体类型
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
            except Exception as e:
                print(f"Graphiti时态查询失败，降级到普通查询: {e}")
                return self.query_entities(entity_type)

        return asyncio.run(temporal_query())

    def search_hybrid(self, query_text: str, top_k: int = 5, vector_weight: float = 0.7, keyword_weight: float = 0.3) -> List[Dict]:
        """
        混合检索（向量 + 关键词），回退模式委托给 search()

        Args:
            query_text: 查询文本
            top_k: 返回前k个结果
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重

        Returns:
            检索结果列表
        """
        if self._use_fallback or not self._connected:
            # 回退模式：委托给关键词搜索
            return self._search_fallback(query_text, limit=top_k)

        # Graphiti模式：使用 graphiti 的 search（返回 EntityEdge）
        async def hybrid_search():
            try:
                # 1. 向量检索（Graphiti search）
                vector_results = await self.graph.search(query=query_text, num_results=top_k)
                
                # 2. 关键词检索（Neo4j CONTAINS）
                keyword_results = []
                if self.neo4j_driver:
                    try:
                        with self.neo4j_driver.session() as session:
                            cypher = (
                                "MATCH (n) WHERE n.id CONTAINS $q OR n.name CONTAINS $q "
                                "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props LIMIT $lmt"
                            )
                            result = session.run(cypher, q=query_text, lmt=top_k)
                            keyword_results = [
                                {
                                    "id": record["id"],
                                    "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                                    "properties": record["props"],
                                    "score": 0.5  # 默认关键词得分
                                }
                                for record in result
                            ]
                    except Exception as e:
                        print(f"关键词检索失败: {e}")
                
                # 3. 合并结果并根据权重计算最终得分
                result_map = {}
                
                # 处理向量检索结果
                for i, r in enumerate(vector_results):
                    result_id = r.name or str(r.uuid)
                    score = (top_k - i) / top_k * vector_weight  # 排名越靠前得分越高
                    result_map[result_id] = {
                        "id": result_id,
                        "type": "EntityEdge",
                        "properties": {
                            "fact": r.fact,
                            "source_node": r.source_node_uuid,
                            "target_node": r.target_node_uuid,
                        },
                        "score": score
                    }
                
                # 处理关键词检索结果
                for i, r in enumerate(keyword_results):
                    result_id = r["id"]
                    score = (top_k - i) / top_k * keyword_weight  # 排名越靠前得分越高
                    if result_id in result_map:
                        # 如果已存在，加权合并得分
                        result_map[result_id]["score"] += score
                    else:
                        # 否则添加新结果
                        r["score"] = score
                        result_map[result_id] = r
                
                # 4. 按得分排序并返回前top_k结果
                sorted_results = sorted(result_map.values(), key=lambda x: x["score"], reverse=True)[:top_k]
                return sorted_results
                
            except Exception as e:
                print(f"Graphiti混合检索失败，降级到 fallback: {e}")
                return self._search_fallback(query_text, limit=top_k)

        return asyncio.run(hybrid_search())

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
        print(f"任务已预留: {task_id}")
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
        print("所有预留任务已清空")

    def clear_graph(self) -> Dict[str, Any]:
        """
        清空图谱中的所有数据（仅 Neo4j 模式）

        Returns:
            清空结果统计
        """
        if not self.neo4j_driver:
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

                print(f"图谱清空完成: 删除了 {cleared_nodes} 个节点和 {cleared_rels} 条关系")

                return {
                    "status": "success",
                    "cleared_nodes": cleared_nodes,
                    "cleared_relationships": cleared_rels,
                    "remaining_nodes": after_nodes,
                    "remaining_relationships": after_rels
                }

        except Exception as e:
            print(f"图谱清空失败: {e}")
            return {"status": "error", "error": str(e), "cleared": 0}

    def retrieve_rag_context(self, query: str, top_k: int = 5) -> str:
        """
        RAG 上下文检索：基于 Graphiti 的向量搜索 + Episode 回忆，
        返回自然语言上下文段落供 LLM 参考。

        三层降级：
        1. Graphiti: search() 向量检索 + retrieve_episodes() 全量回忆
        2. Neo4j Driver: CONTAINS 关键词匹配
        3. Fallback: 内存关键词匹配

        Args:
            query: 查询文本
            top_k: 返回前 k 条相关结果

        Returns:
            自然语言上下文段落（多条拼接）
        """
        if self._mode == "graphiti" and self._connected:
            return self._retrieve_rag_graphiti(query, top_k)
        if self._mode == "neo4j_driver" and self.neo4j_driver:
            return self._retrieve_rag_neo4j(query, top_k)
        return self._retrieve_rag_fallback(query, top_k)

    def _retrieve_rag_graphiti(self, query: str, top_k: int) -> str:
        """Graphiti 模式：向量搜索 + Episode 检索"""
        async def retrieve():
            try:
                # 1. 向量语义搜索（返回 EntityEdge）
                edges = await self.graph.search(query=query, num_results=top_k)
                # 2. 全量 Episode 回忆
                episodes = await self.graph.retrieve_episodes(
                    reference_time=datetime.now()
                )

                context_parts = []

                # 从语义搜索结果中提取事实
                for edge in edges:
                    if edge.fact:
                        context_parts.append(f"- {edge.fact}")

                # 从 Episode 中提取与 query 相关的记忆
                query_lower = query.lower()
                for ep in episodes[:20]:
                    if ep.content and query_lower in ep.content.lower():
                        context_parts.append(f"- [{ep.name}] {ep.content[:200]}")
                    elif context_parts and len(context_parts) < top_k:
                        # 补充一些最近的记忆（即使不完全匹配）
                        if len(context_parts) < 3:
                            context_parts.append(f"- [{ep.name}] {ep.content[:150]}")

                if not context_parts:
                    return ""

                return "历史情报记忆：\n" + "\n".join(context_parts[:top_k])

            except Exception as e:
                print(f"Graphiti RAG 检索失败: {e}")
                return ""

        return asyncio.run(retrieve())

    def _retrieve_rag_neo4j(self, query: str, top_k: int) -> str:
        """Neo4j Driver 模式：Cypher 全文匹配"""
        try:
            with self.neo4j_driver.session() as session:
                cypher = (
                    "MATCH (n) "
                    "WHERE n.id CONTAINS $q OR n.name CONTAINS $q "
                    "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
                    "LIMIT $lmt"
                )
                results = session.run(cypher, q=query, lmt=top_k)
                parts = []
                for r in results:
                    name = r["props"].get("name", r["id"])
                    entity_type = [l for l in r["labels"] if l != "Entity"]
                    type_str = entity_type[0] if entity_type else "Entity"
                    parts.append(f"- {name} ({type_str}): {json.dumps(r['props'], ensure_ascii=False, default=str)[:150]}")

                if not parts:
                    return ""
                return "相关实体数据：\n" + "\n".join(parts)
        except Exception as e:
            print(f"Neo4j RAG 检索失败: {e}")
            return self._retrieve_rag_fallback(query, top_k)

    def _retrieve_rag_fallback(self, query: str, top_k: int) -> str:
        """Fallback 模式：内存关键词匹配"""
        if self.fallback_graph is None:
            return ""
        results = self._search_fallback(query, limit=top_k)
        if not results:
            return ""

        parts = []
        for r in results:
            name = r["properties"].get("name", r["id"])
            entity_type = r.get("type", "Unknown")
            parts.append(f"- {name} ({entity_type}): {json.dumps(r['properties'], ensure_ascii=False, default=str)[:150]}")

        return "相关实体数据：\n" + "\n".join(parts)

    def add_episode(self, name: str, content: str,
                    source_description: str = "",
                    reference_time=None) -> bool:
        """
        添加一条 Episode 到 Graphiti（供外部 Agent 使用）

        Args:
            name: Episode 名称
            content: Episode 内容
            source_description: 来源描述
            reference_time: 参考时间

        Returns:
            是否成功
        """
        if self._use_fallback or not self._connected:
            return False

        if reference_time is None:
            reference_time = datetime.now(timezone.utc)

        async def add():
            try:
                await self.graph.add_episode(
                    name=name,
                    content=content,
                    source_description=source_description,
                    reference_time=reference_time,
                    update_communities=False,
                )
                return True
            except Exception as e:
                print(f"Graphiti 添加 Episode 失败: {e}")
                return False

        return asyncio.run(add())

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
                            content=content,
                            source_description=source_description,
                            reference_time=reference_time,
                            update_communities=False,
                        )
                        success_count += 1
                    except Exception as e:
                        print(f"Graphiti 添加 Episode 失败 {episode.get('name')}: {e}")
                        failed_count += 1
                        failed_episodes.append({"episode": episode, "error": str(e)})

            return {
                "success": success_count,
                "failed": failed_count,
                "failed_episodes": failed_episodes
            }

        return asyncio.run(add_batch())
