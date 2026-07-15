"""
TeamAgentSkillAdapter — 多智能体协作引擎的 Skill 包装。

包装 TeamAgentService 的 list_agents / dispatch_task 方法。
"""
import logging
import time
from typing import Any, Optional

from pydantic import Field
from odap.tools.base import SkillInput, SkillOutput

from odap.biz.core.ontology.application.ontology_app_skill import OntologyAppSkill

logger = logging.getLogger(__name__)


class TeamAgentSkillInput(SkillInput):
    action: str = Field(default="list_agents")
    task: Optional[dict] = Field(default=None)


class TeamAgentSkillAdapter(OntologyAppSkill):
    """多智能体协作引擎 skill 包装。"""
    input_schema = TeamAgentSkillInput

    def __init__(
        self,
        workspace_id: str,
        ontology_id: str,
        name: str = "ontology_team_agent_skill",
        description: str = "包装 TeamAgentService，提供 agent 调度能力。",
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            danger_level="low",
            engine_name="team_agent",
        )

    def bind_engine(self, engine: Any) -> None:
        if not hasattr(engine, "list_agents") or not hasattr(engine, "dispatch_task"):
            raise TypeError(
                f"Engine {type(engine).__name__} 缺少 list_agents / dispatch_task 方法"
            )
        self._engine = engine
        self._bound = True

    def execute(self, input_data: SkillInput) -> SkillOutput:
        start = time.perf_counter()
        validated: TeamAgentSkillInput = self.validate_input(input_data.model_dump())
        action = validated.action
        ctx = self._resolve_ctx(validated)
        try:
            if action == "list_agents":
                result = self.engine.list_agents()
            elif action == "dispatch_task":
                task = dict(validated.task or {})
                task["workspace_id"] = ctx["workspace_id"]
                task["ontology_id"] = ctx["ontology_id"]
                result = self.engine.dispatch_task(task)
            else:
                raise ValueError(f"Unknown team_agent action: {action}")

            elapsed = (time.perf_counter() - start) * 1000
            return self._make_output(
                success=result.get("status", "success") != "error",
                data=result,
                elapsed_ms=elapsed,
                input_data=validated,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return self._make_output(
                success=False, data={}, error=str(e), elapsed_ms=elapsed, input_data=validated,
            )


__all__ = ["TeamAgentSkillAdapter", "TeamAgentSkillInput"]
