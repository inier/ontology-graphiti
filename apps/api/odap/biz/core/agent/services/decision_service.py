"""Agent 决策链（ReAct 步骤留痕）进程内缓冲

定位（ADR-091 §2.2 / §3.8）：
- 本模块的 dict **只作未落库步骤缓冲**，不承担任何决策读取职责
  （台账/详情统一走 `decision_record` + `decision_hub`）
- 对外方法一律要求 `workspace_id` 入参并做归属校验，不匹配按"不存在"处理；
  **不再提供"空 workspace 即不过滤"的分支**——那是原跨空间泄露（G6）的根因
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.core.agent.models.decision_chain import DecisionChain, DecisionPhase, DecisionStep

logger = logging.getLogger("decision_service")


class DecisionScopeError(LookupError):
    """决策不存在，或不属于调用者所在工作空间（两者不区分，不泄漏存在性）。"""


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

    # ---------------- 归属校验 ----------------

    def _owned(self, decision_id: str, workspace_id: str) -> DecisionChain:
        """取决策链并校验归属；`workspace_id` 为空即拒绝（fail-closed）。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")
        chain = self._decisions.get(decision_id)
        if chain is None or chain.workspace_id != workspace_id:
            raise DecisionScopeError(f"Decision {decision_id} not found in workspace")
        return chain

    # ---------------- 写 ----------------

    def record_step(
        self,
        decision_id: str,
        phase: DecisionPhase,
        description: str,
        workspace_id: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """追加 ReAct 步骤。链已存在时校验归属，不存在时以调用者空间建档。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")
        chain = self._decisions.get(decision_id)
        if chain is None:
            chain = DecisionChain(decision_id=decision_id, workspace_id=workspace_id)
            self._decisions[decision_id] = chain
        elif chain.workspace_id != workspace_id:
            raise DecisionScopeError(f"Decision {decision_id} not found in workspace")

        step = DecisionStep(phase=phase, description=description, evidence=evidence or [])
        chain.steps.append(step)
        chain.updated_at = datetime.now(timezone.utc)
        return {
            "decision_id": decision_id,
            "step_id": step.step_id,
            "phase": step.phase.value,
            "description": step.description,
            "timestamp": step.timestamp.isoformat(),
        }

    def create_decision(
        self,
        workspace_id: str,
        task_id: str = "",
        reasoning: str = "",
        evidence: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """建立决策链（空间必填，不接受客户端任意指定）。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")
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

    # ---------------- 读（均需归属校验） ----------------

    def get_decision(self, decision_id: str, workspace_id: str) -> Dict[str, Any]:
        chain = self._owned(decision_id, workspace_id)
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

    def get_decision_chain(self, decision_id: str, workspace_id: str) -> Dict[str, Any]:
        chain = self._owned(decision_id, workspace_id)
        steps = [
            {
                "step_id": step.step_id,
                "phase": step.phase.value,
                "description": step.description,
                "evidence": step.evidence,
                "timestamp": step.timestamp.isoformat(),
            }
            for step in chain.steps
        ]
        return {
            "decision_id": chain.decision_id,
            "task_id": chain.task_id,
            "steps": steps,
            "reasoning": chain.reasoning,
            "evidence": chain.evidence,
        }

    def list_decisions(
        self, workspace_id: str, page: int = 1, page_size: int = 10
    ) -> Dict[str, Any]:
        """空间内列表（空 workspace 直接拒绝，不存在"空即全量"分支）。"""
        if not workspace_id:
            raise ValueError("workspace_id 禁止为空（ADR-076 隔离规则）")
        decisions = [d for d in self._decisions.values() if d.workspace_id == workspace_id]
        decisions.sort(key=lambda d: d.updated_at, reverse=True)
        start = (page - 1) * page_size
        rows = [
            {
                "decision_id": d.decision_id,
                "task_id": d.task_id,
                "steps_count": len(d.steps),
                "workspace_id": d.workspace_id,
                "created_at": d.created_at.isoformat(),
                "updated_at": d.updated_at.isoformat(),
            }
            for d in decisions[start : start + page_size]
        ]
        return {"decisions": rows, "total": len(decisions), "page": page, "page_size": page_size}
