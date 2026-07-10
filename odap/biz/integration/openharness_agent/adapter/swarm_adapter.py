"""DEPRECATED: This adapter delegates to odap.infra.openharness.*.
Use infra-layer imports directly in new code.

Biz 层 SwarmAdapter — 委托给 infra 层 DomainHarness

提供 RL 风格的 step 接口（reset/step/run_episode），
底层委托给 infra.openharness.tool_adapter.DomainHarness。
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger("swarm_adapter")


def _openharness_audit(action: str, *, result_status: str = "success",
                       result_message: str = "", resource: str = None,
                       details: Dict[str, Any] = None) -> None:
    try:
        from odap.infra.security.audit_helper import storage_audit
        storage_audit(action=action, result_status=result_status,
                      result_message=result_message, resource=resource,
                      details=details or {}, service="integration_openharness")
    except Exception as e:
        logger.warning(f"audit failed: {e}")

try:
    from odap.infra.openharness.tool_adapter import DomainHarness, OPENHARNESS_AVAILABLE
    _SWARM_AVAILABLE = OPENHARNESS_AVAILABLE
except ImportError:
    _SWARM_AVAILABLE = False

try:
    from odap.infra.openharness.engine_adapter import (
        OpenHarnessIntegration,
        get_openharness_integration,
        OPENHARNESS_AVAILABLE,
    )
    _V2_AVAILABLE = OPENHARNESS_AVAILABLE
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
                result = {
                    "status": "success",
                    "swarm_id": swarm_id,
                    "tools_count": len(harness.list_available_tools()),
                }
                _openharness_audit(
                    action="openharness_swarm_create",
                    result_status="success",
                    resource=swarm_id,
                    details={
                        "swarm_id": swarm_id,
                        "user_role": user_role,
                        "tools_count": len(harness.list_available_tools()),
                    },
                )
                return result
            except Exception as e:
                logger.warning("Create swarm failed: %s", e)
                _openharness_audit(
                    action="openharness_swarm_create",
                    result_status="failure",
                    result_message=str(e)[:200],
                    resource=swarm_id,
                    details={"swarm_id": swarm_id, "user_role": user_role},
                )
                return {"status": "error", "message": str(e)}

        self._swarms[swarm_id] = {
            "harness": None,
            "config": config,
            "status": "fallback",
        }
        _openharness_audit(
            action="openharness_swarm_create",
            result_status="success",
            resource=swarm_id,
            details={"swarm_id": swarm_id, "mode": "fallback", "user_role": user_role},
        )
        return {"status": "success", "swarm_id": swarm_id, "mode": "fallback"}

    def dispatch_intent(
        self, swarm_id: str, intent: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        swarm = self._swarms.get(swarm_id)
        if not swarm:
            _openharness_audit(
                action="openharness_intent_dispatch",
                result_status="failure",
                result_message=f"Swarm {swarm_id} not found"[:200],
                resource=swarm_id,
                details={"swarm_id": swarm_id},
            )
            return {"status": "error", "message": f"Swarm {swarm_id} not found"}

        harness = swarm.get("harness")
        if harness and _SWARM_AVAILABLE:
            try:
                obs = harness.reset()
                action = {"tool_name": intent, "action": context or {}}
                observation, reward, done, info = harness.step(action)
                _openharness_audit(
                    action="openharness_intent_dispatch",
                    result_status="success",
                    resource=swarm_id,
                    details={
                        "swarm_id": swarm_id,
                        "intent_len": len(intent or ""),
                        "reward": reward,
                        "done": done,
                        "item_count": 1,
                    },
                )
                return {
                    "status": "success",
                    "swarm_id": swarm_id,
                    "observation": observation,
                    "reward": reward,
                    "done": done,
                    "info": info,
                }
            except Exception as e:
                _openharness_audit(
                    action="openharness_intent_dispatch",
                    result_status="failure",
                    result_message=str(e)[:200],
                    resource=swarm_id,
                    details={"swarm_id": swarm_id},
                )
                return {"status": "error", "message": str(e)}

        _openharness_audit(
            action="openharness_intent_dispatch",
            result_status="success",
            resource=swarm_id,
            details={
                "swarm_id": swarm_id,
                "mode": "fallback",
                "intent_len": len(intent or ""),
            },
        )
        return {
            "status": "fallback",
            "swarm_id": swarm_id,
            "intent": intent,
            "context": context,
        }

    def destroy_swarm(self, swarm_id: str) -> Dict[str, Any]:
        if swarm_id not in self._swarms:
            _openharness_audit(
                action="openharness_swarm_destroy",
                result_status="failure",
                result_message=f"Swarm {swarm_id} not found"[:200],
                resource=swarm_id,
                details={"swarm_id": swarm_id},
            )
            return {"status": "error", "message": f"Swarm {swarm_id} not found"}

        del self._swarms[swarm_id]
        _openharness_audit(
            action="openharness_swarm_destroy",
            result_status="success",
            resource=swarm_id,
            details={"swarm_id": swarm_id},
        )
        return {"status": "success", "swarm_id": swarm_id}
