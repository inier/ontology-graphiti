"""Graph 关联知识推理检索支柱 - 复用 GraphManager + NL→Cypher"""

import logging
import re
from typing import Any, Dict, List, Optional

from odap.biz.data.qa.models import RetrievalResult, RetrievalPillar

logger = logging.getLogger(__name__)

# Cypher 安全白名单: 仅允许 READ 操作
_CYPHER_DANGEROUS_KEYWORDS = re.compile(
    r'\b(CREATE|DELETE|DETACH|SET|REMOVE|MERGE|DROP|CALL\s*\{)\b',
    re.IGNORECASE
)


class CypherGenerator:
    """NL→Cypher 生成器"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def generate(self, nl_query: str, schema: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """从自然语言生成 Cypher 查询。LLM 不可用时返回 None。"""
        if not self.llm_client:
            return None
        try:
            schema_desc = ""
            if schema:
                entity_types = schema.get("entity_types", [])
                relation_types = schema.get("relation_types", [])
                if entity_types:
                    schema_desc += f"实体类型: {', '.join(entity_types[:20])}\n"
                if relation_types:
                    schema_desc += f"关系类型: {', '.join(relation_types[:20])}\n"

            prompt = (
                "你是一个 Cypher 查询生成器。根据用户的自然语言问题和图谱 Schema，"
                "生成一个只读的 Cypher 查询（仅 MATCH/RETURN/WHERE/ORDER BY/LIMIT）。\n"
                f"Schema:\n{schema_desc}\n"
                f"问题: {nl_query}\n"
                "Cypher (仅输出查询语句，不要解释):"
            )
            result = self.llm_client.generate(prompt, max_tokens=256, timeout=10)
            if result:
                cypher = result.strip()
                # 清理 markdown 代码块
                cypher = re.sub(r'^```(?:cypher)?\s*', '', cypher)
                cypher = re.sub(r'\s*```$', '', cypher)
                if self.validate(cypher):
                    return cypher
        except Exception as e:
            logger.debug(f"Cypher generation failed: {e}")
        return None

    def validate(self, cypher: str) -> bool:
        """安全校验: 仅允许 READ 操作"""
        if not cypher or not cypher.strip():
            return False
        if _CYPHER_DANGEROUS_KEYWORDS.search(cypher):
            logger.warning(f"Dangerous Cypher rejected: {cypher[:100]}")
            return False
        if not re.search(r'\bMATCH\b', cypher, re.IGNORECASE):
            return False
        return True

    def execute(self, cypher: str, graph_manager=None,
                params: Optional[Dict] = None, timeout: float = 10.0) -> List[Dict]:
        """执行 Cypher 查询"""
        if not graph_manager:
            return []
        try:
            if hasattr(graph_manager, 'execute_cypher'):
                return graph_manager.execute_cypher(cypher, params or {}, timeout=timeout)
            if hasattr(graph_manager, '_neo4j_driver') and graph_manager._neo4j_driver:
                with graph_manager._neo4j_driver.session() as session:
                    result = session.run(cypher, params or {})
                    return [record.data() for record in result]
        except Exception as e:
            logger.error(f"Cypher execution failed: {e}")
        return []


# 预定义 Cypher 模板（LLM 不可用时降级）
_CYPHER_TEMPLATES = {
    "neighbors": "MATCH (n)-[r]-(m) WHERE n.name CONTAINS $name OR n.entity_id = $id RETURN n, type(r) AS rel_type, m LIMIT $limit",
    "path": "MATCH p=shortestPath((n)-[*..3]-(m)) WHERE n.name CONTAINS $name AND m.name CONTAINS $target RETURN p LIMIT $limit",
    "type_count": "MATCH (n:{label}) RETURN n LIMIT $limit",
    "all_relations": "MATCH (n)-[r]->(m) WHERE n.name CONTAINS $name RETURN n, type(r) AS rel_type, m LIMIT $limit",
}


class GraphRetriever:
    """Graph 检索器: 统一图查询入口"""

    def __init__(self, graph_manager=None, cypher_generator: Optional[CypherGenerator] = None):
        self.graph_manager = graph_manager
        self.cypher_generator = cypher_generator or CypherGenerator()

    def search(self, query: str, top_k: int = 10,
               workspace_id: str = "",
               scenario_id: Optional[str] = None,
               mode: str = "auto") -> List[RetrievalResult]:
        """图检索: neighbors / traverse / cypher / auto"""
        if not self.graph_manager:
            return []

        if mode == "auto":
            mode = self._auto_select_mode(query)

        if mode == "cypher":
            return self._search_cypher(query, top_k, workspace_id, scenario_id)
        elif mode == "neighbors":
            return self._search_neighbors(query, top_k)
        elif mode == "traverse":
            return self._search_traverse(query, top_k)
        else:
            # 默认尝试 neighbors
            return self._search_neighbors(query, top_k)

    def _auto_select_mode(self, query: str) -> str:
        """根据查询内容自动选择模式"""
        # 包含"关联/关系/连接" → neighbors
        if re.search(r'关联|关系|连接|相连|邻居', query):
            return "neighbors"
        # 包含"路径/距离/最短" → traverse
        if re.search(r'路径|距离|最短|之间|从.*到', query):
            return "traverse"
        # 包含复杂聚合/统计 → cypher
        if re.search(r'多少|统计|数量|平均|最大|最小|排序|排名', query):
            return "cypher"
        # 默认 neighbors
        return "neighbors"

    def _search_neighbors(self, query: str, top_k: int) -> List[RetrievalResult]:
        """邻居查询"""
        try:
            if hasattr(self.graph_manager, 'get_neighbors'):
                # 尝试从查询中提取实体名
                entity_name = self._extract_entity_name(query)
                if entity_name:
                    raw = self.graph_manager.get_neighbors(entity_name, depth=1)
                    return self._convert_graph_results(raw, "neighbors")
        except Exception as e:
            logger.debug(f"Neighbors search failed: {e}")
        return []

    def _search_traverse(self, query: str, top_k: int) -> List[RetrievalResult]:
        """图遍历"""
        try:
            if hasattr(self.graph_manager, 'traverse'):
                entity_name = self._extract_entity_name(query)
                if entity_name:
                    raw = self.graph_manager.traverse(entity_name, max_depth=3)
                    return self._convert_graph_results(raw, "traverse")
        except Exception as e:
            logger.debug(f"Traverse search failed: {e}")
        return []

    def _search_cypher(self, query: str, top_k: int,
                       workspace_id: str, scenario_id: Optional[str]) -> List[RetrievalResult]:
        """Cypher 查询"""
        schema = self._get_schema(workspace_id)
        cypher = self.cypher_generator.generate(query, schema)
        if not cypher:
            # 降级: 使用模板
            cypher = self._fallback_template(query, top_k)
        if not cypher:
            return []

        records = self.cypher_generator.execute(cypher, self.graph_manager)
        return self._convert_cypher_results(records, cypher)

    def _get_schema(self, workspace_id: str) -> Dict[str, Any]:
        """获取本体 schema"""
        schema: Dict[str, Any] = {"entity_types": [], "relation_types": []}
        try:
            from odap.infra.query.service import QueryService
            qs = QueryService()
            if hasattr(qs, '_schema_source') and qs._schema_source:
                types = qs._schema_source.query_object_types(workspace_id=workspace_id)
                schema["entity_types"] = [t.get("name", "") for t in (types or []) if isinstance(t, dict)]
                rels = qs._schema_source.query_link_definitions(workspace_id=workspace_id)
                schema["relation_types"] = [r.get("name", "") for r in (rels or []) if isinstance(r, dict)]
        except Exception as e:
            logger.debug(f"Schema load failed: {e}")
        return schema

    def _fallback_template(self, query: str, top_k: int) -> Optional[str]:
        """降级 Cypher 模板"""
        entity_name = self._extract_entity_name(query)
        if entity_name:
            return _CYPHER_TEMPLATES["neighbors"]
        return None

    def _extract_entity_name(self, query: str) -> Optional[str]:
        """从查询中提取实体名（简单规则）"""
        # 去除常见查询前缀
        cleaned = re.sub(r'^(查找|查询|搜索|找出|列出|显示|帮我|请|有没有|哪些)', '', query)
        cleaned = re.sub(r'(的关联|的关系|的邻居|有关|相关|连接|相连).*$', '', cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else None

    def _convert_graph_results(self, raw: Any, source: str) -> List[RetrievalResult]:
        """将 GraphManager 结果转为统一格式"""
        results: List[RetrievalResult] = []
        if not raw:
            return results

        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            if isinstance(item, dict):
                results.append(RetrievalResult(
                    doc_id=item.get("entity_id", item.get("id", "")),
                    content=item.get("name", item.get("fact", str(item))),
                    score=float(item.get("score", 0.5)),
                    pillar=RetrievalPillar.GRAPH,
                    source=source,
                    metadata=item,
                ))
        return results

    def _convert_cypher_results(self, records: List[Dict], cypher: str) -> List[RetrievalResult]:
        """将 Cypher 查询结果转为统一格式"""
        results: List[RetrievalResult] = []
        for i, record in enumerate(records):
            # 尝试从记录中提取内容
            content_parts = []
            for key, value in record.items():
                if isinstance(value, dict):
                    content_parts.append(value.get("name", value.get("fact", str(value))))
                elif value is not None:
                    content_parts.append(str(value))
            results.append(RetrievalResult(
                doc_id=f"cypher_{i}",
                content=" | ".join(content_parts) if content_parts else str(record),
                score=0.5,
                pillar=RetrievalPillar.GRAPH,
                source="cypher",
                metadata={"cypher": cypher, "record": record},
            ))
        return results
