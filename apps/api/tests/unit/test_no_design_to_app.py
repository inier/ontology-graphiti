"""
Regression test: P0-4 boundary rule enforcement (R-P0-001).

The architecture constitution states:
  P0-4: Ontology design code MUST NOT import from application/.

This test guards against regressions of the 2 violations previously found
in `odap/biz/core/ontology/design/services/pipeline_service.py`:
  - Line 600: import of SQLiteOMSStorage (application/oms)
  - Line 1314: import of ServiceCatalogService (application/servitization)

The fix uses an event bus (odap.biz.core.ontology.design.events) to decouple
the two subsystems.
"""
import ast
from pathlib import Path
import pytest

ROOT = Path(r"e:\DEMO\AI\ontology-graphiti\odap")
DESIGN_DIR = ROOT / "biz" / "core" / "design"
# Use the actual design path (not the older design/ location)
ACTUAL_DESIGN_DIR = ROOT / "biz" / "core" / "ontology" / "design"

# Subsystems under "application" that design MUST NOT import from directly
APPLICATION_SUBSYSTEMS = (
    "odap.biz.core.ontology.application",
    "odap.biz.core.ontology.oms",
    "odap.biz.core.ontology.servitization",
    "odap.biz.core.ontology.team_agent",
    "odap.biz.core.ontology.harness",
    "odap.biz.core.ontology.runtime",
    "odap.biz.core.ontology.query_api",
    "odap.biz.core.ontology.abution_graph",
    "odap.biz.core.agent",  # Biz-side agent is also application-layer
)

# The contract layer IS allowed (P0-4 exception)
CONTRACT_PREFIX = "odap.biz.core.ontology.design.contract"

# The event bus IS allowed (R-P0-001 exception, lives inside design/)
EVENTS_MODULE = "odap.biz.core.ontology.design.events"


def _is_application_import(module: str) -> bool:
    """Check if a module path is from the application layer."""
    return any(module.startswith(prefix) for prefix in APPLICATION_SUBSYSTEMS)


def _is_allowed_exception(module: str) -> bool:
    """Check if module is an allowed exception (contract, events)."""
    if module == CONTRACT_PREFIX or module.startswith(CONTRACT_PREFIX + "."):
        return True
    if module == EVENTS_MODULE or module.startswith(EVENTS_MODULE + "."):
        return True
    return False


def collect_imports_in_file(path: Path) -> list:
    """Return all (module, lineno) imports in a file."""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                continue
            if node.level and node.module:
                # Relative import — cannot resolve without package context
                continue
            imports.append((node.module, node.lineno))
    return imports


def collect_design_files():
    """Yield all Python files under odap/biz/core/ontology/design/."""
    if not ACTUAL_DESIGN_DIR.exists():
        return
    for path in ACTUAL_DESIGN_DIR.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        # Skip the contract package itself — its job IS to expose design to app
        if "contract" in path.parts:
            continue
        # Skip the events module — its job IS to be the bridge
        if path.name == "events.py":
            continue
        yield path


# ============ Tests ============

class TestDesignNoApplicationImports:
    """P0-4: design MUST NOT import from application/*."""

    def test_no_application_imports_in_design(self):
        """Scan all odap/biz/core/ontology/design/ files for forbidden imports."""
        violations = []
        for py_file in collect_design_files():
            imports = collect_imports_in_file(py_file)
            for module, lineno in imports:
                if _is_application_import(module) and not _is_allowed_exception(module):
                    rel = py_file.relative_to(ROOT.parent)
                    violations.append(f"{rel}:{lineno}  -> {module}")

        assert not violations, (
            f"\n\nFound {len(violations)} P0-4 violation(s) "
            f"(design importing from application/*):\n"
            + "\n".join(violations)
        )

    def test_pipeline_service_no_oms_import(self):
        """The specific line 600 violation: pipeline_service.py must not import OMS."""
        path = ACTUAL_DESIGN_DIR / "services" / "pipeline_service.py"
        imports = collect_imports_in_file(path)
        oms_imports = [m for m, _ in imports if "oms" in m and _is_application_import(m)]
        assert not oms_imports, (
            f"pipeline_service.py still imports OMS: {oms_imports}"
        )

    def test_pipeline_service_no_servitization_import(self):
        """The specific line 1314 violation: pipeline_service.py must not import servitization."""
        path = ACTUAL_DESIGN_DIR / "services" / "pipeline_service.py"
        imports = collect_imports_in_file(path)
        srv_imports = [
            m for m, _ in imports
            if "servitization" in m and _is_application_import(m)
        ]
        assert not srv_imports, (
            f"pipeline_service.py still imports servitization: {srv_imports}"
        )

    def test_pipeline_service_no_agent_import(self):
        """Agent (application-layer) must not be imported from design."""
        path = ACTUAL_DESIGN_DIR / "services" / "pipeline_service.py"
        imports = collect_imports_in_file(path)
        agent_imports = [m for m, _ in imports if "agent" in m and _is_application_import(m)]
        assert not agent_imports, (
            f"pipeline_service.py still imports agent: {agent_imports}"
        )


