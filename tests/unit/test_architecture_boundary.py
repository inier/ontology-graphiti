"""
Architecture Boundary Guard Test

Enforces separation between Design and Application ontology subsystems.
Rules:
 1. Application code MUST NOT import from `odap.biz.core.ontology.design.*`
    EXCEPT through `odap.biz.core.ontology.design.contract.*`.
 2. Design code MUST NOT depend on `application/`.
 3. The contract layer is the only allowed bridge.
 4. Cross-cutting access (read-only ontology queries) goes via design/contract
    or via `odap.infra.query` (the unified semantic query service).
"""
import re
from pathlib import Path

ROOT = Path(r"e:\DEMO\AI\ontology-graphiti")
ONTOLOGY_DIR = ROOT / "odap" / "biz" / "core" / "ontology"
DESIGN_DIR = ONTOLOGY_DIR / "design"
APPLICATION_DIR = ONTOLOGY_DIR / "application"
CONTRACT_DIR = DESIGN_DIR / "contract"

# Application files must NOT use absolute imports of design internals
ABSOLUTE_DESIGN_INTERNAL_IMPORT = re.compile(
    r"from\s+odap\.biz\.core\.ontology\.design\."
    r"(model|engine|version|ingestion|schema|ingestion_split|mock_data|impl|services|storage|interfaces|models)\b"
)

# Design files must NOT use absolute imports of application
ABSOLUTE_APPLICATION_IMPORT = re.compile(
    r"from\s+odap\.biz\.core\.ontology\.application\b"
)

# Design files must NOT reach into application/ via relative paths (..runtime, ..oms, etc.)
RELATIVE_DESIGN_TO_APPLICATION = re.compile(
    r"from\s+\.\.(runtime|servitization|team_agent|oms|abution_graph|harness|api|query_api)\b"
)


def collect_python_files(directory: Path):
    if not directory.exists():
        return []
    return list(directory.rglob("*.py"))


def test_application_does_not_import_design_internals():
    """Application MUST NOT import design internals — use design.contract only."""
    app_files = collect_python_files(APPLICATION_DIR)
    violations = []

    for f in app_files:
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for match in ABSOLUTE_DESIGN_INTERNAL_IMPORT.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                f"  {f.relative_to(ROOT)}:{line_num}: {match.group(0).strip()}"
            )

    assert not violations, (
        "Application code MUST NOT import from design internals.\n"
        "Use `odap.biz.core.ontology.design.contract.get_design_contract()` instead.\n\n"
        "Violations:\n" + "\n".join(violations)
    )


def test_design_does_not_import_application():
    """Design MUST NOT depend on application/ (downstream is forbidden)."""
    design_files = collect_python_files(DESIGN_DIR)
    violations = []

    for f in design_files:
        try:
            content = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for match in ABSOLUTE_APPLICATION_IMPORT.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                f"  {f.relative_to(ROOT)}:{line_num}: {match.group(0).strip()}"
            )

        for match in RELATIVE_DESIGN_TO_APPLICATION.finditer(content):
            line_num = content[: match.start()].count("\n") + 1
            violations.append(
                f"  {f.relative_to(ROOT)}:{line_num}: {match.group(0).strip()}"
            )

    assert not violations, (
        "Design code MUST NOT depend on application/ (upstream may not import downstream).\n\n"
        "Violations:\n" + "\n".join(violations)
    )


def test_contract_layer_exposes_factory():
    """The contract package must export get_design_contract()."""
    init_file = CONTRACT_DIR / "__init__.py"
    assert init_file.exists(), f"Contract init missing: {init_file}"

    content = init_file.read_text(encoding="utf-8")
    assert "get_design_contract" in content, (
        "Contract layer must expose get_design_contract() factory"
    )
    assert "OntologyDesignContract" in content, (
        "Contract layer must expose OntologyDesignContract interface"
    )


def test_contract_interface_defines_immutable_views():
    """View types exposed via contract must be @dataclass(frozen=True)."""
    interface_file = CONTRACT_DIR / "interface.py"
    assert interface_file.exists(), f"Interface file missing: {interface_file}"

    content = interface_file.read_text(encoding="utf-8")
    view_classes = [
        "EntityTypeView",
        "RelationTypeView",
        "PropertyView",
        "OntologyVersionView",
        "OntologyDocumentView",
    ]
    for cls in view_classes:
        # Find "@dataclass(...)" decorator and the class header that follows
        # The class may have multi-line decorator (e.g., @dataclass(...)
        # plus nested @field stuff). We just check that "frozen" appears
        # in the same "decorator block" before the class.
        class_idx = content.find(f"class {cls}")
        assert class_idx > 0, f"View class {cls} not found in interface.py"
        # Look back at most 500 chars for the @dataclass decorator
        prefix = content[max(0, class_idx - 500):class_idx]
        last_dataclass = prefix.rfind("@dataclass")
        assert last_dataclass >= 0, (
            f"View class {cls} is missing @dataclass decorator"
        )
        decorator_text = prefix[last_dataclass:]
        assert "frozen" in decorator_text, (
            f"View class {cls} MUST be @dataclass(frozen=True). "
            f"Found decorator: {decorator_text[:120]!r}"
        )
