package policies.common

import future.keywords.if

default allow := false

allow if {
    input.user.role == "admin"
}

allow if {
    input.action == "observe"
}

allow if {
    input.action == "view"
}

escalation_risk := "high" if {
    input.action == "engage"
    input.target.category == "operational"
    input.target.threat_level == "critical"
} else := "medium" if {
    input.action == "engage"
} else := "low"
