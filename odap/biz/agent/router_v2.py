"""
Agent Router v2 - 语义路由 + Self-Correction + 意图识别

功能：
- 语义路由
- Self-Correction 自校正
- 意图识别
- Worker 工厂
"""

import sys
import os
import re
import json
import time
import threading
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.orchestrator_v2 import SelfCorrectingOrchestratorV2


class Intent(Enum):
    """意图类型"""
    SEARCH = "search"
    ANALYSIS = "analysis"
    COMMAND = "command"
    ATTACK = "attack"
    QUERY = "query"
    RECOMMEND = "recommend"
    UNKNOWN = "unknown"


@dataclass
class RoutingResult:
    """路由结果"""
    intent: str
    confidence: float
    target_agent: str
    parameters: Dict[str, Any]
    reasoning: str


@dataclass
class CorrectionResult:
    """校正结果"""
    original_result: Any
    corrected: bool
    corrections: List[str]
    final_result: Any


class IntentRecognizer:
    """意图识别器"""

    def __init__(self):
        self._patterns = self._init_patterns()

    def _init_patterns(self) -> Dict[str, List[str]]:
        """初始化意图模式"""
        return {
            Intent.SEARCH.value: [
                r"搜索|查找|看看|有没有|查询",
                r"搜索.*雷达|查找.*目标|看看.*区域"
            ],
            Intent.ANALYSIS.value: [
                r"分析|评估|态势|对比|统计",
                r"分析.*领域|力量.*对比|态势.*报告"
            ],
            Intent.COMMAND.value: [
                r"指挥|命令|调度|指示|指令",
                r"指挥.*部队|命令.*单位|下达.*指令"
            ],
            Intent.ATTACK.value: [
                r"攻击|打击|摧毁|歼灭|轰炸",
                r"攻击.*目标|打击.*阵地|摧毁.*设施"
            ],
            Intent.QUERY.value: [
                r"什么|怎么|如何|为什么|多少",
                r"是什么|怎么办|如何做|为什么是"
            ],
            Intent.RECOMMEND.value: [
                r"推荐|建议|最优|最佳|方案",
                r"推荐.*目标|建议.*策略|最优.*方案"
            ]
        }

    def recognize(self, query: str) -> RoutingResult:
        """
        识别意图

        Args:
            query: 用户查询

        Returns:
            路由结果
        """
        query_lower = query.lower()
        scores = {}

        for intent_name, patterns in self._patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    score += 1
            if score > 0:
                scores[intent_name] = score

        if not scores:
            return RoutingResult(
                intent=Intent.UNKNOWN.value,
                confidence=0.0,
                target_agent="general",
                parameters={"query": query},
                reasoning="未识别到明确意图"
            )

        best_intent = max(scores, key=scores.get)
        confidence = scores[best_intent] / sum(scores.values())

        target_agent = self._map_intent_to_agent(best_intent)
        parameters = self._extract_parameters(query, best_intent)

        return RoutingResult(
            intent=best_intent,
            confidence=confidence,
            target_agent=target_agent,
            parameters=parameters,
            reasoning=f"基于关键词匹配识别为 {best_intent}，置信度 {confidence:.2f}"
        )

    def _map_intent_to_agent(self, intent: str) -> str:
        """映射意图到 Agent"""
        mapping = {
            Intent.SEARCH.value: "search_agent",
            Intent.ANALYSIS.value: "analysis_agent",
            Intent.COMMAND.value: "command_agent",
            Intent.ATTACK.value: "strike_agent",
            Intent.QUERY.value: "query_agent",
            Intent.RECOMMEND.value: "recommend_agent",
            Intent.UNKNOWN.value: "general_agent"
        }
        return mapping.get(intent, "general_agent")

    def _extract_parameters(self, query: str, intent: str) -> Dict[str, Any]:
        """提取参数"""
        params = {"raw_query": query}

        area_match = re.search(r'([A-E])\s*区', query)
        if area_match:
            params["area"] = area_match.group(1)

        target_match = re.search(r'(雷达|导弹|坦克|火炮|医院|部队)', query)
        if target_match:
            params["target_type"] = target_match.group(1)

        entity_match = re.search(r'([A-Za-z_0-9]+-[A-Za-z_0-9]+|[A-Za-z_0-9]+_[A-Za-z_0-9]+)', query)
        if entity_match:
            params["entity_id"] = entity_match.group(1)

        return params