# ============ Event bus tests ============

class TestEventBusDecouplesSubsystems:
    """Verify the event bus is the correct decoupling mechanism."""

    def test_events_module_importable(self):
        from odap.biz.core.ontology.design.events import (
            get_event_bus, EventBus, DomainEvent,
            EntityExtractedEvent, OntologyVersionRolledBackEvent,
        )
        assert get_event_bus is not None
        assert EventBus is not None
        assert EntityExtractedEvent is not None
        assert OntologyVersionRolledBackEvent is not None

    def test_event_bus_singleton(self):
        from odap.biz.core.ontology.design.events import get_event_bus, reset_event_bus
        reset_event_bus()
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2, "EventBus should be a singleton"

    def test_subscribe_and_publish(self):
        from odap.biz.core.ontology.design.events import (
            get_event_bus, reset_event_bus, OntologyVersionRolledBackEvent,
        )
        reset_event_bus()
        bus = get_event_bus()
        received = []
        bus.subscribe(
            OntologyVersionRolledBackEvent,
            lambda e: received.append(e),
        )
        bus.publish(OntologyVersionRolledBackEvent(ontology_id="o1", new_version_id="v2"))
        assert len(received) == 1
        assert received[0].ontology_id == "o1"
        assert received[0].new_version_id == "v2"

    def test_multiple_handlers(self):
        from odap.biz.core.ontology.design.events import (
            get_event_bus, reset_event_bus, EntityExtractedEvent,
        )
        reset_event_bus()
        bus = get_event_bus()
        results = []
        bus.subscribe(EntityExtractedEvent, lambda e: results.append("h1"))
        bus.subscribe(EntityExtractedEvent, lambda e: results.append("h2"))
        n = bus.publish(EntityExtractedEvent(entities=({"type": "Foo"},)))
        assert n == 2
        assert "h1" in results and "h2" in results

    def test_handler_exception_does_not_break_others(self):
        from odap.biz.core.ontology.design.events import (
            get_event_bus, reset_event_bus, EntityExtractedEvent,
        )
        reset_event_bus()
        bus = get_event_bus()
        results = []
        def bad_handler(e):
            raise RuntimeError("oops")
        bus.subscribe(EntityExtractedEvent, bad_handler)
        bus.subscribe(EntityExtractedEvent, lambda e: results.append("good"))
        # Should not raise even though bad_handler raised
        n = bus.publish(EntityExtractedEvent(entities=()))
        assert n == 2
        assert "good" in results

    def test_unsubscribe(self):
        from odap.biz.core.ontology.design.events import (
            get_event_bus, reset_event_bus, EntityExtractedEvent,
        )
        reset_event_bus()
        bus = get_event_bus()
        handler = lambda e: None
        bus.subscribe(EntityExtractedEvent, handler)
        assert bus.unsubscribe(EntityExtractedEvent, handler) is True
        # Re-unsubscribe returns False
        assert bus.unsubscribe(EntityExtractedEvent, handler) is False

    def test_publish_with_no_handlers_returns_zero(self):
        from odap.biz.core.ontology.design.events import (
            get_event_bus, reset_event_bus, OntologyCreatedEvent,
        )
        reset_event_bus()
        bus = get_event_bus()
        n = bus.publish(OntologyCreatedEvent(ontology_id="x"))
        assert n == 0

    def test_pipeline_calls_event_publish(self, monkeypatch):
        """The pipeline service's _on_ontology_version_rollback must publish an event."""
        from odap.biz.core.ontology.design.services.pipeline_service import (
            _on_ontology_version_rollback,
        )
        from odap.biz.core.ontology.design.events import (
            get_event_bus, reset_event_bus, OntologyVersionRolledBackEvent,
        )
        reset_event_bus()
        bus = get_event_bus()
        received = []
        bus.subscribe(
            OntologyVersionRolledBackEvent,
            lambda e: received.append(e),
        )
        # Simulate a rollback call
        _on_ontology_version_rollback(None, {"ontology_id": "o1", "version_id": "v2"})
        assert len(received) == 1
        assert received[0].ontology_id == "o1"
