# Changelog

## [1.1.0] - 2026-05-29

### Added

- `@infrastructure` tag convention: placed on the line immediately before `Feature:` in all generated `.feature` files so CI/CD pipelines can identify tests requiring test infrastructure.
- Skeleton → implementation transition guide: Given/When/Then patterns showing how to replace `PendingStepException()` with Application-layer calls via test data builders, service facades, and scenario context assertions.
- Expected test state transition table (`skipped` → `passed`) in implementation handoff and verification templates.
- Concrete BDD-004 implementation guidance: explicit replacement patterns for Given (builder + context), When (facade call), Then (context assertion) steps.
- Verification now distinguishes yellow/inconclusive (`PendingStepException`, pending implementation) from red/failures (assertion errors).

### Changed

- Generalized all Godot-specific terminology to domain-neutral "Presentation layer" language across all commands, templates, docs, and README.
- Replaced gaming-themed Gherkin and C# examples with generic business domain examples (Account Balance / Deposit).
- `GameScenarioContext` → `ScenarioContext` in all skeleton and implementation pattern templates.
- `business/game rule` → `business rule`, `user/player` → `user` throughout.
- Architecture Boundary rules now reference "Presentation-layer components (e.g., UI controls, pages, views)" instead of framework-specific terms.

### Fixed

- `@infrastructure` tag now correctly placed on its own line before `Feature:`, not inline on the Feature line.
- Step definitions skeleton template no longer leaves implementers without a clear path from placeholder to working tests.

## [1.0.0] - 2026-05-13

### Added

- Community-ready documentation for installation, workflow, configuration, troubleshooting, and release usage.
- Dogfood evidence for the full BDD workflow.
- Catalog submission metadata for the Spec Kit community extension process.

### Stable

- Stabilized `/speckit.reqnroll-bdd.plan`.
- Stabilized `/speckit.reqnroll-bdd.generate`.
- Stabilized `/speckit.reqnroll-bdd.inject-tasks`.
- Stabilized `/speckit.reqnroll-bdd.verify`.
- Stabilized optional `before_implement` task injection hook.

### Safety

- Task injection remains optional and idempotent.
- Task injection skips safely when generated BDD artifacts are missing.
- Step definition skeleton guidance remains incomplete by design and does not generate full business logic.

## [0.2.1] - 2026-05-13

### Added

- Added Step Definition Skeleton Guidance to the generated BDD implementation handoff.
- Added skeleton-only guidance for Reqnroll `[Binding]` classes, constructor dependencies, Given/When/Then method signatures, and `PendingStepException`.

### Changed

- Split injected step definition tasks into skeleton creation and Application-boundary completion.
- Updated task block guidance to avoid full business logic during skeleton creation.

### Safety

- Skeleton guidance must not include completed assertions, domain calculations, production method calls, repository implementation, or Godot Presentation binding.

## [0.2.0] - 2026-05-13

### Added

- Added `/speckit.reqnroll-bdd.inject-tasks`.
- Added optional `before_implement` hook for BDD task injection.
- Added `artifact-templates/bdd-task-block-template.md`.
- Added `docs/task-injection-rules.md`.
- Added task injection configuration defaults to `config-template.yml`.

### Changed

- Extended the recommended workflow so BDD tasks can be injected before `/speckit.implement`.

### Safety

- Task injection skips without changing files when BDD generate artifacts are missing.
- Task injection uses bounded marker comments for idempotent updates.

## [0.1.0] - 2026-05-13

### Added

- Added optional `config-template.yml` and manifest `provides.config` entry following the official extension template.
- Initial Reqnroll BDD extension manifest.
- Added `/speckit.reqnroll-bdd.plan`.
- Added `/speckit.reqnroll-bdd.generate`.
- Added `/speckit.reqnroll-bdd.verify`.
- Added artifact templates for BDD planning, traceability, handoff, and verification.
- Added architecture, Gherkin, implementation handoff, and Reqnroll project guidance docs.
- Added Guard Card example artifacts.
