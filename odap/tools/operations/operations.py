"""
执行技能模块
实现领域执行相关功能

Category: operations
Danger Level: high (攻击/指挥操作需要 OPA 权限校验)
"""

import sys
import os

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.graph import GraphManager
from odap.infra.opa import OPAManager

# 初始化图谱管理器和OPA管理器
manager = GraphManager()
opa_manager = OPAManager()

# 攻击目标
def attack_target(target_id, user_role):
    """
    攻击目标

    Args:
        target_id: 目标ID
        user_role: 用户角色

    Returns:
        攻击结果
    """
    # 通过 manager 统一接口查询，兼容 Neo4j / Graphiti / fallback
    target = None
    for entity in manager.query_entities():
        if entity["id"] == target_id:
            target = entity
            break

    if not target:
        # Fail-close: 目标不存在时也拒绝，避免绕过权限检查
        return {"status": "denied", "message": "目标不存在或无法确认目标身份"}

    # 检查权限（传入 target 的完整信息供 OPA 判断）
    allowed = opa_manager.check_permission(user_role, "attack", target)
    if not allowed:
        return {"status": "denied", "message": "权限不足或违反策略"}

    # 执行攻击
    result = {
        "status": "success",
        "message": f"成功攻击目标: {target['properties'].get('name', target_id)}",
        "target": target,
        "user_role": user_role
    }

    return result

# 指挥部队
def command_unit(unit_id, command, user_role):
    """
    指挥部队

    Args:
        unit_id: 部队ID
        command: 命令
        user_role: 用户角色

    Returns:
        指挥结果
    """
    # 通过 manager 统一接口查询
    unit = None
    for entity in manager.query_entities():
        if entity["id"] == unit_id:
            unit = entity
            break

    if not unit:
        return {"status": "denied", "message": "部队不存在或无法确认目标身份"}

    # 检查权限
    allowed = opa_manager.check_permission(user_role, "command", unit)
    if not allowed:
        return {"status": "denied", "message": "权限不足"}

    # 执行命令
    result = {
        "status": "success",
        "message": f"成功指挥部队: {unit['properties'].get('name', unit_id)}",
        "command": command,
        "unit": unit,
        "user_role": user_role
    }

    return result

# 注册技能
register_skill(
    name="attack_target",
    description="攻击目标",
    handler=attack_target,
    category="operations"
)

register_skill(
    name="command_unit",
    description="指挥部队",
    handler=command_unit,
    category="operations"
)