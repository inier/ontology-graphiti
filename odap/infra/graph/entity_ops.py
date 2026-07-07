"""
实体 CRUD 操作 Mixin

提供 GraphManager 的实体增删改查功能，支持 Neo4j / Graphiti / Fallback 三种模式。
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from ._utils import _run_async



import logging

logger = logging.getLogger(__name__)
class EntityOpsMixin:
    """实体 CRUD：add_entity, query_entities, update_entity, get_entity, get_all_entities, get_entity_history"""

    # ------------------------------------------------------------------
    # add_entity
    # ------------------------------------------------------------------
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
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._add_entity_neo4j(entity_id, entity_type, properties)
        if self._test_mode and self._use_fallback:
            return self._add_entity_fallback(entity_id, entity_type, properties)
        return False

    def _add_entity_neo4j(self, entity_id: str, entity_type: str,
                           properties: Dict[str, Any]) -> bool:
        """Neo4j Driver 模式：添加实体（类型安全）

        双 Label 策略：
        - Entity:{safe_type}   → 向后兼容的旧 Label（自然语言名）
        - EntityType:{type_id} → 新的 type_id Label（安全、可索引）
        """
        try:
            safe_type = entity_type.replace(' ', '_')
            self._validate_label(safe_type)

            # 生成 type_id（ASCII 安全标识符）
            entity_type_id = entity_type.lower().replace(' ', '_')
            # 中文类型名转换为安全 ASCII 别名
            if re.search(r'[\u4e00-\u9fff]', entity_type_id):
                entity_type_id = "zh_type"
            self._validate_label(entity_type_id)

            # 双 Label: 旧兼容 + 新 type_id
            label = f"Entity:{safe_type}:EntityType:{entity_type_id}"

            sane_props = self._sanitize_neo4j_properties(properties)
            sane_props["entity_type_id"] = entity_type_id

            prop_items = [(k, v) for k, v in sane_props.items()
                          if k not in ("entity_id", "entity_type", "id", "eid")]

            if not prop_items:
                cypher = f"MERGE (n:{label} {{id: $eid}})"
                params = {"eid": entity_id}
                with self.neo4j_driver.session() as session:
                    session.run(cypher, **params)
                return True

            set_clauses = []
            params = {"eid": entity_id}
            for i, (k, v) in enumerate(prop_items):
                self._validate_property_key(k)
                param_key = f"p{i}"
                set_clauses.append(f"n.{k} = ${param_key}")
                params[param_key] = v

            cypher = f"MERGE (n:{label} {{id: $eid}}) SET {', '.join(set_clauses)}"
            with self.neo4j_driver.session() as session:
                session.run(cypher, **params)
            return True
        except Exception as e:
            logger.info(f'Neo4j 添加实体失败: {e}')
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
                    episode_body=episode_text,
                    source_description=f"数据: {entity_type}",
                    reference_time=datetime.now(timezone.utc),
                    update_communities=False
                )
                return True
            except Exception as e:
                logger.info(f'Graphiti添加实体失败: {e}')
                if self._test_mode and self._use_fallback:
                    return self._add_entity_fallback(entity_id, entity_type, properties)
                return False

        return _run_async(add())

    # ------------------------------------------------------------------
    # query_entities
    # ------------------------------------------------------------------
    def query_entities(self, entity_type=None, area=None, workspace_id=None):
        """
        查询实体

        Args:
            entity_type: 实体类型
            area: 区域
            workspace_id: 工作空间ID（多租户过滤）

        Returns:
            实体列表
        """
        start_time = self._get_time()
        cache_key = self._cache_key("qe", entity_type=entity_type, area=area, workspace_id=workspace_id)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        self._try_reconnect()

        if self._mode == "unavailable" and not self._test_mode:
            return self._unavailable_error()

        try:
            if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
                result = self._query_entities_neo4j(entity_type, area, workspace_id)
            elif self._test_mode and self._use_fallback:
                result = self._query_entities_fallback(entity_type, area, workspace_id)
            else:
                return self._unavailable_error()
            self._record_success()
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            self._record_failure()
            logger.info(f'Query entities failed: {e}')
            if self._test_mode and self._use_fallback:
                return self._query_entities_fallback(entity_type, area, workspace_id)
            return self._unavailable_error()
        finally:
            query_time = self._get_time() - start_time
            self.query_times.append(query_time)
            logger.info(f'Query entities took {query_time:.4f} seconds')

    @staticmethod
    def _get_time():
        import time


        return time.time()

    def _query_entities_neo4j(self, entity_type=None, area=None, workspace_id=None):
        """Neo4j Driver 模式：查询实体"""
        label = entity_type.replace(" ", "_") if entity_type else "Entity"
        self._validate_label(label)
        conditions = []
        params = {}
        if area:
            conditions.append("n.area = $area")
            params["area"] = area
        if workspace_id:
            conditions.append("n.workspace_id = $workspace_id")
            params["workspace_id"] = workspace_id

        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        cypher = f"MATCH (n:{label}){where_clause} RETURN n.id AS id, labels(n) AS labels, properties(n) AS props"

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
            logger.info(f'Neo4j 查询失败: {e}')
            if self._test_mode and self._use_fallback:
                return self._query_entities_fallback(entity_type, area)
            raise

    def _query_entities_fallback(self, entity_type=None, area=None, workspace_id=None):
        """回退模式：查询实体"""
        result = []

        for node_id, node_data in self.fallback_graph.nodes(data=True):
            if entity_type and node_data.get("entity_type") != entity_type:
                continue
            if area and node_data.get("area") != area:
                continue
            if workspace_id and node_data.get("workspace_id") and node_data.get("workspace_id") != workspace_id:
                continue

            result.append({
                "id": node_id,
                "type": node_data.get("entity_type"),
                "properties": {k: v for k, v in node_data.items() if k != "entity_type"}
            })

        return result

    def _query_entities_graphiti(self, entity_type=None, area=None):
        """Graphiti模式：查询实体"""
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
                logger.info(f'Graphiti查询失败: {e}')
                if self._test_mode and self._use_fallback:
                    return self._query_entities_fallback(entity_type, area)
                return []

        return _run_async(query())

    # ------------------------------------------------------------------
    # update_entity
    # ------------------------------------------------------------------
    def update_entity(self, entity_id, properties):
        """
        更新实体属性

        Args:
            entity_id: 实体ID
            properties: 新属性

        Returns:
            是否成功
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._update_entity_neo4j(entity_id, properties)
        if self._test_mode and self._use_fallback:
            return self._update_entity_fallback(entity_id, properties)
        return False

    def _update_entity_neo4j(self, entity_id: str, properties: Dict) -> bool:
        """Neo4j Driver 模式：更新实体"""
        try:
            set_clauses = []
            params = {"eid": entity_id}
            for k, v in properties.items():
                self._validate_property_key(k)
                set_clauses.append(f"n.{k} = ${k}")
                params[k] = v
            cypher = f"MATCH (n:Entity {{id: $eid}}) SET {', '.join(set_clauses)}"
            with self.neo4j_driver.session() as session:
                result = session.run(cypher, **params)
                summary = result.consume()
                return summary.counters.properties_set > 0
        except Exception as e:
            logger.info(f'Neo4j 更新实体失败: {e}')
            return False

    def _update_entity_fallback(self, entity_id, properties):
        """回退模式：更新实体"""
        if entity_id in self.fallback_graph:
            for key, value in properties.items():
                self.fallback_graph.nodes[entity_id][key] = value
            return True
        return False

    def _update_entity_graphiti(self, entity_id, properties):
        """Graphiti模式：更新实体（通过 Episode 描述属性变更）"""
        async def update():
            try:
                parts = [f"{entity_id} 的属性发生了更新"]
                for key, value in properties.items():
                    parts.append(f"它的 {key} 现在是 {value}")
                episode_text = "。".join(parts)

                await self.graph.add_episode(
                    name=f"update_{entity_id}",
                    episode_body=episode_text,
                    source_description=f"属性更新: {entity_id}",
                    reference_time=datetime.now(timezone.utc),
                    update_communities=False
                )
                return True
            except Exception as e:
                logger.info(f'Graphiti 更新实体失败: {e}')
                if self._test_mode and self._use_fallback:
                    return self._update_entity_fallback(entity_id, properties)
                return False

        try:
            return _run_async(update())
        except RuntimeError:
            return _run_async(update())

    # ------------------------------------------------------------------
    # get_entity
    # ------------------------------------------------------------------
    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """
        获取单个实体

        Args:
            entity_id: 实体ID

        Returns:
            实体信息
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._get_entity_neo4j(entity_id)
        if self._test_mode and self._use_fallback:
            return self._get_entity_fallback(entity_id)
        return None

    def _get_entity_neo4j(self, entity_id: str) -> Optional[Dict]:
        """Neo4j Driver 模式：获取单个实体"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run(
                    "MATCH (n:Entity {id: $eid}) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
                    eid=entity_id
                )
                record = result.single()
                if record:
                    return {
                        "id": record["id"],
                        "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                        "properties": record["props"]
                    }
                return None
        except Exception as e:
            logger.info(f'Neo4j 获取实体失败: {e}')
            return None

    def _get_entity_fallback(self, entity_id: str) -> Optional[Dict]:
        """回退模式：获取单个实体"""
        if entity_id in self.fallback_graph:
            data = self.fallback_graph.nodes[entity_id]
            return {
                "id": entity_id,
                "type": data.get("entity_type"),
                "properties": {k: v for k, v in data.items() if k != "entity_type"}
            }
        return None

    # ------------------------------------------------------------------
    # get_all_entities
    # ------------------------------------------------------------------
    def get_all_entities(self, workspace_id=None) -> List[Dict]:
        """
        获取所有实体

        Args:
            workspace_id: 工作空间ID（多租户过滤，None=全部）

        Returns:
            实体列表
        """
        return self.query_entities(workspace_id=workspace_id)

    # ------------------------------------------------------------------
    # get_entity_history
    # ------------------------------------------------------------------
    def get_entity_history(self, entity_id: str) -> List[Dict]:
        """
        获取实体的历史变更记录

        Args:
            entity_id: 实体ID

        Returns:
            历史记录列表
        """
        if self._mode == "unavailable" and not self._test_mode:
            return []
        if self._use_fallback or not self._connected:
            logger.info(f'警告: 回退模式不支持时态查询 (entity_id={entity_id})')
            return []

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
                logger.info(f'Graphiti查询实体历史失败: {e}')
                return []

        return _run_async(get_history())
