import os
import re
import json
import logging
from typing import Dict, Any, List, Optional

from ..storage.sqlite_kb_storage import SQLiteKnowledgeBaseStorage

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    _instance = None

    @classmethod
    def get_instance(cls) -> "KnowledgeBaseService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, storage: SQLiteKnowledgeBaseStorage = None):
        self._storage = storage or SQLiteKnowledgeBaseStorage()
        self._graph_tasks: Dict[str, Dict[str, Any]] = {}

    def _create_llm_client(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            api_base = os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
            model = os.getenv("OPENAI_MODEL", "glm-4-flash")
            config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.7)
            return ZhipuAIClient(config=config)
        except Exception as e:
            logger.warning(f"LLM client init failed: {e}")
            return None

    async def _call_llm(self, prompt: str) -> Optional[Dict[str, Any]]:
        llm = self._create_llm_client()
        if not llm:
            return None
        try:
            from graphiti_core.prompts.models import Message

            messages = [
                Message(role="system", content="你是一个知识图谱构建专家，擅长从文本中提取实体和关系。只返回JSON。"),
                Message(role="user", content=prompt),
            ]

            response, _, _ = await llm._generate_response(messages)
            return response
        except Exception as e:
            logger.warning(f"LLM call failed: {repr(e)}", exc_info=True)
            return None

    def _extract_with_regex(self, content: str, entity_types: List[str] = None) -> Dict[str, Any]:
        entities = []
        relations = []

        # 通用领域实体模式（覆盖军事+电商+企业等领域）
        patterns = [
            # 军事/国防领域
            r'[\u4e00-\u9fff]{2,10}(?:编队|组织|部门|支队|分队|小组|团队)',
            r'[\u4e00-\u9fff]{2,8}(?:系统|设备|平台|载具|传感器|装置)',
            # 电商/企业领域
            r'[\u4e00-\u9fff]{2,10}(?:平台|会员|经销商|服务商|供应商|商家|用户|客户)',
            r'[\u4e00-\u9fff]{2,8}(?:订单|商品|产品|积分|权益|优惠券|发票|评价|活动|库存|结算)',
            r'[\u4e00-\u9fff]{2,8}(?:等级|账户|记录|车辆|档案|预约|营销|合同)',
            # 英文大写词
            r'\b[Bb]2[Bb]2[Cc]\b',
            r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',
            # 中文关键词短语（2-6字常见实体）
            r'[\u4e00-\u9fff]{2,6}(?:管理体系|服务|系统|模型|流程|规则|策略)',
            # 数字+单位模式
            r'\d+(?:元|万元|亿元|分|次|项|级|类)',
        ]

        if entity_types:
            for etype in entity_types:
                if re.search(r'[\u4e00-\u9fff]', etype):
                    patterns.append(rf'[\u4e00-\u9fff]{{2,8}}{re.escape(etype)}')

        found = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            found.update(matches)

        # 构建 name → external_id 映射
        name_to_id = {}
        for name in found:
            entity_type = "extracted_entity"
            if any(kw in name for kw in ('会员', '用户', '客户', 'Member')):
                entity_type = "member"
            elif any(kw in name for kw in ('订单', 'Order')):
                entity_type = "order"
            elif any(kw in name for kw in ('商品', '产品', 'Product')):
                entity_type = "product"
            elif any(kw in name for kw in ('经销商', '服务商', '供应商', '商家', 'Dealer')):
                entity_type = "business_partner"
            elif any(kw in name for kw in ('积分', 'Points')):
                entity_type = "points"
            elif any(kw in name for kw in ('权益', '优惠券', 'Benefit', 'Coupon')):
                entity_type = "benefit"
            elif any(kw in name for kw in ('平台', 'Platform')):
                entity_type = "platform"
            elif any(kw in name for kw in ('车辆', 'Vehicle')):
                entity_type = "vehicle"
            entities.append({"name": name, "type": entity_type, "properties": {}})
            name_to_id[name] = name

        # 关系提取：基于中文关系模式
        RELATION_PATTERNS = [
            (r'([\u4e00-\u9fff]{2,10})的([\u4e00-\u9fff]{2,10})', "HAS_ATTRIBUTE"),
            (r'([\u4e00-\u9fff]{2,10})(?:管理|负责|运营)([\u4e00-\u9fff]{2,10})', "MANAGES"),
            (r'([\u4e00-\u9fff]{2,10})(?:提供|供应|服务)([\u4e00-\u9fff]{2,10})', "PROVIDES"),
            (r'([\u4e00-\u9fff]{2,10})(?:包含|包括|涵盖)([\u4e00-\u9fff]{2,10})', "CONTAINS"),
            (r'([\u4e00-\u9fff]{2,10})(?:属于|归属|隶属)([\u4e00-\u9fff]{2,10})', "BELONGS_TO"),
        ]

        rel_seen = set()
        for sentence in re.split(r'[。，；\n,;]', content):
            sentence = sentence.strip()
            if len(sentence) < 4:
                continue
            for pattern, rel_type in RELATION_PATTERNS:
                for match in re.finditer(pattern, sentence):
                    source, target = match.group(1), match.group(2)
                    rel_key = (source, target, rel_type)
                    if rel_key not in rel_seen:
                        rel_seen.add(rel_key)
                        relations.append({
                            "source": source,
                            "target": target,
                            "type": rel_type,
                        })

        return {"entities": entities, "relations": relations}

    def _write_to_graph(self, kb_id: str, doc_id: str, entities: List[Dict], relations: List[Dict]) -> bool:
        """将抽取的实体和关系写入 Neo4j 图谱。

        使用 GraphWriteProxy（架构规则：业务模块禁止直接使用 GraphManager 写操作）。
        实体 ID 格式: kb_{kb_id}_{entity_name}，确保跨文档去重。
        """
        try:
            from odap.infra.query.graph_write_proxy import get_graph_write_proxy
            write_proxy = get_graph_write_proxy()

            # 检查 GraphManager 是否可用
            gm = write_proxy._get_graph_manager()
            if gm is None or gm._mode == "unavailable":
                logger.warning("GraphManager 处于 unavailable 模式，无法写入图谱数据")
                return False

            # 写入实体，建立 name→entity_id 映射供关系引用
            name_to_id: Dict[str, str] = {}
            success_count = 0
            for entity in entities:
                name = entity.get("name", "")
                etype = entity.get("type", "unknown")
                entity_id = f"kb_{kb_id}_{name}"
                name_to_id[name] = entity_id

                # 生成 type_id（ASCII 安全标识符）
                entity_type_id = etype.lower().replace(' ', '_')
                if re.search(r'[\u4e00-\u9fff]', entity_type_id):
                    entity_type_id = "zh_type"

                props = {
                    **entity.get("properties", {}),
                    "source_doc": doc_id,
                    "kb_id": kb_id,
                    "name": name,
                    "entity_type_id": entity_type_id,
                }
                result = write_proxy.add_entity(entity_id, etype, props)
                if result.get("status") == "success":
                    success_count += 1

            # 写入关系，通过 name_to_id 解析 source/target
            for rel in relations:
                source_name = rel.get("source", "")
                target_name = rel.get("target", "")
                source_id = name_to_id.get(source_name, f"kb_{kb_id}_{source_name}")
                target_id = name_to_id.get(target_name, f"kb_{kb_id}_{target_name}")
                rel_type = rel.get("type", "related_to")
                props = {k: v for k, v in rel.items() if k not in ("source", "target", "type")}
                write_proxy.add_relationship(source_id, target_id, rel_type, props)

            return success_count > 0 or len(entities) == 0
        except Exception as e:
            logger.warning(f"GraphWriteProxy write failed: {repr(e)}", exc_info=True)
            return False

    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        return self._storage.list_knowledge_bases()

    def get_knowledge_base(self, kb_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_knowledge_base(kb_id)
        if not result:
            return {"status": "error", "message": "知识库不存在"}
        return result

    def create_knowledge_base(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_knowledge_base(data)

    def update_knowledge_base(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        result = self._storage.update_knowledge_base(kb_id, data)
        if not result:
            return {"status": "error", "message": "知识库不存在"}
        return result

    def delete_knowledge_base(self, kb_id: str) -> Dict[str, Any]:
        success = self._storage.delete_knowledge_base(kb_id)
        if not success:
            return {"status": "error", "message": "知识库不存在"}
        return {"status": "success", "message": "知识库删除成功"}

    def list_categories(self, kb_id: str) -> List[Dict[str, Any]]:
        return self._storage.list_categories(kb_id)

    def create_category(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_category(kb_id, data)

    def delete_category(self, kb_id: str, category_id: str) -> Dict[str, Any]:
        success = self._storage.delete_category(kb_id, category_id)
        if not success:
            return {"status": "error", "message": "分类不存在"}
        return {"status": "success", "message": "分类删除成功"}

    def list_documents(self, kb_id: str, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._storage.list_documents(kb_id, category_id)

    def create_document(self, kb_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        return self._storage.create_document(kb_id, data)

    def get_document(self, kb_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        result = self._storage.get_document(kb_id, doc_id)
        if not result:
            return {"status": "error", "message": "文档不存在"}
        return result

    def delete_document(self, kb_id: str, doc_id: str) -> Dict[str, Any]:
        success = self._storage.delete_document(kb_id, doc_id)
        if not success:
            return {"status": "error", "message": "文档不存在"}
        return {"status": "success", "message": "文档删除成功"}

    async def build_graph(
        self, doc_id: str, extraction_method: str = "auto", entity_types: List[str] = None
    ) -> Dict[str, Any]:
        doc = self._storage.find_document_by_id(doc_id)
        if not doc:
            return {"status": "error", "message": "文档不存在"}

        content = (doc.get("cleaned_content") or doc.get("content", "")) or ""
        if not content.strip():
            return {"status": "error", "message": "文档内容为空，无法构建图谱"}

        task_id = f"task_{doc_id}"
        self._graph_tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "method": extraction_method,
        }

        entities = []
        relations = []
        used_method = extraction_method

        if extraction_method in ("llm", "auto"):
            prompt = f"""从以下文本中提取实体和关系，以JSON格式返回：
{{
  "entities": [{{"name": "实体名", "type": "类型", "properties": {{}}}}],
  "relations": [{{"source": "实体1", "target": "实体2", "type": "关系类型"}}]
}}

文本内容：
{content[:8000]}"""
            llm_result = await self._call_llm(prompt)
            if llm_result and isinstance(llm_result, dict):
                entities = llm_result.get("entities", [])
                relations = llm_result.get("relations", [])
                used_method = "llm"
            elif extraction_method == "llm":
                self._graph_tasks[task_id] = {
                    "status": "failed",
                    "progress": 0,
                    "method": "llm",
                    "error": "LLM提取失败",
                    "entities_extracted": 0,
                    "relations_extracted": 0,
                }
                return {
                    "task_id": task_id,
                    "status": "failed",
                    "method": "llm",
                    "entities_extracted": 0,
                    "relations_extracted": 0,
                }

        if not entities and extraction_method in ("regex", "auto"):
            regex_result = self._extract_with_regex(content, entity_types)
            entities = regex_result.get("entities", [])
            relations = regex_result.get("relations", [])
            used_method = "regex"

        graph_ok = self._write_to_graph(doc.get("kb_id", ""), doc_id, entities, relations)

        # 索引文档内容到 Graphiti（支持向量语义检索）
        kb_id_from_doc = doc.get("kb_id", "")
        try:
            from odap.infra.graph.graph_service import GraphManager
            from datetime import datetime, timezone
            graph_manager = GraphManager()
            if graph_manager._mode in ("graphiti", "neo4j_driver") and not graph_manager._use_fallback:
                cleaned_content = doc.get("cleaned_content") or content
                if cleaned_content and cleaned_content.strip():
                    episode_name = f"kb_doc_{doc_id}"
                    success = await graph_manager.add_episode(
                        name=episode_name,
                        content=cleaned_content[:50000],
                        source_description=f"KB:{kb_id_from_doc}",
                        reference_time=datetime.now(timezone.utc),
                    )
                    if success:
                        logger.info(f"Document {doc_id} indexed to Graphiti as Episode {episode_name}")
        except Exception as e:
            logger.warning(f"Graphiti Episode indexing skipped for doc {doc_id}: {e}")

        if not graph_ok and entities:
            self._graph_tasks[task_id] = {
                "status": "failed",
                "progress": 0,
                "method": used_method,
                "error": "图数据库写入失败，请检查 Neo4j 连接",
                "entities_extracted": 0,
                "relations_extracted": 0,
            }
            return {
                "task_id": task_id,
                "status": "failed",
                "method": used_method,
                "entities_extracted": 0,
                "relations_extracted": 0,
                "error": "图数据库写入失败，请检查 Neo4j 连接",
            }

        entities_extracted = len(entities)
        relations_extracted = len(relations)
        self._storage.update_document_graph_status(doc_id, True, entities_extracted)

        self._graph_tasks[task_id] = {
            "status": "completed",
            "progress": 100,
            "method": used_method,
            "entities_extracted": entities_extracted,
            "relations_extracted": relations_extracted,
        }

        return {
            "task_id": task_id,
            "status": "completed",
            "entities_extracted": entities_extracted,
            "relations_extracted": relations_extracted,
            "method": used_method,
        }

    def get_graph_build_status(self, task_id: str) -> Dict[str, Any]:
        task = self._graph_tasks.get(task_id)
        if not task:
            return {"status": "error", "message": "任务不存在"}
        return task

    def get_kb_graph(self, kb_id: str) -> Dict[str, Any]:
        """查询指定知识库的图谱数据，返回 nodes + edges 供前端可视化。

        Neo4j 优先；Neo4j 不可用时降级为 SQLite entities_json 数据。
        """
        try:
            from odap.infra.graph.graph_service import GraphManager
            gm = GraphManager()
            if gm._mode != "unavailable" and gm.neo4j_driver:
                # 从 SQLite 收集该知识库的所有 doc_id，用于兼容旧数据（无 kb_id 属性）
                docs = self._storage.list_documents(kb_id)
                doc_ids = [d.get("doc_id", "") for d in docs if d.get("doc_id")]

                with gm.neo4j_driver.session() as session:
                    # 查询该知识库的所有实体节点（兼容新旧数据：kb_id 或 source_doc 匹配）
                    entity_result = session.run(
                        "MATCH (n) "
                        "WHERE n.kb_id = $kb_id OR n.source_doc IN $doc_ids "
                        "RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
                        kb_id=kb_id, doc_ids=doc_ids
                    )
                    nodes = []
                    node_ids = set()
                    for record in entity_result:
                        node_id = record["id"]
                        labels = [lb for lb in (record["labels"] or []) if lb != "Entity"]
                        node_type = labels[0] if labels else "unknown"
                        props = record["props"] or {}
                        nodes.append({
                            "id": node_id,
                            "name": props.get("name", node_id),
                            "type": node_type,
                            "source_doc": props.get("source_doc", ""),
                            "properties": {k: v for k, v in props.items()
                                           if k not in ("id", "name", "source_doc", "kb_id")},
                        })
                        node_ids.add(node_id)

                    # 查询这些实体之间的关系
                    rel_result = session.run(
                        "MATCH (a)-[r]->(b) "
                        "WHERE (a.kb_id = $kb_id OR a.source_doc IN $doc_ids) "
                        "  AND (b.kb_id = $kb_id OR b.source_doc IN $doc_ids) "
                        "RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props",
                        kb_id=kb_id, doc_ids=doc_ids
                    )
                    edges = []
                    edge_idx = 0
                    for record in rel_result:
                        source = record["source"]
                        target = record["target"]
                        if source in node_ids and target in node_ids:
                            edges.append({
                                "id": f"e_{edge_idx}",
                                "source": source,
                                "target": target,
                                "type": record["type"] or "related_to",
                                "properties": record["props"] or {},
                            })
                            edge_idx += 1

                return {
                    "nodes": nodes,
                    "edges": edges,
                    "statistics": {
                        "total_entities": len(nodes),
                        "total_relationships": len(edges),
                    },
                }

            # Neo4j 不可用，降级为 SQLite entities_json 数据
            return self._get_kb_graph_from_sqlite(kb_id)

        except Exception as e:
            logger.warning(f"Failed to get KB graph from Neo4j, falling back to SQLite: {e}")
            return self._get_kb_graph_from_sqlite(kb_id)

    def _get_kb_graph_from_sqlite(self, kb_id: str) -> Dict[str, Any]:
        """从 SQLite 的 entities_json 字段构建图谱数据（Neo4j 不可用时的降级方案）。"""
        try:
            docs = self._storage.list_documents(kb_id)
            nodes = []
            node_ids = set()
            node_name_to_id = {}
            edges = []
            edge_idx = 0

            for doc in docs:
                doc_id = doc.get("doc_id", "")
                entities_data = doc.get("entities_json")
                if not entities_data:
                    continue
                if isinstance(entities_data, str):
                    try:
                        entities_data = json.loads(entities_data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if not isinstance(entities_data, list):
                    continue

                for entity in entities_data:
                    if not isinstance(entity, dict):
                        continue
                    name = entity.get("name", "unknown")
                    entity_id = f"sqlite_{kb_id}_{name}"
                    if entity_id in node_ids:
                        continue
                    entity_type = entity.get("type", "extracted_entity")
                    node_ids.add(entity_id)
                    node_name_to_id[name] = entity_id
                    nodes.append({
                        "id": entity_id,
                        "name": name,
                        "type": entity_type,
                        "source_doc": doc_id,
                        "properties": entity.get("properties", {}),
                    })

                # 从文档的关系数据中提取 edges
                # entities_json 中的每个 entity 的 relations 字段
                for entity in entities_data:
                    if not isinstance(entity, dict):
                        continue
                    rels = entity.get("relations", [])
                    if not isinstance(rels, list):
                        continue
                    for rel in rels:
                        if not isinstance(rel, dict):
                            continue
                        source_name = rel.get("source", "")
                        target_name = rel.get("target", "")
                        if source_name in node_name_to_id and target_name in node_name_to_id:
                            edges.append({
                                "id": f"e_{edge_idx}",
                                "source": node_name_to_id[source_name],
                                "target": node_name_to_id[target_name],
                                "type": rel.get("type", "RELATED_TO"),
                                "properties": {},
                            })
                            edge_idx += 1

            return {
                "nodes": nodes,
                "edges": edges,
                "statistics": {
                    "total_entities": len(nodes),
                    "total_relationships": len(edges),
                },
            }
        except Exception as e:
            logger.warning(f"SQLite fallback graph failed: {e}")
            return {"nodes": [], "edges": [], "statistics": {"total_entities": 0, "total_relationships": 0}, "error": str(e)}

    async def rag_query(
        self, kb_id: str, query: str, top_k: int = 5, threshold: float = 0.1
    ) -> Dict[str, Any]:
        """RAG 语义检索：SQLite 关键词匹配 + Graphiti 向量检索 + LLM 回答。

        查询流程：
        1. SQLite 关键词匹配：直接从 SQLite 读取文档，用 re.search
           匹配中文关键词（含2-gram分词，避免跨平台编码问题）
        2. Graphiti 向量检索：如果 Graphiti 可用，补充语义检索结果
        3. 合并结果，调用 LLM 生成回答
        """
        kb = self._storage.get_knowledge_base(kb_id)
        if not kb:
            return {"status": "error", "message": "知识库不存在"}

        context_parts = []
        sources = []
        related_entities = []
        use_vector = False

        # ================================================================
        # Step 1: SQLite 关键词匹配（re.search + 2-gram中文分词）
        # ================================================================
        docs = self._storage.list_documents(kb_id)

        # 中文关键词匹配：优化分词策略
        #   1) 保留原始查询词（完整匹配）
        #   2) 按常用分隔符拆词
        #   3) 对中文查询做2-gram分词（增强短词召回）
        #   4) 剔除 ≤1 字符的短词
        #   5) 使用 re.search 替代 in 操作符（跨平台编码兼容）
        query_terms = set()
        query_clean = query.strip().lower()
        query_terms.add(query_clean)

        # 按中文标点和空格拆分短词
        for sep in ('的', '和', '与', '或', '，', '、', ' ', ',', ';', '；'):
            for part in query.split(sep):
                part = part.strip().lower()
                if len(part) >= 2:
                    query_terms.add(part)

        # 2-gram 中文分词（如"会员等级"→"会员","员等","等级"）
        query_no_punc = re.sub(r'[\s，,、。；;]', '', query.strip())
        for i in range(len(query_no_punc) - 1):
            bigram = query_no_punc[i:i+2]
            query_terms.add(bigram.lower())

        # 剔除太短的词（≤1字符），但保留原始查询
        query_terms = {t for t in query_terms if len(t) >= 2 or t == query_clean}

        logger.info(
            f"RAG query terms for '{query[:50]}': {len(query_terms)} terms → "
            f"{sorted(query_terms, key=len, reverse=True)[:10]}"
        )

        scored = []
        for doc in docs:
            # 优先使用清洗后的内容，做 UTF-8 安全编解码
            raw_content = doc.get("cleaned_content") or doc.get("content", "") or ""
            try:
                doc_content = raw_content.encode('utf-8').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                doc_content = raw_content
            if not doc_content.strip():
                continue
            content_lower = doc_content.lower()

            # 评分：使用 re.search 替代 in 操作符（更好的中文编码兼容性）
            match_count = 0
            total_term_score = 0
            for term in query_terms:
                if len(term) >= 2 and re.search(re.escape(term), content_lower, re.IGNORECASE):
                    occurrences = len(re.findall(re.escape(term), content_lower, re.IGNORECASE))
                    match_count += 1
                    total_term_score += min(occurrences, 10)  # 最多计数10次

            if match_count == 0:
                continue

            # 综合评分 = 匹配词比例 * 0.5 + 词频归一化 * 0.3 + 长度惩罚 * 0.2
            term_ratio = match_count / max(len(query_terms), 1)
            freq_score = min(total_term_score / 20.0, 1.0)  # 归一化
            # 长度惩罚：短文档优先（但不要太短）
            doc_len = max(len(doc_content), 1)
            length_score = min(10000.0 / max(doc_len, 100), 1.0)
            score = term_ratio * 0.5 + freq_score * 0.3 + length_score * 0.2

            if score >= threshold:
                scored.append((doc, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_docs = scored[:top_k]

        logger.info(
            f"RAG keyword match: {len(scored)} docs matched from {len(docs)} total docs, "
            f"returning top {len(top_docs)}"
        )

        for doc, score in top_docs:
            raw_content = doc.get("cleaned_content") or doc.get("content", "") or ""
            try:
                doc_content = raw_content.encode('utf-8').decode('utf-8')
            except (UnicodeEncodeError, UnicodeDecodeError):
                doc_content = raw_content
            context_parts.append(doc_content[:2000])
            sources.append({
                "doc_id": doc.get("doc_id"),
                "title": doc.get("title", ""),
                "score": round(score, 3),
                "source": "keyword",
            })

        # ================================================================
        # Step 2: Graphiti 向量语义检索（补充结果）
        # ================================================================
        try:
            from odap.infra.graph.graph_service import GraphManager
            graph_manager = GraphManager()

            if graph_manager._mode == "graphiti" and graph_manager.graph:
                try:
                    edges = await graph_manager.graph.search(
                        query=query, num_results=top_k * 2
                    )
                except Exception as ge:
                    logger.warning(f"Graphiti direct search failed: {ge}")
                    edges = []

                if edges:
                    use_vector = True
                    for edge in edges:
                        fact = getattr(edge, "fact", None)
                        if fact and fact.strip():
                            # 去重：避免和关键词结果重复
                            is_dup = False
                            for ex in context_parts:
                                if fact[:100] in ex or ex[:100] in fact:
                                    is_dup = True
                                    break
                            if not is_dup:
                                context_parts.append(fact)
                                edge_name = getattr(edge, "name", "") or ""
                                sources.append({
                                    "edge_id": str(getattr(edge, "uuid", edge_name)),
                                    "name": edge_name,
                                    "score": round(getattr(edge, "score", 0.7), 3),
                                    "source": "vector",
                                })
            elif graph_manager._mode in ("graphiti", "neo4j_driver"):
                try:
                    hybrid_results = graph_manager.search_hybrid(
                        query_text=query, top_k=top_k
                    )
                    if hybrid_results and isinstance(hybrid_results, list):
                        use_vector = True
                        for hr in hybrid_results:
                            if isinstance(hr, dict):
                                props = hr.get("properties", {})
                                fact = props.get("fact", "")
                                if fact:
                                    is_dup = False
                                    for ex in context_parts:
                                        if fact[:100] in ex or ex[:100] in fact:
                                            is_dup = True
                                            break
                                    if not is_dup:
                                        context_parts.append(fact)
                                        sources.append({
                                            "id": hr.get("id", ""),
                                            "type": hr.get("type", ""),
                                            "score": round(hr.get("score", 0.5), 3),
                                            "source": "hybrid",
                                        })
                except Exception as he:
                    logger.warning(f"Hybrid search failed: {he}")
        except Exception as e:
            logger.warning(f"Vector search unavailable, using keyword only: {e}")

        # ================================================================
        # Step 3: LLM 生成答案
        # ================================================================
        answer = ""
        if context_parts:
            context = "\n".join(context_parts[:top_k * 2])

            # 默认答案（LLM 不可用时的回退）
            answer = "相关文档片段：\n" + "\n---\n".join(
                [p[:500] for p in context_parts[:top_k]]
            )

            # 尝试 LLM 生成
            llm = self._create_llm_client()
            if llm:
                try:
                    from graphiti_core.prompts.models import Message

                    max_context = 8000
                    if len(context) > max_context:
                        context = context[:max_context] + "\n...(内容已截断)"

                    messages = [
                        Message(
                            role="system",
                            content="你是一个知识问答助手，基于提供的内容准确回答问题。"
                                    "如果内容不足以回答问题，请诚实说明。",
                        ),
                        Message(
                            role="user",
                            content=f"问题：{query}\n\n参考内容：\n{context}"
                                    f"\n\n请基于以上内容回答问题。",
                        ),
                    ]

                    llm_result, _, _ = await llm._generate_response(messages)

                    if isinstance(llm_result, dict) and "response" in llm_result:
                        answer = llm_result["response"]
                    elif isinstance(llm_result, dict):
                        answer = json.dumps(llm_result, ensure_ascii=False)
                    elif isinstance(llm_result, str):
                        answer = llm_result
                except Exception as e:
                    logger.warning(f"RAG LLM call failed: {repr(e)}", exc_info=True)
        else:
            answer = "未找到与查询相关的文档"

        logger.info(
            f"RAG result: answer={len(answer)} chars, sources={len(sources)}, "
            f"vector={use_vector}, context_parts={len(context_parts)}"
        )
        return {"answer": answer, "sources": sources, "related_entities": related_entities}

    async def crawl_web(self, kb_id: str, urls: List[str], max_depth: int = 1) -> Dict[str, Any]:
        kb = self._storage.get_knowledge_base(kb_id)
        if not kb:
            return {"status": "error", "message": "知识库不存在"}

        results = []
        for url in urls:
            try:
                content = ""
                try:
                    from odap.infra.utils.web_scraper import WebScraper
                    scraper = WebScraper()
                    content = scraper.fetch_url(url)
                    if content:
                        content = scraper.extract_text(content)
                except Exception:
                    try:
                        import urllib.request
                        resp = urllib.request.urlopen(url, timeout=10)
                        html = resp.read().decode("utf-8", errors="replace")
                        content = re.sub(r"<[^>]+>", " ", html)
                        content = re.sub(r"\s+", " ", content).strip()
                    except Exception as e:
                        results.append({"url": url, "status": "failed", "error": str(e)})
                        continue

                doc = self._storage.create_document(kb_id, {
                    "title": url,
                    "content_type": "web",
                    "content": content[:50000],
                })
                results.append({"url": url, "doc_id": doc.get("doc_id"), "status": "success"})
            except Exception as e:
                results.append({"url": url, "status": "failed", "error": str(e)})

        return {"task_id": f"crawl_{kb_id}", "results": results}
