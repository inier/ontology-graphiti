# spec-kit-cost

Track real LLM **dollar cost** across [Spec Kit](https://github.com/github/spec-kit) SDD workflows — per-feature budgets, per-integration comparison, and finance-ready exports.

Token counters tell you how many tokens your spec/plan/tasks/implement runs consumed. They don't tell you what those runs *cost*. As organizations scale spec-driven development across teams, the question moves from "how many tokens?" to "how much did this feature cost to build, and which integration would have been cheaper?"

`spec-kit-cost` answers that question with a small, append-only ledger and five focused commands.

## What it does

| Command | Purpose |
|---|---|
| `/speckit.cost.track` | Record token usage and dollar cost for the most recent SDD phase. |
| `/speckit.cost.report` | Show a cost breakdown for the current feature or whole project. |
| `/speckit.cost.budget` | Set, view, and check per-phase or per-feature budget caps. |
| `/speckit.cost.compare` | Re-price the same workload across every supported model. |
| `/speckit.cost.export` | Export ledger or summary data as CSV / JSON. |

## Why this exists

- **Token-analyzer counts tokens.** This counts dollars.
- **Maintainers and enterprises need cost visibility** before spec-driven development can be adopted at scale.
- **Pricing changes monthly.** Storing rates in a config file (rather than hard-coding them) lets every team adjust to their negotiated contract or provider price drop.

## Install

```bash
specify extension install cost
```

Or pin to a specific release:

```bash
specify extension install cost --version 1.0.0
```

This drops a `cost-config.yml` into `.specify/extensions/cost/`. Edit the `pricing.rates` section to match your organization's negotiated rates if they differ from the public list price.

## Quick start

After running any SDD phase, record the cost:

```
/speckit.specify Add a logout button to the navbar
/speckit.cost.track phase=specify input_tokens=12345 output_tokens=3210

/speckit.plan
/speckit.cost.track phase=plan input_tokens=28400 output_tokens=9150

/speckit.tasks
/speckit.cost.track phase=tasks input_tokens=15000 output_tokens=4800

/speckit.implement
/speckit.cost.track phase=implement input_tokens=180000 output_tokens=52000
```

Then ask for a report:

```
/speckit.cost.report
```

```
Feature: feature/logout-button
Scope:   feature

GROUP        RUNS  INPUT TOK   OUTPUT TOK   COST (USD)
-------------------------------------------------------
specify      1     12,345      3,210        $0.0858
plan         1     28,400      9,150        $1.2375
tasks        1     15,000      4,800        $0.4350
implement    4     180,000     52,000       $11.6400
-------------------------------------------------------
TOTAL        7     235,745     69,160       $13.3983

Budget: $20.00 cap   $13.3983 spent   $6.6017 remaining (67% used)
```

## Setting budgets

```
/speckit.cost.budget set scope=feature amount=20
/speckit.cost.budget set scope=phase phase=implement amount=15
/speckit.cost.budget mode=warn      # or 'block' to fail track when over cap
/speckit.cost.budget show
```

Budgets live in `.specify/extensions/cost/cost-config.yml`, so they're versioned alongside code and reviewed in PRs.

## Comparing integrations

After a few features, run:

```
/speckit.cost.compare
```

```
Feature: feature/logout-button   Phase: all
Tokens:  input=235,745   output=69,160

MODEL                   PROJECTED COST    Δ vs ACTUAL    NOTE
---------------------------------------------------------------------
gemini-2-5-pro          $4.12             -$9.28 (-69%)
claude-haiku-4-5        $5.30             -$8.10 (-60%)
gpt-4o                  $7.04             -$6.36 (-47%)
claude-sonnet-4-6       $13.40            $0.00 (0%)     ← actual
claude-opus-4-7         $67.00            +$53.60 (+400%)
```

Caveats apply (token counts vary by model, cache discounts not modeled, etc.) — the command prints them at the bottom of every comparison.

## Exporting for finance

```
/speckit.cost.export format=csv source=summary out=./monthly-cost.csv
```

The summary export produces one row per `(feature, phase, integration, model)` group — small, readable, and ready to drop into a BI dashboard or RFP response.

## Where the data lives

```
.specify/
└── cost/
    ├── ledger.jsonl        # append-only, one record per /speckit.cost.track run
    └── summary.json        # rolled-up totals by feature/phase/integration
```

Both files are JSON — diff-friendly and trivially scriptable.

## What it does **not** do

- It does not capture prompts, responses, or file contents. The ledger only stores token counts, costs, and the metadata you pass to `track`.
- It does not auto-instrument your AI agent CLI. You pass the token counts in (or a future revision will parse them from a transcript file).
- It does not enforce budgets at the agent level. `block` mode prevents `track` from succeeding once a cap is breached, but the underlying agent run has already happened.

## Compatibility

- spec-kit `>= 0.8.0`
- Works with all integrations: Claude, Copilot, Gemini, OpenCode, and any future integration that records tokens.
- All commands are read/write to local files only — no network calls, no telemetry.

## License

MIT — see [LICENSE](LICENSE).
