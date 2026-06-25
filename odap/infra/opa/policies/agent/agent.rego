# Agent policies - combined commander and director roles
package policies.agent

import future.keywords.if

default allow := false

# Commander role rules
allow if {
    input.agent_role == "commander"
    input.action == "decide"
}

allow if {
    input.agent_role == "commander"
    input.action == "perform"
}

# Director role rules
allow if {
    input.agent_role == "director"
    input.action == "decide"
}

allow if {
    input.agent_role == "director"
    input.action == "perform"
}

# Common rules for intelligence and operations
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

# Admin override
allow if {
    input.user_role == "admin"
}
