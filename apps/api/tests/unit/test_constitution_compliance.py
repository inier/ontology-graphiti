"""Constitution compliance tests for SDD quality gates (G-1..G-12).

Validates that all active specs in `specs/` conform to the BMAD-derived
quality gates defined in `.specify/memory/constitution.md` §"SDD Quality Gates".

Gate mapping:
    G-1  : spec.md Acceptance Criteria use Given/When/Then or equivalent
    G-2  : architecture-impacting spec contains "业务价值" section
    G-3  : spec/plan/tasks consistency (delegated to speckit.analyze)
    G-4  : task granularity ≤ 1 working day
    G-5  : task independently verifiable
    G-6  : task includes verification criterion
    G-7  : routing specs reference test_route_exception_handling
    G-8  : DB/graph specs reference test_sql_injection OR test_audit_cypher_injection
    G-9  : architecture specs reference architecture-verify
    G-10 : tasks reference test command
    G-11 : new spec has prd.md OR explicit "No external business" note
    G-12 : story↔task 1:N relationship (when stories exist)

NOTE: This is a soft-guard test. Initially it reports compliance status
without failing. After a grace period, switch to hard-fail.
"""
import re
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent  # apps/api/tests/unit/

SPECS_ROOT = Path("specs")
CONSTITUTION_PATH = Path(".specify/memory/constitution.md")


def _all_specs() -> list[Path]:
    """Return all spec.md paths in the repo."""
    if not SPECS_ROOT.exists():
        return []
    return sorted(SPECS_ROOT.rglob("spec.md"))


def _all_tasks() -> list[Path]:
    if not SPECS_ROOT.exists():
        return []
    return sorted(SPECS_ROOT.rglob("tasks.md"))


def _all_plans() -> list[Path]:
    if not SPECS_ROOT.exists():
        return []
    return sorted(SPECS_ROOT.rglob("plan.md"))


def _read(p: Path) -> str:
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


# ---------------------------------------------------------------------------
# Constitution existence and version
# ---------------------------------------------------------------------------

def test_constitution_exists():
    """The constitution file MUST exist and be non-empty."""
    assert CONSTITUTION_PATH.exists(), f"missing: {CONSTITUTION_PATH}"
    txt = _read(CONSTITUTION_PATH)
    assert len(txt) > 200, "constitution is suspiciously short"
    # MUST contain the SDD Quality Gates section header
    assert "SDD Quality Gates" in txt, "missing 'SDD Quality Gates' section"
    # MUST declare a version
    assert re.search(r"\*\*Version\*\*:\s*\d+\.\d+\.\d+", txt), "missing Version header"


def test_constitution_lists_all_12_gates():
    """All 12 quality gates (G-1..G-12) MUST be declared."""
    txt = _read(CONSTITUTION_PATH)
    for n in range(1, 13):
        assert f"**G-{n}**" in txt, f"missing quality gate G-{n}"


# ---------------------------------------------------------------------------
# G-1: Acceptance Criteria in Given/When/Then form
# ---------------------------------------------------------------------------

def test_g1_specs_use_given_when_then():
    """G-1: every spec.md MUST contain Given/When/Then or equivalent assertions.

    Equivalent forms detected:
    - Markdown checkbox `- [ ]` for acceptance criteria
    - "Scenario:" Gherkin keyword
    - "When ... Then ..." prose
    """
    specs = _all_specs()
    if not specs:
        pytest.skip("no specs found")
    violations: list[str] = []
    for spec in specs:
        txt = _read(spec)
        if not txt:
            continue
        has_gwt = bool(
            re.search(r"Given[^\n]*\n[^\n]*When", txt, re.IGNORECASE | re.MULTILINE)
            or re.search(r"\*\*Given\*\*|\*\*When\*\*|\*\*Then\*\*", txt, re.IGNORECASE)
            or re.search(r"^\s*-\s*\[\s*[xX ]\s*\]", txt, re.MULTILINE)  # checkboxes
            or "Scenario:" in txt  # Gherkin
        )
        if not has_gwt:
            violations.append(str(spec))
    # Soft-guard: warn, don't fail (pre-BMAD specs may not have Gherkin)
    if violations:
        print(
            f"\n[G-1] {len(violations)}/{len(specs)} specs lack Given/When/Then "
            f"structure:\n  " + "\n  ".join(violations[:5])
        )
    # No hard assert; this is informational for now


# ---------------------------------------------------------------------------
# G-2: architecture-impacting spec MUST have "业务价值" section
# ---------------------------------------------------------------------------

