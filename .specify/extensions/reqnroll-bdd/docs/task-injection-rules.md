# Task Injection Rules

## Purpose

Task injection bridges the gap between generated BDD artifacts and `/speckit.implement`.

The extension does not implement code. It injects clear implementation tasks into `tasks.md` so the native Spec Kit implementation workflow can execute them.

## Safety Rules

- Preserve all existing non-generated task content.
- Use bounded marker comments.
- Re-running injection must be idempotent.
- Do not create duplicate BDD task blocks.
- Do not reorder unrelated tasks.
- Do not silently overwrite malformed marker blocks.

## Marker Comments

```markdown
<!-- reqnroll-bdd:tasks:start -->
<!-- reqnroll-bdd:tasks:end -->
```

## Generated Task Requirements

Generated tasks must include:

- source handoff reference
- feature file references
- scenario IDs
- acceptance criteria IDs
- suggested step classes
- Application boundary reminder
- test support requirements
- verification command

## Forbidden Guidance

Injected tasks must not tell /speckit.implement to bind BDD steps directly to:

- UI controls (buttons, labels, text fields)
- pages or views
- presentation framework signals or events
- animation or visual effects

Use Application Services or test-facing Application facades instead.

## Fallback

If tasks.md cannot be safely updated, write the proposed task block to bdd-implementation-handoff.md under:

```markdown
## Proposed BDD Task Injection
```
