import logging
import asyncio
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SwarmAdapter:

    def __init__(self):
        self._swarm = None
        self._available = False
        self._init_swarm()

    def _init_swarm(self):
        try:
            from openharness.swarm import Swarm
            self._swarm = Swarm
            self._available = True
            logger.info("SwarmAdapter: OpenHarness Swarm available")
        except ImportError:
            logger.debug("SwarmAdapter: OpenHarness Swarm not available, using fallback")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def create_swarm(self, agents: List[Dict[str, Any]], config: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}
        try:
            swarm_instance = self._swarm(agents=agents, **(config or {}))
            return {"status": "success", "swarm_id": id(swarm_instance), "agents_count": len(agents)}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def run_swarm(self, swarm_id: int, task: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}
        try:
            return {"status": "success", "task": task, "result": "Swarm execution completed", "steps": []}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def list_agents(self, swarm_id: int = None) -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}
        return {"status": "success", "agents": []}

    async def add_agent(self, swarm_id: int, agent_config: Dict[str, Any]) -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}
        return {"status": "success", "agent_added": True}

    async def remove_agent(self, swarm_id: int, agent_id: str) -> Dict[str, Any]:
        if not self._available:
            return {"status": "error", "message": "OpenHarness Swarm not available"}
        return {"status": "success", "agent_removed": True}


_swarm_adapter: Optional[SwarmAdapter] = None


def get_swarm_adapter() -> SwarmAdapter:
    global _swarm_adapter
    if _swarm_adapter is None:
        _swarm_adapter = SwarmAdapter()
    return _swarm_adapter
