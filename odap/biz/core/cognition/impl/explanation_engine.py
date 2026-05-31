import logging
import uuid
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ExplanationEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._explanations: Dict[str, Dict[str, Any]] = {}
        self._initialized = True

    def explain(self, decision_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = context or {}
        facts = context.get("facts", [])
        query = context.get("query", f"解释决策 {decision_id}")

        reasoning_chain = self._build_reasoning_chain(query, facts)
        answer = self._generate_answer(query, reasoning_chain)
        confidence = self._calculate_confidence(reasoning_chain)
        sources = self._identify_sources(facts)

        explanation = {
            "explanation_id": str(uuid.uuid4()),
            "decision_id": decision_id,
            "query": query,
            "answer": answer,
            "confidence": confidence,
            "reasoning_chain": reasoning_chain,
            "sources": sources,
            "alternative_explanations": self._generate_alternatives(query, facts),
        }
        self._explanations[explanation["explanation_id"]] = explanation
        return explanation

    def _build_reasoning_chain(self, query: str, facts: List[str]) -> List[Dict[str, Any]]:
        chain = []
        for i, fact in enumerate(facts[:5]):
            chain.append({
                "step_id": str(uuid.uuid4()),
                "step_type": "premise",
                "description": fact,
                "confidence": 0.9,
            })
        if facts:
            conclusion = f"基于 {len(facts)} 个事实推导"
            chain.append({
                "step_id": str(uuid.uuid4()),
                "step_type": "inference",
                "description": conclusion,
                "confidence": 0.85,
            })
        return chain

    def _generate_answer(self, query: str, chain: List[Dict[str, Any]]) -> str:
        if not chain:
            return "没有足够的信息来解释该决策"
        inference_steps = [s for s in chain if s["step_type"] == "inference"]
        if inference_steps:
            return inference_steps[-1]["description"]
        return f"基于 {len(chain)} 个推理步骤得出的结论"

    def _calculate_confidence(self, chain: List[Dict[str, Any]]) -> float:
        if not chain:
            return 0.0
        total = sum(s.get("confidence", 1.0) for s in chain)
        return min(1.0, total / len(chain))

    def _identify_sources(self, facts: List[str]) -> List[str]:
        sources = []
        for fact in facts:
            if "雷达" in fact:
                sources.append("radar_system")
            elif "目标" in fact:
                sources.append("target_tracking")
            elif "威胁" in fact:
                sources.append("threat_analysis")
        return list(set(sources)) if sources else ["knowledge_base"]

    def _generate_alternatives(self, query: str, facts: List[str]) -> List[str]:
        alternatives = []
        if len(facts) > 1:
            alternatives.append("如果只考虑部分因素，结论可能会不同")
        alternatives.append("在不同的上下文中，可能会得出不同的结论")
        return alternatives

    def get_explanation(self, explanation_id: str) -> Optional[Dict[str, Any]]:
        return self._explanations.get(explanation_id)
