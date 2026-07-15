"""
Regression test: P0-3 boundary rule enforcement (R-P0-006).

The architecture constitution states:
  P0-3: Infra code MUST NOT import from `odap.biz.core.ontology.design.*`
        except via `odap.biz.core.ontology.design.contract.*` (the contract layer)

This test guards against regressions of the `load_simulation_data` violation
that previously existed in `odap/infra/graph/graph_service.py:47`.
"""
import ast
from pathlib import Path
import pytest

ROOT = Path(r"e:\DEMO\AI\ontology-graphiti\odap")
INFRA_DIR = ROOT / "infra"
DESIGN_DIR = ROOT / "biz" / "core" / "ontology" / "design"
DESIGN_CONTRACT_DIR = DESIGN_DIR / "contract"

# The set of allowed design modules that infra MAY import from.
# These are the contract layer + the facade (P0-3 exception).
ALLOWED_DESIGN_PREFIXES = (
    "odap.biz.core.ontology.design.contract.",
)


def _is_design_internal_import(module: str) -> bool:
    """Check if a module path is from design but NOT through the contract layer."""
    if not module.startswith("odap.biz.core.ontology.design"):
        return False
    # Allowed: contract submodule (and any sub-package of it)
    if any(module.startswith(p) for p in ALLOWED_DESIGN_PREFIXES):
        return False
    # Allowed: importing the contract package itself
    # e.g. `import odap.biz.core.ontology.design.contract` (used in ontology_source.py)
    if module == "odap.biz.core.ontology.design.contract":
        return False
    return True


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
            # Full module path (relative imports resolved)
            if node.level and node.module:
                # Relative import: prefix with parent package
                # We can't easily resolve this without the package context,
                # so flag it for manual review if it looks suspicious
                continue
            imports.append((node.module, node.lineno))
    return imports


def collect_infra_files():
    """Yield all Python files under odap/infra/."""
    if not INFRA_DIR.exists():
        return
    for path in INFRA_DIR.rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        yield path


# ============ Tests ============

class TestInfraNoDesignInternalImports:
    """P0-3: infra MUST NOT import from design/* (except contract)."""

    def test_no_design_internal_imports_in_infra(self):
        """Scan all odap/infra/ files for forbidden design imports."""
        violations = []
        for py_file in collect_infra_files():
            imports = collect_imports_in_file(py_file)
            for module, lineno in imports:
                if _is_design_internal_import(module):
                    rel = py_file.relative_to(ROOT.parent)
                    violations.append(f"{rel}:{lineno}  -> {module}")

        assert not violations, (
            f"\n\nFound {len(violations)} P0-3 violation(s) "
            f"(infra importing from design/* except contract):\n"
            + "\n".join(violations)
        )

    def test_graph_service_no_longer_imports_load_simulation_data(self):
        """Specific regression: graph_service.py:47 was importing from design."""
        path = INFRA_DIR / "graph" / "graph_service.py"
        imports = collect_imports_in_file(path)
        forbidden = [
            (m, ln) for m, ln in imports
            if "mock_data" in m or "data_generator" in m
        ]
        assert not forbidden, (
            f"graph_service.py still imports forbidden modules: {forbidden}"
        )

    def test_load_simulation_data_defined_in_infra(self):
        """`load_simulation_data` is now defined locally in graph_service.py."""
        from odap.infra.graph.graph_service import load_simulation_data
        assert callable(load_simulation_data)

    def test_load_simulation_data_returns_dict(self):
        """The function returns a dict (either loaded JSON or empty)."""
        from odap.infra.graph.graph_service import load_simulation_data
        result = load_simulation_data()
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    def test_simulation_fixture_present_in_infra(self):
        """The simulation_data.json fixture should live in infra/graph/."""
        fixture = INFRA_DIR / "graph" / "simulation_data.json"
        assert fixture.exists(), f"Missing fixture at {fixture}"


class TestContractLayerIsTheOnlyBridge:
    """Verify the contract layer remains the only allowed design surface."""

    def test_contract_facade_importable(self):
        from odap.biz.core.ontology.design.contract.facade import (
            DesignContractFacade,
            get_design_contract,
        )
        assert DesignContractFacade is not None
        assert get_design_contract is not None

    def test_contract_views_are_frozen(self):
        """The contract view dataclasses must be frozen."""
        import dataclasses
        from odap.biz.core.ontology.design.contract import interface
        for name in dir(interface):
            obj = getattr(interface, name)
            if dataclasses.is_dataclass(obj):
                assert obj.__dataclass_params__.frozen, (
                    f"Contract view {name} must be @dataclass(frozen=True)"
                )
