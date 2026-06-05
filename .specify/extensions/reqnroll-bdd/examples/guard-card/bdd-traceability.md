# BDD Traceability

## Feature

Guard Card Shield Stacking

## Criteria to Scenario Mapping

| Criteria ID | Scenario ID | Scenario Title | Feature File | Status |
| --- | --- | --- | --- | --- |
| AC-001 | SC-001 | Playing one Guard card grants shield | tests/AcceptanceTests/Features/GuardCard.feature | Generated |
| AC-002 | SC-002 | Playing two Guard cards stacks shield | tests/AcceptanceTests/Features/GuardCard.feature | Generated |

## Non-BDD Criteria

| Criteria ID | Recommended Test Type | Reason |
| --- | --- | --- |
| AC-003 | Clarification before test design | End-of-turn shield rule is ambiguous |
| AC-004 | Manual / Smoke Test | Animation visibility belongs to Presentation validation |

## Gaps

| Criteria ID | Gap | Required Action |
| --- | --- | --- |
| AC-003 | Shield expiration behavior is undefined | Clarify rule before test design |
