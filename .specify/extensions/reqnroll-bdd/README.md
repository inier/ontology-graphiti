# Spec Kit Reqnroll BDD Extension

A Spec Kit extension for turning acceptance criteria into Reqnroll-oriented BDD plans, Gherkin feature files, traceability reports, safe task injections, implementation handoffs, and verification reports.

It does **not** replace `/speckit.implement`.  
Instead, it prepares BDD artifacts and implementation guidance so the native Spec Kit workflow can build the test project, step definitions, and production code.

## Overview

`reqnroll-bdd` helps Spec Kit projects introduce Reqnroll BDD acceptance testing without leaking implementation details into `.feature` files.

It focuses on:

- classifying acceptance criteria
- generating Reqnroll-compatible Gherkin
- mapping criteria to scenarios
- preparing implementation handoffs
- injecting BDD implementation tasks before `/speckit.implement`
- verifying BDD coverage, traceability, quality, architecture boundaries, and optional test execution

## Features

- BDD test planning from Spec Kit feature artifacts
- Reqnroll-compatible `.feature` generation
- AC-to-scenario traceability
- Implementation handoff for `/speckit.implement`
- Optional `before_implement` hook for task injection
- Step definition skeleton guidance without full implementation
- Architecture boundary checks
- Optional `dotnet test` verification

## Installation

### From GitHub Release

```bash
specify extension add reqnroll-bdd --from https://github.com/LoogacyStudio/spec-kit-reqnroll-bdd/archive/refs/tags/v1.0.0.zip
```

### Local Development

From a Spec Kit project:

```bash
specify extension add --dev /path/to/spec-kit-reqnroll-bdd
```

Reload your coding agent if the commands do not appear immediately.

## Quick Start

Run the normal Spec Kit flow first:

```text
/speckit.specify
/speckit.plan
/speckit.tasks
```

Then run the Reqnroll BDD flow:

```text
/speckit.reqnroll-bdd.plan
/speckit.reqnroll-bdd.generate
/speckit.implement
/speckit.reqnroll-bdd.verify
```

Before `/speckit.implement` runs, the extension may trigger task injection through the optional `before_implement` hook.

## Workflow

```text
/speckit.specify
  ↓
/speckit.plan
  ↓
/speckit.tasks
  ↓
/speckit.reqnroll-bdd.plan
  ↓
/speckit.reqnroll-bdd.generate
  ↓
/speckit.implement
  ↳ before_implement hook: /speckit.reqnroll-bdd.inject-tasks
  ↓
/speckit.reqnroll-bdd.verify
```

The practical BDD loop is:

```text
plan → generate → implement → verify
```

## Commands

| Command | Purpose | Main Output |
| --- | --- | --- |
| `/speckit.reqnroll-bdd.plan` | Classify acceptance criteria and propose BDD scenario candidates | `specs/{feature}/bdd-test-plan.md` |
| `/speckit.reqnroll-bdd.generate` | Generate `.feature` files, traceability, and implementation handoff | `.feature`, `bdd-traceability.md`, `bdd-implementation-handoff.md` |
| `/speckit.reqnroll-bdd.inject-tasks` | Inject BDD implementation tasks into `tasks.md` | bounded task block in `tasks.md` |
| `/speckit.reqnroll-bdd.verify` | Verify coverage, traceability, Gherkin quality, architecture boundaries, and optional tests | `bdd-verification.md` |

## Hook

| Event | Command | Optional | Description |
| --- | --- | ---: | --- |
| `before_implement` | `speckit.reqnroll-bdd.inject-tasks` | Yes | Inject BDD acceptance test tasks before `/speckit.implement` |

Task injection is safe by design:

- it is optional
- it is idempotent
- it preserves existing non-generated tasks
- it uses bounded marker comments
- it skips safely when BDD generate artifacts are missing

## Generated Artifacts

The extension may generate or update:

```text
specs/{feature}/bdd-test-plan.md
specs/{feature}/bdd-traceability.md
specs/{feature}/bdd-implementation-handoff.md
specs/{feature}/bdd-verification.md
tests/{Project}.AcceptanceTests/Features/*.feature
```

If the target acceptance test project cannot be inferred, generated `.feature` files use:

```text
tests/AcceptanceTests/Features/
```

## Configuration

The extension ships with an optional configuration template:

```text
config-template.yml
```

When installed, configuration may be available at:

```text
.specify/extensions/reqnroll-bdd/reqnroll-bdd-config.yml
```

Key options:

| Option | Purpose |
| --- | --- |
| `target_test_project` | Preferred acceptance test project |
| `default_feature_output_path` | Fallback `.feature` output path |
| `test_boundary` | Recommended binding boundary, default `Application` |
| `dotnet_test_execution` | `auto` or `skip` |
| `allow_rule_keyword` | Allow Gherkin `Rule:` usage |
| `require_ac_tags` | Require scenario AC tags |
| `task_injection.enabled` | Enable task injection behavior |
| `task_injection.fallback_to_handoff` | Write proposed task block to handoff when `tasks.md` is missing |
| `task_injection.replace_existing_block` | Replace existing generated block instead of duplicating |

Example:

