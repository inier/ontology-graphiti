# BDD Implementation Handoff

## Feature

{feature_name}

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

Generate skeleton step definition classes only.

Skeletons may include:

- namespace
- `using Reqnroll;`
- `[Binding]`
- constructor injection for scenario context or Application-layer test facade
- method signatures for Given / When / Then steps
- `throw new PendingStepException();`

Skeletons must not include:

- full production logic
- completed assertions
- domain calculations
- repository implementations
- Presentation-layer access (e.g., UI controls, pages, views)

Example skeleton:

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
- Feature files must remain implementation-agnostic.

### Implementation Patterns

After skeletons are created, BDD-004 must replace each `PendingStepException()` with Application-layer calls. Follow these patterns:

#### Given → Set up test state via builders + scenario context

```csharp
[Given("the account has a balance of {decimal}")]
public void GivenTheAccountHasBalance(decimal amount)
{
    var account = TestDataBuilder.Create()
        .WithBalance(amount)
        .Build();
    _context.SetEntityState(account);
}
```

#### When → Exercise use case via Application facade

```csharp
[When("a deposit of {decimal} is made")]
public void WhenADepositIsMade(decimal amount)
{
    var facade = _context.GetServiceFacade();
    var result = facade.ProcessDeposit(_context.GetEntityId(), amount);
    _context.SetActionResult(result);
}
```

#### Then → Assert observable outcomes from scenario context

```csharp
[Then("the account balance should be {decimal}")]
public void ThenTheAccountBalanceShouldBe(decimal expected)
{
    var account = _context.GetEntityState();
    Assert.Equal(expected, account.Balance);
}
```

#### Expected Test State Transitions

| Phase | Step State | Test Result | Action |
| ----- | ---------- | ----------- | ------ |
| After BDD-003 | `PendingStepException()` | Scenarios show **skipped** (yellow/inconclusive) | Normal — proceed to BDD-004 |
| After BDD-004 | Application calls + assertions | Scenarios show **passed** (green) | Commit |
| After BDD-004 | If still skipped or failed | Inspect test output | Debug step bindings or Application boundary |

### Suggested Task Insertions

| Task ID | Task | Depends On |
| --- | --- | --- |

### Required Verification

```bash
dotnet test
```
