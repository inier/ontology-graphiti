package policies.operations

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.action == "command_unit"
    has_permission(input.user.role, "command_units")
}

allow if {
    input.action == "move"
    has_permission(input.user.role, "command_units")
}

allow if {
    input.action == "defend"
    has_permission(input.user.role, "command_units")
}

allow if {
    input.action == "retreat"
    input.user.role == "commander"
}

allow if {
    input.action == "reinforce"
    input.user.role == "commander"
}

allow if {
    input.user.role == "admin"
}

has_permission(role, perm) if {
    role_permissions[role][_] == perm
}

role_permissions := {
    "commander": ["command_units", "authorize_attacks", "approve_missions"],
    "operator": ["command_units"],
}
