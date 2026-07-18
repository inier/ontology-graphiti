"""Unified Chat Service — OpenHarness-native engine (ADR-051).

Single execution path:
  POST /api/chat/message -> chat() -> _oh_chat()
    -> OHQueryEngineFactory -> QueryEngine.submit_message()
    -> Agent Loop with 17 tools (16 BaseTools + QARetrieverTool)
    -> AG-UI SSE stream

Integrated capabilities:
  .md Skills  -> _load_skills() loads skills/*.md into system prompt
  Ontology    -> _ontology_context() auto-injects type/relation summary
  Swarm       -> SwarmManager available as future tool (not inline routing)
  Memory      -> OH auto_compact via create_engine(max_turns=8)
  Resilience  -> 5-layer: HealthGate/CircuitBreaker/Retry/ToolIsolation/Metrics

No branching. No fallback. One path through OpenHarness.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ChatRequest:
    message: str
    session_id: Optional[str] = None
    ontology_id: Optional[str] = None
    workspace_id: str = "default"
    user_id: str = "anonymous"
    context: Dict[str, Any] = field(default_factory=dict)
    persona: str = "assistant"
    scenario_id: Optional[str] = None
    agent_id: Optional[str] = None


def _ev_run_start(run_id: str) -> dict: return {"type": "RUN_STARTED", "run_id": run_id}
def _ev_run_end(run_id: str) -> dict: return {"type": "RUN_FINISHED", "run_id": run_id}
def _ev_text_start(mid: str) -> dict: return {"type": "TEXT_MESSAGE_START", "message_id": mid}
def _ev_text(mid: str, delta: str) -> dict: return {"type": "TEXT_MESSAGE_CONTENT", "message_id": mid, "delta": delta}
def _ev_text_end(mid: str) -> dict: return {"type": "TEXT_MESSAGE_END", "message_id": mid}


# ---- .md Skills loader ----

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "skills")
_SKILL_CACHE: Dict[str, str] = {}

_PERSONA_SKILLS = {
    "ontology-designer": ["ontology-designer", "graph-query"],
    "qa":               ["graph-query", "data-analyst", "platform-manual"],
    "assistant":        ["platform-manual"],
}


def _load_skill(name: str) -> str:
    if name in _SKILL_CACHE:
        return _SKILL_CACHE[name]
    path = os.path.join(_SKILLS_DIR, f"{name}.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        _SKILL_CACHE[name] = content
        return content
    except FileNotFoundError:
        logger.warning("Skill not found: %s", path)
        return ""


def _load_skills(persona: str, ontology_id: str = None) -> str:
    names = _PERSONA_SKILLS.get(persona, ["platform-manual"])
    parts = []
    for n in names:
        c = _load_skill(n)
        if c:
            parts.append(f"# {n}\n{c}")
    if ontology_id:
        ctx = _ontology_context(ontology_id)
        if ctx:
            parts.insert(0, ctx)
    return "\n\n".join(parts)


def _ontology_context(ontology_id: str) -> str:
    try:
        from odap.biz.core.assistant.plugins.ai_assistant.registry import get_ontology_context
        r = get_ontology_context(ontology_id)
        if r.get("status") != "success":
            return ""
        ctx = r.get("context", {})
        types = ctx.get("object_types", [])
        links = ctx.get("link_types", [])
        lines = [
            f"[Current Ontology: {ontology_id}]",
            f"Object types ({ctx.get('object_type_count', 0)}): "
            + ", ".join(t.get("name", "?") for t in types[:15]),
        ]
        if links:
            lines.append(
                f"Link types ({ctx.get('link_type_count', 0)}): "
                + ", ".join(l.get("name", "?") for l in links[:10])
            )
        return "\n".join(lines)
    except Exception:
        return ""


# ---- UnifiedChatService ----

class UnifiedChatService:
    """OpenHarness-native chat engine with all OH capabilities wired."""

    def __init__(self):
        self._oh_factory = None
        self._qa_retriever_tool = None
        self._swarm_manager = None
        self._resilience = None

    @property
    def oh_factory(self):
        if self._oh_factory is None:
            from odap.infra.openharness.engine_adapter import OHQueryEngineFactory
            self._oh_factory = OHQueryEngineFactory.get_instance()
        return self._oh_factory

    @property
    def qa_retriever_tool(self):
        if self._qa_retriever_tool is None:
            from odap.biz.core.chat.tools.qa_retriever_tool import get_qa_retriever_tool
            self._qa_retriever_tool = get_qa_retriever_tool()
        return self._qa_retriever_tool

    @property
    def swarm_manager(self):
        if self._swarm_manager is None:
            from odap.biz.core.chat.engine.swarm_manager import get_swarm_manager
            self._swarm_manager = get_swarm_manager()
        return self._swarm_manager

    @property
    def resilience(self):
        if self._resilience is None:
            from odap.biz.core.chat.engine.resilience_manager import get_chat_resilience
            self._resilience = get_chat_resilience()
        return self._resilience

    async def chat(self, request: ChatRequest) -> AsyncGenerator[dict, None]:
        rid = f"run_{uuid.uuid4().hex[:12]}"
        mid = f"msg_{uuid.uuid4().hex[:12]}"
        yield _ev_run_start(rid)
        yield _ev_text_start(mid)

        if not await self.resilience.ensure_ready():
            yield _ev_text(mid, "AI service not ready. Check /api/chat/health.")
            yield _ev_text_end(mid); yield _ev_run_end(rid); return

        factory = self.oh_factory
        if factory is None or not factory._initialized:
            yield _ev_text(mid, "AI engine not initialized. Check LLM API key.")
            yield _ev_text_end(mid); yield _ev_run_end(rid); return

        self._register_qa_tool(factory)

        try:
            from odap.infra.resilience.circuit_breaker import CircuitOpenError
            async for ev in self._oh_chat(factory, request, rid, mid):
                yield ev
        except CircuitOpenError:
            yield _ev_text(mid, "LLM temporarily unavailable (circuit open). Retry in ~60s.")
        except Exception as exc:
            logger.exception("UnifiedChat failed")
            yield _ev_text(mid, f"Error: {exc}")

        yield _ev_text_end(mid)
        yield _ev_run_end(rid)

    def _register_qa_tool(self, factory) -> None:
        try:
            qt = self.qa_retriever_tool
            if qt and factory._tool_registry and not factory._tool_registry.get(qt.name):
                factory._tool_registry.register(qt)
        except Exception as e:
            logger.warning("QARetrieverTool: %s", e)

    async def _oh_chat(self, factory, request, rid, mid) -> AsyncGenerator[dict, None]:
        from odap.infra.openharness.agui.web_channel import (
            _stream_agui_events, _map_agui_event_for_frontend, RunAgentInput,
        )
        sp = self._build_prompt(request.persona, request.ontology_id)
        inp = RunAgentInput(
            run_id=rid,
            messages=[{"role": "user", "content": request.message}],
            tools=[],
            context={
                "ontology_id": request.ontology_id,
                "workspace_id": request.workspace_id,
                "persona": request.persona,
                "system_prompt_override": sp,
            },
        )
        async for ev in _stream_agui_events(
            inp, user_id=request.user_id,
            ontology_id=request.ontology_id,
            workspace_id=request.workspace_id,
        ):
            m = _map_agui_event_for_frontend(ev)
            if m:
                yield m

    def _build_prompt(self, persona: str, ontology_id: str = None) -> str:
        from odap.biz.core.chat.engine.swarm_manager import COMMANDER_PROMPT
        parts = [COMMANDER_PROMPT]
        skills = _load_skills(persona, ontology_id)
        if skills:
            parts.append(skills)
        if ontology_id and "[Current Ontology" not in skills:
            ctx = _ontology_context(ontology_id)
            if ctx:
                parts.append(ctx)
        parts.append(
            "Tools: 16 ontology tools + qa_retrieve for RAG. Use proactively."
        )
        return "\n\n".join(parts)

    async def execute_tool(self, name: str, args: dict) -> dict:
        from odap.biz.core.chat.tools import execute_tool_async
        return await self.resilience.tool_resilience.execute_safely(
            name, execute_tool_async, name, args)

    def health(self) -> dict:
        return self.resilience.health_summary()


async def verify_chat_service() -> dict:
    from odap.biz.core.chat.engine.resilience_manager import get_chat_resilience
    r = get_chat_resilience()
    ok = await r.ensure_ready()
    for p in ["assistant", "qa", "ontology-designer"]:
        _load_skills(p)
    return {"service": "unified-chat", "ready": ok, "details": r.health_summary()}
