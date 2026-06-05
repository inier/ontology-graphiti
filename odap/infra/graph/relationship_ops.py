"""
关系操作 Mixin

提供 GraphManager 的关系增删改查功能，支持 Neo4j / Graphiti / Fallback 三种模式。
"""

from datetime import datetime, timezone
from typing import Dict, Any, List

from ._utils import _run_async



import logging

logger = logging.getLogger(__name__)
class RelationshipOpsMixin:
    """关系操作：add_relationship, get_all_relations, get_entity_relations, search_relations, get_relationship_stats, cleanup_self_loops"""

    # ------------------------------------------------------------------
    # add_relationship
    # ------------------------------------------------------------------
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
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._add_relationship_neo4j(source_id, target_id, relationship, properties)
        if self._test_mode and self._use_fallback:
            return self._add_relationship_fallback(source_id, target_id, relationship, properties)
        return False

    def _add_relationship_neo4j(self, source_id: str, target_id: str,
                                relationship: str, properties: Dict = None) -> bool:
        """Neo4j Driver 模式：添加关系（类型安全）"""
        try:
            rel_type = relationship.upper().replace(' ', '_')
            self._validate_label(rel_type)
            sane_props = self._sanitize_neo4j_properties(properties or {})

            set_clauses = []
            params = {"sid": source_id, "tid": target_id}
            for i, (k, v) in enumerate(sane_props.items()):
                param_key = f"rp{i}"
                set_clauses.append(f"r.{k} = ${param_key}")
                params[param_key] = v

            if set_clauses:
                cypher = (
                    f"MATCH (a:Entity {{id: $sid}}), (b:Entity {{id: $tid}}) "
                    f"MERGE (a)-[r:{rel_type}]->(b) "
                    f"SET {', '.join(set_clauses)}"
                )
            else:
                cypher = (
                    f"MATCH (a:Entity {{id: $sid}}), (b:Entity {{id: $tid}}) "
                    f"MERGE (a)-[r:{rel_type}]->(b)"
                )

            with self.neo4j_driver.session() as session:
                session.run(cypher, **params)
            return True
        except Exception as e:
            logger.info(f'Neo4j 添加关系失败: {e}')
            if self._test_mode and self._use_fallback:
                return self._add_relationship_fallback(source_id, target_id, relationship, properties or {})
            return False

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
        """Graphiti模式：添加关系（通过 Episode 描述关系变更）"""
        async def add_rel():
            try:
                parts = [f"{source_id} 与 {target_id} 之间建立了 {relationship} 关系"]
                if properties:
                    for key, value in properties.items():
                        parts.append(f"该关系的 {key} 是 {value}")
                episode_text = "。".join(parts)

                await self.graph.add_episode(
                    name=f"rel_{source_id}_{target_id}",
                    episode_body=episode_text,
                    source_description=f"关系建立: {relationship}",
                    reference_time=datetime.now(timezone.utc),
                    update_communities=False
                )
                return True
            except Exception as e:
                logger.info(f'Graphiti 添加关系失败: {e}')
                if self._test_mode and self._use_fallback:
                    return self._add_relationship_fallback(source_id, target_id, relationship, properties or {})
                return False

        try:
            return _run_async(add_rel())
        except RuntimeError:
            return _run_async(add_rel())

    # ------------------------------------------------------------------
    # get_all_relations
    # ------------------------------------------------------------------
    def get_all_relations(self, workspace_id=None) -> List[Dict]:
        """
        获取所有关系

        Args:
            workspace_id: 工作空间ID（多租户过滤，None=全部）

        Returns:
            关系列表
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._get_all_relations_neo4j(workspace_id)
        if self._test_mode and self._use_fallback:
            return self._get_all_relations_fallback(workspace_id)
        return []

    def _get_all_relations_neo4j(self, workspace_id=None) -> List[Dict]:
        """Neo4j Driver 模式：获取所有关系"""
        try:
            with self.neo4j_driver.session() as session:
                if workspace_id:
                    result = session.run("""
                        MATCH (a)-[r]->(b)
                        WHERE a.workspace_id = $workspace_id AND b.workspace_id = $workspace_id
                        RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props
                    """, workspace_id=workspace_id)
                else:
                    result = session.run("""
                        MATCH (a)-[r]->(b)
                        RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props
                    """)
                return [
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"],
                        "properties": record["props"]
                    }
                    for record in result
                ]
        except Exception as e:
            logger.info(f'Neo4j 获取关系失败: {e}')
            return []

    def _get_all_relations_fallback(self, workspace_id=None) -> List[Dict]:
        """回退模式：获取所有关系"""
        result = []
        for source, target, data in self.fallback_graph.edges(data=True):
            if workspace_id:
                src_ws = self.fallback_graph.nodes[source].get("workspace_id", "")
                tgt_ws = self.fallback_graph.nodes[target].get("workspace_id", "")
                if src_ws != workspace_id or tgt_ws != workspace_id:
                    continue
            result.append({
                "source": source,
                "target": target,
                "type": data.get("relationship", "RELATES_TO"),
                "properties": {k: v for k, v in data.items() if k != "relationship"}
            })
        return result

    # ------------------------------------------------------------------
    # get_entity_relations
    # ------------------------------------------------------------------
    def get_entity_relations(self, entity_id: str) -> List[Dict]:
        """
        获取实体的关系

        Args:
            entity_id: 实体ID

        Returns:
            关系列表
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._get_entity_relations_neo4j(entity_id)
        if self._test_mode and self._use_fallback:
            return self._get_entity_relations_fallback(entity_id)
        return []

    def _get_entity_relations_neo4j(self, entity_id: str) -> List[Dict]:
        """Neo4j Driver 模式：获取实体关系"""
        try:
            with self.neo4j_driver.session() as session:
                result = session.run("""
                    MATCH (a:Entity {id: $eid})-[r]->(b)
                    RETURN b.id AS target, type(r) AS type, properties(r) AS props
                    UNION
                    MATCH (a)-[r]->(b:Entity {id: $eid})
                    RETURN a.id AS target, type(r) AS type, properties(r) AS props
                """, eid=entity_id)
                return [
                    {
                        "target": record["target"],
                        "type": record["type"],
                        "properties": record["props"]
                    }
                    for record in result
                ]
        except Exception as e:
            logger.info(f'Neo4j 获取实体关系失败: {e}')
            return []

    def _get_entity_relations_fallback(self, entity_id: str) -> List[Dict]:
        """回退模式：获取实体关系"""
        result = []
        # 出边
        for target in self.fallback_graph.successors(entity_id):
            data = self.fallback_graph.edges[entity_id, target]
            result.append({
                "target": target,
                "type": data.get("relationship", "RELATES_TO"),
                "direction": "out"
            })
        # 入边
        for source in self.fallback_graph.predecessors(entity_id):
            data = self.fallback_graph.edges[source, entity_id]
            result.append({
                "target": source,
                "type": data.get("relationship", "RELATES_TO"),
                "direction": "in"
            })
        return result

    # ------------------------------------------------------------------
    # search_relations
    # ------------------------------------------------------------------
    def search_relations(self, keyword: str) -> List[Dict]:
        """
        搜索关系

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的关系列表
        """
        all_relations = self.get_all_relations()
        keyword_lower = keyword.lower()
        result = []
        for relation in all_relations:
            if (keyword_lower in relation.get("source", "").lower() or
                keyword_lower in relation.get("target", "").lower() or
                keyword_lower in relation.get("type", "").lower()):
                result.append(relation)
        return result

    # ------------------------------------------------------------------
    # get_relationship_stats
    # ------------------------------------------------------------------
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
            logger.info(f'关系统计获取失败: {e}')
            return {"status": "error", "error": str(e)}

    # ------------------------------------------------------------------
    # cleanup_self_loops
    # ------------------------------------------------------------------
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
                logger.info(f'自环关系清理完成: 清理了 {cleaned} 条自环关系')

                return {"status": "success", "cleaned": cleaned, "remaining": after}

        except Exception as e:
            logger.info(f'自环关系清理失败: {e}')
            return {"status": "error", "error": str(e), "cleaned": 0}
