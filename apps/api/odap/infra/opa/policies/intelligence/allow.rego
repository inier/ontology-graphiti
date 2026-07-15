package policies.intelligence

import future.keywords.if
import future.keywords.in

default allow := false

allow if {
    input.action == "view_intelligence"
    has_permission(input.user.role, "view_intelligence")
}

allow if {
    input.action == "analyze_data"
    has_permission(input.user.role, "analyze_data")
}

allow if {
    input.action == "generate_reports"
    has_permission(input.user.role, "generate_reports")
}

allow if {
    input.user.role == "admin"
}

has_permission(role, perm) if {
    role_permissions[role][_] == perm
}

role_permissions := {
    "commander": ["view_intelligence", "analyze_data", "generate_reports"],
    "intelligence_officer": ["view_intelligence", "analyze_data", "generate_reports"],
    "operator": ["view_intelligence"],
    "auditor": ["view_intelligence"],
}
