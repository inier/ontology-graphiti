# BDD Test Plan

## Feature

Guard Card Shield Stacking

## Summary

Validate that Guard cards add shield and multiple Guard cards stack their shield values within one turn.

## Acceptance Criteria Classification

| Criteria ID | Source | Classification | Reason | BDD Candidate |
| --- | --- | --- | --- | --- |
| AC-001 | spec.md | BDD | Observable player-facing battle rule | SC-001 |
| AC-002 | spec.md | BDD | Observable stacking behavior suitable for acceptance testing | SC-002 |
| AC-003 | spec.md | Not Testable Yet | Shield expiration rule is not defined clearly enough | No |
| AC-004 | spec.md | Manual / Smoke Test | Animation visibility is Presentation behavior | No |

## BDD Scenario Candidates

### SC-001: Playing one Guard card grants shield

- Source criteria: AC-001
- Test boundary: Application
- Reason: The scenario describes an observable rule without binding to implementation internals.

Draft:

```gherkin
@AC-001
Scenario: Playing one Guard card grants shield
  Given the player has 0 shield
  And the player has 1 Guard card in hand
  When the player plays the Guard card
  Then the player should have 5 shield
```

### SC-002: Playing two Guard cards stacks shield

- Source criteria: AC-002
- Test boundary: Application
- Reason: The scenario describes the stacking behavior that must remain true regardless of implementation.

Draft:

```gherkin
@AC-002
Scenario: Playing two Guard cards stacks shield
  Given the player has 0 shield
  And the player has 2 Guard cards in hand
  When the player plays both Guard cards
  Then the player should have 10 shield
  And both Guard cards should be in the discard pile
```

## Non-BDD Test Recommendations

| Criteria ID | Recommended Test Type | Reason |
| --- | --- | --- |
| AC-003 | Clarification before test design | End-of-turn shield rule is ambiguous |
| AC-004 | Manual / Smoke Test | Visual animation should not be bound directly to Reqnroll |

## Ambiguities and Missing Details

| Item | Problem | Suggested Clarification |
| --- | --- | --- |
| AC-003 | Shield expiration behavior is not defined | Specify whether shield expires at end of turn or persists |

## Architecture Notes

Step definitions should bind to Application-layer use cases.

Feature files must not expose Domain internals, Infrastructure details, or Presentation-layer components.
