---
name: speckit-architecture-guard-violation-detection
description: 'Detect architecture violations in plans, tasks, and implementation summaries. Lightweight scanning for early drift detection during planning phase.'
compatibility: Requires spec-kit project structure with .specify/ directory and architecture-guard extension v1.8.9+
metadata:
  author: DyanGalih
  source: architecture-guard:commands/violation-detection.md
---

# speckit.architecture-guard.violation-detection

Lightweight architecture violation scanner for the planning phase. Use this command after writing `plan.md` to catch boundary violations before implementation starts.

## Usage

```
/speckit.architecture-guard.violation-detection [scope]
```

**Scope**: Optional — defaults to the latest plan. Can be `plan`, `tasks`, or `implementation`.

## Process

1. **Load Architecture Constitution**: Read `.specify/memory/architecture_constitution.md` (if present) and the active framework preset.
2. **Static Analysis** of plan.md:
   - Module references that violate boundary rules
   - Cross-layer imports (e.g., `infra` importing from `api`)
   - Missing or broken contract layers
   - Hard-coded module paths in plan steps
3. **Static Analysis** of tasks.md (if provided):
   - Tasks that would create cross-boundary code
   - Tasks that bypass abstraction layers
   - Tasks with no test coverage (TDD violations)
4. **Output Drift Report** with confidence scores.

## Output Format

```text
# Violation Detection Report

## Module Boundary Violations
- ❌ plan.md:142 — "service imports storage directly" (bypasses contract)
- ⚠️ plan.md:203 — "ambiguous module reference" — needs clarification

## Layer Violations
- ❌ plan.md:78 — "infra → api direction" (should be api → infra)

## Test Coverage Gaps
- ⚠️ tasks.md:T045 — No test task defined for new module

## Summary
- Critical: 2
- Warnings: 5
- Suggestions: 3
```

## Integration

This command is registered as `after_plan` hook in `extension.yml`. It runs automatically after `/speckit.plan` completes and offers a non-blocking prompt:

> "Would you like to scan the technical plan for architectural drift and Constitution violations?"

## Notes

- **Non-blocking**: Violations do not fail the plan; they generate refactor tasks
- **Read-only**: Does not modify plan.md or tasks.md
- Use `architecture-review` for full post-implementation review
- Use `refactor-generator` to convert violations into tasks
