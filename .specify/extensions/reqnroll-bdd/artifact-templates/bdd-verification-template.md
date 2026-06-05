# BDD Verification Report

## Feature

{feature_name}

## Summary

| Check | Result | Notes |
| --- | --- | --- |
| Acceptance criteria coverage | | |
| Scenario traceability | | |
| Gherkin quality | | |
| Architecture boundary | | |
| Reqnroll test execution | | |

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
- Result: {Passed | Failed | Skipped (pending implementation) | Skipped (no test project)}
- Notes:

### Interpreting Skipped Results

| Result | Meaning | Action |
| ------ | ------- | ------ |
| **Skipped (yellow/inconclusive)** | Step definitions exist but contain `PendingStepException()` | Normal after BDD-003 — proceed to BDD-004 implementation |
| **Failed (red)** | Step definitions exist but assertions fail or Application boundary throws | Debug step implementation or Application service |
| **Passed (green)** | All steps call Application boundary correctly and assertions hold | Feature is BDD-verified |

## Final Decision

{Pass | Pass with warnings | Fail}

## Required Follow-up Actions

| Priority | Action |
| --- | --- |
