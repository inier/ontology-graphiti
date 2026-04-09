"""
基于graphiti的战场图谱管理模块
使用Neo4j作为图数据库，支持时序知识图谱特性
"""

import sys
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.simulation_data import load_simulation_data

try:
    from graphiti_core import Graphiti
    from graphiti_core.nodes import EntityNode
    from graphiti_core.edges import RelationEdge
    from graphiti_core.graphiti_types import NodeCreate
    GRAPHITI_AVAILABLE = True
except ImportError:
    GRAPHITI_AVAILABLE = False
    print("警告: graphiti-core未安装，将使用回退模式")


class BattlefieldGraphManager:
    """
    战场图谱管理器
    基于graphiti的时序知识图谱，支持动态更新和混合检索
    """

    def __init__(self, neo4j_uri: str = "bolt://localhost:7687",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = "password"):
        """
        初始化战场图谱管理器

        Args:
            neo4j_uri: Neo4j连接URI
            neo4j_user: Neo4j用户名
            neo4j_password: Neo4j密码
        """
        self.graph: Optional[Graphiti] = None
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.reserved_tasks = []
        self._connected = False

        if GRAPHITI_AVAILABLE:
            self._connect_neo4j()
        else:
            self._use_fallback_mode()

        self.initialize_graph()

    def _connect_neo4j(self):
        """
        连接到Neo4j数据库
        """
        try:
            self.graph = Graphiti(
                uri=self.neo4j_uri,
                user=self.neo4j_user,
                password=self.neo4j_password
            )
            self._connected = True
            print(f"已连接到Neo4j: {self.neo4j_uri}")
        except Exception as e:
            print(f"连接Neo4j失败: {e}")
            print("将使用回退模式（基于内存）")
            self._use_fallback_mode()

    def _use_fallback_mode(self):
        """
        使用回退模式（当Neo4j不可用时）
        """
        self._connected = False
        print("使用回退模式（基于内存图谱）")
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
        for civ in data.get("civilian_infrastructures", []):
            self.fallback_graph.add_node(
                civ["id"],
                entity_type=civ["type"],
                **civ["properties"]
            )
        for event in data.get("battle_events", []):
            self.fallback_graph.add_node(
                event["id"],
                entity_type=event["type"],
                **event["properties"]
            )
        for mission in data.get("missions", []):
            self.fallback_graph.add_node(
                mission["id"],
                entity_type=mission["type"],
                **mission["properties"]
            )

        self._establish_fallback_relationships(data)

    def _establish_fallback_relationships(self, data):
        """
        在回退模式图谱中建立实体关系
        """
        for location in data.get("locations", []):
            for contained in location["relationships"].get("contains", []):
                if contained:
                    self.fallback_graph.add_edge(location["id"], contained, relationship="contains")
            for adjacent in location["relationships"].get("adjacent_to", []):
                if adjacent:
                    self.fallback_graph.add_edge(location["id"], adjacent, relationship="adjacent_to")

        for unit in data.get("military_units", []):
            if unit["relationships"].get("located_at"):
                self.fallback_graph.add_edge(
                    unit["id"],
                    unit["relationships"]["located_at"],
                    relationship="located_at"
                )

        for weapon in data.get("weapon_systems", []):
            if weapon["relationships"].get("located_at"):
                self.fallback_graph.add_edge(
                    weapon["id"],
                    weapon["relationships"]["located_at"],
                    relationship="located_at"
                )

        for civ in data.get("civilian_infrastructures", []):
            if civ["relationships"].get("located_at"):
                self.fallback_graph.add_edge(
                    civ["id"],
                    civ["relationships"]["located_at"],
                    relationship="located_at"
                )

    def initialize_graph(self):
        """
        初始化战场图谱
        """
        if self._connected and self.graph:
            self._initialize_from_graphiti()
        else:
            print("图谱初始化完成（回退模式）")

    def _initialize_from_graphiti(self):
        """
        使用graphiti初始化图谱
        """
        try:
            data = load_simulation_data()
            self._add_entities_graphiti(data)
            self._establish_graphiti_relationships(data)
            print("Graphiti图谱初始化完成")
        except Exception as e:
            print(f"Graphiti初始化失败: {e}")
            self._use_fallback_mode()
            self._load_data_to_fallback()

    def _add_entities_graphiti(self, data):
        """
        使用graphiti添加实体
        """
        for location in data.get("locations", []):
            node_data = NodeCreate(
                name=location["properties"].get("name", location["id"]),
                entity_type=location["type"],
                properties=location["properties"]
            )
            self.graph.add_node(node_data)

    def _establish_graphiti_relationships(self, data):
        """
        使用graphiti建立实体关系
        """
        pass

    def query_entities(self, entity_type=None, area=None):
        """
        查询实体

        Args:
            entity_type: 实体类型
            area: 区域

        Returns:
            实体列表
        """
        if not self._connected:
            return self._query_entities_fallback(entity_type, area)

        return self._query_entities_graphiti(entity_type, area)

    def _query_entities_fallback(self, entity_type=None, area=None):
        """
        回退模式：查询实体
        """
        import networkx as nx
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
        try:
            entities = self.graph.get_entities()
            result = []
            for entity in entities:
                if entity_type and entity.entity_type != entity_type:
                    continue
                if area and entity.properties.get("area") != area:
                    continue

                result.append({
                    "id": str(entity.uuid),
                    "type": entity.entity_type,
                    "properties": entity.properties
                })
            return result
        except Exception as e:
            print(f"Graphiti查询失败: {e}")
            return []

    def update_entity(self, entity_id, properties):
        """
        更新实体属性

        Args:
            entity_id: 实体ID
            properties: 要更新的属性

        Returns:
            bool: 更新是否成功
        """
        if not self._connected:
            if entity_id in self.fallback_graph.nodes:
                self.fallback_graph.nodes[entity_id].update(properties)
                return True
            return False

        try:
            entity = self.graph.get_entity_by_name(entity_id)
            if entity:
                for key, value in properties.items():
                    entity.properties[key] = value
                self.graph.update_node(entity)
                return True
            return False
        except Exception as e:
            print(f"Graphiti更新失败: {e}")
            return False

    def add_entity(self, entity_id, entity_type, properties):
        """
        添加新实体

        Args:
            entity_id: 实体ID
            entity_type: 实体类型
            properties: 实体属性

        Returns:
            bool: 添加是否成功
        """
        if not self._connected:
            if entity_id in self.fallback_graph.nodes:
                return False
            self.fallback_graph.add_node(entity_id, entity_type=entity_type, **properties)
            return True

        try:
            node_data = NodeCreate(
                name=properties.get("name", entity_id),
                entity_type=entity_type,
                properties=properties
            )
            self.graph.add_node(node_data)
            return True
        except Exception as e:
            print(f"Graphiti添加实体失败: {e}")
            return False

    def add_relationship(self, source_id, target_id, relationship):
        """
        添加实体关系

        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            relationship: 关系类型

        Returns:
            bool: 添加是否成功
        """
        if not self._connected:
            if source_id not in self.fallback_graph.nodes or target_id not in self.fallback_graph.nodes:
                return False
            self.fallback_graph.add_edge(source_id, target_id, relationship=relationship)
            return True

        try:
            source = self.graph.get_entity_by_name(source_id)
            target = self.graph.get_entity_by_name(target_id)
            if source and target:
                edge = RelationEdge(
                    source_node_uuid=source.uuid,
                    target_node_uuid=target.uuid,
                    rel_type=relationship,
                    properties={}
                )
                self.graph.add_edge(edge)
                return True
            return False
        except Exception as e:
            print(f"Graphiti添加关系失败: {e}")
            return False

    def add_temporal_event(self, entity_id, event_type, description, timestamp=None):
        """
        添加时序事件（graphiti核心特性）

        Args:
            entity_id: 实体ID
            event_type: 事件类型
            description: 事件描述
            timestamp: 事件时间戳

        Returns:
            bool: 添加是否成功
        """
        if not self._connected:
            return False

        try:
            entity = self.graph.get_entity_by_name(entity_id)
            if entity:
                self.graph.add_episode({
                    "entity_uuid": entity.uuid,
                    "fact": description,
                    "source": "battlefield_system"
                })
                return True
            return False
        except Exception as e:
            print(f"添加时序事件失败: {e}")
            return False

    def search_hybrid(self, query_text, top_k=5):
        """
        混合检索（graphiti核心特性）
        结合语义搜索、关键词搜索和图遍历

        Args:
            query_text: 查询文本
            top_k: 返回前k个结果

        Returns:
            检索结果列表
        """
        if not self._connected:
            return []

        try:
            results = self.graph.search(query_text, top_k=top_k)
            return results
        except Exception as e:
            print(f"混合检索失败: {e}")
            return []

    def get_entity_history(self, entity_id):
        """
        获取实体历史（bi-temporal tracking）

        Args:
            entity_id: 实体ID

        Returns:
            实体历史记录
        """
        if not self._connected:
            return []

        try:
            entity = self.graph.get_entity_by_name(entity_id)
            if entity:
                episodes = self.graph.get_entity_episodes(entity.uuid)
                return episodes
            return []
        except Exception as e:
            print(f"获取实体历史失败: {e}")
            return []

    def reserve_task(self, task_data):
        """
        基于图谱预留任务

        Args:
            task_data: 任务数据

        Returns:
            str: 预留任务ID
        """
        task_id = f"RESERVED_TASK_{len(self.reserved_tasks) + 1}"
        task_data["id"] = task_id
        task_data["status"] = "reserved"
        task_data["created_at"] = datetime.now().isoformat()
        self.reserved_tasks.append(task_data)

        if "targets" in task_data:
            for target_id in task_data["targets"]:
                if self._connected:
                    self.add_relationship(task_id, target_id, "targets")
                else:
                    if target_id in self.fallback_graph.nodes:
                        self.fallback_graph.add_edge(task_id, target_id, relationship="targets")

        return task_id

    def get_reserved_tasks(self):
        """
        获取所有预留任务

        Returns:
            预留任务列表
        """
        return self.reserved_tasks

    def clear_reserved_tasks(self):
        """
        清除所有预留任务
        """
        self.reserved_tasks = []

    def get_graph_statistics(self):
        """
        获取图谱统计信息

        Returns:
            统计信息字典
        """
        if not self._connected:
            node_count = self.fallback_graph.number_of_nodes()
            edge_count = self.fallback_graph.number_of_edges()

            type_count = {}
            for node_id, node_data in self.fallback_graph.nodes(data=True):
                node_type = node_data.get("entity_type", "Unknown")
                type_count[node_type] = type_count.get(node_type, 0) + 1

            return {
                "node_count": node_count,
                "edge_count": edge_count,
                "type_count": type_count,
                "mode": "fallback (networkx)"
            }

        try:
            stats = self.graph.get_statistics()
            return {
                "node_count": stats.get("node_count", 0),
                "edge_count": stats.get("edge_count", 0),
                "type_count": stats.get("type_count", {}),
                "mode": "graphiti (neo4j)"
            }
        except Exception as e:
            print(f"获取统计信息失败: {e}")
            return {"mode": "error"}

    def close(self):
        """
        关闭图谱连接
        """
        if self._connected and self.graph:
            try:
                self.graph.close()
            except Exception as e:
                print(f"关闭连接失败: {e}")


if __name__ == "__main__":
    manager = BattlefieldGraphManager()

    stats = manager.get_graph_statistics()
    print("图谱统计信息:")
    print(f"模式: {stats.get('mode', 'unknown')}")
    print(f"节点数: {stats.get('node_count', 0)}")
    print(f"边数: {stats.get('edge_count', 0)}")
    print("按类型统计:")
    for node_type, count in stats.get('type_count', {}).items():
        print(f"- {node_type}: {count}")

    print("\n查询B区的地理位置:")
    b_locations = manager.query_entities(entity_type="Location", area="B")
    for location in b_locations:
        print(f"- {location['properties'].get('name', '未知')}")

    print("\n预留任务测试:")
    task_data = {
        "type": "Mission",
        "properties": {
            "name": "侦察任务",
            "priority": "高"
        },
        "targets": ["WEAPON_Bl_1"]
    }
    task_id = manager.reserve_task(task_data)
    print(f"预留任务ID: {task_id}")

    reserved_tasks = manager.get_reserved_tasks()
    print(f"预留任务数量: {len(reserved_tasks)}")

    manager.close()