class WorkerFactory:
    """Worker 工厂"""

    def __init__(self):
        self._workers: Dict[str, Callable] = {}
        self._register_default_workers()

    def _register_default_workers(self):
        """注册默认 Worker"""
        self._workers["search_agent"] = self._create_search_worker()
        self._workers["analysis_agent"] = self._create_analysis_worker()
        self._workers["command_agent"] = self._create_command_worker()
        self._workers["strike_agent"] = self._create_strike_worker()
        self._workers["recommend_agent"] = self._create_recommend_worker()
        self._workers["general_agent"] = self._create_general_worker()

    def _create_search_worker(self) -> Callable:
        """创建搜索 Worker"""
        def worker(params: Dict, context: Dict) -> Dict:
            from odap.tools import SKILL_CATALOG
            area = params.get("area")
            target_type = params.get("target_type", "radar")

            if target_type == "radar" and "search_radar" in SKILL_CATALOG:
                handler = SKILL_CATALOG["search_radar"]["handler"]
                return handler(area=area)

            return {"status": "success", "data": {"results": []}}
        return worker

    def _create_analysis_worker(self) -> Callable:
        """创建分析 Worker"""
        def worker(params: Dict, context: Dict) -> Dict:
            from odap.tools import SKILL_CATALOG
            if "analyze_domain" in SKILL_CATALOG:
                handler = SKILL_CATALOG["analyze_domain"]["handler"]
                return handler()
            return {"status": "success", "data": {"analysis": "暂无数据"}}
        return worker

    def _create_command_worker(self) -> Callable:
        """创建指挥 Worker"""
        def worker(params: Dict, context: Dict) -> Dict:
            from odap.tools import SKILL_CATALOG
            if "command_unit" in SKILL_CATALOG:
                handler = SKILL_CATALOG["command_unit"]["handler"]
                return handler(
                    unit_id=params.get("entity_id"),
                    command=params.get("raw_query", ""),
                    user_role=context.get("user_role", "pilot")
                )
            return {"status": "success", "data": {"command": "命令已下达"}}
        return worker

    def _create_strike_worker(self) -> Callable:
        """创建打击 Worker"""
        def worker(params: Dict, context: Dict) -> Dict:
            from odap.tools import SKILL_CATALOG
            if "attack_target" in SKILL_CATALOG:
                handler = SKILL_CATALOG["attack_target"]["handler"]
                return handler(
                    target_id=params.get("entity_id"),
                    user_role=context.get("user_role", "pilot")
                )
            return {"status": "success", "data": {"strike": "打击任务已创建"}}
        return worker

    def _create_recommend_worker(self) -> Callable:
        """创建推荐 Worker"""
        def worker(params: Dict, context: Dict) -> Dict:
            from odap.tools import SKILL_CATALOG
            if "recommend_strike_targets" in SKILL_CATALOG:
                handler = SKILL_CATALOG["recommend_strike_targets"]["handler"]
                return handler(
                    user_role=context.get("user_role", "pilot"),
                    area=params.get("area"),
                    target_type=params.get("target_type")
                )
            return {"status": "success", "data": {"recommendations": []}}
        return worker

    def _create_general_worker(self) -> Callable:
        """创建通用 Worker"""
        def worker(params: Dict, context: Dict) -> Dict:
            return {
                "status": "success",
                "data": {
                    "message": "已收到您的请求",
                    "query": params.get("raw_query", "")
                }
            }
        return worker

    def get_worker(self, agent_name: str) -> Optional[Callable]:
        """获取 Worker"""
        return self._workers.get(agent_name)


class SelfCorrector:
    """自校正器"""

    def __init__(self):
        self._correction_rules = self._init_rules()

    def _init_rules(self) -> List[Dict]:
        """初始化校正规则"""
        return [
            {
                "condition": lambda r: r.get("status") == "denied",
                "check": lambda r: "权限不足" in str(r.get("message", "")),
                "action": "escalate"
            },
            {
                "condition": lambda r: r.get("status") == "error",
                "check": lambda r: "找不到" in str(r.get("message", "")),
                "action": "retry_with_broad_query"
            },
            {
                "condition": lambda r: not r.get("success", True),
                "check": lambda r: r.get("error"),
                "action": "report_error"
            }
        ]

    def correct(self, result: Dict, context: Dict) -> CorrectionResult:
        """
        自校正结果

        Args:
            result: 原始结果
            context: 上下文

        Returns:
            校正结果
        """
        corrections = []

        for rule in self._correction_rules:
            if rule["condition"](result) and rule["check"](result):
                action = rule["action"]
                if action == "escalate":
                    corrections.append("权限不足，需要升级处理")
                elif action == "retry_with_broad_query":
                    corrections.append("重新尝试更广泛的查询")
                elif action == "report_error":
                    corrections.append(f"报告错误: {result.get('error')}")

        return CorrectionResult(
            original_result=result,
            corrected=len(corrections) > 0,
            corrections=corrections,
            final_result=result
        )


