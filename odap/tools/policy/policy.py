"""
策略技能模块
实现策略执行模拟、版本管理和回退功能
"""

import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.opa import OPAManager
from odap.biz.ontology.service import OntologyManager

opa_manager = OPAManager()
ontology_manager = OntologyManager()

def simulate_policy_execution(user_role, action, target_type=None):
    """
    模拟策略执行

    Args:
        user_role: 用户角色
        action: 操作类型
        target_type: 目标类型

    Returns:
        模拟执行结果
    """
    result = ontology_manager.simulate_policy_execution(user_role, action, target_type)

    return result

def get_policy_version():
    """
    获取当前策略版本

    Returns:
        策略版本信息
    """
    version = opa_manager.get_policy_version()

    return {
        "status": "success",
        "version": version,
        "message": f"当前策略版本: {version}"
    }

def rollback_policy():
    """
    回退策略版本

    Returns:
        回退结果
    """
    old_version = opa_manager.get_policy_version()
    new_version = opa_manager.rollback_policy()

    return {
        "status": "success",
        "old_version": old_version,
        "new_version": new_version,
        "message": f"策略已从 {old_version} 回退到 {new_version}"
    }

def export_policy(policy_name, version=None, description=""):
    """
    导出策略

    Args:
        policy_name: 策略名称
        version: 版本号
        description: 版本描述

    Returns:
        导出结果
    """
    export_file = ontology_manager.export_policy(policy_name, version=version, description=description)

    return {
        "status": "success",
        "file": export_file,
        "message": f"策略 '{policy_name}' 导出成功"
    }

def import_policy(policy_file):
    """
    导入策略

    Args:
        policy_file: 策略文件路径

    Returns:
        导入结果
    """
    success = ontology_manager.import_policy(policy_file)

    if success:
        return {
            "status": "success",
            "message": f"策略导入成功: {policy_file}"
        }
    else:
        return {
            "status": "error",
            "message": f"策略导入失败: {policy_file}"
        }

def list_policy_versions():
    """
    列出策略版本

    Returns:
        策略版本列表
    """
    policies = ontology_manager.list_policies()

    return {
        "status": "success",
        "policies": policies
    }

def rollback_policy_version(policy_name, version):
    """
    回滚策略版本

    Args:
        policy_name: 策略名称
        version: 版本号

    Returns:
        回滚结果
    """
    success = ontology_manager.rollback_policy(policy_name, version)

    if success:
        return {
            "status": "success",
            "message": f"策略 '{policy_name}' 已回滚到版本 {version}"
        }
    else:
        return {
            "status": "error",
            "message": f"策略回滚失败: {policy_name}@{version}"
        }

def check_permission(user_role, action, resource_type):
    """
    检查权限

    Args:
        user_role: 用户角色
        action: 操作类型
        resource_type: 资源类型

    Returns:
        权限检查结果
    """
    allowed = opa_manager.check_permission(
        user_role,
        action,
        {"type": resource_type}
    )

    return {
        "status": "success",
        "user_role": user_role,
        "action": action,
        "resource_type": resource_type,
        "allowed": allowed,
        "message": "允许执行" if allowed else "拒绝执行"
    }

def get_policy_history():
    """
    获取策略执行历史

    Returns:
        策略执行历史
    """
    history = ontology_manager.get_policy_history()

    return {
        "status": "success",
        "total": len(history),
        "history": history
    }

def clear_policy_history():
    """
    清除策略执行历史

    Returns:
        清除结果
    """
    ontology_manager.clear_policy_history()

    return {
        "status": "success",
        "message": "策略执行历史已清除"
    }

register_skill(
    name="simulate_policy_execution",
    description="模拟策略执行",
    handler=simulate_policy_execution,
    category="policy")


register_skill(
    name="get_policy_version",
    description="获取策略版本",
    handler=get_policy_version,
    category="policy")


register_skill(
    name="rollback_policy",
    description="回退策略版本",
    handler=rollback_policy,
    category="policy")


register_skill(
    name="export_policy",
    description="导出策略",
    handler=export_policy,
    category="policy")


register_skill(
    name="import_policy",
    description="导入策略",
    handler=import_policy,
    category="policy")


register_skill(
    name="list_policy_versions",
    description="列出策略版本",
    handler=list_policy_versions,
    category="policy")


register_skill(
    name="rollback_policy_version",
    description="回滚策略版本",
    handler=rollback_policy_version,
    category="policy")


register_skill(
    name="check_permission",
    description="检查权限",
    handler=check_permission,
    category="policy")


register_skill(
    name="get_policy_history",
    description="获取策略执行历史",
    handler=get_policy_history,
    category="policy")


register_skill(
    name="clear_policy_history",
    description="清除策略执行历史",
    handler=clear_policy_history,
    category="policy")
