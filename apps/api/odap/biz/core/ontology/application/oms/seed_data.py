"""
OMS Object Type and Action Type Seed Data.

This module contains OMS-specific seed data (object types, action types)
used to bootstrap the OMS storage. It is OWNED by the OMS module in the
application layer — the design layer does NOT depend on it.

Moved from design/schema/domain.py to break the cross-boundary dependency:
OMS (application) MUST NOT import from design/schema/.
"""
from typing import Dict, Any


def generate_oms_seed_data() -> Dict[str, Any]:
    """Generate OMS seed data: object types and action types.

    This is the default set of OMS object types and action types. The
    design layer (ontology) can extend this set at runtime via the
    unified query service.
    """
    return {
        "object_types": _OMS_OBJECT_TYPES,
        "action_types": _OMS_ACTION_TYPES,
    }


_OMS_OBJECT_TYPES: Dict[str, Any] = {
    "Agent": {
        "display_name": "Agent",
        "description": "Autonomous agent that performs tasks",
        "basic_properties": [
            {"name": "agent_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "role", "data_type": "string", "is_required": True},
            {"name": "status", "data_type": "string", "is_required": False},
        ],
        "links": [],
        "actions": ["dispatch", "terminate"],
    },
    "Workspace": {
        "display_name": "Workspace",
        "description": "Top-level resource container",
        "basic_properties": [
            {"name": "workspace_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
        ],
        "links": [],
        "actions": ["create", "delete", "update"],
    },
    "Scenario": {
        "display_name": "Scenario",
        "description": "Business scenario under a workspace",
        "basic_properties": [
            {"name": "scenario_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
        ],
        "links": [
            {"name": "belongs_to_workspace", "target_type": "Workspace", "cardinality": "N:1"},
        ],
        "actions": ["create", "delete", "update"],
    },
    "Ontology": {
        "display_name": "Ontology",
        "description": "Ontology document",
        "basic_properties": [
            {"name": "ontology_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
        ],
        "links": [
            {"name": "bound_to_scenario", "target_type": "Scenario", "cardinality": "N:M"},
        ],
        "actions": ["create", "delete", "update", "version"],
    },
    "Simulation": {
        "display_name": "Simulation",
        "description": "Simulation scenario execution",
        "basic_properties": [
            {"name": "simulation_id", "data_type": "string", "is_required": True, "is_primary_key": True},
            {"name": "name", "data_type": "string", "is_required": True},
        ],
        "links": [
            {"name": "uses_ontology", "target_type": "Ontology", "cardinality": "N:1"},
        ],
        "actions": ["start", "stop", "configure"],
    },
}


_OMS_ACTION_TYPES = [
    {
        "action_type_id": "agent.dispatch",
        "name": "dispatch",
        "display_name": "Dispatch Agent",
        "description": "Dispatch an agent to handle a task",
        "target_object_type": "Agent",
        "parameters": [
            {"name": "task_id", "data_type": "string", "is_required": True},
            {"name": "priority", "data_type": "string", "is_required": False},
        ],
        "required_roles": ["director", "operator"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "workspace.create",
        "name": "create",
        "display_name": "Create Workspace",
        "description": "Create a new workspace",
        "target_object_type": "Workspace",
        "parameters": [
            {"name": "name", "data_type": "string", "is_required": True},
            {"name": "description", "data_type": "string", "is_required": False},
        ],
        "required_roles": ["admin"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "workspace.delete",
        "name": "delete",
        "display_name": "Delete Workspace",
        "description": "Cascade-delete a workspace and all its data",
        "target_object_type": "Workspace",
        "parameters": [
            {"name": "workspace_id", "data_type": "string", "is_required": True},
        ],
        "required_roles": ["admin"],
        "confirmation_required": True,
    },
    {
        "action_type_id": "ontology.create",
        "name": "create",
        "display_name": "Create Ontology",
        "description": "Create a new ontology document",
        "target_object_type": "Ontology",
        "parameters": [
            {"name": "name", "data_type": "string", "is_required": True},
        ],
        "required_roles": ["admin", "director"],
        "confirmation_required": False,
    },
    {
        "action_type_id": "simulation.start",
        "name": "start",
        "display_name": "Start Simulation",
        "description": "Start a simulation run",
        "target_object_type": "Simulation",
        "parameters": [
            {"name": "config", "data_type": "dict", "is_required": False},
        ],
        "required_roles": ["operator", "director"],
        "confirmation_required": False,
    },
]
