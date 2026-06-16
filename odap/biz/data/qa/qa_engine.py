"""
问答引擎 - 多轮对话 + RAG + 溯源追踪 + 多跳检索

功能：
- QAEngine 核心
- 多轮对话管理
- RAG 增强生成
- 双时态查询
- 溯源追踪
- 多跳检索（复杂问题分解）
"""

import sys
import os
import json
import time
import re
import logging
import threading
import sqlite3
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)

# CoTBuilder integration (graceful degradation)
try:
    from odap.biz.platform.session_memory.cot_builder import CoTBuilder, CoTNodeType
    _COT_AVAILABLE = True
except ImportError:
    _COT_AVAILABLE = False
    CoTBuilder = None
    CoTNodeType = None

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SimpleReasoningChain:
    """轻量级推理链 — 当 CoTBuilder 不可用时的回退方案。

    提供基本的推理步骤追踪能力，确保 QA 操作始终有审计追踪。
    """

    def __init__(self, query: str):
        self._steps: List[Dict[str, Any]] = []
        self._start_time = datetime.now(timezone.utc)
        self._steps.append({
            "step": "intent",
            "description": f"用户提问: {query[:100]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": 0,
            "metadata": {},
        })

    def add_step(self, step: str, description: str, metadata: Dict[str, Any] = None) -> None:
        """添加推理步骤"""
        now = datetime.now(timezone.utc)
        self._steps.append({
            "step": step,
            "description": description,
            "timestamp": now.isoformat(),
            "duration_ms": int((now - self._start_time).total_seconds() * 1000),
            "metadata": metadata or {},
        })

    def to_list(self) -> List[Dict[str, Any]]:
        """返回推理链列表"""
        return self._steps


class DialogState(Enum):
    """对话状态"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    COMPLETED = "completed"
    ESCALATED = "escalated"


def clarification_reason_to_chinese(reason: str) -> str:
    """将澄清原因转为中文描述"""
    reason_map = {
        "no_results": "未检索到相关信息",
        "low_score": "检索结果相关性较低",
        "ambiguous_pronoun": "问题中包含模糊代词，指代不明确",
        "too_short": "问题描述过于简短",
    }
    return reason_map.get(reason, reason)


@dataclass
class DialogMessage:
    """对话消息"""
    message_id: str
    role: str
    content: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogSession:
    """对话会话"""
    session_id: str
    user_id: str
    created_at: str
    updated_at: str
    state: DialogState
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    agent_id: Optional[str] = None
    messages: List[DialogMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""


@dataclass
class RAGResult:
    """RAG 检索结果"""
    content: str
    source: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceTrace:
    """溯源信息"""
    episode_id: Optional[str]
    entity_id: Optional[str]
    confidence: float
    excerpt: str
    source: str = ""


class DialogManager:
    """多轮对话管理器"""

    def __init__(self, max_history: int = 10, context_window: int = 5):
        self.max_history = max_history
        self.context_window = context_window
        self._sessions: Dict[str, DialogSession] = {}
        self._lock = threading.RLock()

    def create_session(self, user_id: str, workspace_id: Optional[str] = None,
                      scenario_id: Optional[str] = None,
                      agent_id: Optional[str] = None) -> DialogSession:
        """创建新会话"""
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        session = DialogSession(
            session_id=f"SESSION-{uuid.uuid4().hex[:8].upper()}",
            user_id=user_id,
            workspace_id=workspace_id,
            scenario_id=scenario_id,
            agent_id=agent_id,
            created_at=now,
            updated_at=now,
            state=DialogState.NEW
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def add_message(self, session_id: str, role: str, content: str,
                   metadata: Dict = None) -> DialogMessage:
        """添加消息"""
        import uuid
        message = DialogMessage(
            message_id=f"MSG-{uuid.uuid4().hex[:8].upper()}",
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {}
        )

        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.messages.append(message)
                session.updated_at = datetime.now(timezone.utc).isoformat()
                session.state = DialogState.IN_PROGRESS

                if len(session.messages) > self.max_history:
                    self._summarize_and_truncate(session)

        return message

    def _summarize_and_truncate(self, session: DialogSession):
        """摘要并截断历史"""
        if len(session.messages) > self.max_history:
            keep_messages = session.messages[-self.context_window:]
            session.summary = f"[早期对话摘要: {len(session.messages) - self.context_window} 条消息已省略]"
            session.messages = keep_messages

    def get_context(self, session_id: str) -> str:
        """获取对话上下文"""
        with self._lock:
            if session_id not in self._sessions:
                return ""

            session = self._sessions[session_id]
            context_parts = []

            if session.summary:
                context_parts.append(session.summary)

            for msg in session.messages[-self.context_window:]:
                context_parts.append(f"{msg.role}: {msg.content}")

            return "\n".join(context_parts)

    def get_session(self, session_id: str) -> Optional[DialogSession]:
        """获取会话"""
        with self._lock:
            return self._sessions.get(session_id)

    def close_session(self, session_id: str):
        """关闭会话"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id].state = DialogState.COMPLETED

    def get_sessions_by_workspace(self, workspace_id: str) -> List[DialogSession]:
        """根据工作空间ID获取会话列表"""
        with self._lock:
            return [
                session for session in self._sessions.values()
                if session.workspace_id == workspace_id
            ]

    def get_sessions_by_scenario(self, scenario_id: str) -> List[DialogSession]:
        """根据场景ID获取会话列表"""
        with self._lock:
            return [
                session for session in self._sessions.values()
                if session.scenario_id == scenario_id
            ]


