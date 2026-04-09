"""
作战技能模块
实现战场作战相关功能
"""

import sys
import os

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import register_skill
from core.graph_manager import BattlefieldGraphManager
from core.opa_manager import OPAManager

# 初始化图谱管理器和OPA管理器
manager = BattlefieldGraphManager()
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
    # 获取图谱数据
    graph = manager.fallback_graph if hasattr(manager, 'fallback_graph') and manager.fallback_graph else None

    target = None
    if graph:
        for node_id in graph.nodes:
            if node_id == target_id:
                node_data = graph.nodes[node_id]
                target = {
                    "id": node_id,
                    "type": node_data.get("entity_type"),
                    "properties": {k: v for k, v in node_data.items() if k != "entity_type"}
                }
                break

    if not target:
        return {"status": "error", "message": "目标不存在"}

    # 检查权限
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
    # 获取图谱数据
    graph = manager.fallback_graph if hasattr(manager, 'fallback_graph') and manager.fallback_graph else None

    unit = None
    if graph:
        for node_id, node_data in graph.nodes(data=True):
            if node_id == unit_id:
                unit = {
                    "id": node_id,
                    "type": node_data.get("entity_type"),
                    "properties": {k: v for k, v in node_data.items() if k != "entity_type"}
                }
                break

    if not unit:
        return {"status": "error", "message": "部队不存在"}

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
    handler=attack_target
)

register_skill(
    name="command_unit",
    description="指挥部队",
    handler=command_unit
)