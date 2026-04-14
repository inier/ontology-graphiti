# OPA 策略文件
# 定义战场角色权限和访问控制规则
#
# 版本: 2.0.0
# 包名: battlefield
#
# 测试（OPA CLI）:
#   echo '{"input":{"user_role":"commander","action":"attack","resource":{"id":"RADAR_01","type":"WeaponSystem","properties":{"type":"雷达"}}}}' \
#     | opa eval -d core/opa_policy.rego -I 'data.battlefield.allow'

package battlefield

import future.keywords.if
import future.keywords.in

# ============================================================
# 角色定义
# permissions: 该角色拥有的权限标识列表
# restrictions: 额外的限制规则标识列表
# ============================================================
roles := {
    "pilot": {
        "permissions": ["view_intelligence", "request_support"],
        "restrictions": ["cannot_attack", "cannot_command"]
    },
    "commander": {
        "permissions": ["view_intelligence", "command_units", "authorize_attacks", "approve_missions"],
        "restrictions": ["cannot_attack_civilian_infrastructure"]
    },
    "intelligence_analyst": {
        "permissions": ["view_intelligence", "analyze_data", "generate_reports"],
        "restrictions": ["cannot_command", "cannot_attack"]
    }
}

# ============================================================
# Action → Permission 映射
# 某些 action 名称不同于 permission 名称，需要显式映射
# 与 Python Mock 中的 permission_mapping 保持一致
# ============================================================
permission_mapping := {
    "attack":             ["authorize_attacks"],
    "command":            ["command_units"],
    "view_intelligence":  ["view_intelligence"],
    "request_support":    ["request_support"],
    "analyze_data":       ["analyze_data"],
    "generate_reports":   ["generate_reports"],
    "approve_missions":   ["approve_missions"]
}

# ============================================================
# 主规则：allow
# 满足以下全部条件时放行：
#   1. 角色存在
#   2. 角色拥有对应 action 所需的至少一个 permission
#   3. 没有任何 restriction 阻止该操作
# ============================================================
default allow := false

allow if {
    # 条件 1: 角色存在
    roles[input.user_role]

    # 条件 2: 拥有 permission
    has_required_permission(input.user_role, input.action)

    # 条件 3: 无限制
    not is_restricted(input.user_role, input.action, input.resource)
}

# ============================================================
# 辅助：权限检查
# ============================================================

# 检查角色是否拥有执行 action 所需的至少一个 permission
has_required_permission(role, action) if {
    # 找到 action 对应的所需 permissions
    required := permission_mapping[action]
    # 角色的 permissions 中包含至少一个所需 permission
    some perm in required
    perm in roles[role].permissions
}

# 对于未在 permission_mapping 中明确的 action，直接匹配 permission 名
has_required_permission(role, action) if {
    not permission_mapping[action]
    action in roles[role].permissions
}

# ============================================================
# 辅助：限制检查
# ============================================================

# 限制：cannot_attack — 禁止任何攻击行为
is_restricted(role, action, _resource) if {
    "cannot_attack" in roles[role].restrictions
    action == "attack"
}

# 限制：cannot_command — 禁止指挥操作
is_restricted(role, action, _resource) if {
    "cannot_command" in roles[role].restrictions
    action == "command"
}

# 限制：cannot_attack_civilian_infrastructure — 禁止攻击民用设施
is_restricted(role, action, resource) if {
    "cannot_attack_civilian_infrastructure" in roles[role].restrictions
    action == "attack"
    resource.type == "CivilianInfrastructure"
}

# ============================================================
# 调试辅助规则（可选，不影响主 allow 逻辑）
# ============================================================

# 返回决策摘要，便于调试
decision_reason := reason if {
    allow
    reason := "allowed: role has required permission and no active restrictions"
} else := reason if {
    not roles[input.user_role]
    reason := "denied: unknown role"
} else := reason if {
    not has_required_permission(input.user_role, input.action)
    reason := "denied: role lacks required permission for this action"
} else := reason if {
    is_restricted(input.user_role, input.action, input.resource)
    reason := "denied: role has an active restriction blocking this action"
} else := "denied: unknown reason"

# ============================================================
# 策略元数据
# ============================================================
policy_version := "2.0.0"
policy_name := "battlefield_access_control"
