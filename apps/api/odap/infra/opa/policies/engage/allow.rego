package policies.engage

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.action == "engage"
    input.user.role == "director"
    not is_protected_target(input.target)
    equipment_within_params(input.equipment, input.target)
}

allow if {
    input.action == "engage"
    input.user.role == "admin"
}

is_protected_target(target) if {
    target.category == "civilian"
}

is_protected_target(target) if {
    target.category == "medical"
}

is_protected_target(target) if {
    target.category == "historical"
}

is_protected_target(target) if {
    target.category == "diplomatic"
}

equipment_within_params(equipment, target) if {
    equipment.effective_range >= target.distance
}

equipment_within_params(equipment, target) if {
    not target.distance
}

deny_reason := "engage denied: target is protected" if {
    is_protected_target(input.target)
} else := "engage denied: insufficient role" if {
    input.user.role != "director"
    input.user.role != "admin"
} else := "engage denied: equipment out of range" if {
    not equipment_within_params(input.equipment, input.target)
} else := "engage allowed"