class RAGPipeline:
    """RAG 管道"""

    def __init__(self, graphiti_client=None, ingest_storage=None, semantic_map_storage=None,
                 model_storage=None, query_service=None):
        self.graphiti = graphiti_client
        self._query_service = query_service
        self.ingest_storage = ingest_storage
        self.semantic_map_storage = semantic_map_storage
        self.model_storage = model_storage

        # 本体门控服务
        from odap.biz.data.qa.ontology_gate import OntologyGate
        self.ontology_gate = OntologyGate()

    def retrieve(self, query: str, top_k: int = 5,
                 workspace_id: Optional[str] = None,
                 ontology_ids: Optional[List[str]] = None,
                 scenario_id: Optional[str] = None,
                 min_score: Optional[float] = None) -> List[RAGResult]:
        results = []
        has_scenario = scenario_id and scenario_id != "default"
        logger.info(f"RAG retrieve: scenario_id={scenario_id}, has_scenario={has_scenario}, ingest_storage={self.ingest_storage is not None}, semantic_map={self.semantic_map_storage is not None}")

        # 相关性硬阈值：优先使用参数，其次读取环境变量，默认 0.10
        if min_score is None:
            try:
                min_score = float(os.environ.get("QA_MIN_RELEVANCE_SCORE", "0.10"))
            except (ValueError, TypeError):
                min_score = 0.10

        # 本体门控：输入验证
        schemas = []
        if ontology_ids:
            schemas = self.ontology_gate.load_schema(ontology_ids, workspace_id or "default")
            query_validation = self.ontology_gate.validate_query(query, schemas)
            if query_validation.matched_entity_types:
                logger.info(f"OntologyGate: query matched entity types: {query_validation.matched_entity_types}")
            if query_validation.confidence < 1.0:
                logger.info(f"OntologyGate: query confidence={query_validation.confidence}, no ontology types matched")

        if self.graphiti:
            try:
                graphiti_results = self._retrieve_from_graphiti(query, top_k, workspace_id, ontology_ids)
                if has_scenario:
                    for r in graphiti_results:
                        r.score *= 0.3
                results.extend(graphiti_results)
                logger.info(f"RAG Graphiti: {len(graphiti_results)} results")
            except Exception as e:
                logger.warning(f"RAG Graphiti 检索失败: {e}", exc_info=True)

        if self.ingest_storage:
            try:
                sqlite_results = self._retrieve_from_sqlite(query, top_k, scenario_id, ontology_ids)
                if has_scenario:
                    for r in sqlite_results:
                        r.score = min(r.score * 1.5, 1.0)
                results.extend(sqlite_results)
                logger.info(f"RAG SQLite: {len(sqlite_results)} results")
            except Exception as e:
                logger.warning(f"RAG SQLite 检索失败: {e}", exc_info=True)

        if self.semantic_map_storage:
            try:
                sm_results = self._retrieve_from_semantic_map(query, top_k, scenario_id, ontology_ids)
                if has_scenario:
                    for r in sm_results:
                        r.score = min(r.score * 1.5, 1.0)
                results.extend(sm_results)
            except Exception as e:
                logger.warning(f"RAG 语义地图检索失败: {e}")

        # 本体模型实例检索（覆盖 /api/ontology/model/instances 注入的数据）
        if self.model_storage:
            try:
                model_results = self._retrieve_from_model_storage(query, top_k, workspace_id, ontology_ids)
                if has_scenario:
                    for r in model_results:
                        r.score = min(r.score * 1.5, 1.0)
                results.extend(model_results)
                logger.info(f"RAG ModelStorage: {len(model_results)} results")
            except Exception as e:
                logger.warning(f"RAG 本体模型检索失败: {e}")

        # 第5个检索源：基于本体 schema 的 Cypher 检索
        if self.graphiti or (hasattr(self, '_query_service') and self._query_service):
            try:
                graph_retriever_results = self._retrieve_from_graph_retriever(
                    query, top_k, workspace_id, scenario_id, schemas
                )
                if graph_retriever_results:
                    results.extend(graph_retriever_results)
                    logger.info(f"RAG GraphRetriever: {len(graph_retriever_results)} results")
            except Exception as e:
                logger.debug(f"RAG GraphRetriever 检索失败: {e}")

        # 本体门控：输出验证
        if schemas and results:
            result_validation = self.ontology_gate.validate_results(results, schemas)
            if result_validation.score_adjustments:
                results = self.ontology_gate.apply_score_adjustments(results, result_validation)
                logger.info(f"OntologyGate: adjusted {len(result_validation.score_adjustments)} result scores, "
                           f"aligned {result_validation.ontology_aligned}/{result_validation.total}")

        results.sort(key=lambda r: r.score, reverse=True)

        # 相关性硬阈值过滤：移除分数低于 min_score 的结果
        total_before = len(results)
        results = [r for r in results if r.score >= min_score]
        filtered_count = total_before - len(results)
        if filtered_count > 0:
            logger.info(
                f"RAG relevance filter: removed {filtered_count}/{total_before} results "
                f"below min_score={min_score:.2f}"
            )

        # 按 content 去重：多数据源可能返回相同内容，保留分数最高的
        seen_content = set()
        deduped = []
        for r in results:
            key = r.content.strip().lower()[:200]
            if key not in seen_content:
                seen_content.add(key)
                deduped.append(r)
        if len(deduped) < len(results):
            logger.info(f"RAG dedup: removed {len(results) - len(deduped)} duplicate results")
        results = deduped

        return results[:top_k]

    @staticmethod
    def _make_source_label(data: Dict, fallback_id: str = "unknown") -> str:
        """从检索结果数据中生成可读的 source 标签，如 '西游人物:孙悟空' 而非 UUID"""
        props = data.get("properties", {})
        name = props.get("name", "") or data.get("name", "")
        etype = props.get("entity_type", "") or props.get("type", "") or data.get("entity_type", "") or data.get("type", "")
        uid = data.get("id", "") or data.get("entity_id", "") or fallback_id

        if name and etype:
            return f"{etype}:{name}"
        if name:
            return name
        if etype:
            return f"{etype}:{uid[:8]}"
        return uid[:8]

    def _retrieve_from_graphiti(self, query: str, top_k: int,
                                workspace_id: Optional[str],
                                ontology_ids: Optional[List[str]]) -> List[RAGResult]:
        # 优先使用 QueryService（推荐路径）
        if self._query_service is not None:
            try:
                ws = workspace_id or "default"
                result = self._query_service.execute(
                    ws, f".entity with(search='{query}') list({top_k})"
                )
                results = []
                for r in result.rows:
                    props = r.get("properties", {})
                    content = str(props.get("body", ""))
                    if not content:
                        content = str(props.get("description", ""))
                    if not content:
                        content = str(props.get("name", ""))
                    if not content:
                        content = str(props.get("fact", ""))

                    if workspace_id and workspace_id != "default":
                        node_ws = props.get("workspace_id", "")
                        if node_ws and node_ws != workspace_id:
                            continue

                    if ontology_ids:
                        node_oid = props.get("ontology_id", "")
                        if node_oid and node_oid not in ontology_ids:
                            continue

                    results.append(RAGResult(
                        content=content,
                        source=self._make_source_label(r, r.get("id", "unknown")),
                        score=r.get("score", 0.8),
                        metadata=r
                    ))
                return results
            except Exception as e:
                logger.warning(f"RAG QueryService search failed, falling back to graphiti_client: {e}")

        # 回退：直接使用 graphiti_client（向后兼容）
        if not self.graphiti:
            return []

        search_results = self.graphiti.search_hybrid(query, top_k)
        results = []
        for r in search_results:
            props = r.get("properties", {})
            content = str(props.get("body", ""))
            if not content:
                content = str(props.get("description", ""))
            if not content:
                content = str(props.get("name", ""))
            if not content:
                content = str(props.get("fact", ""))

            if workspace_id and workspace_id != "default":
                node_ws = props.get("workspace_id", "")
                if node_ws and node_ws != workspace_id:
                    continue

            if ontology_ids:
                node_oid = props.get("ontology_id", "")
                if node_oid and node_oid not in ontology_ids:
                    continue

            results.append(RAGResult(
                content=content,
                source=self._make_source_label(r, r.get("id", "unknown")),
                score=r.get("score", 0.8),
                metadata=r
            ))
        return results

    @staticmethod
    def _tokenize_chinese(text: str) -> List[str]:
        tokens = []
        current = []
        for ch in text:
            if '\u4e00' <= ch <= '\u9fff':
                current.append(ch)
            else:
                if current:
                    tokens.append(''.join(current))
                    current = []
                if ch.strip():
                    tokens.append(ch)
        if current:
            tokens.append(''.join(current))
        return tokens

    @staticmethod
    def _extract_search_terms(query: str) -> List[str]:
        terms = []
        tokens = RAGPipeline._tokenize_chinese(query)
        for t in tokens:
            if len(t) >= 2:
                terms.append(t)
        if not terms and tokens:
            terms = tokens
        return terms

    def _retrieve_from_sqlite(self, query: str, top_k: int,
                              scenario_id: Optional[str],
                              ontology_ids: Optional[List[str]]) -> List[RAGResult]:
        results = []
        query_lower = query.lower()
        search_terms = self._extract_search_terms(query)

        if scenario_id:
            entities = self.ingest_storage.get_scenario_entities(scenario_id)
            for entity in entities:
                name = entity.get("name", "")
                entity_type = entity.get("entity_type", "")
                aliases = entity.get("aliases", [])
                props = entity.get("basic_properties", {})
                desc_parts = []
                if name:
                    desc_parts.append(f"{name}")
                if entity_type:
                    desc_parts.append(f"类型:{entity_type}")
                if aliases:
                    desc_parts.append(f"别名:{','.join(aliases)}")
                if props:
                    for k, v in props.items():
                        desc_parts.append(f"{k}:{v}")

                content = " | ".join(desc_parts)
                score = 0.0
                for term in search_terms:
                    if term in content:
                        score += 0.15
                if name and name.lower() in query_lower:
                    score += 0.6
                if name:
                    for term in search_terms:
                        if term in name:
                            score += 0.4
                            break
                for alias in aliases:
                    if alias.lower() in query_lower:
                        score += 0.5
                if entity_type and entity_type.lower() in query_lower:
                    score += 0.3
                if score == 0:
                    score = 0.05

                # 本体范围过滤：非目标本体的结果大幅降权
                if ontology_ids:
                    entity_oid = entity.get("ontology_id", "")
                    if entity_oid and entity_oid not in ontology_ids:
                        score *= 0.3

                results.append(RAGResult(
                    content=content,
                    source=self._make_source_label(entity, entity.get("entity_id", "unknown")),
                    score=min(score, 1.0),
                    metadata={"type": "entity", "entity_type": entity_type}
                ))

            rel_data = self.ingest_storage.get_scenario_relations(scenario_id)
            node_map = {}
            for node in rel_data.get("nodes", []):
                nid = node.get("id", node.get("entity_id", ""))
                nname = node.get("name", node.get("label", nid))
                if nid:
                    node_map[nid] = nname
            for link in rel_data.get("links", []):
                link_type = link.get("type", "related_to")
                source_id = link.get("source", "")
                target_id = link.get("target", "")
                source_name = node_map.get(source_id, source_id)
                target_name = node_map.get(target_id, target_id)
                content = f"关系: {source_name} --[{link_type}]--> {target_name}"
                score = 0.2
                if link_type.lower() in query_lower:
                    score += 0.5
                name_matched = False
                for term in search_terms:
                    if term in source_name or term in target_name:
                        name_matched = True
                        break
                if name_matched:
                    score += 0.6
                if source_name.lower() in query_lower or target_name.lower() in query_lower:
                    score += 0.4

                # 本体范围过滤：非目标本体的关系结果降权
                if ontology_ids:
                    link_oid = link.get("ontology_id", "")
                    if link_oid and link_oid not in ontology_ids:
                        score *= 0.3

                results.append(RAGResult(
                    content=content,
                    source=self._make_source_label(link, link.get("id", "unknown")),
                    score=min(score, 1.0),
                    metadata={"type": "relation", "relation_type": link_type}
                ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _retrieve_from_semantic_map(self, query: str, top_k: int,
                                    scenario_id: Optional[str],
                                    ontology_ids: Optional[List[str]] = None) -> List[RAGResult]:
        results = []
        query_lower = query.lower()
        search_terms = self._extract_search_terms(query)

        if scenario_id:
            maps = self.semantic_map_storage.list_by_scenario(scenario_id)
        else:
            maps = self.semantic_map_storage.list_all(limit=5)

        if not maps:
            return []

        sm = maps[0]
        for obj in sm.objects:
            desc_parts = [obj.name]
            if obj.name_en:
                desc_parts.append(f"英文名:{obj.name_en}")
            if obj.object_type:
                desc_parts.append(f"类型:{obj.object_type}")
            if obj.type_definition_name:
                desc_parts.append(f"本体定义:{obj.type_definition_name}")
            if obj.aliases:
                desc_parts.append(f"别名:{','.join(obj.aliases)}")
            for key, val in obj.properties.items():
                if isinstance(val, dict):
                    for sk, sv in val.items():
                        desc_parts.append(f"{key}.{sk}:{sv}")
                else:
                    desc_parts.append(f"{key}:{val}")

            content = " | ".join(str(p) for p in desc_parts)
            score = 0.0
            if obj.name and obj.name.lower() in query_lower:
                score += 0.7
            if obj.name:
                for term in search_terms:
                    if term in obj.name:
                        score += 0.5
                        break
            for alias in obj.aliases:
                if alias.lower() in query_lower:
                    score += 0.5
            if obj.object_type and obj.object_type.lower() in query_lower:
                score += 0.4
            if obj.type_definition_name and obj.type_definition_name.lower() in query_lower:
                score += 0.3
            for term in search_terms:
                if term in content:
                    score += 0.1
            if score == 0:
                score = 0.03

            # 本体范围过滤：非目标本体的语义地图对象降权
            if ontology_ids:
                obj_oid = getattr(obj, 'ontology_id', '') or (obj.properties.get("ontology_id", "") if hasattr(obj, 'properties') and isinstance(obj.properties, dict) else "")
                if obj_oid and obj_oid not in ontology_ids:
                    score *= 0.3

            results.append(RAGResult(
                content=content,
                source=f"{obj.object_type}:{obj.name}" if obj.name else obj.entity_id,
                score=min(score, 1.0),
                metadata={
                    "type": "semantic_map_object",
                    "object_type": obj.object_type,
                    "cluster": obj.cluster,
                    "type_definition_id": obj.type_definition_id,
                }
            ))

        for rel in sm.relations:
            content = f"关系: {rel.source_object_id} --[{rel.relation_type}]--> {rel.target_object_id}"
            if rel.display_name:
                content = f"关系: {rel.source_object_id} --[{rel.display_name}]--> {rel.target_object_id}"
            score = 0.1
            if rel.relation_type.lower() in query_lower:
                score += 0.5

            results.append(RAGResult(
                content=content,
                source=f"{rel.relation_type}:{rel.source_name}->{rel.target_name}" if hasattr(rel, 'source_name') and rel.source_name else rel.relation_id,
                score=min(score, 1.0),
                metadata={"type": "semantic_map_relation", "relation_type": rel.relation_type}
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _retrieve_from_model_storage(self, query: str, top_k: int,
                                      workspace_id: Optional[str] = None,
                                      ontology_ids: Optional[List[str]] = None) -> List[RAGResult]:
        """从本体模型实例存储中检索（覆盖 /api/ontology/model/instances 注入的数据）

        当用户通过本体设计 API 创建实体类型和实例后，QA 引擎可以检索这些数据。
        注意：实例可能存储在 workspace_id="default" 下，因此同时检索指定 workspace 和 default。
        """
        results = []
        query_lower = query.lower()
        search_terms = self._extract_search_terms(query)

        try:
            # 获取所有实体类型
            entity_types = self.model_storage.list_entity_types()
            type_name_map = {t["type_id"]: t.get("display_name") or t.get("name", "")
                             for t in entity_types}

            # 遍历每种类型，检索实例（同时查指定 workspace 和 default）
            for et in entity_types:
                tid = et["type_id"]
                seen_ids = set()
                instances = []

                # 查指定 workspace
                if workspace_id:
                    for inst in self.model_storage.list_instances(
                            type_id=tid, workspace_id=workspace_id, page_size=100):
                        iid = inst.get("instance_id")
                        if iid and iid not in seen_ids:
                            seen_ids.add(iid)
                            instances.append(inst)

                # 查 default workspace（兼容未绑定 workspace 的实例）
                for inst in self.model_storage.list_instances(
                        type_id=tid, workspace_id="default", page_size=100):
                    iid = inst.get("instance_id")
                    if iid and iid not in seen_ids:
                        seen_ids.add(iid)
                        instances.append(inst)

                # 无 workspace 过滤时查全部
                if not workspace_id:
                    instances = self.model_storage.list_instances(
                        type_id=tid, page_size=100)

                if not instances:
                    continue

                type_display = type_name_map.get(tid, tid)

                for inst in instances:
                    props = inst.get("properties") or {}
                    if isinstance(props, str):
                        try:
                            import json as _json
                            props = _json.loads(props)
                        except Exception:
                            props = {}

                    # 构建可搜索文本
                    desc_parts = [f"[{type_display}]"]
                    name_val = props.get("name", "")
                    if name_val:
                        desc_parts.append(f"名称:{name_val}")
                    for k, v in props.items():
                        if k == "name":
                            continue
                        if isinstance(v, (list, dict)):
                            import json as _json
                            v = _json.dumps(v, ensure_ascii=False)
                        desc_parts.append(f"{k}:{v}")

                    content = " | ".join(desc_parts)

                    # 计算相关性得分
                    score = 0.0
                    for term in search_terms:
                        if term in content:
                            score += 0.15
                    if name_val and name_val.lower() in query_lower:
                        score += 0.6
                    if name_val:
                        for term in search_terms:
                            if term in name_val:
                                score += 0.4
                                break
                    # 类型名匹配（如"人物""事件"）
                    type_name = et.get("name", "").lower()
                    type_display_lower = type_display.lower()
                    if type_name in query_lower or type_display_lower in query_lower:
                        score += 0.3
                    if score == 0:
                        score = 0.02  # 极低基础分，保证可排序

                    # 本体范围过滤：非目标本体的模型实例降权
                    if ontology_ids:
                        inst_oid = inst.get("ontology_id", "")
                        if inst_oid and inst_oid not in ontology_ids:
                            score *= 0.3

                    results.append(RAGResult(
                        content=content,
                        source=self._make_source_label(inst, inst.get("instance_id", "unknown")),
                        score=min(score, 1.0),
                        metadata={
                            "type": "model_instance",
                            "entity_type": et.get("name"),
                            "type_display": type_display,
                        }
                    ))
        except Exception as e:
            logger.warning(f"Model storage retrieval error: {e}", exc_info=True)

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k * 3]  # 返回稍多结果，由外层截断

    def _retrieve_from_graph_retriever(self, query: str, top_k: int,
                                        workspace_id: Optional[str],
                                        scenario_id: Optional[str],
                                        schemas: List) -> List[RAGResult]:
        """基于本体 schema 的 Cypher 检索（第5个检索源）"""
        try:
            from odap.biz.data.qa.retrieval.graph_retriever import GraphRetriever
            # 使用 graphiti 或 graph_manager
            graph_manager = self.graphiti
            if not graph_manager and hasattr(self, '_query_service') and self._query_service:
                try:
                    graph_manager = getattr(self._query_service, '_graph_manager', None)
                except Exception:
                    pass
            if not graph_manager:
                return []

            retriever = GraphRetriever(graph_manager)
            results = retriever._search_cypher(query, top_k, workspace_id or "default", scenario_id)
            # 转换为 RAGResult
            rag_results = []
            for r in results:
                rag_results.append(RAGResult(
                    content=r.content if hasattr(r, 'content') else str(r),
                    source=self._make_source_label(r.metadata if hasattr(r, 'metadata') else {}, "graph_retriever"),
                    score=r.score if hasattr(r, 'score') else 0.5,
                    metadata=r.metadata if hasattr(r, 'metadata') else {},
                ))
            return rag_results
        except Exception as e:
            logger.debug(f"GraphRetriever search failed: {e}")
            return []

    def rerank(self, query: str, results: List[RAGResult]) -> List[RAGResult]:
        """重排序"""
        return sorted(results, key=lambda r: r.score, reverse=True)

    def generate_context(self, results: List[RAGResult]) -> str:
        """生成上下文"""
        if not results:
            return "未找到相关信息。"

        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(f"[{i}] {r.content}")

        return "\n".join(context_parts)


class TemporalQueryParser:
    """双时态查询解析器"""

    def __init__(self):
        self._patterns = {
            r"上周|上周.*?": "last_week",
            r"这周|本周|这周.*?": "this_week",
            r"上个月|上月": "last_month",
            r"现在|当前|此刻": "now",
            r"事件发生时|当时": "event_time",
            r"(\d{4})年(\d{1,2})月(\d{1,2})日": "specific_date",
            r"(\d+)小时前": "hours_ago",
        }

    def parse(self, query: str) -> Dict[str, Any]:
        """
        解析时间表达式

        Args:
            query: 查询文本

        Returns:
            时间参数
        """
        result = {
            "has_temporal": False,
            "valid_time": None,
            "transaction_time": None,
            "description": query
        }

        for pattern, time_type in self._patterns.items():
            match = re.search(pattern, query)
            if match:
                result["has_temporal"] = True
                result["time_type"] = time_type
                result["match_text"] = match.group(0)
                break

        return result


class SourceTracer:
    """溯源追踪器"""

    def __init__(self, graphiti_client=None, query_service=None):
        self.graphiti = graphiti_client
        self._query_service = query_service

    def trace(self, answer: str, query: str, rag_results: List["RAGResult"] = None) -> List[SourceTrace]:
        """
        追踪答案来源

        Args:
            answer: 生成的回答
            query: 原始查询
            rag_results: RAG检索结果

        Returns:
            溯源列表
        """
        if "未找到" in answer or "无法找到" in answer or "未查询到" in answer:
            return []

        traces = []

        if rag_results:
            for r in rag_results[:3]:
                props = r.metadata.get("properties", {}) if r.metadata else {}
                name = props.get("name", r.source)
                traces.append(SourceTrace(
                    episode_id=None,
                    entity_id=r.source,
                    confidence=r.score,
                    excerpt=name,
                    source=name
                ))
        elif self._query_service is not None:
            try:
                result = self._query_service.execute("default", ".entity list(3)")
                for entity in result.rows[:3]:
                    entity_name = entity.get("properties", {}).get("name", entity.get("id", ""))
                    traces.append(SourceTrace(
                        episode_id=None,
                        entity_id=entity.get("id"),
                        confidence=0.7,
                        excerpt=entity_name,
                        source=entity_name
                    ))
            except Exception:
                pass
        elif self.graphiti:
            try:
                entities = self.graphiti.query_entities()
                for entity in entities[:3]:
                    entity_name = entity.get("properties", {}).get("name", entity.get("id", ""))
                    traces.append(SourceTrace(
                        episode_id=None,
                        entity_id=entity.get("id"),
                        confidence=0.7,
                        excerpt=entity_name,
                        source=entity_name
                    ))
            except Exception:
                pass

        return traces


class QAEngineV2:
    """
    问答引擎

    功能：
    - 多轮对话管理
    - RAG 增强生成
    - 双时态查询
    - 溯源追踪
    - 复杂问题升级
    """

    def __init__(self, graphiti_client=None, use_mock: bool = False,
                 ingest_storage=None, semantic_map_storage=None,
                 model_storage=None, query_service=None):
        self.dialog_manager = DialogManager()
        self.ingest_storage = ingest_storage
        self.semantic_map_storage = semantic_map_storage
        self._query_service = query_service
        self.rag_pipeline = RAGPipeline(
            graphiti_client,
            ingest_storage=ingest_storage,
            semantic_map_storage=semantic_map_storage,
            model_storage=model_storage,
            query_service=query_service,
        )
        self.temporal_parser = TemporalQueryParser()
        self.source_tracer = SourceTracer(graphiti_client, query_service=query_service)
        self.graphiti = graphiti_client
        self.use_mock = use_mock
        self._llm_client = None
        self._cot_enabled = _COT_AVAILABLE

        self._escalation_keywords = ["为什么", "原因", "解释", "详细"]
        self._complex_patterns = [r"如果.*?会.*?", r".*?和.*?对比", r".*?的最佳.*?"]

        # 多跳检索规划器
        from odap.biz.data.qa.impl.multihop_planner import MultiHopPlanner, MultiHopExecutor
        self._multihop_planner = MultiHopPlanner(llm_client=None)
        self._multihop_executor = MultiHopExecutor(
            rag_pipeline=self.rag_pipeline,
            planner=self._multihop_planner,
        )

        # 共指消解：代词列表
        self._pronouns = ["它", "他", "她", "这个", "那个", "这些", "那些"]

        # 工具注册
        self._tools: List[Dict[str, Any]] = []

    def _resolve_coreferences(self, query: str, context: str) -> str:
        """基于规则的共指消解：将代词替换为对话上下文中最近提及的实体。

        Args:
            query: 用户当前问题
            context: 对话上下文文本

        Returns:
            消解后的查询文本
        """
        if not query or not context:
            return query

        # 检查查询中是否包含代词
        has_pronoun = any(p in query for p in self._pronouns)
        if not has_pronoun:
            return query

        # 从上下文中提取最近的实体名（启发式：取每行中 user 消息的关键名词）
        # 策略：从上下文最后一条 user 消息中提取最长的中文名词短语
        recent_entity = None
        lines = context.strip().split("\n")
        # 从后往前查找 user 行
        for line in reversed(lines):
            if line.startswith("user:"):
                content = line[len("user:"):].strip()
                # 提取中文实体名：取最长的连续中文字符串（2-20字符）
                chinese_segments = re.findall(r'[\u4e00-\u9fff]{2,20}', content)
                if chinese_segments:
                    # 取最长的作为实体名
                    recent_entity = max(chinese_segments, key=len)
                    break

        if not recent_entity:
            return query

        # 替换代词
        resolved = query
        for pronoun in self._pronouns:
            if pronoun in resolved:
                resolved = resolved.replace(pronoun, recent_entity, 1)
                logger.info(
                    "QAEngine coreference resolved: '%s' -> '%s' (entity: %s)",
                    query, resolved, recent_entity,
                )
                break  # 只替换第一个匹配的代词

        return resolved

    @property
    def llm_client(self):
        if self._llm_client is None:
            try:
                from odap.infra.llm.llm_service import ZhipuAIClient
                from graphiti_core.llm_client.config import LLMConfig
                import os
                api_key = os.getenv('OPENAI_API_KEY', '')
                api_base = os.getenv('OPENAI_API_BASE', 'https://open.bigmodel.cn/api/paas/v4')
                model = os.getenv('OPENAI_MODEL', 'glm-4')
                if api_key:
                    config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.7)
                    self._llm_client = ZhipuAIClient(config=config)
                else:
                    self._llm_client = None
            except Exception as e:
                logger.warning(f"QAEngine: LLM client init failed: {e}")
                self._llm_client = None
        return self._llm_client

    def ask(self, query: str, user_id: str = "user",
           session_id: str = None, context: Dict = None,
           workspace_id: Optional[str] = None,
           scenario_id: Optional[str] = None,
           agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        问答

        Args:
            query: 用户问题
            user_id: 用户 ID
            session_id: 会话 ID（可选）
            context: 额外上下文
            workspace_id: 工作空间 ID（可选）
            scenario_id: 场景 ID（可选）
            agent_id: 智能体 ID（可选）

        Returns:
            回答结果
        """
        from odap.infra.llm.prompt_sanitizer import PromptSanitizer
        query = PromptSanitizer.sanitize_input(query)
        if not session_id:
            session = self.dialog_manager.create_session(user_id, workspace_id, scenario_id, agent_id)
            session_id = session.session_id
        else:
            session = self.dialog_manager.get_session(session_id)
            if not session:
                session = self.dialog_manager.create_session(user_id, workspace_id, scenario_id, agent_id)
                session_id = session.session_id
            else:
                if workspace_id and not session.workspace_id:
                    session.workspace_id = workspace_id
                if scenario_id and not session.scenario_id:
                    session.scenario_id = scenario_id
                if agent_id and not session.agent_id:
                    session.agent_id = agent_id

        # 如果会话处于 WAITING_FOR_CLARIFICATION 状态，将用户的新输入与原始上下文合并
        clarification_context = None
        if session and session.state == DialogState.WAITING_FOR_CLARIFICATION:
            # 保存原始问题上下文，用于合并
            clarification_context = session.context.get("original_query", "")
            # 重置状态，准备正常回答
            session.state = DialogState.IN_PROGRESS

        self.dialog_manager.add_message(session_id, "user", query)

        # Initialize CoT reasoning chain
        cot_builder = None
        cot_root = None
        simple_chain = None
        if self._cot_enabled:
            try:
                cot_builder = CoTBuilder()
                cot_root = cot_builder.start(query)
            except Exception as cot_err:
                logger.warning(f"QAEngine: CoT start failed: {cot_err}")
                cot_builder = None
                cot_root = None

        # 当 CoTBuilder 不可用时，使用 SimpleReasoningChain 作为回退
        if not cot_builder:
            simple_chain = SimpleReasoningChain(query)

        try:
            dialog_context = self.dialog_manager.get_context(session_id)
            # 如果有追问上下文，合并到 full_query（含共指消解）
            if clarification_context:
                resolved_query = self._resolve_coreferences(query, dialog_context)
                full_query = f"{dialog_context}\n原始问题: {clarification_context}\n用户补充: {resolved_query}" if dialog_context else f"原始问题: {clarification_context}\n用户补充: {resolved_query}"
            else:
                full_query = f"{dialog_context}\n用户: {query}" if dialog_context else query

            temporal_params = self.temporal_parser.parse(query)

            ontology_ids = None
            if scenario_id and scenario_id != "default":
                ontology_ids = self._get_ontology_ids_for_scenario(scenario_id)

            rag_results = []
            context_text = "未找到相关信息。"
            entities = []
            multihop_metadata: Dict[str, Any] = {"multihop_used": False, "complexity": "unknown", "hop_count": 0, "hop_details": []}
            # 优先使用 QueryService 进行实体/时态查询
            if self._query_service is not None:
                try:
                    ws = workspace_id or "default"
                    if temporal_params["has_temporal"]:
                        result = self._query_service.execute(ws, ".temporal range()")
                        entities = result.rows
                    else:
                        result = self._query_service.execute(ws, ".entity list()")
                        entities = result.rows
                except Exception as qs_err:
                    logger.warning(f"QAEngine QueryService query failed: {qs_err}")
                    entities = []
            elif self.graphiti:
                try:
                    if temporal_params["has_temporal"]:
                        entities = self.graphiti.query_temporal(
                            valid_time=temporal_params.get("valid_time"),
                            transaction_time=temporal_params.get("transaction_time")
                        )
                    else:
                        entities = self.graphiti.query_entities(
                            workspace_id=workspace_id if workspace_id and workspace_id != "default" else None
                        )
                except Exception as graphiti_err:
                    logger.warning(f"QAEngine graphiti query failed: {graphiti_err}")
                    entities = []

            try:
                logger.info(f"QAEngine ask: scenario_id={scenario_id}, workspace_id={workspace_id}, ontology_ids={ontology_ids}")
                # 多跳检索：复杂问题自动分解为多步检索链
                rag_results, multihop_metadata = self._execute_multihop_retrieval(
                    full_query,
                    workspace_id=workspace_id,
                    scenario_id=scenario_id,
                    ontology_ids=ontology_ids,
                    top_k=10,
                    original_query=query,
                )

                if not rag_results and entities and not scenario_id:
                    for entity in entities[:10]:
                        props = entity.get("properties", {})
                        name = props.get("name", "")
                        etype = entity.get("type", "")
                        content = f"{name} (类型:{etype})"
                        if props:
                            for k, v in list(props.items())[:5]:
                                if k not in ("name", "type"):
                                    content += f" | {k}:{v}"
                        rag_results.append(RAGResult(
                            content=content,
                            source=self._make_source_label(entity, entity.get("id", "unknown")),
                            score=0.6,
                            metadata=entity
                        ))

                context_text = self.rag_pipeline.generate_context(rag_results)

                # 二次过滤警告：如果最高分结果仍低于 0.15，记录警告
                if rag_results and rag_results[0].score < 0.15:
                    logger.warning(
                        f"QAEngine ask: top RAG result score={rag_results[0].score:.3f} "
                        f"is below 0.15, results may not be relevant to query '{query[:50]}'"
                    )

                # CoT: RAG augmentation step
                if cot_builder and cot_root:
                    try:
                        rag_node = cot_builder.add_child(
                            cot_root, CoTNodeType.RAG_AUGMENT,
                            label=f"RAG 检索完成: {len(rag_results)} 条结果",
                            detail=context_text[:200] if context_text else "",
                        )
                        cot_builder.start_timing(rag_node.id)
                        cot_builder.update_status(rag_node.id, "done")
                        cot_builder.finish_timing(rag_node.id)
                        rag_node.metadata["result_count"] = len(rag_results)
                    except Exception as cot_err:
                        logger.warning(f"QAEngine: CoT RAG node failed: {cot_err}")
                elif simple_chain:
                    simple_chain.add_step(
                        "rag_augment",
                        f"RAG 检索完成: {len(rag_results)} 条结果",
                        {"result_count": len(rag_results)},
                    )

            except Exception as rag_err:
                logger.warning(f"QAEngine RAG retrieval failed, using template fallback: {rag_err}", exc_info=True)
                multihop_metadata = {"multihop_used": False, "complexity": "unknown", "hop_count": 0, "hop_details": []}

            # 追问/澄清检查：如果检索结果不足或问题模糊，请求用户补充信息
            needs_clarification, clarification_reason, clarification_questions = self._needs_clarification(
                query, rag_results
            )
            if needs_clarification:
                # 保存原始问题到会话上下文，以便后续追问时合并
                session.context["original_query"] = query

                clarification_answer = f"您的问题需要进一步澄清：{clarification_reason_to_chinese(clarification_reason)}"
                self.dialog_manager.add_message(session_id, "assistant", clarification_answer, {
                    "clarification": True,
                    "reason": clarification_reason,
                    "questions": clarification_questions,
                })
                # 在 add_message 之后设置状态（add_message 会将状态设为 IN_PROGRESS）
                session.state = DialogState.WAITING_FOR_CLARIFICATION

                # CoT: partial reasoning chain for clarification
                if cot_builder:
                    reasoning_chain = self._build_reasoning_chain(cot_builder)
                elif simple_chain:
                    simple_chain.add_step("clarification", f"需要澄清: {clarification_reason}")
                    reasoning_chain = simple_chain.to_list()
                else:
                    reasoning_chain = []

                return {
                    "session_id": session_id,
                    "answer": clarification_answer,
                    "sources": [],
                    "dialog_state": DialogState.WAITING_FOR_CLARIFICATION.value,
                    "clarification_questions": clarification_questions,
                    "clarification_reason": clarification_reason,
                    "suggested_actions": [],
                    "decision_available": False,
                    "charts": [],
                    "temporal": [],
                    "reports": [],
                    "multihop": multihop_metadata,
                    "reasoning_chain": reasoning_chain,
                }

            answer = self._generate_answer(query, context_text, rag_results, agent_context=context)

            # CoT: LLM inference step
            if cot_builder and cot_root:
                try:
                    llm_node = cot_builder.add_child(
                        cot_root, CoTNodeType.LLM_INFER,
                        label="LLM 生成回答",
                        detail=answer[:200] if answer else "",
                    )
                    cot_builder.start_timing(llm_node.id)
                    cot_builder.update_status(llm_node.id, "done")
                    cot_builder.finish_timing(llm_node.id)
                    llm_node.metadata["answer_length"] = len(answer) if answer else 0
                except Exception as cot_err:
                    logger.warning(f"QAEngine: CoT LLM node failed: {cot_err}")
            elif simple_chain:
                simple_chain.add_step(
                    "llm_infer",
                    "LLM 生成回答",
                    {"answer_length": len(answer) if answer else 0},
                )

            if "未找到相关信息" in answer:
                traces = []
            else:
                traces = self.source_tracer.trace(answer, query, rag_results)

            # CoT: Entity link steps for traced sources
            if cot_builder and cot_root and traces:
                try:
                    for trace in traces[:5]:
                        entity_node = cot_builder.add_child(
                            cot_root, CoTNodeType.ENTITY_LINK,
                            label=f"溯源: {trace.excerpt[:50]}",
                            detail=trace.source,
                        )
                        entity_node.metadata["confidence"] = trace.confidence
                        entity_node.metadata["entity_id"] = trace.entity_id
                        cot_builder.update_status(entity_node.id, "done")
                except Exception as cot_err:
                    logger.warning(f"QAEngine: CoT entity link nodes failed: {cot_err}")
            elif simple_chain and traces:
                for trace in traces[:5]:
                    simple_chain.add_step(
                        "entity_link",
                        f"溯源: {trace.excerpt[:50]}",
                        {"confidence": trace.confidence, "entity_id": trace.entity_id},
                    )

            self.dialog_manager.add_message(session_id, "assistant", answer, {
                "traces": [{"source": t.source, "excerpt": t.excerpt} for t in traces],
                "rag_results": len(rag_results)
            })

            # CoT: Synthesis step
            reasoning_chain = []
            if cot_builder and cot_root:
                try:
                    cot_builder.add_child(
                        cot_root, CoTNodeType.SYNTHESIS,
                        label="推理链综合",
                        detail=answer[:100] if answer else "",
                    )
                    reasoning_chain = self._build_reasoning_chain(cot_builder)
                except Exception as cot_err:
                    logger.warning(f"QAEngine: CoT synthesis node failed: {cot_err}")
            elif simple_chain:
                simple_chain.add_step("synthesis", "推理链综合")
                reasoning_chain = simple_chain.to_list()

            return {
                "session_id": session_id,
                "answer": answer,
                "sources": [{"source": t.source, "excerpt": t.excerpt, "confidence": t.confidence} for t in traces],
                "dialog_state": session.state.value if session else "unknown",
                "suggested_actions": self._extract_suggested_actions(query, rag_results),
                "decision_available": self._is_decision_intent(query),
                "charts": self._extract_charts(query, answer, rag_results),
                "temporal": self._extract_temporal(query, temporal_params, entities),
                "reports": self._extract_reports(query, answer, rag_results),
                "multihop": multihop_metadata,
                "reasoning_chain": reasoning_chain,
            }
        except Exception as e:
            logger.error(f"QAEngine ask failed: {e}")
            fallback_answer = self._answer_general(query, "未找到相关信息。", [])
            self.dialog_manager.add_message(session_id, "assistant", fallback_answer, {
                "traces": [],
                "rag_results": 0
            })
            # CoT: partial reasoning chain for error case
            if cot_builder:
                reasoning_chain = self._build_reasoning_chain(cot_builder)
            elif simple_chain:
                simple_chain.add_step("error", f"QA 失败: {str(e)[:100]}")
                reasoning_chain = simple_chain.to_list()
            else:
                reasoning_chain = []
            return {
                "session_id": session_id,
                "answer": fallback_answer,
                "sources": [],
                "dialog_state": "error",
                "error": str(e),
                "reasoning_chain": reasoning_chain,
            }

    async def ask_stream(self, query: str, user_id: str = "user",
                         session_id: str = None, context: Dict = None,
                         workspace_id: Optional[str] = None,
                         scenario_id: Optional[str] = None,
                         agent_id: Optional[str] = None):
        """
        流式问答 - 先同步检索RAG，再流式生成回答

        Yields:
            dict: 流式事件，格式:
                {"type": "session_id", "value": "..."}
                {"type": "thinking", "value": "检索中..."}
                {"type": "sources", "value": [...]}
                {"type": "content", "value": "token chunk"}
                {"type": "end", "value": {"session_id": "..."}}
        """
        from odap.infra.llm.prompt_sanitizer import PromptSanitizer
        query = PromptSanitizer.sanitize_input(query)
        if not session_id:
            session = self.dialog_manager.create_session(user_id, workspace_id, scenario_id, agent_id)
            session_id = session.session_id
        else:
            session = self.dialog_manager.get_session(session_id)
            if not session:
                session = self.dialog_manager.create_session(user_id, workspace_id, scenario_id, agent_id)
                session_id = session.session_id
            else:
                if workspace_id and not session.workspace_id:
                    session.workspace_id = workspace_id
                if scenario_id and not session.scenario_id:
                    session.scenario_id = scenario_id
                if agent_id and not session.agent_id:
                    session.agent_id = agent_id

        # 如果会话处于 WAITING_FOR_CLARIFICATION 状态，将用户的新输入与原始上下文合并
        clarification_context = None
        if session and session.state == DialogState.WAITING_FOR_CLARIFICATION:
            clarification_context = session.context.get("original_query", "")
            session.state = DialogState.IN_PROGRESS

        yield {"type": "session_id", "value": session_id}
        yield {"type": "thinking", "value": "正在检索相关知识..."}

        self.dialog_manager.add_message(session_id, "user", query)

        # Initialize CoT reasoning chain
        cot_builder = None
        cot_root = None
        simple_chain = None
        if self._cot_enabled:
            try:
                cot_builder = CoTBuilder()
                cot_root = cot_builder.start(query)
            except Exception as cot_err:
                logger.warning(f"QAEngine stream: CoT start failed: {cot_err}")
                cot_builder = None
                cot_root = None

        # 当 CoTBuilder 不可用时，使用 SimpleReasoningChain 作为回退
        if not cot_builder:
            simple_chain = SimpleReasoningChain(query)

        try:
            dialog_context = self.dialog_manager.get_context(session_id)
            # 如果有追问上下文，合并到 full_query（含共指消解）
            if clarification_context:
                resolved_query = self._resolve_coreferences(query, dialog_context)
                full_query = f"{dialog_context}\n原始问题: {clarification_context}\n用户补充: {resolved_query}" if dialog_context else f"原始问题: {clarification_context}\n用户补充: {resolved_query}"
            else:
                full_query = f"{dialog_context}\n用户: {query}" if dialog_context else query

            temporal_params = self.temporal_parser.parse(query)

            ontology_ids = None
            if scenario_id and scenario_id != "default":
                ontology_ids = self._get_ontology_ids_for_scenario(scenario_id)

            # ── 推理步骤1: 查询理解 ──
            query_understanding_parts = [f"原始查询: {query}"]
            if temporal_params.get("has_temporal"):
                query_understanding_parts.append(f"时态查询: valid_time={temporal_params.get('valid_time')}, transaction_time={temporal_params.get('transaction_time')}")
            if ontology_ids:
                query_understanding_parts.append(f"限定本体: {len(ontology_ids)} 个")
            if scenario_id and scenario_id != "default":
                query_understanding_parts.append(f"限定场景: {scenario_id}")
            if dialog_context:
                query_understanding_parts.append(f"含对话上下文，合并查询: {full_query[:80]}")
            yield {
                "type": "reasoning",
                "value": {
                    "step": "query_understanding",
                    "description": " | ".join(query_understanding_parts),
                    "detail": {
                        "original_query": query,
                        "has_temporal": temporal_params.get("has_temporal", False),
                        "has_dialog_context": bool(dialog_context),
                        "ontology_count": len(ontology_ids) if ontology_ids else 0,
                        "scenario_id": scenario_id,
                    },
                }
            }

            # RAG检索（同步，快速）
            rag_results = []
            context_text = "未找到相关信息。"
            entities = []
            multihop_metadata: Dict[str, Any] = {"multihop_used": False, "complexity": "unknown", "hop_count": 0, "hop_details": []}

            # ── 检索策略选择：根据查询复杂度和本体匹配选择快速/完整路径 ──
            from odap.biz.data.qa.impl.multihop_planner import QueryComplexity
            complexity = self._multihop_planner.detect_complexity(query)
            ontology_matched = False
            if ontology_ids:
                schemas = self.rag_pipeline.ontology_gate.load_schema(ontology_ids, workspace_id or "default")
                if schemas:
                    qv = self.rag_pipeline.ontology_gate.validate_query(query, schemas)
                    ontology_matched = bool(qv.matched_entity_types or qv.matched_relation_types)

            # 快速路径：简单查询 + 高本体匹配 → 仅 SQLite + ModelStorage + 直接格式化输出
            use_fast_path = (
                complexity == QueryComplexity.SIMPLE
                and ontology_matched
                and not temporal_params.get("has_temporal", False)
            )

            if use_fast_path:
                # 快速路径：仅使用 SQLite + ModelStorage 检索
                yield {
                    "type": "reasoning",
                    "value": {
                        "step": "retrieval_strategy",
                        "description": f"快速路径: 简单查询+本体匹配(ontology_matched={ontology_matched})，仅 SQLite + ModelStorage",
                        "detail": {"strategy": "fast_path", "complexity": complexity.value, "ontology_matched": ontology_matched},
                    }
                }
                try:
                    if self.ingest_storage:
                        sqlite_results = self.rag_pipeline._retrieve_from_sqlite(
                            query, 5, scenario_id, ontology_ids
                        )
                        rag_results.extend(sqlite_results)
                    if self.model_storage:
                        model_results = self.rag_pipeline._retrieve_from_model_storage(
                            query, 5, workspace_id, ontology_ids
                        )
                        rag_results.extend(model_results)
                    rag_results.sort(key=lambda r: r.score, reverse=True)
                    rag_results = rag_results[:5]
                    context_text = self.rag_pipeline.generate_context(rag_results)
                    multihop_metadata["complexity"] = complexity.value
                    multihop_metadata["hop_details"] = [
                        {"hop_index": 0, "query": query, "result_count": len(rag_results), "strategy": "fast_path"}
                    ]
                except Exception as fast_err:
                    logger.warning(f"QAEngine fast path failed, falling back to full path: {fast_err}")
                    rag_results = []
                    use_fast_path = False

            if not use_fast_path:
                # 完整路径：全部5个检索源 + LLM 生成
                yield {
                    "type": "reasoning",
                    "value": {
                        "step": "retrieval_strategy",
                        "description": f"完整路径: complexity={complexity.value}, ontology_matched={ontology_matched}",
                        "detail": {"strategy": "full_path", "complexity": complexity.value, "ontology_matched": ontology_matched},
                    }
                }
                # 优先使用 QueryService 进行实体/时态查询
                entity_source = None
                if self._query_service is not None:
                    try:
                        ws = workspace_id or "default"
                        if temporal_params["has_temporal"]:
                            result = await self._query_service.execute_async(ws, ".temporal range()")
                            entities = result.rows
                            entity_source = "QueryService(temporal)"
                        else:
                            result = await self._query_service.execute_async(ws, ".entity list()")
                            entities = result.rows
                            entity_source = "QueryService(entity)"
                    except Exception as qs_err:
                        logger.warning(f"QAEngine stream QueryService query failed: {qs_err}")
                        entities = []
                elif self.graphiti:
                    try:
                        if temporal_params["has_temporal"]:
                            entities = await asyncio.to_thread(
                                self.graphiti.query_temporal,
                                valid_time=temporal_params.get("valid_time"),
                                transaction_time=temporal_params.get("transaction_time")
                            )
                            entity_source = "Graphiti(temporal)"
                        else:
                            entities = await asyncio.to_thread(
                                self.graphiti.query_entities,
                                workspace_id=workspace_id if workspace_id and workspace_id != "default" else None
                            )
                            entity_source = "Graphiti(entity)"
                    except Exception as graphiti_err:
                        logger.warning(f"QAEngine stream graphiti query failed: {graphiti_err}")
                        entities = []

                # ── 推理步骤2: 实体预检索 ──
                if entity_source:
                    yield {
                        "type": "reasoning",
                        "value": {
                            "step": "entity_preretrieval",
                            "description": f"实体预检索 [{entity_source}]: 获取 {len(entities)} 个实体",
                            "detail": {"source": entity_source, "entity_count": len(entities)},
                        }
                    }

                try:
                    # 多跳检索：复杂问题自动分解为多步检索链
                    # 使用 asyncio.to_thread 避免同步阻塞调用冻结事件循环
                    rag_results, multihop_metadata = await asyncio.to_thread(
                        self._execute_multihop_retrieval,
                        full_query,
                        workspace_id=workspace_id,
                        scenario_id=scenario_id,
                        ontology_ids=ontology_ids,
                        top_k=10,
                        original_query=query,
                    )

                    if not rag_results and entities and not scenario_id:
                        for entity in entities[:10]:
                            props = entity.get("properties", {})
                            name = props.get("name", "")
                            etype = entity.get("type", "")
                            content = f"{name} (类型:{etype})"
                            if props:
                                for k, v in list(props.items())[:5]:
                                    if k not in ("name", "type"):
                                        content += f" | {k}:{v}"
                            rag_results.append(RAGResult(
                                content=content,
                                source=self._make_source_label(entity, entity.get("id", "unknown")),
                                score=0.6,
                                metadata=entity
                            ))

                    context_text = self.rag_pipeline.generate_context(rag_results)

                    # 二次过滤警告：如果最高分结果仍低于 0.15，记录警告
                    if rag_results and rag_results[0].score < 0.15:
                        logger.warning(
                            f"QAEngine stream: top RAG result score={rag_results[0].score:.3f} "
                            f"is below 0.15, results may not be relevant to query '{query[:50]}'"
                        )

                    # ── 推理步骤3: RAG 检索结果汇总 ──
                    complexity_val = multihop_metadata.get("complexity", "unknown")
                    multihop_used = multihop_metadata.get("multihop_used", False)
                    hop_count = multihop_metadata.get("hop_count", 1)
                    source_breakdown = {}
                    for r in rag_results:
                        src = r.source.split(":")[0] if ":" in r.source else r.source
                        source_type = src if src else "unknown"
                        source_breakdown[source_type] = source_breakdown.get(source_type, 0) + 1
                    source_desc = ", ".join(f"{k}: {v}条" for k, v in source_breakdown.items())

                    rag_desc_parts = [f"检索到 {len(rag_results)} 条相关结果"]
                    if multihop_used:
                        rag_desc_parts.append(f"多跳检索({complexity_val}, {hop_count}跳)")
                    if source_desc:
                        rag_desc_parts.append(f"来源分布[{source_desc}]")
                    if rag_results:
                        rag_desc_parts.append(f"最高相关度: {rag_results[0].score:.2f}")

                    yield {
                        "type": "reasoning",
                        "value": {
                            "step": "rag_augment",
                            "description": " | ".join(rag_desc_parts),
                            "detail": {
                                "result_count": len(rag_results),
                                "multihop_used": multihop_used,
                                "complexity": complexity_val,
                                "hop_count": hop_count,
                                "source_breakdown": source_breakdown,
                                "top_score": rag_results[0].score if rag_results else 0,
                                "hop_details": multihop_metadata.get("hop_details", []),
                            },
                        }
                    }

                except Exception as rag_err:
                    logger.warning(f"QAEngine stream RAG retrieval failed: {rag_err}", exc_info=True)
                    multihop_metadata = {"multihop_used": False, "complexity": "unknown", "hop_count": 0, "hop_details": []}

            # 追问/澄清检查：如果检索结果不足或问题模糊，发送澄清事件
            needs_clarification, clarification_reason, clarification_questions = self._needs_clarification(
                query, rag_results
            )
            if needs_clarification:
                # 保存原始问题到会话上下文，以便后续追问时合并
                session.context["original_query"] = query
                session.state = DialogState.WAITING_FOR_CLARIFICATION

                clarification_answer = f"您的问题需要进一步澄清：{clarification_reason_to_chinese(clarification_reason)}"
                self.dialog_manager.add_message(session_id, "assistant", clarification_answer, {
                    "clarification": True,
                    "reason": clarification_reason,
                    "questions": clarification_questions,
                })

                yield {
                    "type": "clarification",
                    "value": {
                        "questions": clarification_questions,
                        "reason": clarification_reason,
                    }
                }
                # CoT: partial reasoning chain for clarification
                if cot_builder:
                    reasoning_chain = self._build_reasoning_chain(cot_builder)
                elif simple_chain:
                    simple_chain.add_step("clarification", f"需要澄清: {clarification_reason}")
                    reasoning_chain = simple_chain.to_list()
                else:
                    reasoning_chain = []
                yield {
                    "type": "end",
                    "value": {
                        "session_id": session_id,
                        "dialog_state": DialogState.WAITING_FOR_CLARIFICATION.value,
                        "reasoning_chain": reasoning_chain,
                    }
                }
                return

            # 发送检索来源
            sources = [{"source": r.source, "excerpt": r.content[:100], "confidence": r.score}
                       for r in rag_results[:5]]
            yield {"type": "sources", "value": sources}

            # ── 推理步骤4: 溯源详情 ──
            for idx, r in enumerate(rag_results[:5]):
                yield {
                    "type": "reasoning",
                    "value": {
                        "step": "source_trace",
                        "description": f"来源#{idx+1}: [{r.source}] 相关度={r.score:.2f} | {r.content[:80]}",
                        "detail": {
                            "source": r.source,
                            "score": r.score,
                            "content_preview": r.content[:200],
                        },
                    }
                }

            # ── 生成回答：高置信度直接格式化输出，低置信度走 LLM ──
            HIGH_CONFIDENCE_THRESHOLD = 0.5
            use_direct_answer = (
                rag_results
                and rag_results[0].score >= HIGH_CONFIDENCE_THRESHOLD
                and len(rag_results) <= 5
            )

            full_answer = ""

            if use_direct_answer:
                # 高置信度：直接格式化检索结果，无需等待 LLM
                yield {
                    "type": "reasoning",
                    "value": {
                        "step": "answer_strategy",
                        "description": f"检索结果置信度高(top={rag_results[0].score:.2f})，直接格式化输出",
                        "detail": {"strategy": "direct_format", "top_score": rag_results[0].score},
                    }
                }
                full_answer = self._format_rag_results(query, rag_results)
                yield {"type": "content", "value": full_answer}
            else:
                yield {"type": "thinking", "value": "正在生成回答..."}

                # 低置信度或无结果：走 LLM 流式生成
                async for token in self._generate_with_llm_stream(
                    query, context_text, rag_results, agent_context=context
                ):
                    full_answer += token
                    yield {"type": "content", "value": token}

                # 如果LLM流式失败返回空，使用模板兜底
                if not full_answer:
                    full_answer = self._generate_answer(query, context_text, rag_results, agent_context=context)
                    if full_answer:
                        yield {"type": "content", "value": full_answer}

            # ── 推理步骤5: 生成完成 ──
            strategy_label = "直接格式化" if use_direct_answer else "LLM 生成"
            yield {
                "type": "reasoning",
                "value": {
                    "step": "llm_infer",
                    "description": f"{strategy_label}完成 | 回答长度: {len(full_answer)} 字符 | 上下文: {len(context_text)} 字符",
                    "detail": {
                        "strategy": "direct_format" if use_direct_answer else "llm_stream",
                        "answer_length": len(full_answer) if full_answer else 0,
                        "context_length": len(context_text),
                        "rag_result_count": len(rag_results),
                    },
                }
            }

            # 保存对话
            traces = self.source_tracer.trace(full_answer, query, rag_results) if "未找到" not in full_answer else []
            self.dialog_manager.add_message(session_id, "assistant", full_answer, {
                "traces": [{"source": t.source, "excerpt": t.excerpt} for t in traces],
                "rag_results": len(rag_results)
            })

            # 发送额外数据
            charts = self._extract_charts(query, full_answer, rag_results)
            for chart in charts:
                yield {"type": "chart", "value": chart}

            temporal_data = self._extract_temporal(query, temporal_params, entities)
            for t in temporal_data:
                yield {"type": "temporal", "value": t}

            # 发送多跳检索元数据
            if multihop_metadata.get("multihop_used"):
                yield {"type": "multihop", "value": multihop_metadata}

            # CoT: Synthesis step
            reasoning_chain = []
            if cot_builder and cot_root:
                try:
                    cot_builder.add_child(
                        cot_root, CoTNodeType.SYNTHESIS,
                        label="推理链综合",
                        detail=full_answer[:100] if full_answer else "",
                    )
                    reasoning_chain = self._build_reasoning_chain(cot_builder)
                    yield {
                        "type": "reasoning",
                        "value": {
                            "step": "synthesis",
                            "description": "推理链综合完成",
                        }
                    }
                except Exception as cot_err:
                    logger.warning(f"QAEngine stream: CoT synthesis node failed: {cot_err}")
            elif simple_chain:
                simple_chain.add_step("synthesis", "推理链综合")
                reasoning_chain = simple_chain.to_list()
                yield {
                    "type": "reasoning",
                    "value": {
                        "step": "synthesis",
                        "description": "推理链综合完成",
                    }
                }

            yield {"type": "end", "value": {"session_id": session_id, "reasoning_chain": reasoning_chain}}

        except Exception as e:
            logger.error(f"QAEngine ask_stream failed: {e}")
            fallback_answer = self._answer_general(query, "未找到相关信息。", [])
            if cot_builder:
                reasoning_chain = self._build_reasoning_chain(cot_builder)
            elif simple_chain:
                simple_chain.add_step("error", f"QA 失败: {str(e)[:100]}")
                reasoning_chain = simple_chain.to_list()
            else:
                reasoning_chain = []
            yield {"type": "content", "value": fallback_answer}
            yield {"type": "end", "value": {"session_id": session_id, "error": str(e), "reasoning_chain": reasoning_chain}}

    def register_tool(self, name: str, description: str, handler: callable,
                      parameters: Optional[Dict[str, Any]] = None) -> None:
        """注册工具供 ask_with_tools 使用

        Args:
            name: 工具名称
            description: 工具描述
            handler: 工具执行函数，接受 Dict 参数，返回 Dict 结果
            parameters: 工具参数 schema（可选）
        """
        self._tools.append({
            "name": name,
            "description": description,
            "handler": handler,
            "parameters": parameters or {},
        })

    def ask_with_tools(self, query: str, user_id: str = "user",
                      session_id: str = None) -> Dict[str, Any]:
        """带工具调用的问答 - ReAct 模式

        如果有工具可用，实现简单的 ReAct 循环：
        1. 让 LLM 判断是否需要调用工具
        2. 如果需要，执行工具并将结果反馈给 LLM
        3. 重复直到 LLM 给出最终答案或达到最大迭代次数

        如果没有工具，委托给 self.ask() 并标注 tools_available: False
        """
        if not self._tools:
            result = self.ask(query, user_id, session_id)
            result["tools_available"] = False
            return result

        # ReAct 循环
        max_iterations = 3
        current_query = query
        tool_calls_log = []

        for iteration in range(max_iterations):
            # 构建包含工具描述的 prompt
            tools_desc = "\n".join(
                f"- {t['name']}: {t['description']}" for t in self._tools
            )
            tool_names = ", ".join(t["name"] for t in self._tools)

            react_prompt = (
                f"你可以使用以下工具来帮助回答问题：\n{tools_desc}\n\n"
                f"如果你想调用工具，请回复格式：TOOL_CALL: <工具名> | <参数JSON>\n"
                f"如果你想直接回答，请直接给出答案。\n\n"
                f"问题：{current_query}"
            )

            # 使用 LLM 判断是否需要调用工具
            llm_response = self._call_llm_for_tool_decision(react_prompt)

            if llm_response and llm_response.startswith("TOOL_CALL:"):
                # 解析工具调用
                try:
                    parts = llm_response[len("TOOL_CALL:"):].strip().split("|", 1)
                    tool_name = parts[0].strip()
                    tool_args = {}
                    if len(parts) > 1:
                        import json as _json
                        tool_args = _json.loads(parts[1].strip())

                    # 查找并执行工具
                    tool = next((t for t in self._tools if t["name"] == tool_name), None)
                    if tool:
                        try:
                            tool_result = tool["handler"](tool_args)
                            tool_calls_log.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "result": tool_result,
                                "iteration": iteration,
                            })
                            # 将工具结果反馈给 LLM
                            current_query = (
                                f"{query}\n\n"
                                f"工具 {tool_name} 返回结果：{tool_result}\n"
                                f"请基于以上结果回答原始问题。"
                            )
                        except Exception as e:
                            logger.warning(f"QAEngine ask_with_tools: tool {tool_name} failed: {e}")
                            tool_calls_log.append({
                                "tool": tool_name,
                                "args": tool_args,
                                "error": str(e),
                                "iteration": iteration,
                            })
                            current_query = (
                                f"{query}\n\n"
                                f"工具 {tool_name} 执行失败：{e}\n"
                                f"请尝试直接回答原始问题。"
                            )
                    else:
                        logger.warning(f"QAEngine ask_with_tools: unknown tool {tool_name}")
                        current_query = f"{query}\n\n工具 {tool_name} 不存在，请直接回答原始问题。"
                except Exception as e:
                    logger.warning(f"QAEngine ask_with_tools: failed to parse tool call: {e}")
                    current_query = f"{query}\n\n工具调用解析失败，请直接回答原始问题。"
            else:
                # LLM 给出了最终答案，退出循环
                break

        # 最终调用 ask 生成完整结果
        result = self.ask(current_query, user_id, session_id)
        result["tools_available"] = True
        result["tool_calls"] = tool_calls_log
        return result

    def _call_llm_for_tool_decision(self, prompt: str) -> Optional[str]:
        """调用 LLM 判断是否需要使用工具

        Returns:
            LLM 响应文本，如果 LLM 不可用则返回 None
        """
        if not self.llm_client:
            return None

        try:
            import os
            import requests as _requests
            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "deepseek-ai/deepseek-v4-pro")

            if api_key:
                resp = _requests.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "你是一个智能助手，可以使用工具来帮助回答问题。"},
                            {"role": "user", "content": prompt},
                        ],
                        "max_tokens": 512,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"QAEngine _call_llm_for_tool_decision failed: {e}")

        return None

    async def ask_with_oadp(self, query: str, user_id: str = "user",
                      session_id: str = None, context: Dict = None,
                      workspace_id: Optional[str] = None,
                      scenario_id: Optional[str] = None,
                      auto_decide: bool = False) -> Dict[str, Any]:
        """OADP 闭环问答：QA→Decision→Action→Feedback"""
        qa_result = self.ask(query, user_id, session_id, context, workspace_id, scenario_id)

        if auto_decide and qa_result.get('decision_available'):
            try:
                from odap.biz.decision.decision_pipeline.pipeline import get_decision_pipeline
                from odap.biz.decision.decision_pipeline.schemas import AnalysisInput
                pipeline = get_decision_pipeline()
                pipeline_input = AnalysisInput(
                    query=query,
                    context=context or {},
                    workspace_id=workspace_id,
                    scenario_id=scenario_id,
                    agent_id=user_id,
                )
                pipeline_result = await pipeline.execute(pipeline_input)
                qa_result['oadp_pipeline'] = {
                    'pipeline_id': pipeline_result.pipeline_id,
                    'stages': {k: v.value for k, v in pipeline_result.stages.items()},
                    'decision': pipeline_result.decision.model_dump() if pipeline_result.decision else None,
                    'action_record': pipeline_result.action_record,
                    'feedback': pipeline_result.feedback,
                }
            except Exception as e:
                qa_result['oadp_pipeline'] = {'error': str(e)}

        return qa_result

    def _extract_charts(self, query: str, answer: str, rag_results: List) -> List[Dict[str, Any]]:
        chart_keywords = {
            "趋势": "line", "变化": "line", "走势": "line", "对比": "bar", "比较": "bar",
            "排名": "bar", "分布": "pie", "占比": "pie", "比例": "pie", "构成": "pie",
            "关联": "scatter", "相关性": "scatter", "热力": "heatmap", "密度": "heatmap",
            "评估": "radar", "能力": "radar", "综合": "radar",
        }
        detected_type = None
        for kw, ctype in chart_keywords.items():
            if kw in query:
                detected_type = ctype
                break
        if not detected_type or not rag_results:
            return []

        if detected_type in ("line", "bar"):
            categories = []
            values = []
            for r in rag_results[:8]:
                name = r.content.split('|')[0].strip()[:10] if r.content else f"Item{len(categories)+1}"
                categories.append(name)
                values.append(round(r.score * 100, 1))
            matched_kw = next((k for k in chart_keywords if k in query), "分析")
            return [{"chart_type": detected_type, "title": f"数据{matched_kw}", "data": {"categories": categories, "values": values}}]
        elif detected_type == "pie":
            type_counts = {}
            for r in rag_results:
                etype = r.metadata.get("entity_type", r.metadata.get("type", "其他"))
                type_counts[etype] = type_counts.get(etype, 0) + 1
            categories = list(type_counts.keys())[:6]
            values = [type_counts[c] for c in categories]
            return [{"chart_type": "pie", "title": "数据分布", "data": {"categories": categories, "values": values}}]
        elif detected_type == "scatter":
            points = []
            for r in rag_results:
                x = round(r.score * 100, 1)
                y = len(r.content) if r.content else 0
                points.append([x, y])
            return [{"chart_type": "scatter", "title": "数据关联分析", "data": {"points": points}}]
        elif detected_type == "heatmap":
            type_time_map = {}
            for r in rag_results:
                etype = r.metadata.get("entity_type", r.metadata.get("type", "其他"))
                time_period = r.metadata.get("time_period", r.metadata.get("period", "未知"))
                key = (etype, time_period)
                type_time_map[key] = type_time_map.get(key, 0) + 1
            y_labels = sorted(set(k[0] for k in type_time_map.keys()))[:5]
            x_labels = sorted(set(k[1] for k in type_time_map.keys()))[:7]
            heatmap_data = []
            for i, yl in enumerate(y_labels):
                for j, xl in enumerate(x_labels):
                    val = type_time_map.get((yl, xl), 0)
                    if val > 0:
                        heatmap_data.append([j, i, val])
            if not heatmap_data:
                for i, yl in enumerate(y_labels):
                    for j, xl in enumerate(x_labels):
                        heatmap_data.append([j, i, 0])
            return [{"chart_type": "heatmap", "title": "数据热力图", "data": {"xLabels": x_labels, "yLabels": y_labels, "heatmapData": heatmap_data}}]
        elif detected_type == "radar":
            type_scores = {}
            type_counts = {}
            for r in rag_results:
                etype = r.metadata.get("entity_type", r.metadata.get("type", "其他"))
                type_scores[etype] = type_scores.get(etype, 0.0) + r.score
                type_counts[etype] = type_counts.get(etype, 0) + 1
            categories = list(type_scores.keys())[:6]
            values = [round(type_scores[c] / type_counts[c] * 100, 1) for c in categories]
            return [{"chart_type": "radar", "title": "综合评估", "data": {"categories": categories, "values": values}}]
        return []

    def _extract_temporal(self, query: str, temporal_params: Dict, entities: List) -> List[Dict[str, Any]]:
        if not temporal_params.get("has_temporal"):
            temporal_keywords = ["什么时候", "何时", "时间", "历史", "过去", "之前", "期间"]
            if not any(kw in query for kw in temporal_keywords):
                return []

        valid_time = temporal_params.get("valid_time") or "自动解析"
        time_type = temporal_params.get("time_type") or "relative"

        entity_names = []
        for e in entities[:5]:
            props = e.get("properties", {})
            name = props.get("name", "")
            if name:
                entity_names.append(name)

        return [{
            "time_type": time_type,
            "valid_time": str(valid_time),
            "answer": f"在 {valid_time} 时刻，共发现 {len(entities)} 个相关实体" + (f"，包括: {', '.join(entity_names[:3])}" if entity_names else ""),
            "entity_count": len(entities),
        }]

    def _extract_reports(self, query: str, answer: str, rag_results: List) -> List[Dict[str, Any]]:
        report_keywords = ["报告", "分析报告", "总结", "摘要", "评估报告", "态势", "简报"]
        if not any(kw in query for kw in report_keywords):
            return []
        import uuid
        summary_parts = []
        if rag_results:
            source_names = []
            for r in rag_results[:5]:
                name = r.metadata.get("entity_type", r.metadata.get("type", ""))
                if name and name not in source_names:
                    source_names.append(name)
            if source_names:
                summary_parts.append(f"涉及类型: {', '.join(source_names)}")
            avg_score = sum(r.score for r in rag_results) / len(rag_results)
            summary_parts.append(f"共检索 {len(rag_results)} 条相关数据，平均相关度 {round(avg_score * 100, 1)}%")
        summary_body = answer[:200] if len(answer) > 200 else answer
        if summary_parts:
            summary_body = "；".join(summary_parts) + "。" + summary_body
        return [{
            "report_id": str(uuid.uuid4())[:8],
            "title": f"分析报告 — {query[:20]}",
            "summary": summary_body,
            "created_at": datetime.now().isoformat(),
        }]

    def _build_reasoning_chain(self, cot_builder) -> List[Dict[str, Any]]:
        """将 CoTBuilder 的推理树转换为扁平的 reasoning_chain 列表

        每个条目包含:
        - step: 节点类型 (如 "intent", "rag_augment", "llm_infer")
        - description: 人类可读的步骤描述
        - timestamp: 步骤发生时间
        - duration_ms: 步骤耗时
        - metadata: 可选附加数据
        """
        if not cot_builder:
            return []
        try:
            tree = cot_builder.get_tree()
            chain = []
            for node_id, node in tree.nodes.items():
                entry = {
                    "step": node.type.value,
                    "description": node.label,
                    "timestamp": node.timing.started_at.isoformat() if node.timing and node.timing.started_at else None,
                    "duration_ms": node.timing.duration_ms if node.timing else None,
                    "metadata": dict(node.metadata) if node.metadata else {},
                }
                if node.detail:
                    entry["metadata"]["detail"] = node.detail
                chain.append(entry)
            return chain
        except Exception as e:
            logger.warning(f"QAEngine: failed to build reasoning chain: {e}")
            return []

    def _is_decision_intent(self, query: str) -> bool:
        decision_keywords = [
            "应该", "建议", "如何处理", "怎么办", "决策", "行动",
            "攻击", "防御", "撤退", "增援", "移动", "部署",
            "推荐", "最优", "最佳方案", "执行",
        ]
        return any(kw in query for kw in decision_keywords)

    def _get_ontology_ids_for_scenario(self, scenario_id: str) -> Optional[List[str]]:
        if not scenario_id or scenario_id == "default":
            return None
        try:
            from odap.biz.platform.workspace.storage.sqlite_storage import SQLiteStorage
            ws_storage = SQLiteStorage()

            conn = sqlite3.connect(ws_storage.db_path)
            try:
                rows = conn.execute(
                    "SELECT ontology_id FROM scenario_ontology_bindings "
                    "WHERE scenario_id = ? AND binding_status = 'active'",
                    (scenario_id,)
                ).fetchall()
                if rows:
                    return [r[0] for r in rows if r[0]]
            finally:
                conn.close()

            scenario = ws_storage.get_scenario(scenario_id)
            if scenario and scenario.get("ontology_id"):
                return [scenario["ontology_id"]]

            ontology_ids_json = scenario.get("ontology_ids") if scenario else None
            if ontology_ids_json:
                if isinstance(ontology_ids_json, str):
                    import json as _json
                    try:
                        return _json.loads(ontology_ids_json)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(ontology_ids_json, list):
                    return ontology_ids_json
        except Exception as e:
            logger.warning(f"QAEngine: failed to get ontology IDs for scenario {scenario_id}: {e}")
        return None

    def _needs_clarification(self, query: str, rag_results: List["RAGResult"],
                             score_threshold: float = 0.15) -> Tuple[bool, str, List[str]]:
        """
        判断是否需要追问/澄清

        Args:
            query: 用户问题
            rag_results: RAG 检索结果
            score_threshold: RAG 分数低于此阈值视为结果不足

        Returns:
            (needs_clarification, reason, suggested_questions)
        """
        suggested_questions: List[str] = []

        # 条件 1：零结果
        if not rag_results:
            reason = "no_results"
            suggested_questions = [
                "您能否提供更具体的实体名称或关键词？",
                "您想了解哪个领域或类型的信息？",
                "请描述您关注的场景或时间范围。",
            ]
            return True, reason, suggested_questions

        # 条件 2：所有结果分数均低于阈值
        max_score = max(r.score for r in rag_results)
        if max_score < score_threshold:
            reason = "low_score"
            # 从低分结果中提取实体名/类型作为追问线索
            entity_hints = []
            type_hints = []
            for r in rag_results[:5]:
                content_first = r.content.split("|")[0].strip()[:20] if r.content else ""
                if content_first:
                    entity_hints.append(content_first)
                etype = r.metadata.get("entity_type", r.metadata.get("type", ""))
                if etype and etype not in type_hints:
                    type_hints.append(etype)

            if entity_hints:
                hints_str = "、".join(entity_hints[:3])
                suggested_questions.append(f"您是想查询与「{hints_str}」相关的信息吗？")
            if type_hints:
                types_str = "、".join(type_hints[:3])
                suggested_questions.append(f"请确认您关注的数据类型，例如：{types_str}？")
            if not suggested_questions:
                suggested_questions.append("请提供更详细的问题描述，以便我精确检索。")
            suggested_questions.append("您可以换个说法或补充更多上下文吗？")
            return True, reason, suggested_questions

        # 条件 3：问题含模糊代词且无明确指代
        vague_pronouns = ["它", "那个", "这个", "他们", "她们", "它们", "那", "这"]
        has_vague_pronoun = any(p in query for p in vague_pronouns)
        if has_vague_pronoun:
            # 检查对话上下文中是否有明确指代对象
            # 如果问题很短且含代词，大概率是追问但缺乏上下文
            stripped = query.strip()
            if len(stripped) < 8:
                reason = "ambiguous_pronoun"
                # 从 RAG 结果中提取可能的指代对象
                referent_hints = []
                for r in rag_results[:3]:
                    name = r.content.split("|")[0].strip()[:15] if r.content else ""
                    if name:
                        referent_hints.append(name)
                if referent_hints:
                    hints_str = "、".join(referent_hints)
                    suggested_questions.append(f"您提到的代词是指「{hints_str}」中的哪一个？")
                else:
                    suggested_questions.append("您提到的「它/那个/这个」具体指什么？")
                suggested_questions.append("请用完整的名称或描述替换代词。")
                return True, reason, suggested_questions

        # 条件 4：问题过短（少于 4 个有效字符）
        # 过滤掉标点和空格后计算有效字符数
        effective_chars = re.sub(r'[\s\W]+', '', query)
        if len(effective_chars) < 4:
            reason = "too_short"
            type_hints = []
            for r in rag_results[:5]:
                etype = r.metadata.get("entity_type", r.metadata.get("type", ""))
                if etype and etype not in type_hints:
                    type_hints.append(etype)
            if type_hints:
                types_str = "、".join(type_hints[:3])
                suggested_questions.append(f"您想了解哪方面的信息？例如：{types_str}？")
            else:
                suggested_questions.append("请提供更详细的问题描述。")
            suggested_questions.append("您可以描述具体的实体名称或关系类型吗？")
            suggested_questions.append("请补充您关注的时间范围或场景。")
            return True, reason, suggested_questions

        return False, "", []

    def _extract_suggested_actions(self, query: str, rag_results: List) -> List[Dict[str, Any]]:
        if not self._is_decision_intent(query):
            return []
        try:
            from odap.biz.data.qa.semantic_retriever.retriever import get_semantic_retriever
            retriever = get_semantic_retriever()
            import asyncio
            import concurrent.futures
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, retriever.retrieve(query, top_k=5))
                        result = future.result(timeout=10)
                        return result.suggested_actions[:5]
            except RuntimeError:
                pass
            result = asyncio.run(retriever.retrieve(query, top_k=5))
            return result.suggested_actions[:5]
        except Exception:
            return []

    def _execute_multihop_retrieval(
        self,
        query: str,
        workspace_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        ontology_ids: Optional[List[str]] = None,
        top_k: int = 10,
        original_query: Optional[str] = None,
    ) -> Tuple[List["RAGResult"], Dict[str, Any]]:
        """
        执行多跳检索：复杂问题分解为多步检索链

        如果查询复杂度足够高，使用 MultiHopPlanner 分解并执行多跳检索；
        如果查询简单，回退到标准单跳 RAG。

        Args:
            query: 完整查询（含对话上下文），用于 RAG 检索
            workspace_id: 工作空间 ID
            scenario_id: 场景 ID
            ontology_ids: 本体 ID 列表
            top_k: 返回的最大结果数
            original_query: 用户原始问题（不含上下文），用于复杂度检测

        Returns:
            (rag_results, multihop_metadata) 元组
            - rag_results: RAGResult 列表
            - multihop_metadata: 多跳检索元数据（hop 数、复杂度等）
        """
        from odap.biz.data.qa.impl.multihop_planner import QueryComplexity

        # 使用原始问题（不含对话上下文）检测复杂度
        complexity_query = original_query if original_query else query
        complexity = self._multihop_planner.detect_complexity(complexity_query)

        # 加载本体 schema（用于本体感知的多跳规划）
        schemas = []
        if ontology_ids:
            schemas = self.rag_pipeline.ontology_gate.load_schema(ontology_ids, workspace_id or "default")

        multihop_metadata: Dict[str, Any] = {
            "multihop_used": False,
            "complexity": complexity.value,
            "hop_count": 1,
            "hop_details": [],
        }

        # 简单查询直接单跳
        if complexity == QueryComplexity.SIMPLE:
            rag_results = self.rag_pipeline.retrieve(
                query, top_k=top_k,
                workspace_id=workspace_id,
                ontology_ids=ontology_ids,
                scenario_id=scenario_id,
            )
            multihop_metadata["hop_details"] = [
                {"hop_index": 0, "query": query, "result_count": len(rag_results)}
            ]
            return rag_results, multihop_metadata

        # 复杂查询使用多跳执行器
        try:
            exec_result = self._multihop_executor.execute(
                query=query,
                workspace_id=workspace_id,
                scenario_id=scenario_id,
                ontology_ids=ontology_ids,
                top_k=top_k,
                schemas=schemas,
            )

            # 将 dict 结果转回 RAGResult
            rag_results = []
            for r in exec_result.get("results", []):
                rag_results.append(RAGResult(
                    content=r.get("content", ""),
                    source=r.get("source", "unknown"),
                    score=r.get("score", 0.0),
                    metadata=r.get("metadata", {}),
                ))

            multihop_metadata["multihop_used"] = True
            multihop_metadata["hop_count"] = exec_result.get("hop_count", 1)
            multihop_metadata["hop_details"] = exec_result.get("hop_details", [])
            multihop_metadata["plan"] = exec_result.get("plan", {})

            logger.info(
                "QAEngine multihop: query='%s' complexity=%s hops=%d results=%d",
                query[:40],
                complexity.value,
                multihop_metadata["hop_count"],
                len(rag_results),
            )

            return rag_results, multihop_metadata

        except Exception as e:
            logger.warning(
                "QAEngine multihop retrieval failed, falling back to single-hop: %s", e
            )
            rag_results = self.rag_pipeline.retrieve(
                query, top_k=top_k,
                workspace_id=workspace_id,
                ontology_ids=ontology_ids,
                scenario_id=scenario_id,
            )
            multihop_metadata["multihop_used"] = False
            multihop_metadata["fallback_reason"] = str(e)
            multihop_metadata["hop_details"] = [
                {"hop_index": 0, "query": query, "result_count": len(rag_results)}
            ]
            return rag_results, multihop_metadata

    def _generate_answer(self, query: str, context: str, rag_results: List["RAGResult"],
                         agent_context: Dict = None) -> str:
        llm_answer = self._generate_with_llm(query, context, rag_results, agent_context)
        if llm_answer:
            return llm_answer

        if rag_results:
            return self._answer_general(query, context, rag_results)

        if context:
            return f"根据已有信息：{context[:500]}"

        query_lower = query.lower()
        if "雷达" in query_lower:
            return self._answer_radar(query, context, rag_results)
        elif "力量" in query_lower and "对比" in query_lower:
            return self._answer_force_comparison(query, context, rag_results)
        elif any(kw in query_lower for kw in ["态势", "分析"]):
            return self._answer_situation(query, context, rag_results)
        else:
            return self._answer_general(query, context, rag_results)

    def _generate_with_llm(self, query: str, context: str, rag_results: List["RAGResult"],
                           agent_context: Dict = None) -> Optional[str]:
        if not self.llm_client:
            return None
        try:
            source_count = len(rag_results)

            if agent_context and agent_context.get("agent_name"):
                agent_name = agent_context.get("agent_name", "")
                main_object = agent_context.get("main_object", "")
                description = agent_context.get("description", "")
                related_objects = agent_context.get("related_objects", [])
                related_skills = agent_context.get("related_skills", [])
                related_knowledge_bases = agent_context.get("related_knowledge_bases", [])

                role_desc = f"你是智能体「{agent_name}」"
                if main_object:
                    role_desc += f"，专注于{main_object}领域"
                if description:
                    role_desc += f"。{description}"

                knowledge_parts = []
                if related_objects:
                    knowledge_parts.append(f"关联对象: {', '.join(related_objects)}")
                if related_skills:
                    knowledge_parts.append(f"可用技能: {', '.join(related_skills)}")
                if related_knowledge_bases:
                    knowledge_parts.append(f"知识库: {', '.join(related_knowledge_bases)}")

                system_prompt = (
                    f"{role_desc}。"
                    "请基于以下检索到的上下文信息，以该智能体的专业视角回答用户的问题。"
                    "如果上下文信息不足以回答问题，请明确说明。"
                    "回答时引用具体的数据来源，不要编造信息。"
                )
                if knowledge_parts:
                    system_prompt += "\n" + "\n".join(knowledge_parts)
            else:
                system_prompt = (
                    "你是一个专业的本体驱动分析决策平台(ODAP)的AI助手。"
                    "请基于以下检索到的上下文信息，准确、专业地回答用户的问题。"
                    "如果上下文信息不足以回答问题，请明确说明。"
                    "回答时引用具体的数据来源，不要编造信息。"
                )

            user_prompt = (
                f"用户问题：{query}\n\n"
                f"检索到的上下文信息（共{source_count}条）：\n{context}\n\n"
                f"请基于以上信息回答用户的问题。"
            )

            try:
                import os
                import requests as _requests
                api_key = os.getenv("OPENAI_API_KEY", "")
                base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
                model = os.getenv("OPENAI_MODEL", "deepseek-ai/deepseek-v4-pro")
                if api_key:
                    max_retries = 1  # P1-fix: 减少重试次数，快速降级
                    last_err = None
                    for attempt in range(max_retries):
                        try:
                            resp = _requests.post(
                                f"{base_url}/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {api_key}",
                                    "Content-Type": "application/json",
                                },
                                json={
                                    "model": model,
                                    "messages": [
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": user_prompt},
                                    ],
                                    "max_tokens": 1024,
                                },
                                timeout=15,  # P1-fix: 15s 超时，避免长时间阻塞
                            )
                            resp.raise_for_status()
                            data = resp.json()
                            return data["choices"][0]["message"]["content"]
                        except _requests.exceptions.Timeout as te:
                            last_err = te
                            logger.warning(f"QAEngine LLM call timeout (attempt {attempt+1}/{max_retries}): {te}")
                            if attempt < max_retries - 1:
                                time.sleep(2 ** attempt)
                        except _requests.exceptions.ConnectionError as ce:
                            last_err = ce
                            logger.warning(f"QAEngine LLM call connection error (attempt {attempt+1}/{max_retries}): {ce}")
                            if attempt < max_retries - 1:
                                time.sleep(2 ** attempt)
                        except _requests.exceptions.HTTPError as he:
                            status_code = he.response.status_code if he.response else 0
                            if status_code in (429, 502, 503):
                                last_err = he
                                logger.warning(f"QAEngine LLM call HTTP {status_code} (attempt {attempt+1}/{max_retries}): {he}")
                                if attempt < max_retries - 1:
                                    time.sleep(2 ** attempt)
                            else:
                                raise
                    logger.warning(f"QAEngine LLM call failed after {max_retries} retries: {last_err}")
            except Exception as llm_err:
                logger.warning(f"QAEngine sync LLM call failed: {llm_err}")

            if self.llm_client and not api_key:
                import asyncio
                async def _call_llm():
                    from graphiti_core.prompts.models import Message
                    messages = [
                        Message(role="system", content=system_prompt),
                        Message(role="user", content=user_prompt),
                    ]
                    result, _, _ = await self.llm_client._generate_response(messages, max_tokens=1024)
                    return result

                try:
                    loop = asyncio.get_running_loop()
                    if loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(asyncio.run, _call_llm())
                            result = future.result(timeout=15)
                    else:
                        result = asyncio.run(_call_llm())
                except RuntimeError:
                    result = asyncio.run(_call_llm())
                except concurrent.futures.TimeoutError:
                    logger.warning("QAEngine graphiti LLM call timed out (15s)")
                    return None

                if isinstance(result, dict):
                    return result.get('response', str(result))
                return str(result) if result else None

            return None

        except Exception as e:
            logger.warning(f"QAEngine LLM generation failed, falling back to template: {e}")
            return None

    async def _generate_with_llm_stream(self, query: str, context: str,
                                         rag_results: List["RAGResult"],
                                         agent_context: Dict = None):
        """流式LLM生成，逐token yield输出"""
        import os
        api_key = os.getenv("OPENAI_API_KEY", "")
        base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
        model = os.getenv("OPENAI_MODEL", "deepseek-ai/deepseek-v4-pro")

        if not api_key:
            # 无API key，回退到同步模板回答并一次性yield
            answer = self._generate_answer(query, context, rag_results, agent_context=agent_context)
            if answer:
                yield answer
            return

        source_count = len(rag_results)

        if agent_context and agent_context.get("agent_name"):
            agent_name = agent_context.get("agent_name", "")
            main_object = agent_context.get("main_object", "")
            description = agent_context.get("description", "")
            related_objects = agent_context.get("related_objects", [])
            related_skills = agent_context.get("related_skills", [])
            related_knowledge_bases = agent_context.get("related_knowledge_bases", [])

            role_desc = f"你是智能体「{agent_name}」"
            if main_object:
                role_desc += f"，专注于{main_object}领域"
            if description:
                role_desc += f"。{description}"

            knowledge_parts = []
            if related_objects:
                knowledge_parts.append(f"关联对象: {', '.join(related_objects)}")
            if related_skills:
                knowledge_parts.append(f"可用技能: {', '.join(related_skills)}")
            if related_knowledge_bases:
                knowledge_parts.append(f"知识库: {', '.join(related_knowledge_bases)}")

            system_prompt = (
                f"{role_desc}。"
                "请基于以下检索到的上下文信息，以该智能体的专业视角回答用户的问题。"
                "如果上下文信息不足以回答问题，请明确说明。"
                "回答时引用具体的数据来源，不要编造信息。"
            )
            if knowledge_parts:
                system_prompt += "\n" + "\n".join(knowledge_parts)
        else:
            system_prompt = (
                "你是一个专业的本体驱动分析决策平台(ODAP)的AI助手。"
                "请基于以下检索到的上下文信息，准确、专业地回答用户的问题。"
                "如果上下文信息不足以回答问题，请明确说明。"
                "回答时引用具体的数据来源，不要编造信息。"
            )

        user_prompt = (
            f"用户问题：{query}\n\n"
            f"检索到的上下文信息（共{source_count}条）：\n{context}\n\n"
            f"请基于以上信息回答用户的问题。"
        )

        try:
            import httpx
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 1024,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk_data = json.loads(data_str)
                                choices = chunk_data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue
        except httpx.TimeoutException as e:
            logger.warning(f"QAEngine stream LLM call timeout: {e}")
            answer = self._generate_answer(query, context, rag_results, agent_context=agent_context)
            if answer:
                yield answer
        except httpx.HTTPStatusError as e:
            logger.warning(f"QAEngine stream LLM HTTP error {e.response.status_code}: {e}")
            answer = self._generate_answer(query, context, rag_results, agent_context=agent_context)
            if answer:
                yield answer
        except Exception as e:
            logger.warning(f"QAEngine stream LLM failed, falling back to template: {e}")
            answer = self._generate_answer(query, context, rag_results, agent_context=agent_context)
            if answer:
                yield answer

    def _answer_radar(self, query: str, context: str, rag_results: List["RAGResult"]) -> str:
        if not rag_results:
            return f"针对 '{query}' 未找到相关目标信息。"
        return f"找到 {len(rag_results)} 个相关目标:\n" + "\n".join([f"- {r.content}" for r in rag_results[:10]])

    def _answer_force_comparison(self, query: str, context: str, rag_results: List["RAGResult"]) -> str:
        if not rag_results:
            return f"针对 '{query}' 未找到力量对比数据，请确保图谱中包含相关实体。"
        red_entities = []
        blue_entities = []
        for r in rag_results:
            content = r.content.lower()
            if '红方' in content or 'red' in content:
                red_entities.append(r.content)
            elif '蓝方' in content or 'blue' in content:
                blue_entities.append(r.content)
        parts = ["力量对比分析（基于图谱数据）:"]
        if red_entities:
            parts.append(f"红方: {len(red_entities)} 个实体\n" + "\n".join(f"  - {e[:100]}" for e in red_entities[:5]))
        if blue_entities:
            parts.append(f"蓝方: {len(blue_entities)} 个实体\n" + "\n".join(f"  - {e[:100]}" for e in blue_entities[:5]))
        if not red_entities and not blue_entities:
            parts.append(f"共检索到 {len(rag_results)} 条相关信息:\n" + "\n".join(f"  - {r.content[:100]}" for r in rag_results[:5]))
        return "\n".join(parts)

    def _answer_situation(self, query: str, context: str, rag_results: List["RAGResult"]) -> str:
        if not rag_results:
            return f"针对 '{query}' 未找到态势数据，请确保图谱中包含相关实体。"
        parts = [f"当前态势概览（基于 {len(rag_results)} 条检索结果）:"]
        type_counts: Dict[str, int] = {}
        for r in rag_results:
            for keyword in ('Unit', 'Location', 'Equipment', 'Event', '单位', '位置', '装备', '事件'):
                if keyword.lower() in r.content.lower():
                    type_counts[keyword] = type_counts.get(keyword, 0) + 1
                    break
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
            parts.append(f"- {t}: {c} 个")
        parts.append("\n详细信息:")
        for r in rag_results[:8]:
            parts.append(f"  - {r.content[:120]}")
        return "\n".join(parts)

    def _format_rag_results(self, query: str, rag_results: List["RAGResult"]) -> str:
        """高置信度时直接格式化检索结果，跳过 LLM 调用"""
        if not rag_results:
            return f"针对您的问题「{query}」，未找到相关信息。"

        parts = [f"针对您的问题「{query}」，检索到 {len(rag_results)} 条相关信息：\n"]

        for idx, r in enumerate(rag_results, 1):
            # source 现在是 "类型:名称" 格式，直接使用
            source_label = r.source

            # 格式化内容
            content = r.content.strip()
            # 如果内容是 key:value 格式，美化展示
            if "|" in content:
                fields = content.split("|")
                name_field = fields[0].strip()
                detail_fields = [f.strip() for f in fields[1:] if f.strip()]
                parts.append(f"**{idx}. {name_field}**")
                for field in detail_fields:
                    if ":" in field:
                        k, v = field.split(":", 1)
                        parts.append(f"   - {k.strip()}: {v.strip()}")
                    else:
                        parts.append(f"   - {field}")
            else:
                parts.append(f"**{idx}.** {content}")

            parts.append(f"   _来源: {source_label} | 置信度: {r.score:.0%}_")
            parts.append("")

        return "\n".join(parts)

    def _answer_general(self, query: str, context: str, rag_results: List["RAGResult"]) -> str:
        if "未找到相关信息" in context or not rag_results:
            return f"针对您的问题 '{query}'，未找到相关信息。"
        return f"针对您的问题 '{query}'，我找到了 {len(rag_results)} 条相关信息。\n\n{context}"

    def get_dialog_history(self, session_id: str) -> List[Dict]:
        """获取对话历史"""
        session = self.dialog_manager.get_session(session_id)
        if not session:
            return []

        return [{
            "message_id": m.message_id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp
        } for m in session.messages]

    def close_dialog(self, session_id: str):
        """关闭对话"""
        self.dialog_manager.close_session(session_id)


class IntelligenceAgentBridge:
    """智能体桥接器 - 复杂问题升级"""

    def __init__(self, qa_engine: QAEngineV2, swarm_orchestrator=None):
        self.qa_engine = qa_engine
        self.swarm = swarm_orchestrator

    def should_escalate(self, query: str) -> bool:
        """判断是否需要升级"""
        for pattern in self.qa_engine._complex_patterns:
            if re.search(pattern, query):
                return True

        for keyword in self.qa_engine._escalation_keywords:
            if keyword in query:
                return True

        return False

    def escalate(self, query: str, context: Dict) -> Dict[str, Any]:
        """升级到 Intelligence Agent"""
        if self.swarm:
            return self.swarm.run_task(query, context.get("user_id", "system"))

        return {
            "success": False,
            "error": "Swarm orchestrator not available",
            "escalated": True
        }


if __name__ == "__main__":
    logger.info('问答引擎测试')

    logger.info('\n=== 测试问答引擎 ===')
    qa = QAEngineV2(use_mock=True)

    logger.info('\n1. 测试雷达查询:')
    result = qa.ask("B区有哪些雷达?")
    logger.info(f"  会话 ID: {result['session_id']}")
    logger.info(f"  回答: {result['answer'][:100]}...")
    logger.info(f"  来源数: {len(result['sources'])}")

    logger.info('\n2. 测试多轮对话:')
    result2 = qa.ask("还有其他的吗?", session_id=result["session_id"])
    logger.info(f"  回答: {result2['answer'][:100]}...")

    logger.info('\n3. 测试力量对比:')
    result3 = qa.ask("A区和B区的力量对比如何?")
    logger.info(f"  回答: {result3['answer']}")

    logger.info('\n4. 测试溯源:')
    for source in result3["sources"]:
        logger.info(f"  - 来源: {source['source']}")
        logger.info(f"    内容: {source['excerpt'][:50]}...")

    logger.info('\n5. 测试对话历史:')
    history = qa.get_dialog_history(result["session_id"])
    logger.info(f'  历史消息数: {len(history)}')
