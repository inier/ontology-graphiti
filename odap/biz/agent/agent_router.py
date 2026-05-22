import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class AgentType(str, Enum):
    COMMANDER = "commander"
    INTELLIGENCE = "intelligence"
    OPERATIONS = "operations"


class AgentRouter:
    ROUTING_KEYWORDS = {
        AgentType.COMMANDER: [
            "决策", "命令", "指挥", "方案", "选择", "批准", "审批",
            "decide", "command", "approve", "strategy", "plan",
        ],
        AgentType.INTELLIGENCE: [
            "情报", "侦察", "态势", "分析", "报告", "搜索", "查询",
            "intelligence", "recon", "analyze", "report", "search", "query",
        ],
        AgentType.OPERATIONS: [
            "执行", "攻击", "防御", "移动", "撤退", "增援", "操作",
            "execute", "attack", "defend", "move", "retreat", "reinforce", "operate",
        ],
    }

    DEFAULT_AGENT = AgentType.COMMANDER

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._custom_rules = self._config.get("custom_rules", {})

    def route(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        scores = self._score_agents(query, context or {})
        best_agent = max(scores, key=scores.get)
        confidence = scores[best_agent]

        if confidence < 0.1:
            best_agent = self.DEFAULT_AGENT
            confidence = 0.0

        return {
            "agent_type": best_agent.value if isinstance(best_agent, AgentType) else best_agent,
            "confidence": round(confidence, 3),
            "scores": {k.value if isinstance(k, AgentType) else k: round(v, 3) for k, v in scores.items()},
            "query": query,
        }

    def _score_agents(self, query: str, context: Dict[str, Any]) -> Dict[AgentType, float]:
        scores = {agent: 0.0 for agent in AgentType}
        query_lower = query.lower()

        for agent_type, keywords in self.ROUTING_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    scores[agent_type] += 1.0

        if context:
            ctx_action = context.get("action", "").lower()
            ctx_role = context.get("user_role", "").lower()
            if ctx_action:
                for agent_type, keywords in self.ROUTING_KEYWORDS.items():
                    if ctx_action in keywords:
                        scores[agent_type] += 2.0
            if ctx_role == "commander":
                scores[AgentType.COMMANDER] += 1.0
            elif ctx_role == "intelligence_officer":
                scores[AgentType.INTELLIGENCE] += 1.0
            elif ctx_role == "operator":
                scores[AgentType.OPERATIONS] += 1.0

        total = sum(scores.values())
        if total > 0:
            scores = {k: v / total for k, v in scores.items()}

        return scores
