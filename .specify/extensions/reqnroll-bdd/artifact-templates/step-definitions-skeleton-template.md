# Step Definitions Skeleton Guidance

## Purpose

This section provides suggested Reqnroll step definition skeletons for `/speckit.implement`.

The skeletons are intentionally incomplete. They define class shape, binding attributes, constructor dependencies, and pending step methods only.

They must not contain full business logic, production code implementation, domain calculations, repository implementation, or Presentation-layer binding.

## Suggested Step Definition Classes

| Step Class | Feature File | Scenario IDs | Binding Boundary | Notes |
| --- | --- | --- | --- | --- |
| {StepClassName} | {FeatureFile} | {ScenarioIds} | Application | Bind to Application service or test-facing facade |

## Skeleton Example

```csharp
using Reqnroll;

namespace {AcceptanceTestNamespace}.Steps;

[Binding]
public sealed class {StepClassName}
{
    private readonly {ScenarioContextClass} _context;

    public {StepClassName}({ScenarioContextClass} context)
    {
        _context = context;
    }

    [Given("{given_step_pattern}")]
    public void Given{StepMethodName}()
    {
        throw new PendingStepException();
    }

    [When("{when_step_pattern}")]
    public void When{StepMethodName}()
    {
        throw new PendingStepException();
    }

    [Then("{then_step_pattern}")]
    public void Then{StepMethodName}()
    {
        throw new PendingStepException();
    }
}
```

## Skeleton Rules

- Use `[Binding]` classes.
- Group related steps by feature or business capability.
- Inject only test support objects such as scenario context, test data builders, or an Application-layer test facade.
- Step methods may be generated with `throw new PendingStepException();`.
- Do not fill in assertions.
- Do not call production methods directly unless `/speckit.implement` later decides the correct Application boundary.
- Do not bind to Presentation-layer components (e.g., UI controls, pages, views).
- Do not implement domain calculations inside step definitions.

## Transition Guide: Skeleton → Implementation

After BDD-003 creates skeletons, BDD-004 must replace each `PendingStepException()` with Application-layer calls. Follow this pattern:

### Given Steps — Set up test state

Replace `throw new PendingStepException();` with calls to test data builders and scenario context:

```csharp
[Given("the account has a balance of {decimal}")]
public void GivenTheAccountHasBalance(decimal amount)
{
    // Build test state through Application-layer test facade
    var account = TestDataBuilder.Create()
        .WithBalance(amount)
        .Build();
    _context.SetEntityState(account);
}
```

### When Steps — Exercise the use case

Replace `throw new PendingStepException();` with a call to the Application Service or test facade:

```csharp
[When("a deposit of {decimal} is made")]
public void WhenADepositIsMade(decimal amount)
{
    // Exercise the Application-layer use case
    var facade = _context.GetServiceFacade();
    var result = facade.ProcessDeposit(_context.GetEntityId(), amount);
    _context.SetActionResult(result);
}
```

### Then Steps — Assert observable outcomes

Replace `throw new PendingStepException();` with assertions against scenario context:

```csharp
[Then("the account balance should be {decimal}")]
public void ThenTheAccountBalanceShouldBe(decimal expected)
{
    var account = _context.GetEntityState();
    Assert.Equal(expected, account.Balance);
}
```

### Key Rules

- Step methods call the Application boundary (service or test facade), never Domain internals directly.
- Scenario context carries state between steps.
- Test data builders produce consistent test fixtures.
- Assertions use standard test assertion libraries (xUnit/NUnit/MSTest), not domain-custom assertion helpers.
- After all steps are implemented, run `dotnet test` — scenarios should transition from "skipped" (yellow/inconclusive) to "passed" (green).
