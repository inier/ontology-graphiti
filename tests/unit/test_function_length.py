"""R-P3-001 enforcement: functions MUST be ≤ 40 lines (governance rule).

Per `.specify/memory/constitution.md` §"I. 简单":
    "每个函数 MUST 只做一件事；函数体超过 40 行时 MUST 拆分"

This is the CI gate. Currently informational (counts violations); can be made
hard-fail by changing the ``max(1, ... )`` line below.

Tracked in R-P3-001: split 213 functions > 40 lines (opportunistic).
"""
import ast
from pathlib import Path

import pytest

# Per constitution §"I. 简单"
MAX_FUNCTION_LINES = 40

# Allowlist: certain files are exempt (entrypoints, mock data generators, DB init)
EXEMPT_FILES = (
    "odap/web/api/app.py",          # local dev entry — large builder functions
    "odap/tools/",                  # mock data generators
    "tests/",                       # tests may be long
    "migrations/",                  # raw SQL may be long
)


def _is_exempt(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(e in s for e in EXEMPT_FILES)


def _collect_violations() -> list[tuple[str, int, int, str]]:
    """Walk odap/ and collect all (file, line, n_lines, function_name) > MAX."""
    violations: list[tuple[str, int, int, str]] = []
    for f in Path("odap").rglob("*.py"):
        if _is_exempt(f):
            continue
        try:
            src = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            n_lines = (node.end_lineno or node.lineno) - node.lineno + 1
            if n_lines > MAX_FUNCTION_LINES:
                violations.append(
                    (str(f).replace("\\", "/"), node.lineno, n_lines, node.name)
                )
    violations.sort(key=lambda x: -x[2])
    return violations


def test_function_length_drift_summary():
    """Informational: report drift count (does not hard-fail yet).

    Goal: track progress of R-P3-001. When this count reaches 0, switch to the
    hard-fail variant below.
    """
    violations = _collect_violations()
    n = len(violations)
    # Top 10 offenders printed for visibility
    top = "\n".join(f"  {f}:{l} {n:>3}L {name}" for f, l, n, name in violations[:10])
    print(f"\n[R-P3-001] {n} functions > {MAX_FUNCTION_LINES} lines in non-exempt code")
    if top:
        print(f"Top 10 offenders:\n{top}")
    # Currently informational; will become hard-fail when count = 0
    # Uncomment the assert below to enable hard-fail
    # assert n == 0, f"{n} functions > {MAX_FUNCTION_LINES} lines (R-P3-001 still in progress)"


def test_no_function_exceeds_40_lines_in_exempt_files_clean():
    """Exempt files are still scanned, but only for new growth (regression check).

    We don't assert on absolute count for exempt files, but we DO require that
    the count hasn't grown compared to the baseline snapshot below.
    """
    # Baseline counts captured 2026-06-05
    BASELINE_EXEMPT = {
        "odap/web/api/app.py": 2,  # _build_app + MockDataWebService.__init__
    }
    violations_by_file: dict[str, int] = {}
    for rel, _count in BASELINE_EXEMPT.items():
        p = Path(rel)
        if not p.exists():
            continue
        try:
            src = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        n = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nl = (node.end_lineno or node.lineno) - node.lineno + 1
                if nl > MAX_FUNCTION_LINES:
                    n += 1
        violations_by_file[rel] = n

    for rel, baseline in BASELINE_EXEMPT.items():
        current = violations_by_file.get(rel, 0)
        assert current <= baseline, (
            f"{rel}: {current} long functions (baseline {baseline}). "
            f"Refactor existing long functions in this exempt file before adding new ones."
        )


def test_function_length_regression_guard():
    """Hard-fail guard: in non-exempt code, no NEW functions may exceed 40 lines.

    Tracks a snapshot of offenders. Any function in the snapshot is allowed
    to stay (R-P3-001 backlog), but no NEW long function may be added.
    """
    # Snapshot of current offenders (regenerated on each test run)
    violations = _collect_violations()
    snapshot_path = Path("tests/unit/test_function_length_snapshot.txt")
    if not snapshot_path.exists():
        snapshot_path.write_text(
            "\n".join(f"{f}:{l} {n}L {name}" for f, l, n, name in violations),
            encoding="utf-8",
        )
        return  # first run: seed the snapshot

    snapshot_lines = snapshot_path.read_text(encoding="utf-8").strip().splitlines()
    snapshot_set = set(snapshot_lines)
    current_set = {f"{f}:{l} {n}L {name}" for f, l, n, name in violations}

    new_violations = current_set - snapshot_set
    assert not new_violations, (
        f"{len(new_violations)} new long functions introduced (forbidden):\n  "
        + "\n  ".join(sorted(new_violations))
    )

    # If we got here, we can prune the snapshot
    removed = snapshot_set - current_set
    if removed:
        # Re-write snapshot (drift went down — good!)
        snapshot_path.write_text("\n".join(sorted(current_set)), encoding="utf-8")
