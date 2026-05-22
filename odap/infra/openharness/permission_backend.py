import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class OPAPermissionBackend:
    """OpenHarness 权限后端 - 使用 OPA 策略引擎"""

    POLICY_MAP = {
        "attack_target": "policies.attack.allow",
        "command_unit": "policies.operations.allow",
        "move": "policies.operations.allow",
        "defend": "policies.operations.allow",
        "retreat": "policies.operations.allow",
        "reinforce": "policies.operations.allow",
        "radar_search": "policies.intelligence.allow",
        "view_intelligence": "policies.intelligence.allow",
        "analyze_data": "policies.intelligence.allow",
        "generate_reports": "policies.intelligence.allow",
        "observe": "policies.intelligence.allow",
    }

    DEFAULT_POLICY = "policies.common.default"

    def __init__(self, opa_manager=None):
        self._opa_manager = opa_manager

    @property
    def opa(self):
        if self._opa_manager is None:
            try:
                from odap.infra.opa.opa_service_v2 import OPAManagerV2
                self._opa_manager = OPAManagerV2()
            except Exception as e:
                logger.warning(f"OPAPermissionBackend: OPA manager init failed: {e}")
                self._opa_manager = None
        return self._opa_manager

    async def check(self, tool_name: str, tool_input: dict, context: dict) -> bool:
        policy = self.POLICY_MAP.get(tool_name, self.DEFAULT_POLICY)

        input_data = {
            "action": tool_name,
            "tool_input": tool_input,
            "user": {
                "role": context.get("user_role", context.get("role", "unknown")),
                "id": context.get("user_id", context.get("agent_id", "")),
            },
            "target": context.get("target", {}),
            "weapon": context.get("weapon", {}),
        }

        if self.opa is None:
            logger.warning(f"OPAPermissionBackend: OPA unavailable, fail-closed for {tool_name}")
            return False

        try:
            result = self.opa.check_permission_abac(
                user=context.get("user_role", "unknown"),
                action=tool_name,
                resource=context.get("target", {}),
                environment=context.get("environment", {}),
            )
            return result.get("allow", False)
        except Exception as e:
            logger.error(f"OPAPermissionBackend check failed (fail-closed): {e}")
            return False

    async def check_and_raise(self, tool_name: str, tool_input: dict, context: dict):
        if not await self.check(tool_name, tool_input, context):
            raise PermissionDeniedError(
                tool=tool_name,
                context=context,
            )


class PermissionDeniedError(Exception):
    def __init__(self, tool: str, context: dict):
        self.tool = tool
        self.context = context
        super().__init__(f"Permission denied for tool: {tool}")
