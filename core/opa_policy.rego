# OPA策略文件
# 定义角色权限和策略规则

# 包名
package battlefield

# 角色权限定义
roles = {
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

# 资源类型定义
resource_types = {
    "radar": "WeaponSystem",
    "hospital": "CivilianInfrastructure",
    "military_unit": "MilitaryUnit",
    "mission": "Mission"
}

# 权限检查
allow {
    # 检查用户是否有相应的权限
    has_permission(input.user_role, input.action)
    
    # 检查是否有特殊限制
    not has_restriction(input.user_role, input.action, input.resource)
}

# 检查用户是否有相应的权限
has_permission(role, action) {
    roles[role].permissions[_] == action
}

# 检查是否有特殊限制
has_restriction(role, action, resource) {
    # 检查是否禁止攻击
    roles[role].restrictions[_] == "cannot_attack"
    action == "attack"
}

# 检查是否禁止指挥
has_restriction(role, action, resource) {
    roles[role].restrictions[_] == "cannot_command"
    action == "command"
}

# 检查是否禁止攻击民用设施
has_restriction(role, action, resource) {
    roles[role].restrictions[_] == "cannot_attack_civilian_infrastructure"
    action == "attack"
    is_civilian_infrastructure(resource)
}

# 检查是否为民用设施
is_civilian_infrastructure(resource) {
    resource.type == "CivilianInfrastructure"
}

# 检查是否为雷达
is_radar(resource) {
    resource.type == "WeaponSystem"
    resource.properties.type == "雷达"
}

# 策略执行模拟
policy_simulation {
    # 模拟策略执行
    allow
    # 记录执行日志
    simulation_log = [
        {"action": input.action, "resource": input.resource.id, "result": "allowed"}
    ]
}

# 版本回退
get_previous_version {
    # 返回之前的策略版本
    previous_version = "1.0.0"
}