def test_g2_architecture_specs_have_business_value():
    """G-2: specs touching architecture MUST contain a 业务价值 section."""
    specs = _all_specs()
    if not specs:
        pytest.skip("no specs found")
    arch_keywords = ("架构", "architecture", "routing", "认证", "权限", "audit")
    violations: list[str] = []
    for spec in specs:
        txt = _read(spec)
        if not any(kw in txt.lower() for kw in arch_keywords):
            continue  # not architecture-related, skip
        if "业务价值" not in txt and "Business Value" not in txt:
            violations.append(str(spec))
    if violations:
        print(
            f"\n[G-2] {len(violations)} architecture specs lack 业务价值 section:\n  "
            + "\n  ".join(violations[:5])
        )


# ---------------------------------------------------------------------------
# G-4: Task granularity — count tasks per spec
# ---------------------------------------------------------------------------

def test_g4_task_count_is_reasonable():
    """G-4: tasks per spec SHOULD be 2-20 (granularity check)."""
    tasks_files = _all_tasks()
    if not tasks_files:
        pytest.skip("no tasks.md found")
    oversized: list[tuple[str, int]] = []
    for tf in tasks_files:
        txt = _read(tf)
        n = len(re.findall(r"^##\s+T-\d+", txt, re.MULTILINE))
        if n > 30:
            oversized.append((str(tf), n))
    if oversized:
        print(
            f"\n[G-4] {len(oversized)} task lists may be too large to complete "
            f"in 1 day (re-evaluate granularity):\n  "
            + "\n  ".join(f"{p}: {n} tasks" for p, n in oversized[:5])
        )


# ---------------------------------------------------------------------------
# G-6: Task has verification criterion
# ---------------------------------------------------------------------------

def test_g6_tasks_have_verification():
    """G-6: each task MUST include a verification or test reference."""
    tasks_files = _all_tasks()
    if not tasks_files:
        pytest.skip("no tasks.md found")
    missing: list[tuple[str, str]] = []
    for tf in tasks_files:
        txt = _read(tf)
        # Split by task headings
        task_blocks = re.split(r"^##\s+T-\d+", txt, flags=re.MULTILINE)[1:]
        for i, block in enumerate(task_blocks, start=1):
            has_verify = bool(
                re.search(r"Verification|验证|✅|Acceptance|验收|pytest|curl", block, re.IGNORECASE)
            )
            if not has_verify:
                t_match = re.search(r"^##\s+(T-\d+)", block, re.MULTILINE)
                t_name = t_match.group(1) if t_match else f"task{i}"
                missing.append((str(tf), t_name))
    if missing:
        print(
            f"\n[G-6] {len(missing)} tasks may lack a verification criterion "
            f"(sample):\n  " + "\n  ".join(f"{p} :: {t}" for p, t in missing[:5])
        )


# ---------------------------------------------------------------------------
# G-7/G-8/G-9: Required regression test references in architecture specs
# ---------------------------------------------------------------------------

def test_g7_g8_g9_required_test_files_exist():
    """G-7/G-8/G-9: the regression test files referenced by quality gates
    MUST exist in the test suite."""
    required = [
        _TESTS_DIR / "test_route_exception_handling.py",    # G-7
        _TESTS_DIR / "test_audit_cypher_injection.py",      # G-8 (Cypher)
        _TESTS_DIR / "test_silent_except_handling.py",      # R-P1-004
        _TESTS_DIR / "test_function_length.py",             # R-P3-001
    ]
    for p in required:
        assert p.exists(), f"G-7/G-8 required test missing: {p}"


# ---------------------------------------------------------------------------
# G-11: New specs SHOULD have prd.md OR explicit "no external business" note
# ---------------------------------------------------------------------------

def test_g11_new_specs_have_prd_or_note():
    """G-11: every new spec directory SHOULD have prd.md or 业务方 note.

    Soft-guard: report only.
    """
    spec_dirs = [p.parent for p in _all_specs()]
    if not spec_dirs:
        pytest.skip("no specs found")
    missing: list[str] = []
    for sd in spec_dirs:
        if sd.name.startswith("000-"):
            continue  # legacy / no-business specs
        prd = sd / "prd.md"
        spec = sd / "spec.md"
        spec_txt = _read(spec)
        has_note = "No external business" in spec_txt or "无业务方" in spec_txt
        if not prd.exists() and not has_note:
            missing.append(str(sd))
    if missing:
        print(
            f"\n[G-11] {len(missing)} new specs lack prd.md / 业务方 note:\n  "
            + "\n  ".join(missing[:5])
        )
