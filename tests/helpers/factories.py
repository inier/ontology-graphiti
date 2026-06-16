"""Shared test factories for ODAP domain models.

Each factory function returns a plain dict that can be passed directly
to service/storage methods.  Use ``**overrides`` to customise any field.

Usage::

    from tests.helpers.factories import make_ontology, make_workspace

    ont = make_ontology(name="My Ontology")
    ws = make_workspace()
"""

import uuid
from datetime import datetime


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> str:
    return datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Workspace & Scenario
# ---------------------------------------------------------------------------


def make_workspace(**overrides) -> dict:
    base = {
        "name": "test-workspace",
        "description": "A test workspace",
        "owner_id": "user-001",
        "status": "active",
    }
    base.update(overrides)
    return base


def make_scenario(**overrides) -> dict:
    base = {
        "name": "test-scenario",
        "description": "A test scenario",
        "workspace_id": overrides.get("workspace_id", "ws-001"),
        "status": "active",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Ontology
# ---------------------------------------------------------------------------


def make_ontology(**overrides) -> dict:
    base = {
        "name": "test-ontology",
        "workspace_id": "ws-001",
        "scenario_id": "sc-001",
        "description": "A test ontology",
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


def make_object_type(**overrides) -> dict:
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "Person",
        "display_name": "Person",
        "description": "A person entity",
        "properties": [{"name": "age", "type": "integer"}],
        "links": [{"name": "works_at", "target": "Organization"}],
    }
    base.update(overrides)
    return base


def make_link_type(**overrides) -> dict:
    base = {
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "name": "works_at",
        "display_name": "Works At",
        "description": "Employment relationship",
        "source_type": "Person",
        "target_type": "Organization",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


def make_agent(**overrides) -> dict:
    base = {
        "name": "test-agent",
        "display_name": "Test Agent",
        "workspace_id": "ws-001",
        "role": "analyst",
        "description": "A test agent",
        "status": "active",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Role & Permission
# ---------------------------------------------------------------------------


def make_role(**overrides) -> dict:
    base = {
        "name": "test-role",
        "description": "A test role",
        "role_type": "MEMBER",
        "permissions": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Business
# ---------------------------------------------------------------------------


def make_business_rule(**overrides) -> dict:
    base = {
        "name": "test-rule",
        "description": "A test business rule",
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "condition": "x > 0",
        "action": "approve",
    }
    base.update(overrides)
    return base


def make_business_process(**overrides) -> dict:
    base = {
        "name": "test-process",
        "description": "A test business process",
        "ontology_id": "ont-001",
        "version_id": "ver-001",
        "steps": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


def make_simulation_scenario(**overrides) -> dict:
    base = {
        "name": "test-simulation",
        "description": "A test simulation scenario",
        "ontology_id": "ont-001",
        "status": "DRAFT",
    }
    base.update(overrides)
    return base


def make_event(**overrides) -> dict:
    base = {
        "name": "test-event",
        "event_type": "custom",
        "description": "A test event",
        "timestamp": _now(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# QA
# ---------------------------------------------------------------------------


def make_qa_session(**overrides) -> dict:
    base = {
        "workspace_id": "ws-001",
        "scenario_id": "sc-001",
        "user_id": "user-001",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


def make_skill(**overrides) -> dict:
    base = {
        "name": "test-skill",
        "description": "A test skill",
        "version": "1.0.0",
        "status": "active",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------


def make_hook(**overrides) -> dict:
    base = {
        "name": "test-hook",
        "event_type": "ontology.created",
        "handler_code": "def handle(event): pass",
        "status": "active",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


def make_decision_option(**overrides) -> dict:
    base = {
        "name": "test-option",
        "description": "A test decision option",
        "risk_level": "low",
        "expected_outcome": "positive",
    }
    base.update(overrides)
    return base
