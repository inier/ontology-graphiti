# Reqnroll Project Guidance

## Recommended test location

```text
tests/{Project}.AcceptanceTests/
  Features/
  Steps/
  TestSupport/
```

## Recommended boundary

```text
Steps call Application Services or test-facing Application facades.
Application calls Domain.
Presentation is not involved.
```

## Recommended test support

- Scenario context
- Test data builders
- In-memory repositories
- domain object mothers
- fake event dispatcher if needed

## Suggested package direction

The implementation command may choose the exact Reqnroll test framework package set based on the target project, but the acceptance test project should be isolated from Presentation-layer runtime dependencies unless the feature explicitly requires a smoke or integration boundary.
