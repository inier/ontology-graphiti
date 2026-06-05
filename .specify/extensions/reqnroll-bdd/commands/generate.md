---
description: "Generate Reqnroll-compatible Gherkin feature files, traceability mapping, and implementation handoff."
---

# Reqnroll BDD Generate

## User Input

```text
$ARGUMENTS
```

## Objective

Generate Reqnroll-compatible `.feature` files from `bdd-test-plan.md`.

Also generate traceability and implementation handoff artifacts for `/speckit.implement`.

## Required Inputs

Read:

- `specs/{feature}/bdd-test-plan.md`
- `specs/{feature}/spec.md`
- `specs/{feature}/plan.md` if present
- `specs/{feature}/tasks.md` if present
- `.specify/memory/constitution.md` if present

If `bdd-test-plan.md` does not exist, stop and tell the user to run:

```text
/speckit.reqnroll-bdd.plan
```

## Output Files

Generate or update:

```text
tests/{Project}.AcceptanceTests/Features/*.feature
specs/{feature}/bdd-traceability.md
specs/{feature}/bdd-implementation-handoff.md
```

If the target acceptance test project cannot be inferred, use:

```text
tests/AcceptanceTests/Features/
```

Document that assumption in `bdd-implementation-handoff.md`.

## Gherkin Rules

Feature files must:

1. Use Reqnroll-compatible Gherkin.
2. Place `@infrastructure` on the line immediately before `Feature:` so CI/CD pipelines can identify tests that require test infrastructure (in-memory fakes, test data builders, scenario context). Example:

    ```gherkin
    @infrastructure
    Feature: Account Balance Management
    ```

3. Use requirement language, not implementation language.
4. Tag each scenario with its source criteria ID, for example `@AC-001`.
5. Prefer one main `When` per scenario.
6. Keep each scenario focused on one behavior.
7. Use `Rule:` when multiple scenarios describe the same business rule.
8. Avoid UI implementation details.
9. Avoid Domain/Internal implementation names.
10. Give each generated scenario a stable scenario ID in comments or traceability, such as `SC-001`.

## Forbidden Terms in `.feature`

Do not use these unless they are actual domain language from the spec:

- Aggregate
- Repository
- DTO
- Handler
- Controller
- ViewModel
- Presenter
- Presentation-layer terms (e.g., UI widget, page, view, component names)
- method
- class
- service method
- database table

## Allowed Style

Allowed:

```gherkin
@infrastructure
Feature: Account Balance Management

  Rule: Deposits increase the account balance

    @AC-001
    Scenario: Making a single deposit increases balance
      Given the account has a balance of 100.00
      When a deposit of 50.00 is made
      Then the account balance should be 150.00
```

Forbidden:

```gherkin
Feature: Account Balance Management
  Scenario: AccountAggregate applies DepositCommand
    Given AccountAggregate has Balance.Value = 100
    When AccountAppService.Handle DepositCommand
    Then Balance.Value should be 150
```

## Traceability Output

Create:

```text
specs/{feature}/bdd-traceability.md
```

Required structure:

```markdown
# BDD Traceability

## Feature

{feature name}

## Criteria to Scenario Mapping

| Criteria ID | Scenario ID | Scenario Title | Feature File | Status |
| --- | --- | --- | --- | --- |

## Non-BDD Criteria

| Criteria ID | Recommended Test Type | Reason |
| --- | --- | ---   |

## Gaps

| Criteria ID | Gap | Required Action |
| --- | --- | --- |
```

## Implementation Handoff Output

Create:

```text
specs/{feature}/bdd-implementation-handoff.md
```

Required structure:

````markdown
# BDD Implementation Handoff

## Feature

{feature name}

## Purpose

This handoff guides `/speckit.implement` to implement the generated Reqnroll BDD specifications.

## Required Implementation Tasks

### Test Project

- Create or update the Reqnroll acceptance test project.
- Add the required Reqnroll test framework packages if missing.
- Ensure `.feature` files are included in the test project.

### Step Definitions

| Scenario ID | Feature File | Suggested Step Class | Binding Boundary |
| --- | --- | --- | --- |

### Step Definition Skeleton Guidance

Provide suggested skeletons for step definition classes.

The skeletons are guidance for `/speckit.implement`, not full implementation.

Allowed skeleton content:

- class name
- namespace suggestion
- `[Binding]`
- constructor injection for scenario context or Application-layer test facade
- Given / When / Then method signatures
- `throw new PendingStepException();`

Forbidden skeleton content:

- completed assertions
- domain rule calculations
- direct repository implementation
- production method internals
- Presentation-layer access (e.g., UI controls, pages, views)

Skeleton example:

```csharp
using Reqnroll;

namespace {AcceptanceTestNamespace}.Steps;

[Binding]
public sealed class {SuggestedStepClass}
{
    private readonly ScenarioContext _context;

    public {SuggestedStepClass}(ScenarioContext context)
    {
        _context = context;
    }

    [Given("{step pattern}")]
    public void GivenSomePrecondition()
    {
        throw new PendingStepException();
    }

    [When("{step pattern}")]
    public void WhenSomeActionOccurs()
    {
        throw new PendingStepException();
    }

    [Then("{step pattern}")]
    public void ThenSomeOutcomeIsObserved()
    {
        throw new PendingStepException();
    }
}
```

### Test Support

Create or update:

- Scenario context
- Test data builders
- In-memory repositories or fakes
- Application-layer test facade if useful

### Architecture Rules

- Step definitions may call Application Services or test-facing Application facades.
- Step definitions must not call Presentation-layer components.
- Step definitions must not depend on UI controls, pages, views, or presentation framework events.
- Feature files must remain implementation-agnostic.

### Suggested Task Insertions

Add these tasks to `tasks.md` or execute them during `/speckit.implement`:

| Task ID | Task | Depends On |
| --- | --- | --- |

### Required Verification

Run this if a .NET test project exists:

~~~bash
dotnet test
~~~

````

## Completion Criteria

The command is complete when:

- `.feature` files exist for all BDD candidates.
- Every generated scenario has an AC tag.
- `bdd-traceability.md` maps criteria to scenarios.
- `bdd-implementation-handoff.md` gives enough information for `/speckit.implement`.
- No C# implementation code is generated by this command.
- Step definition skeleton guidance is provided without full implementation logic.
