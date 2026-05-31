import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("swarm_adapter")

try:
    from odap.infra.openharness.tool_adapter import DomainHarness, OPENHARNESS_AVAILABLE
    _SWARM_AVAILABLE = OPENHARNESS_AVAILABLE
except ImportError:
    _SWARM_AVAILABLE = False

try:
    from odap.infra.openharness.v2_adapter import (
        OpenHarnessIntegration,
        get_openharness_integration,
        OPENHARNESS_V2_AVAILABLE,
    )
    _V2_AVAILABLE = OPENHARNESS_V2_AVAILABLE
except ImportError:
    _V2_AVAILABLE = False


class SwarmAdapter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._swarms: Dict[str, Any] = {}
        self._initialized = True

    def create_swarm(self, config: Dict[str, Any]) -> Dict[str, Any]:
        swarm_id = config.get("swarm_id", str(uuid.uuid4()))
        user_role = config.get("user_role", "intelligence_analyst")

        if _SWARM_AVAILABLE:
            try:
                harness = DomainHarness(user_role=user_role)
                self._swarms[swarm_id] = {
                    "harness": harness,
                    "config": config,
                    "status": "active",
                }
                return {
                    "status": "success",
                    "swarm_id": swarm_id,
                    "tools_count": len(harness.list_available_tools()),
                }
            except Exception as e:
                logger.warning("Create swarm failed: %s", e)
                return {"status": "error", "message": str(e)}

        self._swarms[swarm_id] = {
            "harness": None,
            "config": config,
            "status": "fallback",
        }
        return {"status": "success", "swarm_id": swarm_id, "mode": "fallback"}

    def dispatch_intent(
        self, swarm_id: str, intent: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        swarm = self._swarms.get(swarm_id)
        if not swarm:
            return {"status": "error", "message": f"Swarm {swarm_id} not found"}

        harness = swarm.get("harness")
        if harness and _SWARM_AVAILABLE:
            try:
                obs = harness.reset()
                action = {"tool_name": intent, "action": context or {}}
                observation, reward, done, info = harness.step(action)
                return {
                    "status": "success",
                    "swarm_id": swarm_id,
                    "observation": observation,
                    "reward": reward,
                    "done": done,
                    "info": info,
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "fallback",
            "swarm_id": swarm_id,
            "intent": intent,
            "context": context,
        }

    def get_swarm_status(self, swarm_id: str) -> Dict[str, Any]:
        swarm = self._swarms.get(swarm_id)
        if not swarm:
            return {"status": "error", "message": f"Swarm {swarm_id} not found"}

        return {
            "status": "success",
            "swarm_id": swarm_id,
            "swarm_status": swarm.get("status"),
            "config": swarm.get("config"),
        }

    def destroy_swarm(self, swarm_id: str) -> Dict[str, Any]:
        if swarm_id not in self._swarms:
            return {"status": "error", "message": f"Swarm {swarm_id} not found"}

        del self._swarms[swarm_id]
        return {"status": "success", "swarm_id": swarm_id}
