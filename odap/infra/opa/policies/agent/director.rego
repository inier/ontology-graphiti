package policies.agent

import future.keywords.if

default allow := false

allow if {
    input.agent_role == "director"
    input.action == "decide"
}

allow if {
    input.agent_role == "intelligence"
    input.action == "observe"
}

allow if {
    input.agent_role == "intelligence"
    input.action == "analyze"
}

allow if {
    input.agent_role == "operations"
    input.action == "perform"
}

allow if {
    input.agent_role == "director"
    input.action == "perform"
}

allow if {
    input.user_role == "admin"
}
