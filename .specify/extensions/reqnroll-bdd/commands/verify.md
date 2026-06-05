---
description: "Verify BDD coverage, scenario quality, architecture boundaries, and optional Reqnroll test execution."
---

# Reqnroll BDD Verify

## User Input

```text
$ARGUMENTS
```

## Objective

Verify that generated BDD artifacts are complete, traceable, and architecturally clean.

Optionally run `dotnet test` if a .NET test project is present.

## Required Inputs

Read:

- `specs/{feature}/spec.md`
- `specs/{feature}/bdd-test-plan.md`
- `specs/{feature}/bdd-traceability.md`
- `specs/{feature}/bdd-implementation-handoff.md`
- generated `.feature` files
- `.specify/memory/constitution.md` if present

## Verification Checks

### 1. Acceptance Criteria Coverage

Check:

- Every acceptance criterion is classified.
- Every BDD-classified criterion has at least one scenario.
- Every scenario maps back to at least one criterion.

### 2. Scenario Traceability

Check:

- Every scenario has a tag like `@AC-001`.
- Every tag exists in the traceability table.
- No orphan scenario exists.

### 3. Gherkin Quality

Check:

- Scenario titles are specific.
- Scenario has clear `Given` / `When` / `Then`.
- Scenario has no more than one main `When` unless justified.
- Scenario is not too broad.
- Scenario does not assert unrelated outcomes.
- Scenario does not use vague wording such as "works correctly".

### 4. Architecture Boundary

Fail if `.feature` files mention implementation details such as:

- Aggregate
- Repository
- DTO
- Handler
- Controller
- ViewModel
- Presenter
- Presentation-layer terms (e.g., UI widget, page, view, component names)
- method names
- class names

Warn if step implementation guidance binds directly to Presentation.

### 5. Reqnroll / dotnet Test Execution

If a `.sln` or `.csproj` exists and Reqnroll packages appear configured, run:

```bash
dotnet test
```

If no test project exists, skip test execution and report it as skipped, not failed.

Interpreting test results:

| Result | Meaning | Verdict |
| ------ | ------- | ------- |
| All green | All scenarios pass | Pass |
| Yellow / inconclusive | `PendingStepException()` still present in step definitions — implementation not yet completed | Warning — note that BDD-004 is pending |
| Red / failures | Assertions fail or Application boundary throws | Fail — requires debugging |
| No test project | Cannot run tests | Skipped — not a failure |

## Output File

Create or update:

```text
specs/{feature}/bdd-verification.md
```

## Required Output Structure

```markdown
# BDD Verification Report

## Feature

{feature name}

## Summary

| Check | Result | Notes |
| --- | --- | --- |
| Acceptance criteria coverage | Pass/Warning/Fail | |
| Scenario traceability | Pass/Warning/Fail | |
| Gherkin quality | Pass/Warning/Fail | |
| Architecture boundary | Pass/Warning/Fail | |
| Reqnroll test execution | Pass/Skipped/Fail | |

## Coverage Details

| Criteria ID | Status | Scenario(s) | Notes |
| --- | --- | --- | --- |

## Scenario Quality Findings

| Severity | Scenario | Problem | Suggested Fix |
| --- | --- | --- | --- |

## Architecture Boundary Findings

| Severity | File | Term/Issue | Suggested Fix |
| --- | --- | --- | --- |

## Test Execution

- Command:
- Result:
- Notes:

## Final Decision

One of:

- Pass
- Pass with warnings
- Fail

## Required Follow-up Actions

| Priority | Action |
| --- | --- |
```

## Pass / Fail Rules

Fail if:

- Any BDD-classified acceptance criterion has no scenario.
- Any scenario lacks traceability.
- Feature files expose implementation details.
- `dotnet test` runs and fails (red / assertion failures).

Warn if:

- Test execution is skipped because no Reqnroll project exists.
- Tests return yellow/inconclusive (step definitions have `PendingStepException()` — BDD-004 implementation is pending).
- Scenario wording is vague.
- A scenario is too broad.
- A criterion is classified as Not Testable Yet.

Pass only if:

- All BDD criteria are covered.
- All scenarios are traceable.
- No architecture leakage exists.
- Optional tests pass or are justifiably skipped/pending.
