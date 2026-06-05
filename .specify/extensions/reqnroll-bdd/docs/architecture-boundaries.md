# Architecture Boundaries

## Core Principle

Reqnroll BDD scenarios describe observable behavior, not implementation structure.

## Recommended Binding Path

```text
.feature
  ↓
Step Definitions
  ↓
Application Service / Use Case Facade
  ↓
Domain
```

## Forbidden Binding Path

```text
.feature
  ↓
Step Definitions
  ↓
Presentation Layer (UI controls / pages / views)
```

## Layer Rules

### Domain

Use unit tests for:

- Value Object invariants
- Aggregate invariants
- rule calculations
- pure domain behavior

### Application

Use Reqnroll BDD for:

- use cases
- user-visible behavior
- business rule examples
- accepted/rejected actions
- workflow-level state changes

### Presentation

Do not bind BDD directly to:

- UI controls (buttons, labels, text fields)
- pages or views
- animation or visual effects
- presentation framework signals or events

Use manual QA or smoke tests for UI and visual behavior.
