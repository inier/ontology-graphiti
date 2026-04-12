"""
基于graphiti的战场图谱管理模块
使用Neo4j作为图数据库，支持时序知识图谱特性

解决方案：在单个 asyncio.run() 中完成所有 graphiti 操作
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

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

from data.simulation_data import load_simulation_data

# 尝试导入graphiti-core
try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EntityNode, EpisodicNode
    from graphiti_core.edges import Edge, EntityEdge
    from graphiti_core.embedder.client import EmbedderClient
    GRAPHITI_AVAILABLE = True
except ImportError as e:
    GRAPHITI_AVAILABLE = False
    print(f"警告: graphiti-core 未安装 ({e})，将使用回退模式")


class BattlefieldGraphManager:
    """
    战场图谱管理器
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
        初始化战场图谱管理器

        Args:
            neo4j_uri: Neo4j连接URI (默认从环境变量读取)
            neo4j_user: Neo4j用户名 (默认从环境变量读取)
            neo4j_password: Neo4j密码 (默认从环境变量读取)
        """
        if BattlefieldGraphManager._initialized:
            return

        self.graph: Optional[Graphiti] = None
        self.neo4j_uri = neo4j_uri or os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = neo4j_user or os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = neo4j_password or os.getenv('NEO4J_PASSWORD', 'neo4j123456')
        self.reserved_tasks = []
        self._connected = False
        self._use_fallback = True

        # 先使用回退模式加载数据
        self._use_fallback_mode()

        BattlefieldGraphManager._initialized = True

    def _create_llm_client(self):
        """创建LLM客户端（使用智谱AI适配器）"""
        from graphiti_core.llm_client.config import LLMConfig
        from core.llm_clients import ZhipuAIClient

        config = LLMConfig(
            model=OPENAI_MODEL,
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_API_BASE,
            temperature=0.7
        )
        return ZhipuAIClient(config=config)

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

                print(f"创建Graphiti实例连接到 {self.neo4j_uri}...")
                self.graph = Graphiti(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                    llm_client=llm_client
                )

                print("构建graphiti索引和约束...")
                await self.graph.build_indices_and_constraints()
                print("索引和约束构建完成")

                print("加载数据到 Neo4j...")
                await self._add_episodes_to_graphiti()
                print("Graphiti图谱初始化完成")

                self._connected = True
                self._use_fallback = False
                return True

            except Exception as e:
                print(f"Graphiti初始化失败: {e}")
                import traceback
                traceback.print_exc()
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
        reference_time = datetime.now()

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
                    episode_body=episode_text,
                    source_description=f"战场数据: {entity.get('type')}",
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
        if self._use_fallback or not self._connected:
            return self._query_entities_fallback(entity_type, area)

        return self._query_entities_graphiti(entity_type, area)

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
                        "properties": {"body": episode.episode_body}
                    })
                return result
            except Exception as e:
                print(f"Graphiti查询失败: {e}")
                return []

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
        if self._use_fallback or not self._connected:
            return self._update_entity_fallback(entity_id, properties)

        return self._update_entity_graphiti(entity_id, properties)

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
        if self._use_fallback or not self._connected:
            return self._get_statistics_fallback()

        return self._get_statistics_graphiti()

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
                print(f"获取统计信息失败: {e}")
                return {"error": str(e), "mode": "graphiti"}

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
        if self._use_fallback or not self._connected:
            return self._search_fallback(query, limit)

        return self._search_graphiti(query, limit)

    def _search_fallback(self, query: str, limit: int = 10) -> List[Dict]:
        """回退模式：搜索"""
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
        """Graphiti模式：搜索"""
        async def search():
            try:
                results = await self.graph.search(query=query, limit=limit)
                return [{"id": r.name or str(r.uuid), "type": "Entity",
                         "properties": {"body": r.episode_body}} for r in results]
            except Exception as e:
                print(f"Graphiti搜索失败: {e}")
                return []

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
        if self._use_fallback or not self._connected:
            return self._add_entity_fallback(entity_id, entity_type, properties)
        return self._add_entity_graphiti(entity_id, entity_type, properties)

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
                    episode_body=episode_text,
                    source_description=f"战场数据: {entity_type}",
                    reference_time=datetime.now(),
                    update_communities=False
                )
                return True
            except Exception as e:
                print(f"Graphiti添加实体失败: {e}")
                return False

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
                        "timestamp": str(getattr(e, 'created_at', 'unknown')),
                        "body": e.episode_body
                    }
                    for e in episodes
                    if e.name == entity_id or (hasattr(e, 'uuid') and str(e.uuid) == entity_id)
                ]
            except Exception as e:
                print(f"Graphiti查询实体历史失败: {e}")
                return []

        return asyncio.run(get_history())

    def search_hybrid(self, query_text: str, top_k: int = 5) -> List[Dict]:
        """
        混合检索（向量 + 关键词），回退模式委托给 search()

        Args:
            query_text: 查询文本
            top_k: 返回前k个结果

        Returns:
            检索结果列表
        """
        if self._use_fallback or not self._connected:
            # 回退模式：委托给关键词搜索
            return self._search_fallback(query_text, limit=top_k)

        # Graphiti模式：使用 graphiti 的 search
        async def hybrid_search():
            try:
                results = await self.graph.search(query=query_text, limit=top_k)
                return [
                    {
                        "id": r.name or str(r.uuid),
                        "type": "Entity",
                        "properties": {"body": r.episode_body},
                        "score": getattr(r, 'score', None)
                    }
                    for r in results
                ]
            except Exception as e:
                print(f"Graphiti混合检索失败: {e}")
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
