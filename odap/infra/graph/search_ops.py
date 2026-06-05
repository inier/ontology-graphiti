"""
搜索与遍历操作 Mixin

提供 GraphManager 的搜索、混合检索、RAG 上下文、邻居查询、图遍历等功能。
"""

import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any

from ._utils import _run_async



import logging

logger = logging.getLogger(__name__)
class SearchOpsMixin:
    """搜索与遍历：search, search_hybrid, search_entities, retrieve_rag_context, get_neighbors, traverse, analyze_graph"""

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """
        搜索实体

        Args:
            query: 搜索查询
            limit: 返回结果数量限制

        Returns:
            匹配的实体列表
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._search_neo4j(query, limit)
        if self._test_mode and self._use_fallback:
            return self._search_fallback(query, limit)
        return []

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
            logger.info(f'Neo4j 搜索失败: {e}')
            if self._test_mode and self._use_fallback:
                return self._search_fallback(query, limit)
            return []

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

    def _search_neo4j_keyword(self, query_text: str, limit: int = 5) -> List[Dict]:
        """Neo4j 关键词检索模式"""
        # 提取 user: 或 用户: 后面的内容
        matches = re.findall(r'(?i)(?:user:|用户:)\s*([^\n]+)', query_text)
        if matches:
            unique_matches = list(dict.fromkeys(matches))
            clean_query = " ".join(unique_matches)
        else:
            clean_query = query_text

        clean_query = clean_query.replace("\n", " ").replace("\r", " ")
        clean_query = " ".join(clean_query.split())

        logger.info(f"[DEBUG] _search_neo4j_keyword: original='{query_text}', cleaned='{clean_query}'")

        if not clean_query:
            logger.info('[DEBUG] 查询词为空，返回空结果')
            return []

        try:
            with self.neo4j_driver.session() as session:
                cypher = (
                    "MATCH (n) "
                    "WHERE n.id CONTAINS $q OR n.name CONTAINS $q "
                    "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props "
                    "LIMIT $lmt"
                )
                result = session.run(cypher, q=clean_query, lmt=limit)
                keyword_results = [
                    {
                        "id": record["id"],
                        "type": [l for l in record["labels"] if l != "Entity"][0] if len(record["labels"]) > 1 else "Entity",
                        "properties": record["props"],
                        "score": 0.8
                    }
                    for record in result
                ]
                logger.info(f'[DEBUG] Neo4j 检索返回 {len(keyword_results)} 条结果')
                return keyword_results
        except Exception as e:
            logger.info(f'Neo4j 关键词检索失败: {e}')
            if self._test_mode and self._use_fallback:
                return self._search_fallback(query_text, limit=limit)
            return []

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
                logger.info(f'Graphiti搜索失败: {e}')
                if self._test_mode and self._use_fallback:
                    return self._search_fallback(query, limit)
                return []

        return _run_async(search())

    # ------------------------------------------------------------------
    # search_hybrid
    # ------------------------------------------------------------------
    def search_hybrid(self, query_text: str, top_k: int = 5, vector_weight: float = 0.7, keyword_weight: float = 0.3) -> List[Dict]:
        """
        混合检索（向量 + 关键词）

        Args:
            query_text: 查询文本
            top_k: 返回前k个结果
            vector_weight: 向量检索权重
            keyword_weight: 关键词检索权重

        Returns:
            检索结果列表
        """
        if self._use_fallback or not self._connected:
            if self._test_mode:
                logger.info(f"[DEBUG] 使用回退模式搜索: '{query_text}'")
                return self._search_fallback(query_text, limit=top_k)
            return self._unavailable_error()

        if self.graph and self._connected:
            async def hybrid_search():
                try:
                    vector_results = await self.graph.search(query=query_text, num_results=top_k)

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
                                        "score": 0.5
                                    }
                                    for record in result
                                ]
                        except Exception as e:
                            logger.info(f'Neo4j关键词检索失败: {e}')

                    combined = {}
                    for r in vector_results:
                        entity_id = r.name or str(r.uuid)
                        combined[entity_id] = {
                            "id": entity_id,
                            "type": "EntityEdge",
                            "properties": {
                                "fact": r.fact,
                                "source_node": r.source_node_uuid,
                                "target_node": r.target_node_uuid,
                            },
                            "score": r.score if hasattr(r, 'score') else 0.7
                        }

                    for r in keyword_results:
                        if r["id"] not in combined:
                            combined[r["id"]] = r

                    final_results = sorted(combined.values(), key=lambda x: x.get("score", 0), reverse=True)[:top_k]
                    return final_results

                except Exception as e:
                    logger.info(f'Graphiti混合检索失败: {e}')
                    if self.neo4j_driver:
                        return self._search_neo4j_keyword(query_text, limit=top_k)
                    raise RuntimeError("Graphiti检索失败，且没有可用的降级方案")

            return _run_async(hybrid_search())

        if self.neo4j_driver:
            return self._search_neo4j_keyword(query_text, limit=top_k)

        return self._unavailable_error()

    # ------------------------------------------------------------------
    # search_entities
    # ------------------------------------------------------------------
    def search_entities(self, keyword: str) -> List[Dict]:
        """
        搜索实体

        Args:
            keyword: 搜索关键词

        Returns:
            匹配的实体列表
        """
        return self.search(keyword)

    # ------------------------------------------------------------------
    # retrieve_rag_context
    # ------------------------------------------------------------------
    def retrieve_rag_context(self, query: str, top_k: int = 5) -> str:
        """
        RAG 上下文检索：基于 Graphiti 的向量搜索 + Episode 回忆，
        返回自然语言上下文段落供 LLM 参考。

        Args:
            query: 查询文本
            top_k: 返回前 k 条相关结果

        Returns:
            自然语言上下文段落（多条拼接）
        """
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._retrieve_rag_neo4j(query, top_k)
        if self._test_mode and self._use_fallback:
            return self._retrieve_rag_fallback(query, top_k)
        return ""

    def _retrieve_rag_graphiti(self, query: str, top_k: int) -> str:
        """Graphiti 模式：向量搜索 + Episode 检索"""
        async def retrieve():
            try:
                edges = await self.graph.search(query=query, num_results=top_k)
                episodes = await self.graph.retrieve_episodes(
                    reference_time=datetime.now()
                )

                context_parts = []

                for edge in edges:
                    if edge.fact:
                        context_parts.append(f"- {edge.fact}")

                query_lower = query.lower()
                for ep in episodes[:20]:
                    if ep.content and query_lower in ep.content.lower():
                        context_parts.append(f"- [{ep.name}] {ep.content[:200]}")
                    elif context_parts and len(context_parts) < top_k:
                        if len(context_parts) < 3:
                            context_parts.append(f"- [{ep.name}] {ep.content[:150]}")

                if not context_parts:
                    return ""

                return "历史情报记忆：\n" + "\n".join(context_parts[:top_k])

            except Exception as e:
                logger.info(f'Graphiti RAG 检索失败: {e}')
                return ""

        return _run_async(retrieve())

    def _retrieve_rag_neo4j(self, query: str, top_k: int) -> str:
        """Neo4j Driver 模式：Cypher 全文匹配"""
        try:
            with self.neo4j_driver.session() as session:
                cypher = (
                    "MATCH (n) "
                    "WHERE n.id CONTAINS $q OR n.name CONTAINS $q OR n.properties.name CONTAINS $q "
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
            logger.info(f'Neo4j RAG 检索失败: {e}')
            if self._test_mode and self._use_fallback:
                return self._retrieve_rag_fallback(query, top_k)
            return ""

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

    # ------------------------------------------------------------------
    # get_neighbors
    # ------------------------------------------------------------------
    def get_neighbors(self, entity_id: str, direction: str = "both", depth: int = 1, workspace_id: str = None) -> List[Dict]:
        """
        获取实体的邻居节点

        Args:
            entity_id: 起始实体ID
            direction: 遍历方向 ("out"/"in"/"both")
            depth: 遍历深度 (1-3)
            workspace_id: 工作空间ID

        Returns:
            邻居节点列表，每个元素含 id, type, properties, distance, direction
        """
        depth = max(1, min(depth, 3))
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._get_neighbors_neo4j(entity_id, direction, depth, workspace_id)
        if self._test_mode and self._use_fallback:
            return self._get_neighbors_fallback(entity_id, direction, depth)
        return []

    def _get_neighbors_neo4j(self, entity_id: str, direction: str, depth: int, workspace_id: str = None) -> List[Dict]:
        """Neo4j Driver 模式：获取邻居节点"""
        try:
            ws_filter = " AND b.workspace_id = $workspace_id" if workspace_id else ""
            if direction == "out":
                pattern = "(a:Entity {id: $eid})-[r*1..{d}]->(b)"
            elif direction == "in":
                pattern = "(a:Entity {id: $eid})<-[r*1..{d}]-(b)"
            else:
                pattern = "(a:Entity {id: $eid})-[r*1..{d}]-(b)"
            query = f"""
                MATCH {pattern}
                WHERE NOT b:Episode{ws_filter}
                RETURN DISTINCT b.id AS id, b.entity_type AS type,
                       b.name AS name, length(r) AS distance
                ORDER BY distance
                LIMIT 100
            """
            query = query.replace("{d}", str(depth))
            params = {"eid": entity_id}
            if workspace_id:
                params["workspace_id"] = workspace_id
            with self.neo4j_driver.session() as session:
                result = session.run(query, **params)
                neighbors = []
                for record in result:
                    node_id = record["id"]
                    if node_id == entity_id:
                        continue
                    neighbors.append({
                        "id": node_id,
                        "type": record["type"],
                        "name": record.get("name", ""),
                        "distance": record["distance"],
                    })
                return neighbors
        except Exception as e:
            logger.info(f'Neo4j 获取邻居失败: {e}')
            return []

    def _get_neighbors_fallback(self, entity_id: str, direction: str, depth: int) -> List[Dict]:
        """回退模式：获取邻居节点"""
        visited = {entity_id}
        current_level = {entity_id}
        neighbors = []
        for d in range(1, depth + 1):
            next_level = set()
            for nid in current_level:
                if direction in ("out", "both"):
                    for succ in self.fallback_graph.successors(nid):
                        if succ not in visited:
                            visited.add(succ)
                            next_level.add(succ)
                            data = self.fallback_graph.nodes.get(succ, {})
                            neighbors.append({
                                "id": succ,
                                "type": data.get("entity_type", "Unknown"),
                                "name": data.get("name", succ),
                                "distance": d,
                            })
                if direction in ("in", "both"):
                    for pred in self.fallback_graph.predecessors(nid):
                        if pred not in visited:
                            visited.add(pred)
                            next_level.add(pred)
                            data = self.fallback_graph.nodes.get(pred, {})
                            neighbors.append({
                                "id": pred,
                                "type": data.get("entity_type", "Unknown"),
                                "name": data.get("name", pred),
                                "distance": d,
                            })
            current_level = next_level
        return neighbors

    # ------------------------------------------------------------------
    # traverse
    # ------------------------------------------------------------------
    def traverse(self, start_id: str, max_depth: int = 3, workspace_id: str = None) -> Dict[str, Any]:
        """
        从起始实体遍历图，返回子图

        Args:
            start_id: 起始实体ID
            max_depth: 最大遍历深度 (1-5)
            workspace_id: 工作空间ID

        Returns:
            子图数据，含 nodes 和 edges
        """
        max_depth = max(1, min(max_depth, 5))
        if self._mode in ("neo4j_driver", "graphiti") and self.neo4j_driver:
            return self._traverse_neo4j(start_id, max_depth, workspace_id)
        if self._test_mode and self._use_fallback:
            return self._traverse_fallback(start_id, max_depth)
        return self._unavailable_error()

    def _traverse_neo4j(self, start_id: str, max_depth: int, workspace_id: str = None) -> Dict[str, Any]:
        """Neo4j Driver 模式：图遍历"""
        try:
            ws_filter = " AND b.workspace_id = $workspace_id" if workspace_id else ""
            node_query = f"""
                MATCH (a:Entity {{id: $eid}})-[r*1..{max_depth}]-(b:Entity)
                WHERE NOT b:Episode{ws_filter}
                RETURN DISTINCT b.id AS id, b.entity_type AS type, b.name AS name,
                       properties(b) AS props
            """
            edge_query = f"""
                MATCH (a:Entity {{id: $eid}})-[r*1..{max_depth}]-(b:Entity)
                WHERE NOT b:Episode
                WITH DISTINCT a, b
                MATCH (a)-[e]->(b)
                RETURN a.id AS source, type(e) AS type, b.id AS target, properties(e) AS props
            """
            params = {"eid": start_id}
            if workspace_id:
                params["workspace_id"] = workspace_id
            nodes = []
            with self.neo4j_driver.session() as session:
                result = session.run(node_query, **params)
                seen = set()
                for record in result:
                    nid = record["id"]
                    if nid in seen:
                        continue
                    seen.add(nid)
                    props = dict(record.get("props", {}))
                    props.pop("entity_type", None)
                    props.pop("id", None)
                    nodes.append({
                        "id": nid,
                        "type": record["type"],
                        "name": record.get("name", ""),
                        "properties": props,
                    })
                edges = []
                result = session.run(edge_query, **params)
                seen_edges = set()
                for record in result:
                    edge_key = (record["source"], record["target"], record["type"])
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": record["source"],
                        "target": record["target"],
                        "type": record["type"],
                        "properties": record.get("props", {}),
                    })
            start_data = self.get_entity(start_id) or {"id": start_id, "type": "Unknown", "name": ""}
            if not any(n["id"] == start_id for n in nodes):
                nodes.insert(0, start_data)
            return {"nodes": nodes, "edges": edges, "start_id": start_id, "max_depth": max_depth}
        except Exception as e:
            logger.info(f'Neo4j 图遍历失败: {e}')
            return {"nodes": [], "edges": [], "start_id": start_id, "max_depth": max_depth}

    def _traverse_fallback(self, start_id: str, max_depth: int) -> Dict[str, Any]:
        """回退模式：图遍历"""
        visited_nodes = {}
        visited_edges = []
        queue = [(start_id, 0)]
        seen = {start_id}
        while queue:
            nid, dist = queue.pop(0)
            data = self.fallback_graph.nodes.get(nid, {})
            if nid not in visited_nodes:
                visited_nodes[nid] = {
                    "id": nid,
                    "type": data.get("entity_type", "Unknown"),
                    "name": data.get("name", nid),
                    "properties": {k: v for k, v in data.items() if k not in ("entity_type", "name")},
                }
            if dist >= max_depth:
                continue
            for succ in self.fallback_graph.successors(nid):
                edge_data = self.fallback_graph.edges[nid, succ]
                visited_edges.append({
                    "source": nid,
                    "target": succ,
                    "type": edge_data.get("relationship", "RELATES_TO"),
                    "properties": {k: v for k, v in edge_data.items() if k != "relationship"},
                })
                if succ not in seen:
                    seen.add(succ)
                    queue.append((succ, dist + 1))
            for pred in self.fallback_graph.predecessors(nid):
                edge_data = self.fallback_graph.edges[pred, nid]
                visited_edges.append({
                    "source": pred,
                    "target": nid,
                    "type": edge_data.get("relationship", "RELATES_TO"),
                    "properties": {k: v for k, v in edge_data.items() if k != "relationship"},
                })
                if pred not in seen:
                    seen.add(pred)
                    queue.append((pred, dist + 1))
        return {
            "nodes": list(visited_nodes.values()),
            "edges": visited_edges,
            "start_id": start_id,
            "max_depth": max_depth,
        }

    # ------------------------------------------------------------------
    # analyze_graph
    # ------------------------------------------------------------------
    def analyze_graph(self) -> Dict[str, Any]:
        """
        分析图谱

        Returns:
            分析结果
        """
        stats = self.get_statistics()
        entities = self.get_all_entities()
        relations = self.get_all_relations()

        # 实体类型分布
        entity_types = {}
        for entity in entities:
            etype = entity.get("type", "Unknown")
            entity_types[etype] = entity_types.get(etype, 0) + 1

        # 关系类型分布
        relation_types = {}
        for relation in relations:
            rtype = relation.get("type", "Unknown")
            relation_types[rtype] = relation_types.get(rtype, 0) + 1

        return {
            "total_entities": len(entities),
            "total_relations": len(relations),
            "entity_types": entity_types,
            "relation_types": relation_types,
            "density": len(relations) / max(len(entities), 1),
            "statistics": stats,
        }
