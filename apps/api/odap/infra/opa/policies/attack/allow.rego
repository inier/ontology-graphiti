package policies.attack

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.action == "attack"
    input.user.role == "commander"
    not is_protected_target(input.target)
    weapon_within_params(input.weapon, input.target)
}

allow if {
    input.action == "attack"
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

weapon_within_params(weapon, target) if {
    weapon.effective_range >= target.distance
}

weapon_within_params(weapon, target) if {
    not target.distance
}

deny_reason := "attack denied: target is protected" if {
    is_protected_target(input.target)
} else := "attack denied: insufficient role" if {
    input.user.role != "commander"
    input.user.role != "admin"
} else := "attack denied: weapon out of range" if {
    not weapon_within_params(input.weapon, input.target)
} else := "attack allowed"
