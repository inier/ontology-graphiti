"""
任务管理技能模块
实现基于图谱的任务预留和管理功能
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import register_skill
from core.graph_manager import BattlefieldGraphManager

manager = BattlefieldGraphManager()

def reserve_task(task_name, task_type, targets, priority="medium", user_role=None):
    """
    预留任务

    Args:
        task_name: 任务名称
        task_type: 任务类型
        targets: 目标列表
        priority: 优先级
        user_role: 用户角色

    Returns:
        任务预留结果
    """
    if not targets or len(targets) == 0:
        return {"status": "error", "message": "目标列表不能为空"}

    task_data = {
        "type": task_type,
        "name": task_name,
        "priority": priority,
        "targets": targets,
        "user_role": user_role,
        "created_at": datetime.now().isoformat()
    }

    task_id = manager.reserve_task(task_data)

    return {
        "status": "success",
        "task_id": task_id,
        "message": f"任务 '{task_name}' 已预留",
        "task_data": task_data
    }

def get_reserved_tasks():
    """
    获取所有预留任务

    Returns:
        预留任务列表
    """
    tasks = manager.get_reserved_tasks()

    return {
        "status": "success",
        "total": len(tasks),
        "tasks": tasks
    }

def clear_reserved_tasks():
    """
    清除所有预留任务

    Returns:
        清除结果
    """
    manager.clear_reserved_tasks()

    return {
        "status": "success",
        "message": "所有预留任务已清除"
    }

def get_task_by_id(task_id):
    """
    根据ID获取任务

    Args:
        task_id: 任务ID

    Returns:
        任务信息
    """
    tasks = manager.get_reserved_tasks()

    for task in tasks:
        if task.get("id") == task_id:
            return {
                "status": "success",
                "task": task
            }

    return {
        "status": "error",
        "message": f"任务 {task_id} 不存在"
    }

def cancel_task(task_id):
    """
    取消任务

    Args:
        task_id: 任务ID

    Returns:
        取消结果
    """
    tasks = manager.get_reserved_tasks()

    for i, task in enumerate(tasks):
        if task.get("id") == task_id:
            tasks.pop(i)
            return {
                "status": "success",
                "message": f"任务 {task_id} 已取消"
            }

    return {
        "status": "error",
        "message": f"任务 {task_id} 不存在"
    }

def query_tasks_by_status(status):
    """
    根据状态查询任务

    Args:
        status: 任务状态

    Returns:
        任务列表
    """
    tasks = manager.get_reserved_tasks()

    filtered_tasks = [t for t in tasks if t.get("status") == status]

    return {
        "status": "success",
        "total": len(filtered_tasks),
        "tasks": filtered_tasks
    }

register_skill(
    name="reserve_task",
    description="预留任务",
    handler=reserve_task
)

register_skill(
    name="get_reserved_tasks",
    description="获取所有预留任务",
    handler=get_reserved_tasks
)

register_skill(
    name="clear_reserved_tasks",
    description="清除所有预留任务",
    handler=clear_reserved_tasks
)

register_skill(
    name="get_task_by_id",
    description="根据ID获取任务",
    handler=get_task_by_id
)

register_skill(
    name="cancel_task",
    description="取消任务",
    handler=cancel_task
)

register_skill(
    name="query_tasks_by_status",
    description="根据状态查询任务",
    handler=query_tasks_by_status
)