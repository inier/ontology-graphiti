---
description: "Set, view, and check per-phase or per-feature budget caps."
---

# /speckit.cost.budget

Manage budget caps for the current project. Caps are stored in `cost-config.yml` so they're reviewed alongside other config in PRs.

## User Input

$ARGUMENTS

Subcommands:

```
/speckit.cost.budget show
/speckit.cost.budget set scope=<feature|phase> phase=<phase> amount=<currency-amount>
/speckit.cost.budget reset scope=<feature|phase> [phase=<phase>]
/speckit.cost.budget mode=<warn|block>
```

If `$ARGUMENTS` is empty, default to `show`.

## Steps

### 1. Load configuration

Read `.specify/extensions/cost/cost-config.yml`. If missing, copy it from the bundled template (`config-template.yml`) before editing.

### 2. Dispatch on subcommand

#### `show`

Print the current budgets and `on_exceed` mode in a small table:

```
Mode: warn

Scope         Phase       Cap          Spent (current feature)    Status
---------------------------------------------------------------------------
per_feature   —           $50.00       $13.40                     OK (27%)
per_phase     specify     —            $0.09                      no cap
per_phase     plan        $5.00        $1.24                      OK (25%)
per_phase     tasks       —            $0.43                      no cap
per_phase     implement   $30.00       $11.64                     OK (39%)
```

Pull "Spent" totals from the aggregate summary file for the current feature (current git branch).

#### `set`

Validate `amount` parses as a positive number; reject otherwise. Update the matching key in `cost-config.yml`:

- `scope=feature` → `budgets.per_feature = amount`
- `scope=phase phase=<phase>` → `budgets.per_phase.<phase> = amount`

Preserve unrelated keys, comments, and ordering as best as possible (use a YAML library that supports round-tripping; otherwise rewrite the file with stable ordering and re-emit comments from the bundled template).

Print a confirmation: `Set <scope>[/<phase>] cap to $<amount>.`

#### `reset`

Set the matching key back to `null`. Confirm with `Cleared <scope>[/<phase>] cap.`

#### `mode`

Update `budgets.on_exceed` to `warn` or `block`. Reject any other value.

### 3. Persist atomically

Write to a sibling temp file, then `os.replace` over the original. Never leave the config file truncated on a crash.

## Examples

```
/speckit.cost.budget set scope=feature amount=50
/speckit.cost.budget set scope=phase phase=implement amount=30
/speckit.cost.budget mode=block
/speckit.cost.budget show
/speckit.cost.budget reset scope=phase phase=implement
```

## Notes

- Budgets only fire when a record is appended via `/speckit.cost.track`. They are not enforced retroactively against the existing ledger.
- `block` mode is a soft guard — it prevents `/speckit.cost.track` from succeeding once the cap is breached, but it does not interrupt an already-running spec/plan/tasks/implement command. The budget is a contract with the developer, not a kill switch on the agent.
