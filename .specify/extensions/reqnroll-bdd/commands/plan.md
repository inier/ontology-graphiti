---
description: "Create a BDD test plan from the current Spec Kit feature specification."
---

# Reqnroll BDD Plan

## User Input

```text
$ARGUMENTS
```

## Objective

Create a BDD test plan from the active Spec Kit feature specification.

This command must not generate Gherkin files or C# code. It only classifies acceptance criteria and proposes BDD scenario candidates.

## Required Inputs

Locate and read the active feature artifacts:

- `specs/{feature}/spec.md`
- `specs/{feature}/plan.md` if present
- `specs/{feature}/tasks.md` if present
- `.specify/memory/constitution.md` if present

If `$ARGUMENTS` names a feature folder, use that folder.

If multiple feature folders exist and the active feature cannot be inferred, ask the user to specify the target feature folder.

## Core Rules

1. Treat BDD scenarios as executable requirement examples.
2. Prefer Application-layer acceptance tests for Reqnroll.
3. Do not turn every requirement into BDD.
4. Classify each acceptance criterion into one of:
   - BDD
   - Domain Unit Test
   - Application Test
   - Integration Test
   - Manual / Smoke Test
   - Not Testable Yet
5. Identify ambiguity before generating scenarios.
6. Do not use implementation terms in scenario candidates.
7. If acceptance criteria do not have IDs, assign stable IDs such as `AC-001` and record the mapping.

## Architecture Boundary Rules

BDD candidates may describe:

- user actions
- observable application behavior
- domain-visible state changes
- business rules
- accepted/rejected outcomes

BDD candidates must not mention:

- Aggregate
- Entity internals
- Repository
- DTO
- Handler
- Controller
- Presentation-layer components (e.g., UI widgets, pages, views)
- internal method names

## Output File

Create or update:

```text
specs/{feature}/bdd-test-plan.md
```

## Required Output Structure

```markdown
# BDD Test Plan

## Feature

{feature name}

## Summary

{short summary}

## Acceptance Criteria Classification

| Criteria ID | Source | Classification | Reason | BDD Candidate |
| --- | --- | --- | --- | --- |

## BDD Scenario Candidates

### SC-001: {scenario title}

- Source criteria: AC-001
- Test boundary: Application
- Reason: {why this is suitable for BDD}

Draft:

~~~gherkin
Scenario: {scenario title}
  Given ...
  When ...
  Then ...
~~~

## Non-BDD Test Recommendations

| Criteria ID | Recommended Test Type | Reason |
| --- | --- | --- |

## Ambiguities and Missing Details

| Item | Problem | Suggested Clarification |
| --- | --- | --- |

## Architecture Notes

Step definitions should bind to Application-layer use cases.

Feature files must not expose Domain internals, Infrastructure details, or Presentation-layer components.
```

## Completion Criteria

The command is complete when:

- Every acceptance criterion has been classified.
- Every BDD candidate has a source criteria ID.
- Ambiguous criteria are reported instead of guessed.
- No `.feature` or C# files are generated.
