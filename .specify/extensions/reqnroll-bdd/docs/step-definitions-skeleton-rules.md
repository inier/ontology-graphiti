# Step Definitions Skeleton Rules

## Purpose

Step definition skeleton guidance helps `/speckit.implement` create the Reqnroll binding surface without over-generating production logic.

## Allowed

Skeletons may include:

- namespace suggestion
- `using Reqnroll;`
- `[Binding]`
- class declaration
- constructor injection
- scenario context dependency
- Application-layer test facade dependency
- Given / When / Then method signatures
- `throw new PendingStepException();`

## Forbidden

Skeletons must not include:

- completed assertions
- domain calculations
- production code internals
- repository implementation
- infrastructure setup beyond test support placeholders
- Presentation-layer access (e.g., UI controls, pages, views)
- visual or animation assertions

## Recommended Skeleton Pattern

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

    [Given("{step pattern}")]
    public void GivenSomePrecondition()
    {
        throw new PendingStepException();
    }
}
```

## Boundary

Skeletons define the binding surface only.

The actual implementation should be completed later through Application Services or test-facing Application facades.

## Transition: Skeleton → Implementation

After skeletons are created (BDD-003), the implementation task (BDD-004) must replace each `PendingStepException()` with Application-layer calls. Follow these patterns:

### Given → Set up test state via builders + context

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

### When → Exercise use case via Application facade

```csharp
[When("a deposit of {decimal} is made")]
public void WhenADepositIsMade(decimal amount)
{
    var facade = _context.GetServiceFacade();
    var result = facade.ProcessDeposit(_context.GetEntityId(), amount);
    _context.SetActionResult(result);
}
```

### Then → Assert observable outcomes from context

```csharp
[Then("the account balance should be {decimal}")]
public void ThenTheAccountBalanceShouldBe(decimal expected)
{
    var account = _context.GetEntityState();
    Assert.Equal(expected, account.Balance);
}
```

### Key constraints

- Steps call the Application boundary (service or test facade), never Domain internals.
- Scenario context carries state between steps.
- After implementation, `dotnet test` should transition scenarios from "skipped" (PendingStepException → yellow/inconclusive) to "passed" (green).
