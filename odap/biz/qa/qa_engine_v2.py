"""
问答引擎 - 多轮对话 + RAG + 溯源追踪

功能：
- QAEngine 核心
- 多轮对话管理
- RAG 增强生成
- 双时态查询
- 溯源追踪
"""

import sys
import os
import json
import time
import re
import threading
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from collections import deque

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DialogState(Enum):
    """对话状态"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    COMPLETED = "completed"
    ESCALATED = "escalated"


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
                      scenario_id: Optional[str] = None) -> DialogSession:
        """创建新会话"""
        import uuid
        now = datetime.now(timezone.utc).isoformat()
        session = DialogSession(
            session_id=f"SESSION-{uuid.uuid4().hex[:8].upper()}",
            user_id=user_id,
            workspace_id=workspace_id,
            scenario_id=scenario_id,
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

    def __init__(self, graphiti_client=None):
        self.graphiti = graphiti_client

    def retrieve(self, query: str, top_k: int = 5) -> List[RAGResult]:
        """
        检索相关信息

        Args:
            query: 查询文本
            top_k: 返回数量

        Returns:
            检索结果列表
        """
        if not self.graphiti:
            raise RuntimeError("Graphiti 连接不可用，无法执行查询")

        try:
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
                
                results.append(RAGResult(
                    content=content,
                    source=r.get("id", "unknown"),
                    score=r.get("score", 0.8),
                    metadata=r
                ))
            return results
        except RuntimeError as e:
            print(f"RAG 检索失败: {e}")
            raise e
        except Exception as e:
            print(f"RAG 检索失败: {e}")
            raise RuntimeError(f"RAG 检索失败: {e}")

    def _mock_retrieve(self, query: str, top_k: int) -> List[RAGResult]:
        """Mock 检索"""
        return [
            RAGResult(
                content=f"这是关于 '{query}' 的相关信息。",
                source="mock_source_1",
                score=0.9,
                metadata={}
            ),
            RAGResult(
                content=f"另外一条关于 '{query}' 的参考内容。",
                source="mock_source_2",
                score=0.7,
                metadata={}
            )
        ][:top_k]

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

    def __init__(self, graphiti_client=None):
        self.graphiti = graphiti_client

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
    问答引擎 v2

    功能：
    - 多轮对话管理
    - RAG 增强生成
    - 双时态查询
    - 溯源追踪
    - 复杂问题升级
    """

    def __init__(self, graphiti_client=None, use_mock: bool = False):
        self.dialog_manager = DialogManager()
        self.rag_pipeline = RAGPipeline(graphiti_client)
        self.temporal_parser = TemporalQueryParser()
        self.source_tracer = SourceTracer(graphiti_client)
        self.graphiti = graphiti_client
        self.use_mock = use_mock
        self._llm_client = None

        self._escalation_keywords = ["为什么", "原因", "解释", "详细"]
        self._complex_patterns = [r"如果.*?会.*?", r".*?和.*?对比", r".*?的最佳.*?"]

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
           scenario_id: Optional[str] = None) -> Dict[str, Any]:
        """
        问答

        Args:
            query: 用户问题
            user_id: 用户 ID
            session_id: 会话 ID（可选）
            context: 额外上下文
            workspace_id: 工作空间 ID（可选）
            scenario_id: 场景 ID（可选）

        Returns:
            回答结果
        """
        if not session_id:
            session = self.dialog_manager.create_session(user_id, workspace_id, scenario_id)
            session_id = session.session_id
        else:
            session = self.dialog_manager.get_session(session_id)
            if not session:
                session = self.dialog_manager.create_session(user_id, workspace_id, scenario_id)
                session_id = session.session_id
            else:
                if workspace_id and not session.workspace_id:
                    session.workspace_id = workspace_id
                if scenario_id and not session.scenario_id:
                    session.scenario_id = scenario_id

        self.dialog_manager.add_message(session_id, "user", query)

        try:
            dialog_context = self.dialog_manager.get_context(session_id)
            full_query = f"{dialog_context}\n用户: {query}" if dialog_context else query

            temporal_params = self.temporal_parser.parse(query)

            if temporal_params["has_temporal"] and self.graphiti:
                entities = self.graphiti.query_temporal(
                    valid_time=temporal_params.get("valid_time"),
                    transaction_time=temporal_params.get("transaction_time")
                )
            else:
                entities = self.graphiti.query_entities() if self.graphiti else []

            rag_results = self.rag_pipeline.retrieve(full_query, top_k=5)
            context_text = self.rag_pipeline.generate_context(rag_results)

            answer = self._generate_answer(query, context_text, rag_results)

            if "未找到相关信息" in answer:
                traces = []
            else:
                traces = self.source_tracer.trace(answer, query, rag_results)

            self.dialog_manager.add_message(session_id, "assistant", answer, {
                "traces": [{"source": t.source, "excerpt": t.excerpt} for t in traces],
                "rag_results": len(rag_results)
            })

            return {
                "session_id": session_id,
                "answer": answer,
                "sources": [{"source": t.source, "excerpt": t.excerpt, "confidence": t.confidence} for t in traces],
                "dialog_state": session.state.value if session else "unknown",
                "suggested_actions": self._extract_suggested_actions(query, rag_results),
                "decision_available": self._is_decision_intent(query),
            }
        except RuntimeError as e:
            error_msg = str(e)
            self.dialog_manager.add_message(session_id, "assistant", error_msg, {
                "traces": [],
                "rag_results": 0
            })
            return {
                "session_id": session_id,
                "answer": error_msg,
                "sources": [],
                "dialog_state": "error",
                "error": error_msg
            }

    def ask_with_tools(self, query: str, user_id: str = "user",
                      session_id: str = None) -> Dict[str, Any]:
        """带工具调用的问答"""
        return self.ask(query, user_id, session_id)

    async def ask_with_oadp(self, query: str, user_id: str = "user",
                      session_id: str = None, context: Dict = None,
                      workspace_id: Optional[str] = None,
                      scenario_id: Optional[str] = None,
                      auto_decide: bool = False) -> Dict[str, Any]:
        """OADP 闭环问答：QA→Decision→Action→Feedback"""
        qa_result = self.ask(query, user_id, session_id, context, workspace_id, scenario_id)

        if auto_decide and qa_result.get('decision_available'):
            try:
                from odap.biz.decision_pipeline.pipeline import get_decision_pipeline
                from odap.biz.decision_pipeline.schemas import AnalysisInput
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

    def _is_decision_intent(self, query: str) -> bool:
        decision_keywords = [
            "应该", "建议", "如何处理", "怎么办", "决策", "行动",
            "攻击", "防御", "撤退", "增援", "移动", "部署",
            "推荐", "最优", "最佳方案", "执行",
        ]
        return any(kw in query for kw in decision_keywords)

    def _extract_suggested_actions(self, query: str, rag_results: List) -> List[Dict[str, Any]]:
        if not self._is_decision_intent(query):
            return []
        try:
            from odap.biz.qa.semantic_retriever.retriever import get_semantic_retriever
            retriever = get_semantic_retriever()
            import asyncio
            result = asyncio.get_event_loop().run_until_complete(
                retriever.retrieve(query, top_k=5)
            )
            return result.suggested_actions[:5]
        except Exception:
            return []

    def _generate_answer(self, query: str, context: str, rag_results: List["RAGResult"]) -> str:
        if self.use_mock:
            return self._mock_generate(query, context, rag_results)

        llm_answer = self._generate_with_llm(query, context, rag_results)
        if llm_answer:
            return llm_answer

        query_lower = query.lower()
        if "雷达" in query_lower:
            return self._answer_radar(query, context, rag_results)
        elif "力量" in query_lower and "对比" in query_lower:
            return self._answer_force_comparison(query, context, rag_results)
        elif any(kw in query_lower for kw in ["态势", "分析"]):
            return self._answer_situation(query, context, rag_results)
        else:
            return self._answer_general(query, context, rag_results)

    def _generate_with_llm(self, query: str, context: str, rag_results: List["RAGResult"]) -> Optional[str]:
        if not self.llm_client:
            return None
        try:
            import asyncio
            from graphiti_core.prompts.models import Message

            source_count = len(rag_results)
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

            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ]

            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None

            result, _, _ = loop.run_until_complete(
                self.llm_client._generate_response(messages, max_tokens=2048)
            )

            if isinstance(result, dict):
                return result.get('response', str(result))
            return str(result) if result else None

        except Exception as e:
            logger.warning(f"QAEngine LLM generation failed, falling back to template: {e}")
            return None

    def _mock_generate(self, query: str, context: str, rag_results: List["RAGResult"]) -> str:
        """Mock 生成回答"""
        return f"根据您的问题 '{query}'，这是基于 {len(rag_results)} 条检索结果和上下文信息的回答。\n\n{context[:200]}..."

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
    print("问答引擎 v2 测试")

    print("\n=== 测试问答引擎 ===")
    qa = QAEngineV2(use_mock=True)

    print("\n1. 测试雷达查询:")
    result = qa.ask("B区有哪些雷达?")
    print(f"  会话 ID: {result['session_id']}")
    print(f"  回答: {result['answer'][:100]}...")
    print(f"  来源数: {len(result['sources'])}")

    print("\n2. 测试多轮对话:")
    result2 = qa.ask("还有其他的吗?", session_id=result["session_id"])
    print(f"  回答: {result2['answer'][:100]}...")

    print("\n3. 测试力量对比:")
    result3 = qa.ask("A区和B区的力量对比如何?")
    print(f"  回答: {result3['answer']}")

    print("\n4. 测试溯源:")
    for source in result3["sources"]:
        print(f"  - 来源: {source['source']}")
        print(f"    内容: {source['excerpt'][:50]}...")

    print("\n5. 测试对话历史:")
    history = qa.get_dialog_history(result["session_id"])
    print(f"  历史消息数: {len(history)}")
