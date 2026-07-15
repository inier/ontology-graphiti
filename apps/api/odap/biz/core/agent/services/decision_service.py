import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from odap.biz.core.agent.models.decision_chain import DecisionChain, DecisionStep, DecisionPhase

logger = logging.getLogger("decision_service")


class DecisionService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._decisions: Dict[str, DecisionChain] = {}
        self._initialized = True

    def record_step(self, decision_id: str, phase: DecisionPhase, description: str, evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if decision_id not in self._decisions:
            self._decisions[decision_id] = DecisionChain(decision_id=decision_id)

        chain = self._decisions[decision_id]
        step = DecisionStep(
            phase=phase,
            description=description,
            evidence=evidence or [],
        )
        chain.steps.append(step)
        chain.updated_at = datetime.now(timezone.utc)

        return {
            "decision_id": decision_id,
            "step_id": step.step_id,
            "phase": step.phase.value,
            "description": step.description,
            "timestamp": step.timestamp.isoformat(),
        }

    def get_decision(self, decision_id: str) -> Dict[str, Any]:
        chain = self._decisions.get(decision_id)
        if not chain:
            return {"status": "error", "message": f"Decision {decision_id} not found"}

        return {
            "decision_id": chain.decision_id,
            "task_id": chain.task_id,
            "reasoning": chain.reasoning,
            "evidence": chain.evidence,
            "workspace_id": chain.workspace_id,
            "steps_count": len(chain.steps),
            "created_at": chain.created_at.isoformat(),
            "updated_at": chain.updated_at.isoformat(),
        }

    def get_decision_chain(self, decision_id: str) -> Dict[str, Any]:
        chain = self._decisions.get(decision_id)
        if not chain:
            return {"status": "error", "message": f"Decision {decision_id} not found"}

        steps = []
        for step in chain.steps:
            steps.append({
                "step_id": step.step_id,
                "phase": step.phase.value,
                "description": step.description,
                "evidence": step.evidence,
                "timestamp": step.timestamp.isoformat(),
            })

        return {
            "decision_id": chain.decision_id,
            "task_id": chain.task_id,
            "steps": steps,
            "reasoning": chain.reasoning,
            "evidence": chain.evidence,
        }

    def list_decisions(self, workspace_id: Optional[str] = None, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
        decisions = list(self._decisions.values())

        if workspace_id:
            decisions = [d for d in decisions if d.workspace_id == workspace_id]

        decisions.sort(key=lambda d: d.updated_at, reverse=True)

        total = len(decisions)
        start = (page - 1) * page_size
        end = start + page_size

        result = []
        for d in decisions[start:end]:
            result.append({
                "decision_id": d.decision_id,
                "task_id": d.task_id,
                "steps_count": len(d.steps),
                "workspace_id": d.workspace_id,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            })

        return {
            "decisions": result,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def create_decision(self, task_id: str = "", workspace_id: Optional[str] = None, reasoning: str = "", evidence: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        chain = DecisionChain(
            task_id=task_id,
            workspace_id=workspace_id,
            reasoning=reasoning,
            evidence=evidence or [],
        )
        self._decisions[chain.decision_id] = chain

        return {
            "decision_id": chain.decision_id,
            "task_id": chain.task_id,
            "workspace_id": chain.workspace_id,
            "created_at": chain.created_at.isoformat(),
        }
