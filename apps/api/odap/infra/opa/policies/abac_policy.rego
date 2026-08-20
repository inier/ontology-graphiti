package domain.abac

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    "system_admin" in input.subject.roles
}

allow if {
    clearance_sufficient
    workspace_isolated
    action_permitted
    environment_ok
    high_privilege_check
}

clearance_order := {
    "public": 1,
    "confidential": 2,
    "secret": 3,
    "top_secret": 4,
}

clearance_sufficient if {
    clearance_order[input.subject.clearance_level] >= clearance_order[input.resource.classification]
}

workspace_isolated if {
    input.environment.isolation_level != "strict"
}

workspace_isolated if {
    input.environment.isolation_level == "strict"
    input.subject.workspace_id == input.resource.workspace_id
}

action_permitted if {
    some role in input.subject.roles
    input.action.type in role_permissions[role]
}

role_permissions := {
    "admin": ["*"],
    "director": ["view", "create", "update", "delete", "approve", "coordinate_units", "authorize_engagements"],
    "analyst": ["view", "analyze_data", "generate_reports", "view_information"],
    "operator": ["view", "perform", "observe"],
    "observer": ["view"],
    "auditor": ["view", "export"],
    "team_leader": ["view", "create", "update", "approve"],
    "member": ["view", "create", "update"],
    "project_owner": ["view", "create", "update", "delete", "approve"],
    "guest": ["view"],
}

environment_ok if {
    not input.environment.time_of_day
}

environment_ok if {
    input.environment.time_of_day
    within_working_hours
}

within_working_hours if {
    input.environment.time_of_day >= "09:00"
    input.environment.time_of_day <= "18:00"
}

# 白皮书 §2.2: 高敏操作强制要求会话时长 > 5 分钟（防范 Prompt 注入秒级攻击）
high_privilege_actions := {
    "refund", "send_email", "delete_user", "transfer_money",
    "approve_mission", "authorize_engagements",
}

# 非高敏操作：直接通过
high_privilege_check if {
    not input.action.type in high_privilege_actions
}

# 高敏操作：要求会话时长 >= 300 秒
high_privilege_check if {
    input.action.type in high_privilege_actions
    input.environment.session_duration_seconds >= 300
}

deny_reasons := [reason |
    reason := "insufficient_clearance"
    not clearance_sufficient
]

deny if {
    not clearance_sufficient
}

deny if {
    input.environment.isolation_level == "strict"
    input.subject.workspace_id != input.resource.workspace_id
}

deny if {
    input.action.type in high_privilege_actions
    input.environment.session_duration_seconds < 300
}
