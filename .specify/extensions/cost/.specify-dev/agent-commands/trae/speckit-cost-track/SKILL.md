---
name: speckit-cost-track
description: Record token usage and dollar cost for the current SDD phase.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: cost:commands/track.md
---

# /speckit.cost.track

Record an entry in the cost ledger for the most recent SDD phase you ran. Use this immediately after `/speckit.specify`, `/speckit.plan`, `/speckit.tasks`, or `/speckit.implement` so the ledger stays accurate.

## User Input

$ARGUMENTS

Argument format (all key=value, space-separated; `phase` is required):

```
phase=<specify|plan|tasks|implement> \
  feature=<branch-or-feature-id> \
  integration=<claude|copilot|gemini|opencode> \
  model=<model-id-from-pricing-table> \
  input_tokens=<int> \
  output_tokens=<int> \
  notes="<optional free text>"
```

If `feature` is omitted, the current git branch name is used. If `integration` is omitted, the value recorded in `.specify/integration.json` is used. If `model` is omitted, the integration's default model from the pricing table is used.

## Steps

### 1. Load configuration

Read `.specify/extensions/cost/cost-config.yml`. If it doesn't exist, fall back to the extension defaults bundled in `extension.yml`.

Cache the resolved pricing table, budget caps, and storage paths.

### 2. Resolve missing arguments

- If `feature` is missing, run `git rev-parse --abbrev-ref HEAD` and use the branch name.
- If `integration` is missing, read `.specify/integration.json` and use `integration.integration`.
- If `model` is missing, look up the integration's default in the pricing table.

### 3. Validate inputs

- `phase` must be one of `specify | plan | tasks | implement`. Reject anything else.
- `input_tokens` and `output_tokens` must be non-negative integers.
- `model` must exist in `pricing.rates`. If unknown, print the known model IDs and ask the user to either pick one or add the missing rate to `cost-config.yml` before retrying.

### 4. Compute cost

```
input_cost  = input_tokens  / 1_000_000 * rates[model].input_per_mtok
output_cost = output_tokens / 1_000_000 * rates[model].output_per_mtok
total_cost  = input_cost + output_cost
```

Round each component to 4 decimal places when displayed; store the unrounded value in the ledger.

### 5. Append to ledger

Append one JSON object per line to `storage.ledger_path` (default `.specify/cost/ledger.jsonl`):

```json
{
  "timestamp": "<ISO 8601 UTC>",
  "feature": "<feature>",
  "phase": "<phase>",
  "integration": "<integration>",
  "model": "<model>",
  "input_tokens": <int>,
  "output_tokens": <int>,
  "input_cost": <float>,
  "output_cost": <float>,
  "total_cost": <float>,
  "currency": "<currency>",
  "notes": "<notes or empty string>"
}
```

Create the parent directory if it doesn't exist. Never overwrite existing lines — the ledger is append-only.

### 6. Update aggregate summary

Read `storage.aggregate_path` (or start fresh) and increment totals for the matching `(feature, phase, integration)` triple. Persist atomically (write to a temp file, then `os.replace`).

### 7. Check budgets

Look up the relevant cap in `budgets`:
- `per_phase[<phase>]` for the phase total across this feature.
- `per_feature` for the lifetime feature total.

If the new cumulative total exceeds a cap:
- `on_exceed: warn` → print a yellow warning with the cap, current spend, and overage. Continue.
- `on_exceed: block` → print a red error and exit non-zero. The ledger entry has already been appended; the user can lower the cap or run `/speckit.cost.budget reset` to clear it.

### 8. Print confirmation

```
Recorded: feature=<feature> phase=<phase> integration=<integration> model=<model>
  tokens: <input>+<output> = <total>
  cost:   $<input_cost> + $<output_cost> = $<total_cost>
  feature total: $<feature_total>   phase total: $<phase_total>
```

If a budget warning fired, append it on the next line.

## Notes

- Most agent CLIs surface `input_tokens` and `output_tokens` in their final report; copy them from there. A future revision will accept a transcript file path and parse counts automatically.
- Cached/prompt-cache reads count as input tokens for cost purposes here; if your provider bills cache reads at a discount, add `cache_input_per_mtok` to the pricing entry and split the input count manually for now.