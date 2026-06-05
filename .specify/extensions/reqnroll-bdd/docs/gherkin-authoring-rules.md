# Gherkin Authoring Rules

## Good Feature File

```gherkin
@infrastructure
Feature: Account Balance Management
  Users can deposit funds and view their updated account balance.

  Rule: Deposits increase the account balance

    @AC-001
    Scenario: Making a single deposit increases balance
      Given the account has a balance of 100.00
      When a deposit of 50.00 is made
      Then the account balance should be 150.00

    @AC-002
    Scenario: Making multiple deposits accumulates balance
      Given the account has a balance of 100.00
      When a deposit of 50.00 is made
      And a deposit of 25.00 is made
      Then the account balance should be 175.00
```

## Bad Feature File

```gherkin
Feature: Account Balance Management
  Scenario: AccountAggregate applies DepositCommand
    Given AccountAggregate has Balance.Value = 100
    When AccountAppService.Handle DepositCommand
    Then Balance.Value should be 150
```

## Rules

- Tag the `Feature:` line with `@infrastructure` so CI/CD can identify tests that need test infrastructure (in-memory fakes, builders, scenario context).
- Use user-facing language appropriate to the domain.
- Use domain language only when it is part of the product vocabulary.
- Avoid class names and method names.
- Prefer one main `When`.
- Keep each scenario focused.
- Tag every scenario with its source acceptance criterion.
- Use `Rule:` to group multiple scenarios under the same business rule.
- Avoid UI implementation details unless the spec is explicitly about UI behavior.