```yaml
reqnroll_bdd:
  target_test_project: ""
  default_feature_output_path: "tests/AcceptanceTests/Features"
  test_boundary: "Application"
  dotnet_test_execution: "auto"
  allow_rule_keyword: true
  require_ac_tags: true

  task_injection:
    enabled: true
    mode: "update_tasks"
    hook_event: "before_implement"
    fallback_to_handoff: true
    marker_start: "<!-- reqnroll-bdd:tasks:start -->"
    marker_end: "<!-- reqnroll-bdd:tasks:end -->"
    insertion_strategy: "append"
    replace_existing_block: true
    fail_on_malformed_marker: true
```

## Usage Example

Given acceptance criteria such as:

```text
AC-001: When the player moves into an empty tile, the player position changes.
AC-002: When the player enters an encounter tile, an encounter starts.
```

`/speckit.reqnroll-bdd.plan` classifies the criteria and proposes BDD scenarios.

`/speckit.reqnroll-bdd.generate` may produce:

```gherkin
@AC-001
Scenario: Moving into an empty tile changes the player position
  Given the player is at the starting position
  When the player moves into an empty tile
  Then the player position should change
```

`/speckit.reqnroll-bdd.inject-tasks` may inject:

```markdown
<!-- reqnroll-bdd:tasks:start -->

## BDD Acceptance Test Tasks

- [ ] BDD-003 Create step definition skeletons
  - Boundary: Application
  - Skeleton only: `[Binding]`, constructor dependencies, Given/When/Then method signatures, and `PendingStepException`.

- [ ] BDD-004 Complete step definitions through the Application boundary

<!-- reqnroll-bdd:tasks:end -->
```

## Architecture Boundary

Recommended binding path:

```text
.feature
  ↓
Step Definitions
  ↓
Application Service / Use Case Facade
  ↓
Domain
```

Forbidden binding path:

```text
.feature
  ↓
Step Definitions
  ↓
Presentation Layer (UI controls / pages / views)
```

BDD scenarios should describe observable behavior, not implementation structure.

## Step Definition Skeleton Guidance

The generated implementation handoff may include Reqnroll step definition skeleton guidance.

Skeletons may include:

- `using Reqnroll;`
- `[Binding]`
- class declaration
- constructor injection
- scenario context or Application-layer test facade dependency
- Given / When / Then method signatures
- `throw new PendingStepException();`

Skeletons must not include:

- completed assertions
- domain calculations
- production method internals
- repository implementation
- Presentation-layer access (e.g., UI controls, pages, views)

Example skeleton:

```csharp
using Reqnroll;

namespace AcceptanceTests.Steps;

[Binding]
public sealed class MovementStepDefinitions
{
    private readonly ScenarioContext _context;

    public MovementStepDefinitions(ScenarioContext context)
    {
        _context = context;
    }

    [Given("the user is at the starting position")]
    public void GivenTheUserIsAtTheStartingPosition()
    {
        throw new PendingStepException();
    }
}
```

## Safety and Non-goals

This extension does not:

- replace `/speckit.implement`
- provide `/speckit.reqnroll-bdd.implement`
- automatically install NuGet packages
- generate complete C# step definitions
- modify production code directly
- automate Presentation-layer tests
- bind BDD steps to Presentation-layer components

Task injection is opportunistic. It only modifies `tasks.md` when these files exist:

```text
specs/{feature}/bdd-implementation-handoff.md
specs/{feature}/bdd-traceability.md
specs/{feature}/tasks.md
```

If BDD generate artifacts are missing, task injection skips without changing files.

## Troubleshooting

### The hook runs but no tasks are injected

Run:

```text
/speckit.reqnroll-bdd.generate
```

Task injection only modifies `tasks.md` when these files exist:

```text
bdd-implementation-handoff.md
bdd-traceability.md
tasks.md
```

### Tests are skipped in verify

`/speckit.reqnroll-bdd.verify` only runs `dotnet test` when a .NET test project appears configured.

If no Reqnroll test project exists, test execution is reported as skipped, not failed.

### Feature files mention implementation details

Run:

```text
/speckit.reqnroll-bdd.verify
```

Then remove architecture leakage such as:

```text
Aggregate
Repository
DTO
Handler
Controller
ViewModel
Presenter
UI widget names
page names
view names
method
class
service method
database table
```

### Step definitions are binding to UI

Move the binding target to an Application Service or test-facing Application facade.

Do not bind Reqnroll steps directly to Presentation-layer components (e.g., UI controls, pages, views).

## Documentation

Additional docs:

```text
docs/architecture-boundaries.md
docs/gherkin-authoring-rules.md
docs/implementation-handoff-rules.md
docs/reqnroll-project-guidance.md
docs/task-injection-rules.md
docs/step-definitions-skeleton-rules.md
docs/community-submission.md
docs/dogfood/
```

## Compatibility

Target Spec Kit version:

```text
>=0.8.0
```

Optional tool:

```text
dotnet
```

`dotnet` is only required when you want verification to run .NET tests.

## Contributing

Contributions should preserve the extension scope:

- keep `/speckit.implement` as the implementation executor
- keep `.feature` files implementation-agnostic
- keep task injection idempotent and safe
- keep step definition skeletons incomplete by design
- update README and CHANGELOG for workflow changes

## License

MIT
