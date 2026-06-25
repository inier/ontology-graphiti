# T066 OPA policy for ontology assistant endpoints
# Controls access to AI-assisted ontology configuration features.
# Roles: admin (full access), owner/editor (workspace members), viewer (read-only)

package odap.ontology_assistant

import future.keywords.if
import future.keywords.in

default allow := false

# Admin users have full access to all actions
allow if {
    input.user.role == "admin"
}

# Workspace owners and editors can use all AI assistant features
allow if {
    input.user.ws_role in {"owner", "editor"}
    input.user.ws_id == input.workspace_id
}

# Workspace viewers can only access read-only endpoints (health, infer-type, suggest-constraints, list suggestions)
allow if {
    input.user.ws_role == "viewer"
    input.user.ws_id == input.workspace_id
    input.action in {
        "ontology_assistant:health",
        "ontology_assistant:infer_type",
        "ontology_assistant:suggest_constraints",
        "ontology_assistant:list_suggestions",
    }
}

# Deny if no workspace role and not admin
deny if {
    not input.user.ws_role
    input.action != "ontology_assistant:health"
}
