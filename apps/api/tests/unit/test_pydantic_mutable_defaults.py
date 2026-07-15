"""
Regression test: detect mutable default values in Pydantic models.

Pydantic v2 fields with `= []`, `= {}`, or `= set()` are P0 violations because
Pydantic does NOT deep-copy them — the same mutable object is shared across
all instances, leading to subtle cross-instance contamination bugs.

This test uses AST scanning to catch all such patterns across the codebase.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(r"e:\DEMO\AI\ontology-graphiti")
ODAP_DIR = ROOT / "odap"

# Directories to scan
SCAN_DIRS = [
    ODAP_DIR / "biz",
    ODAP_DIR / "infra",
    ODAP_DIR / "web",
]

# Skip these (test fixtures, generated code)
SKIP_PATTERNS = {"__pycache__", ".git", "tests"}


def _is_pydantic_model_class(node: ast.ClassDef) -> bool:
    """Check if a class inherits from BaseModel."""
    for base in node.bases:
        # Direct name match: BaseModel
        if isinstance(base, ast.Name) and base.id in {"BaseModel", "RootModel"}:
            return True
        # Attr match: pydantic.BaseModel
        if isinstance(base, ast.Attribute) and base.attr in {"BaseModel", "RootModel"}:
            return True
    return False


def _is_mutable_default(node: ast.AST) -> bool:
    """Detect `[]`, `{}`, or `set()` literals as default values."""
    if isinstance(node, ast.List):
        return True
    if isinstance(node, ast.Dict):
        return True
    if isinstance(node, ast.Call):
        # set() / list() / dict() calls
        if isinstance(node.func, ast.Name) and node.func.id in {"set", "list", "dict"}:
            return True
    return False


def _is_already_fixed(node: ast.AST) -> bool:
    """Check if the field uses Field(default_factory=...) which is correct."""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "Field":
            for kw in node.keywords:
                if kw.arg in {"default_factory", "default"}:
                    return True
    return False


def scan_file(path: Path) -> list:
    """Return list of (line, field_name, default_repr) for mutable defaults in Pydantic models."""
    try:
        source = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    findings = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not _is_pydantic_model_class(node):
            continue

        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            target = stmt.target
            if not isinstance(target, ast.Name):
                continue

            # Check for `name: List[X] = []` pattern (no Field() wrapper)
            if stmt.value is None:
                continue
            if _is_already_fixed(stmt.value):
                continue
            if _is_mutable_default(stmt.value):
                findings.append((stmt.lineno, target.id, ast.unparse(stmt.value)))

    return findings


def collect_python_files():
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for path in scan_dir.rglob("*.py"):
            if any(part in SKIP_PATTERNS for part in path.parts):
                continue
            yield path


def test_no_pydantic_mutable_defaults():
    """No Pydantic model may use mutable default values like `= []` or `= {}`."""
    all_findings = []
    for path in collect_python_files():
        findings = scan_file(path)
        for lineno, field, default in findings:
            rel = path.relative_to(ROOT)
            all_findings.append(f"  {rel}:{lineno}  field={field!r}  default={default}")

    assert not all_findings, (
        f"\n\nFound {len(all_findings)} Pydantic mutable default(s).\n"
        "All must be replaced with `Field(default_factory=list/dict/set)`:\n\n"
        + "\n".join(all_findings)
    )


def test_schemas_compile_and_import():
    """Sanity check that all modified schemas still import correctly."""
    from odap.biz.core.ontology.application.runtime.api.schemas import (
        CreateFunctionRequest,
        CreateContractRequest,
        CreateTriggerRequest,
    )
    from odap.biz.core.ontology.application.oms.schemas import (
        ObjectTypeDefinition,
        ActionTypeDefinition,
    )
    from odap.biz.core.ontology.application.harness.api.schemas import (
        AdvanceStageRequest,
        CreateHITLRequest,
    )
    from odap.infra.object_service.schemas import ObjectQuery, ObjectQueryResult

    # Verify the fields work as expected
    fn = CreateFunctionRequest(name="test", target_object_type="X")
    assert fn.dependencies == []
    assert fn.input_schema == {}

    cq = CreateContractRequest(action_type_id="a-1")
    assert cq.read_set == []
    assert cq.preconditions == []

    ot = ObjectTypeDefinition(type_id="t", name="T")
    assert ot.properties == []
    assert ot.links == []

    at = ActionTypeDefinition(action_type_id="a", name="A", target_object_type="X")
    assert at.parameters == []
    assert at.required_roles == []

    tr = CreateTriggerRequest(name="trig", target_object_type="X")
    assert tr.conditions == []
    assert tr.parameters == {}

    adv = AdvanceStageRequest()
    assert adv.stage_output == {}

    hitl = CreateHITLRequest(stage="s", title="T")
    assert hitl.affected_objects == []

    oq = ObjectQuery()
    assert oq.filters == []
    assert oq.sorts == []

    oqr = ObjectQueryResult(object_id="o", object_type="X")
    assert oqr.properties == {}
    assert oqr.links == []


def test_independent_instances():
    """Each Pydantic model instance must have its own list/dict (no shared state)."""
    from odap.biz.core.ontology.application.runtime.api.schemas import (
        CreateFunctionRequest,
    )

    a = CreateFunctionRequest(name="a", target_object_type="X")
    b = CreateFunctionRequest(name="b", target_object_type="X")

    a.dependencies.append("dep1")
    assert b.dependencies == [], (
        f"CRITICAL: mutable default caused shared state! "
        f"b.dependencies is {b.dependencies} but should be []"
    )

    a.input_schema["key"] = "value"
    assert b.input_schema == {}, (
        f"CRITICAL: mutable default caused shared state! "
        f"b.input_schema is {b.input_schema} but should be {{}}"
    )
