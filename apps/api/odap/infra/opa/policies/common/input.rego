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
    "view_information",
    "analyze_data",
    "generate_reports",
    "coordinate_unit",
    "move",
    "engage",
    "hold",
    "withdraw",
    "support",
    "observe",
    "communicate",
    "decide",
    "perform",
]
