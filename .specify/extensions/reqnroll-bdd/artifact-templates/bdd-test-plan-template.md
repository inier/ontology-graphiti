# BDD Test Plan

## Feature

{feature_name}

## Summary

{summary}

## Acceptance Criteria Classification

| Criteria ID | Source | Classification | Reason | BDD Candidate |
| --- | --- | --- | --- | --- |

## BDD Scenario Candidates

### SC-001: {scenario_title}

- Source criteria: AC-001
- Test boundary: Application
- Reason: {reason}

Draft:

```gherkin
Scenario: {scenario_title}
  Given ...
  When ...
  Then ...
```

## Non-BDD Test Recommendations

| Criteria ID | Recommended Test Type | Reason |
| ----------- | --------------------- | ------ |

## Ambiguities and Missing Details

| Item | Problem | Suggested Clarification |
| ---- | ------- | ----------------------- |

## Architecture Notes

Step definitions should bind to Application-layer use cases.

Feature files must not expose Domain internals, Infrastructure details, or Presentation-layer components.
