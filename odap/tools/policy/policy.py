import sys
import os
import json
import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odap.tools import register_skill
from odap.infra.opa import OPAManager
from odap.biz.core.ontology.design.schema.domain import ROLES, DOMAIN_CONFIG

opa_manager = OPAManager()
_policy_history = []
_policy_dir = "core/policies"

if not os.path.exists(_policy_dir):
    os.makedirs(_policy_dir)


def simulate_policy_execution(user_role, action, target_type=None):
    result = {
        "role": user_role,
        "action": action,
        "target_type": target_type,
        "timestamp": datetime.datetime.now().isoformat(),
        "allowed": True,
        "reason": ""
    }

    if user_role not in ROLES:
        result["allowed"] = False
        result["reason"] = f"角色 {user_role} 不存在"
    else:
        role_config = ROLES[user_role]
        permissions = role_config.get("permissions", [])
        restrictions = role_config.get("restrictions", [])

        action_permission_map = {
            "view_intelligence": ["view_intelligence"],
            "request_support": ["request_support"],
            "command_units": ["command_units"],
            "authorize_attacks": ["authorize_attacks"],
            "approve_missions": ["approve_missions"],
            "analyze_data": ["analyze_data"],
            "generate_reports": ["generate_reports"],
            "attack": ["authorize_attacks"],
            "command": ["command_units"]
        }

        required_permissions = action_permission_map.get(action, [])

        for perm in required_permissions:
            if perm not in permissions:
                result["allowed"] = False
                result["reason"] = f"角色 {user_role} 缺少必要权限: {perm}"
                break

        for restriction in restrictions:
            if restriction == "cannot_attack" and action == "attack":
                result["allowed"] = False
                result["reason"] = f"角色 {user_role} 被限制执行攻击操作"
                break
            elif restriction == "cannot_command" and action == "command":
                result["allowed"] = False
                result["reason"] = f"角色 {user_role} 被限制执行指挥操作"
                break
            elif restriction == "cannot_attack_civilian_infrastructure" and target_type == "CivilianInfrastructure":
                result["allowed"] = False
                result["reason"] = f"角色 {user_role} 被限制攻击民用设施"
                break

    if result["allowed"]:
        result["reason"] = f"角色 {user_role} 有权执行 {action} 操作"

    _policy_history.append(result)

    return result


def get_policy_version():
    version = opa_manager.get_policy_version()

    return {
        "status": "success",
        "version": version,
        "message": f"当前策略版本: {version}"
    }


def rollback_policy():
    old_version = opa_manager.get_policy_version()
    new_version = opa_manager.rollback_policy()

    return {
        "status": "success",
        "old_version": old_version,
        "new_version": new_version,
        "message": f"策略已从 {old_version} 回退到 {new_version}"
    }


def export_policy(policy_name, version=None, description=""):
    if not version:
        version = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    policy_data = {
        "policy_name": policy_name,
        "version": version,
        "description": description,
        "timestamp": datetime.datetime.now().isoformat(),
        "roles": ROLES,
        "domain_config": DOMAIN_CONFIG
    }

    export_file = os.path.join(_policy_dir, f"policy_{policy_name}_{version}.json")

    with open(export_file, 'w', encoding='utf-8') as f:
        json.dump(policy_data, f, ensure_ascii=False, indent=2)

    return {
        "status": "success",
        "file": export_file,
        "message": f"策略 '{policy_name}' 导出成功"
    }


def import_policy(policy_file):
    if not os.path.exists(policy_file):
        return {
            "status": "error",
            "message": f"策略导入失败: {policy_file}"
        }

    try:
        with open(policy_file, 'r', encoding='utf-8') as f:
            json.load(f)
        return {
            "status": "success",
            "message": f"策略导入成功: {policy_file}"
        }
    except Exception:
        return {
            "status": "error",
            "message": f"策略导入失败: {policy_file}"
        }


def list_policy_versions():
    policies = []

    if not os.path.exists(_policy_dir):
        return {
            "status": "success",
            "policies": policies
        }

    for filename in os.listdir(_policy_dir):
        if filename.startswith("policy_") and filename.endswith(".json"):
            parts = filename.replace("policy_", "").replace(".json", "").split("_")
            policy_name = parts[0] if parts else "unknown"
            version = "_".join(parts[1:]) if len(parts) > 1 else "unknown"
            file_path = os.path.join(_policy_dir, filename)

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                policies.append({
                    "policy_name": data.get("policy_name", policy_name),
                    "version": data.get("version", version),
                    "description": data.get("description", ""),
                    "timestamp": data.get("timestamp", ""),
                    "file": filename
                })
            except Exception:
                pass

    policies.sort(key=lambda x: x["timestamp"], reverse=True)

    return {
        "status": "success",
        "policies": policies
    }


def rollback_policy_version(policy_name, version):
    import_file = os.path.join(_policy_dir, f"policy_{policy_name}_{version}.json")

    if not os.path.exists(import_file):
        return {
            "status": "error",
            "message": f"策略回滚失败: {policy_name}@{version}"
        }

    try:
        with open(import_file, 'r', encoding='utf-8') as f:
            json.load(f)
        return {
            "status": "success",
            "message": f"策略 '{policy_name}' 已回滚到版本 {version}"
        }
    except Exception:
        return {
            "status": "error",
            "message": f"策略回滚失败: {policy_name}@{version}"
        }


def check_permission(user_role, action, resource_type):
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
    return {
        "status": "success",
        "total": len(_policy_history),
        "history": _policy_history
    }


def clear_policy_history():
    _policy_history.clear()

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
