---
name: speckit-architecture-guard-architecture-verify
description: 'Perform an architecture-aware verification gate validating implementation against spec, plan, tasks, and constitution. Stricter than architecture-review; can block CI/CD.'
compatibility: Requires spec-kit project structure with .specify/ directory and architecture-guard extension v1.8.9+
metadata:
  author: DyanGalih
  source: architecture-guard:commands/architecture-verify.md
---

# speckit.architecture-guard.architecture-verify

Architecture-aware verification gate. This is a STRICTER version of `architecture-review` designed to run as a release/CI gate.

## Usage

```
/speckit.architecture-guard.architecture-verify [scope]
```

**Scope**: Optional — defaults to the latest feature. Supports `--strict` flag to fail on warnings.

## When to Use

- Pre-merge verification
- Pre-release verification
- After a major refactor
- Before deployment to production

## Process

1. **Load All Artifacts** (spec, plan, tasks, constitutions).
2. **Run Architecture Review** with `--strict` mode.
3. **Run Violation Detection** across the entire codebase.
4. **Run Spec Compliance** check — verify each acceptance scenario has implementation evidence.
5. **Run Test Coverage** check — verify critical paths have tests.
6. **Generate Verification Report** with PASS/FAIL status.

## Output Format

```text
# Architecture Verification: [feature-name]

## Gates
- [✅] Spec compliance: 14/14 scenarios
- [✅] Boundary rules: 0 violations
- [⚠️] Test coverage: 85% (target 90%)
- [✅] Constitution compliance: PASS

## Decision
**Status**: PASS
**Blockers**: 0
**Warnings**: 2
**Score**: 92/100
```

## Exit Codes

This command emits a process exit code:
- `0` — PASS (all gates green)
- `1` — FAIL (blockers present)
- `2` — WARN (warnings only, configurable)

## CI/CD Integration

```yaml
# Example GitHub Action
- name: Architecture Verify
  run: |
    /speckit.architecture-guard.architecture-verify specs/001-feature
    if [ $? -ne 0 ]; then exit 1; fi
```

## Difference from architecture-review

| Aspect | review | verify |
|--------|--------|--------|
| Read-only | ✅ | ✅ |
| Refactor generation | ✅ | ❌ (only report) |
| Exit code | no | yes (CI-friendly) |
| Strict mode | optional | default |
| Use case | development | release |

## Notes

- Use `--strict` to fail on warnings
- For the lighter planning-phase check, use `violation-detection`
- For refactor-task generation, use `refactor-generator`
