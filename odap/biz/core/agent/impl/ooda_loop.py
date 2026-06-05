import logging
import asyncio
from typing import Any, Dict, List, Optional
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class OODAPhase(str, Enum):
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"


class OODALoop:
    def __init__(self, agent_id: str = "", role: str = "intelligence"):
        self.agent_id = agent_id
        self.role = role
        self.current_phase = OODAPhase.OBSERVE
        self.history: List[Dict[str, Any]] = []
        self.observations: List[Dict[str, Any]] = []
        self.analysis: Dict[str, Any] = {}
        self.decision: Dict[str, Any] = {}

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        observe_result = await self._observe(context)
        orient_result = await self._orient(observe_result)
        decide_result = await self._decide(orient_result)
        act_result = await self._act(decide_result)
        return {
            "status": "success",
            "agent_id": self.agent_id,
            "role": self.role,
            "observe": observe_result,
            "orient": orient_result,
            "decide": decide_result,
            "act": act_result,
            "history": self.history,
        }

    async def _observe(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.OBSERVE
        raw_observations = context.get("observations", [])
        query = context.get("query", "")
        workspace_id = context.get("workspace_id", "")

        self.observations = []
        for obs in raw_observations:
            if isinstance(obs, dict):
                self.observations.append(obs)
            elif isinstance(obs, str):
                self.observations.append({"content": obs, "source": "input"})

        if query and not any(o.get("content") == query for o in self.observations):
            self.observations.append({"content": query, "source": "query", "workspace_id": workspace_id})

        graph_data = context.get("graph_data", {})
        if graph_data:
            entities = graph_data.get("entities", [])
            relationships = graph_data.get("relationships", [])
            self.observations.append({
                "content": f"Graph data: {len(entities)} entities, {len(relationships)} relationships",
                "source": "knowledge_graph",
                "entity_count": len(entities),
                "relationship_count": len(relationships),
            })

        result = {
            "observations": self.observations,
            "observation_count": len(self.observations),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "observe", "result": result})
        return result

    async def _orient(self, observe_result: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.ORIENT
        observations = observe_result.get("observations", [])

        entity_types = set()
        key_entities = []
        for obs in observations:
            source = obs.get("source", "")
            content = obs.get("content", "")
            if source == "knowledge_graph":
                entity_count = obs.get("entity_count", 0)
                if entity_count > 0:
                    entity_types.add("graph_entities")
            if content and len(content) < 200:
                key_entities.append(content)

        urgency = "normal"
        for obs in observations:
            content = obs.get("content", "").lower()
            if any(kw in content for kw in ["紧急", "urgent", "critical", "紧急", "立即", "immediately"]):
                urgency = "high"
                break

        completeness = "partial"
        if len(observations) >= 3 and any(o.get("source") == "knowledge_graph" for o in observations):
            completeness = "sufficient"
        elif len(observations) >= 5:
            completeness = "sufficient"
        elif len(observations) == 0:
            completeness = "empty"

        self.analysis = {
            "key_entities": key_entities[:10],
            "entity_types": list(entity_types),
            "urgency": urgency,
            "data_completeness": completeness,
            "observation_count": len(observations),
        }

        result = {
            "analysis": self.analysis,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "orient", "result": result})
        return result

    async def _decide(self, orient_result: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.DECIDE
        analysis = orient_result.get("analysis", {})
        urgency = analysis.get("urgency", "normal")
        completeness = analysis.get("data_completeness", "partial")

        if completeness == "empty":
            decision = "request_more_data"
            reasoning = "No observations available, need more data before proceeding"
            confidence = 0.2
        elif urgency == "high":
            decision = "act_immediately"
            reasoning = "Urgent situation detected, proceeding with available data"
            confidence = 0.7
        elif completeness == "sufficient":
            decision = "proceed"
            reasoning = "Sufficient data available for informed decision"
            confidence = 0.85
        else:
            decision = "proceed_with_caution"
            reasoning = "Partial data available, proceeding with caution"
            confidence = 0.6

        if self.role == "commander":
            if decision == "proceed":
                decision = "proceed_with_strategy"
                reasoning += " (commander review)"
        elif self.role == "operations":
            if decision in ("proceed", "proceed_with_caution"):
                decision = "execute"
                reasoning += " (operations execution)"

        self.decision = {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "analysis": analysis,
        }

        result = {
            "decision": decision,
            "reasoning": reasoning,
            "confidence": confidence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "decide", "result": result})
        return result

    async def _act(self, decide_result: Dict[str, Any]) -> Dict[str, Any]:
        self.current_phase = OODAPhase.ACT
        decision = decide_result.get("decision", "proceed")
        confidence = decide_result.get("confidence", 0.5)

        if decision == "request_more_data":
            action = "gather_intelligence"
            result_status = "pending_data"
        elif decision in ("act_immediately", "execute"):
            action = "execute_task"
            result_status = "executing"
        elif decision in ("proceed", "proceed_with_strategy", "proceed_with_caution"):
            action = "execute_with_monitoring"
            result_status = "in_progress"
        else:
            action = "wait"
            result_status = "idle"

        result = {
            "action": action,
            "result": result_status,
            "confidence": confidence,
            "decision": decision,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.history.append({"phase": "act", "result": result})
        return result
