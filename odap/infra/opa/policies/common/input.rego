package policies.common

import future.keywords.if

valid_input if {
    input.action
    input.user.role
}

valid_action if {
    valid_actions[_] == input.action
}

valid_actions := [
    "view",
    "view_intelligence",
    "analyze_data",
    "generate_reports",
    "command_unit",
    "move",
    "attack",
    "defend",
    "retreat",
    "reinforce",
    "observe",
    "communicate",
    "decide",
    "perform",
]
