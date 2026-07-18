"""Swarm Manager — OH-native multi-agent coordination.

Phase A: Bridges to existing SwarmAdapter for 3-agent (Commander/Intelligence/Operations)
coordination, using OH's TeamLifecycleManager instead of home-made OODA loop.

Phase B/C: Becomes the primary multi-agent orchestration layer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Agent role prompts (from existing DomainSwarm, consolidated) ───────────────

COMMANDER_PROMPT = """You are the Commander Agent of the ODAP platform.

Your role is the decision-making center. You:
1. Receive user requests and understand their intent
2. Delegate tasks to Intelligence (analysis) and Operations (execution) agents
3. Synthesize their outputs into a coherent final response
4. Make the final call on any write operations (create/update/delete)

Decision rules:
- Read-only queries → delegate to Intelligence
- Ontology modifications → delegate to Operations after Intelligence analysis
- Complex multi-step tasks → orchestrate both agents sequentially
- Simple questions → answer directly

Always verify with Intelligence before authorizing write operations.
"""

INTELLIGENCE_PROMPT = """You are the Intelligence Agent of the ODAP platform.

Your role is Observe + Orient:
1. Query the knowledge graph to gather relevant information
2. Analyze data patterns, identify anomalies, check completeness
3. Provide structured analysis results to the Commander
4. Suggest possible interpretations and implications

Your tools:
- qa_retrieve — Full RAG retrieval (BM25 + vector + graph)
- list_entities, search_entities — Entity queries
- query_relations — Graph traversal
- query_temporal — Time-based queries
- get_ontology_context — Current ontology state
- suggest_properties, suggest_relations — Design suggestions
- check_completeness — Completeness analysis

DO NOT perform write operations. Report findings clearly with data.
"""

OPERATIONS_PROMPT = """You are the Operations Agent of the ODAP platform.

Your role is Act:
1. Execute ontology modifications (create/update/delete types, properties, links)
2. Perform batch operations efficiently
3. Report execution results with confirmation details
4. Support undo/rollback when possible

Your tools:
- create_object_type, delete_object_type — Type management
- add_property, update_property, remove_property — Property management
- add_properties — Batch property creation
- create_link_type, delete_link_type — Relationship management

Rules:
- Always confirm what you're about to change before executing
- Use add_properties for batch operations (not repeated add_property)
- Report exactly what was created/modified/deleted
- If a write fails, suggest corrective action
"""


class SwarmManager:
    """OH-native multi-agent coordinator using SwarmAdapter.

    Replaces the home-made OODA loop in DomainSwarm with OH's
    InProcessBackend + TeamLifecycleManager.
    """

    def __init__(self):
        self._swarm_adapter = None
        self._initialized = False

    @property
    def swarm_adapter(self):
        if self._swarm_adapter is None:
            try:
                from odap.infra.openharness.swarm_adapter import SwarmAdapter
                self._swarm_adapter = SwarmAdapter()
            except Exception as e:
                logger.warning("SwarmManager: SwarmAdapter init failed: %s", e)
                self._swarm_adapter = None
        return self._swarm_adapter

    async def initialize(self) -> bool:
        """Initialize the three-agent Swarm team."""
        if self._initialized:
            return True

        adapter = self.swarm_adapter
        if adapter is None or not adapter.available:
            logger.info("SwarmManager: SwarmAdapter not available, skipping swarm init")
            return False

        try:
            agents = [
                {
                    "name": "commander",
                    "role": "commander",
                    "system_prompt": COMMANDER_PROMPT,
                    "type": "director",
                },
                {
                    "name": "intelligence",
                    "role": "intelligence",
                    "system_prompt": INTELLIGENCE_PROMPT,
                    "type": "analyst",
                },
                {
                    "name": "operations",
                    "role": "operations",
                    "system_prompt": OPERATIONS_PROMPT,
                    "type": "executor",
                },
            ]

            result = await adapter.create_swarm(
                agents=agents,
                config={"team_name": "odap", "mode": "hierarchical"},
            )

            if result.get("status") == "ok":
                self._initialized = True
                logger.info("SwarmManager: 3-agent swarm initialized successfully")
                return True
            else:
                logger.warning("SwarmManager: swarm creation failed: %s", result.get("message"))
                return False

        except Exception as e:
            logger.exception("SwarmManager: swarm initialization failed")
            return False

    async def run_with_swarm(
        self, user_input: str, context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Run a task through the Swarm team.

        In Phase A, this delegates to the SwarmAdapter for multi-agent execution.
        In Phase B/C, this becomes the primary execution path.
        """
        if not self._initialized:
            await self.initialize()

        adapter = self.swarm_adapter
        if adapter is None or not adapter.available:
            return {
                "status": "fallback",
                "message": "Swarm not available, use direct QueryEngine",
            }

        try:
            result = await adapter.run_task(
                team_name="odap",
                task=user_input,
                context=context,
            )
            return {"status": "ok", "result": result}
        except Exception as e:
            logger.exception("SwarmManager: task execution failed")
            return {"status": "error", "message": str(e)}

    def is_available(self) -> bool:
        """Check if Swarm coordination is available."""
        adapter = self.swarm_adapter
        return adapter is not None and adapter.available


# ── Singleton ──

_swarm_manager: Optional[SwarmManager] = None


def get_swarm_manager() -> SwarmManager:
    """Get or create the SwarmManager singleton."""
    global _swarm_manager
    if _swarm_manager is None:
        _swarm_manager = SwarmManager()
    return _swarm_manager


__all__ = [
    "SwarmManager",
    "get_swarm_manager",
    "COMMANDER_PROMPT",
    "INTELLIGENCE_PROMPT",
    "OPERATIONS_PROMPT",
]
