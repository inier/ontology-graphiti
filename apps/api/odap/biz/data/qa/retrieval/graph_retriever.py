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
    """NL→Cypher 生成器（**确定性模板匹配**，无 LLM）。

    本体论原则（严格）：
    - 不生成 Cypher 文本，仅从**预定义模板** + 本体 schema（实体类型/关系类型）
      精确匹配选择模板，再填充已提取的实体名。
    - 模板是白名单（只读 MATCH/RETURN），无任何 LLM 生成内容。
    """

    def __init__(self, llm_client=None):
        # llm_client 保留以兼容旧调用方，但**不再使用**（确定性模板匹配无 LLM）。
        self.llm_client = None

    def generate(self, nl_query: str, schema: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """确定性生成：从模板库选择并填充实体名。无法匹配时返回 None。"""
        entity_name = _extract_entity_name(nl_query)
        if not entity_name:
            return None

        # 根据查询意图选择模板（确定性规则）
        template = self._select_template(nl_query, schema)
        if template is None:
            return None

        # path 模板含 {target} 占位符，无法确定性填充时返回 None（不猜测）
        if "{target}" in template:
            return None

        cypher = template.format(name=entity_name, limit=10)
        return cypher

    def _select_template(self, nl_query: str, schema: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """确定性选择模板：按查询关键词 + schema 关系类型匹配"""
        # 路径/最短 → path 模板（含 {target}，由调用方判断是否可填充）
        if re.search(r'路径|距离|最短|之间|从.*到', nl_query):
            return _CYPHER_TEMPLATES.get("path")
        # 统计/聚合 → type_count 模板（需 schema 实体类型）
        if re.search(r'多少|统计|数量|平均|最大|最小|排序|排名', nl_query):
            # 匹配 schema 中的实体类型（确定性，非 LLM 推断）
            label = self._match_entity_type(nl_query, schema)
            if label:
                return _CYPHER_TEMPLATES["type_count"].format(label=label, limit=10)
            return None
        # 关系/关联 → neighbors（默认）
        return _CYPHER_TEMPLATES.get("neighbors")

    def _match_entity_type(self, nl_query: str, schema: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """从 schema 中确定性匹配实体类型名（精确子串命中，非语义匹配）"""
        if not schema:
            return None
        for et in schema.get("entity_types", []):
            if et and et in nl_query:
                return et
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


# 预定义 Cypher 模板（确定性白名单，仅 READ）
# 注意：type_count 使用 {label} 占位符（由 schema 精确匹配填充），
#       其余模板使用 {name}/{limit} 占位符（由已提取实体名填充）。
_CYPHER_TEMPLATES = {
    "neighbors": "MATCH (n)-[r]-(m) WHERE n.name CONTAINS '{name}' RETURN n, type(r) AS rel_type, m LIMIT {limit}",
    "path": "MATCH p=shortestPath((n)-[*..3]-(m)) WHERE n.name CONTAINS '{name}' AND m.name CONTAINS '{target}' RETURN p LIMIT {limit}",
    "type_count": "MATCH (n:{label}) RETURN n LIMIT {limit}",
    "all_relations": "MATCH (n)-[r]->(m) WHERE n.name CONTAINS '{name}' RETURN n, type(r) AS rel_type, m LIMIT {limit}",
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
        """邻居查询：委托 _search_cypher 走 neighbors 模板。

        历史实现直接调 graph_manager.get_neighbors(entity_name)，但真实签名是
        get_neighbors(entity_id, direction, depth, workspace_id)——传名字语义不匹配，
        恒返回空。改为委托 _search_cypher，Cypher 模板 `WHERE n.name CONTAINS '{name}'`
        按名字查询语义正确。
        """
        return self._search_cypher(query, top_k, "", None)

    def _search_traverse(self, query: str, top_k: int) -> List[RetrievalResult]:
        """图遍历：委托 _search_cypher 走 path/neighbors 模板。

        同 _search_neighbors 的原因：graph_manager.traverse(start_id) 需要 entity_id
        而非 entity_name，直接调用恒空；委托给 Cypher 路径以按名字命中。
        """
        return self._search_cypher(query, top_k, "", None)

    def _search_cypher(self, query: str, top_k: int,
                       workspace_id: str, scenario_id: Optional[str]) -> List[RetrievalResult]:
        """Cypher 查询（确定性模板，无 LLM 生成）"""
        schema = self._get_schema(workspace_id)
        cypher = self.cypher_generator.generate(query, schema)
        if not cypher:
            # 降级: 使用已填充实体名的 neighbors 模板
            cypher = self._fallback_template(query, top_k)
        if not cypher:
            return []

        # 安全校验：CypherGenerator.validate() 之前在真实路径上从未被调用（探查报告 D1 次生缺陷）
        if not self.cypher_generator.validate(cypher):
            logger.warning(f"GraphRetriever: Cypher rejected by validate(): {cypher[:120]}")
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
            logger.warning(f"GraphRetriever: schema load failed (workspace_id={workspace_id!r}): {e}")
        return schema

    def _fallback_template(self, query: str, top_k: int) -> Optional[str]:
        """降级 Cypher 模板（返回已填充实体名的 neighbors 模板）"""
        entity_name = _extract_entity_name(query)
        if entity_name:
            return _CYPHER_TEMPLATES["neighbors"].format(name=entity_name, limit=top_k)
        return None

    def _convert_graph_results(self, raw: Any, source: str) -> List[RetrievalResult]:
        """将 GraphManager 结果转为统一格式（原为 _extract_entity_name return 后的死代码，D1 修复复位）"""
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
        """将 Cypher 查询结果转为统一格式（原为 _extract_entity_name return 后的死代码，D1 修复复位）"""
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


def _extract_entity_name(query: str) -> Optional[str]:
    """从查询中提取实体名（确定性规则，非 LLM）"""
    # 去除常见查询前缀
    cleaned = re.sub(r'^(查找|查询|搜索|找出|列出|显示|帮我|请|有没有|哪些)', '', query)
    cleaned = re.sub(r'(的关联|的关系|的邻居|有关|相关|连接|相连).*$', '', cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None