class AgentRouterV2:
    """
    Agent Router v2

    功能：
    - 语义路由
    - Self-Correction 自校正
    - 意图识别
    - Worker 工厂
    """

    def __init__(self, user_role: str = "pilot"):
        self.user_role = user_role
        self.intent_recognizer = IntentRecognizer()
        self.worker_factory = WorkerFactory()
        self.self_corrector = SelfCorrector()
        self.orchestrator = SelfCorrectingOrchestratorV2(user_role=user_role)
        self._routing_history: List[RoutingResult] = []
        self._lock = threading.RLock()

    def route(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """
        路由查询

        Args:
            query: 用户查询
            context: 上下文

        Returns:
            路由结果
        """
        context = context or {}

        routing_result = self.intent_recognizer.recognize(query)

        with self._lock:
            self._routing_history.append(routing_result)
            if len(self._routing_history) > 100:
                self._routing_history.pop(0)

        worker = self.worker_factory.get_worker(routing_result.target_agent)
        if not worker:
            return {
                "success": False,
                "error": f"Worker not found: {routing_result.target_agent}",
                "routing": {
                    "intent": routing_result.intent,
                    "confidence": routing_result.confidence
                }
            }

        full_context = {
            "user_role": self.user_role,
            **context
        }

        try:
            result = worker(routing_result.parameters, full_context)

            correction = self.self_corrector.correct(result, full_context)

            return {
                "success": True,
                "routing": {
                    "intent": routing_result.intent,
                    "confidence": routing_result.confidence,
                    "target_agent": routing_result.target_agent,
                    "reasoning": routing_result.reasoning
                },
                "result": result,
                "correction": {
                    "was_corrected": correction.corrected,
                    "corrections": correction.corrections
                }
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "routing": {
                    "intent": routing_result.intent,
                    "confidence": routing_result.confidence
                }
            }

    def route_and_execute(self, query: str, context: Dict = None) -> Dict[str, Any]:
        """
        路由并执行（使用 Swarm Orchestrator）

        Args:
            query: 用户查询
            context: 上下文

        Returns:
            执行结果
        """
        context = context or {}

        routing_result = self.intent_recognizer.recognize(query)

        swarm_result = self.orchestrator.run(query, context.get("user_id", "system"))

        return {
            "success": swarm_result.get("success", False),
            "routing": {
                "intent": routing_result.intent,
                "confidence": routing_result.confidence,
                "target_agent": routing_result.target_agent
            },
            "result": swarm_result
        }

    def get_routing_history(self, limit: int = 10) -> List[Dict]:
        """获取路由历史"""
        with self._lock:
            history = self._routing_history[-limit:]
            return [{
                "intent": r.intent,
                "confidence": r.confidence,
                "target_agent": r.target_agent,
                "reasoning": r.reasoning
            } for r in reversed(history)]


if __name__ == "__main__":
    print("Agent Router v2 测试")

    print("\n=== 测试意图识别 ===")
    recognizer = IntentRecognizer()

    test_queries = [
        "帮我看看 B 区有没有雷达",
        "分析一下当前领域态势",
        "我想攻击 A 区的目标",
        "力量对比怎么样",
        "推荐一下打击方案"
    ]

    for query in test_queries:
        result = recognizer.recognize(query)
        print(f"\n查询: {query}")
        print(f"  意图: {result.intent}")
        print(f"  置信度: {result.confidence:.2f}")
        print(f"  目标 Agent: {result.target_agent}")

    print("\n=== 测试 Agent Router ===")
    router = AgentRouterV2(user_role="commander")

    result = router.route("帮我看看 B 区有没有雷达")
    print(f"\n路由结果:")
    print(f"  成功: {result.get('success')}")
    print(f"  意图: {result['routing']['intent']}")
    print(f"  Agent: {result['routing']['target_agent']}")

    print("\n=== 测试自校正 ===")
    test_result = {"status": "denied", "message": "权限不足"}
    correction = router.self_corrector.correct(test_result, {"user_role": "pilot"})
    print(f"\n原始结果: {test_result}")
    print(f"  被校正: {correction.corrected}")
    print(f"  校正内容: {correction.corrections}")

    print("\n=== 测试路由历史 ===")
    history = router.get_routing_history()
    print(f"路由历史: {len(history)} 条")
