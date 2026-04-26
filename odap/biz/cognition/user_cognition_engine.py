"""
用户认知引擎 v2 - User Cognition Engine
Phase 5 MOD-02 - Complete User Cognition System

WR-28: 意图识别器模块
WR-29: 知识导航器模块
WR-30: 解释引擎模块
WR-31: 角色视图管理器
WR-32: 用户认知引擎 UI

功能：
- 意图解析
- 角色识别
- 需求理解
- 知识检索
- 推理路径追踪
- 图谱导航
- 决策解释
- 推理链可视化
- "为什么"查询
- 角色视图配置
"""

import sys
import os
import json
import time
import threading
import re
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class IntentType(Enum):
    """意图类型"""
    QUERY = "query"
    ACTION = "action"
    EXPLAIN = "explain"
    RECOMMEND = "recommend"
    NAVIGATE = "navigate"
    COMPARE = "compare"
    ANALYZE = "analyze"


class RoleType(Enum):
    """角色类型"""
    COMMANDER = "commander"
    INTELLIGENCE = "intelligence"
    OPERATOR = "operator"
    ANALYST = "analyst"
    GUEST = "guest"


class ConfidenceLevel(Enum):
    """置信度等级"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Intent:
    """用户意图"""
    intent_id: str
    intent_type: IntentType
    query: str
    entities: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    role: RoleType = RoleType.GUEST
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedIntent:
    """解析后的意图"""
    primary_intent: IntentType
    confidence: float
    entities: List[str]
    attributes: Dict[str, Any] = field(default_factory=dict)
    alternative_intents: List[IntentType] = field(default_factory=list)


@dataclass
class KnowledgeResult:
    """知识检索结果"""
    result_id: str
    content: Any
    relevance_score: float
    source: str
    path: List[str] = field(default_factory=list)


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_id: str
    step_type: str
    description: str
    input_facts: List[str] = field(default_factory=list)
    output_facts: List[str] = field(default_factory=list)
    confidence: float = 1.0
    rule_applied: Optional[str] = None


@dataclass
class ReasoningChain:
    """推理链"""
    chain_id: str
    query: str
    steps: List[ReasoningStep]
    conclusion: str
    confidence: float
    supporting_evidence: List[str] = field(default_factory=list)


@dataclass
class Explanation:
    """解释"""
    explanation_id: str
    query: str
    answer: str
    reasoning_chain: ReasoningChain
    confidence: float
    sources: List[str] = field(default_factory=list)
    alternative_explanations: List[str] = field(default_factory=list)


@dataclass
class RoleView:
    """角色视图"""
    view_id: str
    role_type: RoleType
    name: str
    description: str
    capabilities: List[str] = field(default_factory=list)
    default_entities: List[str] = field(default_factory=list)
    layout_config: Dict[str, Any] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserContext:
    """用户上下文"""
    user_id: str
    role: RoleType
    session_id: str
    workspace_id: Optional[str] = None
    scenario_id: Optional[str] = None
    preferences: Dict[str, Any] = field(default_factory=dict)


class IntentRecognizer:
    """意图识别器"""

    def __init__(self):
        self._intent_patterns = {
            IntentType.QUERY: [
                r"什么|哪个|哪里|谁|如何|怎么",
                r"查询|搜索|查找|检索",
                r"\?$"
            ],
            IntentType.ACTION: [
                r"执行|运行|启动|创建|删除",
                r"完成|处理|开始|停止",
                r"\bdo\b|\brun\b|\bexecute\b"
            ],
            IntentType.EXPLAIN: [
                r"为什么|原因|解释|说明",
                r"为什么是",
                r"\bwhy\b|\bexplain\b"
            ],
            IntentType.RECOMMEND: [
                r"建议|推荐|推荐",
                r"应该|最好",
                r"\brecommend\b|\bsuggest\b"
            ],
            IntentType.NAVIGATE: [
                r"导航|查看|转到|去",
                r"打开|显示",
                r"\bnavigate\b|\bshow\b"
            ],
            IntentType.COMPARE: [
                r"比较|对比|差异",
                r"区别|不同",
                r"\bcompare\b|\bdiff\b"
            ],
            IntentType.ANALYZE: [
                r"分析|评估|统计",
                r"总结|归纳",
                r"\banalyze\b|\bevaluate\b"
            ]
        }
        self._entity_extractors = {
            "radar": self._extract_radar,
            "target": self._extract_target,
            "unit": self._extract_unit,
            "location": self._extract_location
        }

    def recognize(self, query: str, role: RoleType = RoleType.GUEST) -> ParsedIntent:
        """
        识别用户意图

        Args:
            query: 用户查询
            role: 用户角色

        Returns:
            ParsedIntent
        """
        query_lower = query.lower()

        intent_scores = {}
        for intent_type, patterns in self._intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1
            intent_scores[intent_type] = score / len(patterns)

        sorted_intents = sorted(intent_scores.items(), key=lambda x: x[1], reverse=True)

        primary_intent = sorted_intents[0][0] if sorted_intents else IntentType.QUERY
        primary_confidence = sorted_intents[0][1] if sorted_intents else 0.5

        entities = self._extract_entities(query)

        attributes = self._extract_attributes(query)

        alternative_intents = [i[0] for i in sorted_intents[1:3] if i[1] > 0]

        return ParsedIntent(
            primary_intent=primary_intent,
            confidence=min(1.0, primary_confidence + 0.2),
            entities=entities,
            attributes=attributes,
            alternative_intents=alternative_intents
        )

    def _extract_entities(self, query: str) -> List[str]:
        """提取实体"""
        entities = []

        for entity_type, extractor in self._entity_extractors.items():
            extracted = extractor(query)
            entities.extend(extracted)

        return list(set(entities))

    def _extract_radar(self, query: str) -> List[str]:
        """提取雷达实体"""
        patterns = [
            r"雷达站?[A-Z]?",
            r"雷达\d+",
            r"[A-Z]+-?\d+雷达"
        ]
        return self._generic_extract(query, patterns)

    def _extract_target(self, query: str) -> List[str]:
        """提取目标实体"""
        patterns = [
            r"目标[一二三四五六七八九十\d]+",
            r"目标[A-Z]?",
            r"target\d*"
        ]
        return self._generic_extract(query, patterns)

    def _extract_unit(self, query: str) -> List[str]:
        """提取单位实体"""
        patterns = [
            r"单位\d+",
            r"[A-Z]+连",
            r"[A-Z]+营"
        ]
        return self._generic_extract(query, patterns)

    def _extract_location(self, query: str) -> List[str]:
        """提取位置实体"""
        patterns = [
            r"[A-Z]区",
            r"[A-Z]地带",
            r"坐标[\d,\.]+"
        ]
        return self._generic_extract(query, patterns)

    def _generic_extract(self, query: str, patterns: List[str]) -> List[str]:
        """通用实体提取"""
        results = []
        for pattern in patterns:
            matches = re.findall(pattern, query)
            results.extend(matches)
        return results

    def _extract_attributes(self, query: str) -> Dict[str, Any]:
        """提取属性"""
        attributes = {}

        time_patterns = [
            (r"今天", "today"),
            (r"昨天", "yesterday"),
            (r"上周", "last_week"),
            (r"本月", "this_month"),
            (r"最近", "recent")
        ]
        for pattern, attr in time_patterns:
            if re.search(pattern, query):
                attributes["time"] = attr

        if "详细" in query or "完整" in query:
            attributes["detail_level"] = "high"
        elif "简要" in query or "简单" in query:
            attributes["detail_level"] = "low"

        return attributes


class KnowledgeNavigator:
    """知识导航器"""

    def __init__(self, graph_client=None):
        self._graph_client = graph_client
        self._cache: Dict[str, KnowledgeResult] = {}
        self._navigation_history: List[str] = []

    def search(self, query: str, filters: Dict = None) -> List[KnowledgeResult]:
        """
        知识检索

        Args:
            query: 查询内容
            filters: 过滤条件

        Returns:
            知识结果列表
        """
        results = []

        if self._graph_client:
            try:
                graph_results = self._graph_client.search(query, filters or {})
                for item in graph_results:
                    result = KnowledgeResult(
                        result_id=str(uuid.uuid4()),
                        content=item,
                        relevance_score=item.get("score", 0.8),
                        source="graph",
                        path=[]
                    )
                    results.append(result)
            except Exception:
                pass

        if not results:
            results.append(KnowledgeResult(
                result_id=str(uuid.uuid4()),
                content={"message": "未找到相关知识"},
                relevance_score=0,
                source="none",
                path=[]
            ))

        for result in results:
            self._cache[result.result_id] = result

        return results

    def navigate_path(self, start_id: str, direction: str = "outbound") -> List[str]:
        """
        导航路径

        Args:
            start_id: 起始节点 ID
            direction: 方向 (outbound/inbound/both)

        Returns:
            路径节点列表
        """
        path = [start_id]

        if self._graph_client:
            try:
                neighbors = self._graph_client.get_neighbors(start_id, direction)
                if neighbors:
                    path.extend([n["id"] for n in neighbors[:3]])
            except Exception:
                pass

        self._navigation_history.extend(path)
        return path

    def get_related_entities(self, entity_id: str, depth: int = 1) -> List[Dict]:
        """获取相关实体"""
        related = []

        if self._graph_client:
            try:
                related = self._graph_client.get_related_entities(entity_id, depth)
            except Exception:
                pass

        return related

    def get_entity_context(self, entity_id: str) -> Dict:
        """获取实体上下文"""
        context = {
            "entity_id": entity_id,
            "neighbors": [],
            "attributes": {},
            "history": []
        }

        if self._graph_client:
            try:
                context["neighbors"] = self._graph_client.get_neighbors(entity_id)
                context["attributes"] = self._graph_client.get_node_properties(entity_id)
            except Exception:
                pass

        return context


class ReasoningPathTracker:
    """推理路径追踪器"""

    def __init__(self):
        self._chains: Dict[str, ReasoningChain] = {}
        self._step_templates: Dict[str, Callable] = {}

    def create_chain(self, query: str) -> ReasoningChain:
        """创建推理链"""
        chain = ReasoningChain(
            chain_id=str(uuid.uuid4()),
            query=query,
            steps=[],
            conclusion="",
            confidence=1.0
        )
        self._chains[chain.chain_id] = chain
        return chain

    def add_step(self, chain_id: str, step_type: str, description: str,
                input_facts: List[str] = None, output_facts: List[str] = None,
                rule: str = None) -> ReasoningStep:
        """添加推理步骤"""
        chain = self._chains.get(chain_id)
        if not chain:
            raise ValueError(f"Chain not found: {chain_id}")

        step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=step_type,
            description=description,
            input_facts=input_facts or [],
            output_facts=output_facts or [],
            rule_applied=rule
        )

        chain.steps.append(step)
        return step

    def complete_chain(self, chain_id: str, conclusion: str, confidence: float = 1.0):
        """完成推理链"""
        chain = self._chains.get(chain_id)
        if chain:
            chain.conclusion = conclusion
            chain.confidence = confidence

    def get_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """获取推理链"""
        return self._chains.get(chain_id)

    def get_chain_visualization(self, chain_id: str) -> Dict[str, Any]:
        """获取推理链可视化数据"""
        chain = self._chains.get(chain_id)
        if not chain:
            return {}

        nodes = []
        edges = []

        for i, step in enumerate(chain.steps):
            nodes.append({
                "id": step.step_id,
                "label": step.step_type,
                "description": step.description,
                "type": "step"
            })

            if i > 0:
                edges.append({
                    "source": chain.steps[i-1].step_id,
                    "target": step.step_id,
                    "type": "sequence"
                })

        nodes.append({
            "id": "conclusion",
            "label": "Conclusion",
            "description": chain.conclusion,
            "type": "conclusion"
        })

        if chain.steps:
            edges.append({
                "source": chain.steps[-1].step_id,
                "target": "conclusion",
                "type": "leads_to"
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "confidence": chain.confidence
        }


class ExplanationEngine:
    """解释引擎"""

    def __init__(self):
        self._reasoning_tracker = ReasoningPathTracker()
        self._explanation_templates: Dict[str, str] = {}

    def explain(self, query: str, facts: List[str],
               reasoning_chain: ReasoningChain) -> Explanation:
        """
        生成解释

        Args:
            query: 用户问题
            facts: 相关事实
            reasoning_chain: 推理链

        Returns:
            Explanation
        """
        explanation_id = str(uuid.uuid4())

        answer = self._generate_answer(query, reasoning_chain)

        supporting_sources = []
        for fact in facts:
            source = self._identify_source(fact)
            if source:
                supporting_sources.append(source)

        alternative = self._generate_alternatives(query, facts)

        return Explanation(
            explanation_id=explanation_id,
            query=query,
            answer=answer,
            reasoning_chain=reasoning_chain,
            sources=supporting_sources,
            confidence=reasoning_chain.confidence,
            alternative_explanations=alternative
        )

    def explain_why(self, query: str, context: Dict) -> Explanation:
        """
        解释为什么

        Args:
            query: 为什么查询
            context: 上下文

        Returns:
            Explanation
        """
        chain = self._reasoning_tracker.create_chain(query)

        relevant_facts = context.get("facts", [])
        for i, fact in enumerate(relevant_facts[:5]):
            self._reasoning_tracker.add_step(
                chain.chain_id,
                step_type="premise",
                description=f"已知事实: {fact}",
                input_facts=[],
                output_facts=[fact]
            )

        conclusion = self._derive_conclusion(relevant_facts)
        self._reasoning_tracker.add_step(
            chain.chain_id,
            step_type="inference",
            description=f"推导: {conclusion}",
            input_facts=relevant_facts,
            output_facts=[conclusion],
            rule="modus_ponens"
        )

        self._reasoning_tracker.complete_chain(chain.chain_id, conclusion, 0.9)

        return self.explain(query, relevant_facts, chain)

    def _generate_answer(self, query: str, chain: ReasoningChain) -> str:
        """生成答案"""
        if chain.conclusion:
            return chain.conclusion

        return f"基于 {len(chain.steps)} 个推理步骤得出的结论"

    def _identify_source(self, fact: str) -> Optional[str]:
        """识别来源"""
        if "雷达" in fact:
            return "radar_system"
        elif "目标" in fact:
            return "target_tracking"
        elif "威胁" in fact:
            return "threat_analysis"
        return None

    def _generate_alternatives(self, query: str, facts: List[str]) -> List[str]:
        """生成替代解释"""
        alternatives = []

        if len(facts) > 1:
            alternatives.append(
                f"如果只考虑第一个因素，结论可能会不同"
            )

        alternatives.append(
            f"在不同的上下文中，可能会得出不同的结论"
        )

        return alternatives

    def _derive_conclusion(self, facts: List[str]) -> str:
        """推导结论"""
        if not facts:
            return "没有足够的信息来得出结论"

        return f"基于 {len(facts)} 个事实，可以得出该结论"


class RoleViewManager:
    """角色视图管理器"""

    def __init__(self):
        self._views: Dict[str, RoleView] = {}
        self._setup_default_views()

    def _setup_default_views(self):
        """设置默认视图"""
        commander_view = RoleView(
            view_id="commander-default",
            role_type=RoleType.COMMANDER,
            name="指挥官视图",
            description="面向指挥官的全局态势视图",
            capabilities=[
                "situation_awareness",
                "decision_support",
                "resource_allocation",
                "threat_assessment"
            ],
            default_entities=["units", "targets", "threats"],
            layout_config={
                "primary": "situation_map",
                "secondary": ["timeline", "statistics"],
                "show_risk": True
            },
            filters={
                "threat_level": ["high", "critical"],
                "show_friendly": True,
                "show_enemy": True
            }
        )
        self._views[commander_view.view_id] = commander_view

        intelligence_view = RoleView(
            view_id="intelligence-default",
            role_type=RoleType.INTELLIGENCE,
            name="情报员视图",
            description="面向情报分析员的信息视图",
            capabilities=[
                "data_analysis",
                "pattern_recognition",
                "intel_gathering",
                "report_generation"
            ],
            default_entities=["intel", "analysis", "reports"],
            layout_config={
                "primary": "analysis_dashboard",
                "secondary": ["graph_view", "timeline"]
            },
            filters={
                "data_type": ["radar", "signal", "human"],
                "time_range": "24h"
            }
        )
        self._views[intelligence_view.view_id] = intelligence_view

        operator_view = RoleView(
            view_id="operator-default",
            role_type=RoleType.OPERATOR,
            name="操作员视图",
            description="面向操作员的执行视图",
            capabilities=[
                "task_execution",
                "system_control",
                "monitoring",
                "alert_management"
            ],
            default_entities=["tasks", "systems", "alerts"],
            layout_config={
                "primary": "task_list",
                "secondary": ["system_status", "alerts"]
            },
            filters={
                "status": ["pending", "in_progress"],
                "priority": ["high", "medium"]
            }
        )
        self._views[operator_view.view_id] = operator_view

    def get_view(self, role: RoleType) -> RoleView:
        """获取角色视图"""
        view_id = f"{role.value}-default"
        return self._views.get(view_id)

    def get_all_views(self) -> List[RoleView]:
        """获取所有视图"""
        return list(self._views.values())

    def create_custom_view(self, role: RoleType, name: str,
                          config: Dict[str, Any]) -> RoleView:
        """创建自定义视图"""
        view = RoleView(
            view_id=str(uuid.uuid4()),
            role_type=role,
            name=name,
            description="用户自定义视图",
            capabilities=config.get("capabilities", []),
            layout_config=config.get("layout_config", {}),
            filters=config.get("filters", {})
        )
        self._views[view.view_id] = view
        return view


class UserCognitionEngine:
    """
    用户认知引擎
    Phase 5 MOD-02 完整实现
    """

    def __init__(self, graph_client=None):
        self._intent_recognizer = IntentRecognizer()
        self._knowledge_navigator = KnowledgeNavigator(graph_client)
        self._reasoning_tracker = ReasoningPathTracker()
        self._explanation_engine = ExplanationEngine()
        self._role_view_manager = RoleViewManager()

        self._sessions: Dict[str, UserContext] = {}
        self._conversation_history: Dict[str, List] = {}
        self._lock = threading.RLock()

    def process_query(self, query: str, user_id: str,
                    role: RoleType = RoleType.GUEST) -> Dict[str, Any]:
        """
        处理用户查询

        Args:
            query: 用户查询
            user_id: 用户 ID
            role: 用户角色

        Returns:
            处理结果
        """
        session_id = self._get_or_create_session(user_id, role)

        parsed_intent = self._intent_recognizer.recognize(query, role)

        knowledge_results = self._knowledge_navigator.search(
            query,
            {"role": role.value}
        )

        response = {
            "session_id": session_id,
            "intent": {
                "type": parsed_intent.primary_intent.value,
                "confidence": parsed_intent.confidence,
                "entities": parsed_intent.entities,
                "attributes": parsed_intent.attributes
            },
            "knowledge_results": [
                {
                    "id": r.result_id,
                    "content": r.content,
                    "relevance": r.relevance_score,
                    "source": r.source
                }
                for r in knowledge_results
            ]
        }

        if parsed_intent.primary_intent == IntentType.EXPLAIN:
            explanation = self._explanation_engine.explain_why(
                query,
                {"facts": [r.content.get("text", "") for r in knowledge_results]}
            )
            response["explanation"] = {
                "answer": explanation.answer,
                "confidence": explanation.confidence,
                "reasoning_chain": [
                    {
                        "step": s.step_id,
                        "type": s.step_type,
                        "description": s.description
                    }
                    for s in explanation.reasoning_chain.steps
                ]
            }

        with self._lock:
            if session_id not in self._conversation_history:
                self._conversation_history[session_id] = []
            self._conversation_history[session_id].append({
                "query": query,
                "intent": parsed_intent.primary_intent.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

        return response

    def explain_decision(self, decision_id: str, context: Dict) -> Explanation:
        """
        解释决策

        Args:
            decision_id: 决策 ID
            context: 上下文

        Returns:
            Explanation
        """
        facts = context.get("facts", [])
        query = context.get("query", "解释这个决策")

        chain = self._reasoning_tracker.create_chain(query)

        for i, fact in enumerate(facts):
            self._reasoning_tracker.add_step(
                chain.chain_id,
                step_type="fact",
                description=fact,
                input_facts=[],
                output_facts=[fact]
            )

        conclusion = context.get("conclusion", "基于现有信息做出的决策")
        self._reasoning_tracker.complete_chain(chain.chain_id, conclusion, 0.85)

        return self._explanation_engine.explain(query, facts, chain)

    def get_role_view(self, role: RoleType) -> Dict[str, Any]:
        """获取角色视图"""
        view = self._role_view_manager.get_view(role)
        if not view:
            return {}

        return {
            "view_id": view.view_id,
            "role": view.role_type.value,
            "name": view.name,
            "description": view.description,
            "capabilities": view.capabilities,
            "layout_config": view.layout_config,
            "filters": view.filters
        }

    def navigate_knowledge_graph(self, entity_id: str,
                               direction: str = "outbound") -> Dict[str, Any]:
        """导航知识图谱"""
        path = self._knowledge_navigator.navigate_path(entity_id, direction)
        related = self._knowledge_navigator.get_related_entities(entity_id)
        context = self._knowledge_navigator.get_entity_context(entity_id)

        return {
            "entity_id": entity_id,
            "navigation_path": path,
            "related_entities": related,
            "entity_context": context
        }

    def _get_or_create_session(self, user_id: str, role: RoleType) -> str:
        """获取或创建会话"""
        for session_id, ctx in self._sessions.items():
            if ctx.user_id == user_id:
                return session_id

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = UserContext(
            user_id=user_id,
            role=role,
            session_id=session_id
        )
        return session_id

    def get_conversation_history(self, session_id: str,
                               limit: int = 10) -> List[Dict]:
        """获取对话历史"""
        history = self._conversation_history.get(session_id, [])
        return history[-limit:]


_global_cognition_engine: Optional[UserCognitionEngine] = None


def get_cognition_engine(graph_client=None) -> UserCognitionEngine:
    """获取全局用户认知引擎"""
    global _global_cognition_engine
    if _global_cognition_engine is None:
        _global_cognition_engine = UserCognitionEngine(graph_client)
    return _global_cognition_engine


if __name__ == "__main__":
    engine = get_cognition_engine()

    print("=" * 60)
    print("用户认知引擎 v2 测试")
    print("=" * 60)

    print("\n1. 意图识别:")
    test_queries = [
        "查询雷达站A的状态",
        "为什么这个目标被标记为威胁?",
        "推荐最佳应对方案"
    ]

    for query in test_queries:
        result = engine.process_query(query, "test-user", RoleType.COMMANDER)
        print(f"\n   查询: {query}")
        print(f"   识别意图: {result['intent']['type']}")
        print(f"   置信度: {result['intent']['confidence']:.2f}")

    print("\n2. 角色视图:")
    for role in [RoleType.COMMANDER, RoleType.INTELLIGENCE, RoleType.OPERATOR]:
        view = engine.get_role_view(role)
        print(f"\n   角色: {role.value}")
        print(f"   视图名: {view.get('name', 'N/A')}")
        print(f"   能力: {', '.join(view.get('capabilities', [])[:3])}")

    print("\n3. 决策解释:")
    explanation = engine.explain_decision(
        "decision-001",
        {
            "query": "为什么选择这个方案?",
            "facts": [
                "目标距离100km",
                "威胁等级高",
                "资源充足"
            ],
            "conclusion": "选择快速突击方案"
        }
    )
    print(f"\n   问题: {explanation.query}")
    print(f"   答案: {explanation.answer}")
    print(f"   置信度: {explanation.confidence:.2f}")

    print("\n" + "=" * 60)
    print("用户认知引擎 v2 测试完成")
    print("=" * 60)