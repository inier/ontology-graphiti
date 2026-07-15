import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

WRITE_TOOLS = frozenset({
    "write_entity",
    "write_relation",
    "write_episode",
    "add_entity",
    "add_relationship",
    "delete_entity",
    "delete_relationship",
})


class QueryServiceWriteGuard:
    """
    Agent 写操作安全守卫
    通过 OpenHarness PreToolUse Hook 拦截写操作，调用 OPA 校验

    设计原则 (Agent Safe):
    - 查询工具默认只读，无需校验
    - 写操作需显式启用，经过 OPA 策略校验
    - OPA 不可用时 fail-closed（拒绝写操作）
    """

    def __init__(self, opa_backend=None):
        self._opa_backend = opa_backend

    def _get_opa_backend(self):
        if self._opa_backend is None:
            try:
                from odap.infra.opa.opa_manager import OPAManager
                self._opa_backend = OPAManager()
            except Exception:
                logger.warning("OPA Manager 不可用，写操作将被拒绝 (fail-closed)")
        return self._opa_backend

    async def execute(self, tool_name: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        执行安全检查

        Args:
            tool_name: 工具名称
            arguments: 工具参数
            context: 执行上下文（含 user_role, workspace_id 等）

        Returns:
            True 允许执行，False 拒绝执行
        """
        if tool_name not in WRITE_TOOLS:
            return True

        user_role = context.get("user_role", "guest")
        workspace_id = context.get("workspace_id", "default")

        opa = self._get_opa_backend()
        if opa is None:
            logger.warning(
                f"OPA 不可用，拒绝写操作: tool={tool_name}, role={user_role}, workspace={workspace_id}"
            )
            return False

        try:
            result = await opa.check(
                f"policies.agent_write.{tool_name}.allow",
                {
                    "action": tool_name,
                    "resource": arguments,
                    "subject": {"role": user_role},
                    "workspace_id": workspace_id,
                },
            )
            if not result:
                logger.warning(
                    f"OPA denied write: tool={tool_name}, role={user_role}, workspace={workspace_id}"
                )
            return result
        except Exception as e:
            logger.error(f"OPA check error: {e}, fail-closed denying write operation")
            return False


class QueryServiceToolRegistry:
    """
    QueryService 工具注册表
    将 QueryService 的查询能力注册为 OpenHarness 可用的工具

    工具分类:
    - read: 只读查询工具，无需 OPA 校验
    - write: 写操作工具，需 OPA 校验
    """

    READ_TOOLS = {
        "query_schema": {
            "description": "查询本体类型定义（实体类型、关系类型、动作类型）",
            "parameters": {
                "query": {"type": "string", "description": "查询表达式，如 with(type='Unit')"},
                "workspace_id": {"type": "string", "description": "工作空间ID", "default": "default"},
            },
            "safety": "read",
        },
        "query_entity": {
            "description": "查询运行时实体",
            "parameters": {
                "query": {"type": "string", "description": "查询表达式，如 with(type='MilitaryUnit')"},
                "workspace_id": {"type": "string", "description": "工作空间ID", "default": "default"},
                "limit": {"type": "integer", "description": "返回数量限制", "default": 20},
            },
            "safety": "read",
        },
        "query_topo": {
            "description": "查询拓扑关系和图遍历",
            "parameters": {
                "entity_id": {"type": "string", "description": "起始实体ID"},
                "depth": {"type": "integer", "description": "遍历深度", "default": 2},
                "direction": {"type": "string", "description": "遍历方向 (out/in/both)", "default": "both"},
                "workspace_id": {"type": "string", "description": "工作空间ID", "default": "default"},
            },
            "safety": "read",
        },
        "query_temporal": {
            "description": "查询时态数据（历史版本、双时态查询）",
            "parameters": {
                "entity_id": {"type": "string", "description": "实体ID"},
                "valid_time": {"type": "string", "description": "有效时间"},
                "workspace_id": {"type": "string", "description": "工作空间ID", "default": "default"},
            },
            "safety": "read",
        },
    }

    WRITE_TOOLS = {
        "write_entity": {
            "description": "写入/更新实体（需 OPA 审批）",
            "parameters": {
                "entity_id": {"type": "string", "description": "实体ID"},
                "entity_type": {"type": "string", "description": "实体类型"},
                "properties": {"type": "object", "description": "实体属性"},
                "workspace_id": {"type": "string", "description": "工作空间ID", "default": "default"},
            },
            "safety": "write",
            "requires_confirmation": True,
        },
        "write_relation": {
            "description": "写入/更新关系（需 OPA 审批）",
            "parameters": {
                "source_id": {"type": "string", "description": "源实体ID"},
                "target_id": {"type": "string", "description": "目标实体ID"},
                "relation_type": {"type": "string", "description": "关系类型"},
                "properties": {"type": "object", "description": "关系属性"},
                "workspace_id": {"type": "string", "description": "工作空间ID", "default": "default"},
            },
            "safety": "write",
            "requires_confirmation": True,
        },
    }

    @classmethod
    def all_tools(cls) -> Dict[str, Dict[str, Any]]:
        return {**cls.READ_TOOLS, **cls.WRITE_TOOLS}

    @classmethod
    def read_tools(cls) -> Dict[str, Dict[str, Any]]:
        return dict(cls.READ_TOOLS)

    @classmethod
    def write_tools(cls) -> Dict[str, Dict[str, Any]]:
        return dict(cls.WRITE_TOOLS)

    @classmethod
    def is_write_tool(cls, tool_name: str) -> bool:
        return tool_name in cls.WRITE_TOOLS or tool_name in WRITE_TOOLS
