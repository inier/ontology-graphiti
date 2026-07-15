import logging
import re
import uuid
from typing import Dict, Any, List, Optional

from odap.infra.config_composer import get_config

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

        llm_result = self._explain_with_llm(query, facts)
        if llm_result:
            reasoning_chain = llm_result.get("reasoning_chain", self._build_reasoning_chain(query, facts))
            answer = llm_result.get("answer", self._generate_answer(query, reasoning_chain))
            confidence = llm_result.get("confidence", self._calculate_confidence(reasoning_chain))
        else:
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

    def _explain_with_llm(self, query, facts):
        try:
            import requests
            import json
            api_key = get_config("llm.api_key", "")
            base_url = get_config("llm.api_base", "https://api.openai.com/v1")
            model = get_config("llm.model", "deepseek-ai/deepseek-v4-pro")
            if not api_key:
                return None
            facts_text = "\n".join(f"- {f}" for f in facts) if facts else "无已知事实"
            prompt = f"""基于以下事实，对用户问题进行推理分析，返回JSON格式：
{{"answer": "推理结论", "confidence": 0.0-1.0, "reasoning_chain": [{{"step_type": "premise|inference", "description": "步骤描述", "confidence": 0.0-1.0}}]}}

用户问题：{query}
已知事实：
{facts_text}

仅返回JSON，不要其他内容。"""
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 512},
                timeout=10,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                chain = []
                for step in parsed.get("reasoning_chain", []):
                    chain.append({
                        "step_id": str(uuid.uuid4()),
                        "step_type": step.get("step_type", "inference"),
                        "description": step.get("description", ""),
                        "confidence": step.get("confidence", 0.7),
                    })
                return {
                    "answer": parsed.get("answer", ""),
                    "confidence": min(1.0, parsed.get("confidence", 0.5)),
                    "reasoning_chain": chain,
                }
        except Exception:
            return None

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
            if "传感器" in fact:
                sources.append("sensor_system")
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
