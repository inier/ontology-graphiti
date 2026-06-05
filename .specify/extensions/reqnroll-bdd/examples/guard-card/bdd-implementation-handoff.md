# BDD Implementation Handoff

## Feature

Guard Card Shield Stacking

## Purpose

This handoff guides `/speckit.implement` to implement the generated Reqnroll BDD specifications.

## Required Implementation Tasks

### Test Project

- Create or update the Reqnroll acceptance test project.
- Add the required Reqnroll test framework packages if missing.
- Ensure `.feature` files are included in the test project.

Assumption:

```text
tests/AcceptanceTests/Features/
```

is used because the target project name cannot be inferred from the example alone.

### Step Definitions

| Scenario ID | Feature File | Suggested Step Class | Binding Boundary |
| --- | --- | --- | --- |
| SC-001 | GuardCard.feature | GuardCardSteps | Application |
| SC-002 | GuardCard.feature | GuardCardSteps | Application |

### Test Support

Create or update:

- Scenario context
- Battle test data builder
- Card test data builder
- In-memory battle repository or fake battle state
- Application-layer test facade if useful

### Architecture Rules

- Step definitions may call Application Services or test-facing Application facades.
- Step definitions must not call Presentation-layer components.
- Step definitions must not depend on UI controls, pages, views, or presentation framework events.
- Feature files must remain implementation-agnostic.

### Implementation Patterns

After skeletons are created (BDD-003), BDD-004 must replace each `PendingStepException()` with Application-layer calls:

**Given → Set up test state via builders + scenario context:**

```csharp
[Given("the player has {int} shield")]
public void GivenThePlayerHasShield(int amount)
{
    var battle = BattleTestDataBuilder.Create()
        .WithPlayerShield(amount)
        .Build();
    _context.SetBattleState(battle);
}
```

**When → Exercise use case via Application facade:**

```csharp
[When("the player plays the Guard card")]
public void WhenThePlayerPlaysTheGuardCard()
{
    var facade = _context.GetBattleFacade();
    var result = facade.PlayCard(_context.GetPlayerId(), CardType.Guard);
    _context.SetActionResult(result);
}
```

**Then → Assert observable outcomes from scenario context:**

```csharp
[Then("the player should have {int} shield")]
public void ThenThePlayerShouldHaveShield(int expected)
{
    var battle = _context.GetBattleState();
    Assert.Equal(expected, battle.PlayerShield);
}
```

**Expected test state transitions:**

| Phase | Step State | Test Result | Action |
| ----- | ---------- | ----------- | ------ |
| After BDD-003 | `PendingStepException()` | Scenarios show **skipped** (yellow/inconclusive) | Normal — proceed to BDD-004 |
| After BDD-004 | Application calls + assertions | Scenarios show **passed** (green) | Commit |
| After BDD-004 | If still skipped or failed | Inspect test output | Debug step bindings or Application boundary |

### Suggested Task Insertions

| Task ID | Task | Depends On |
| --- | --- | --- |
| BDD-001 | Create or update the Reqnroll acceptance test project | None |
| BDD-002 | Include GuardCard.feature in the acceptance test project | BDD-001 |
| BDD-003 | Create GuardCardSteps skeletons with Given / When / Then method signatures and `PendingStepException` | BDD-002 |
| BDD-004 | Complete GuardCardSteps through the Application boundary or an Application-layer test facade | BDD-003 |
| BDD-005 | Add scenario context, battle and card test data builders, in-memory battle state, and optional Application-layer test facade | BDD-003 |
| BDD-006 | Run acceptance tests and fix failing implementation | BDD-004, BDD-005 |

### Required Verification

Run this if a .NET test project exists:

```bash
dotnet test
```
