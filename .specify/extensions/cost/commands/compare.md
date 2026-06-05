---
description: "Compare cost-per-feature across integrations (claude, copilot, gemini, opencode)."
---

# /speckit.cost.compare

Estimate what each integration would have cost for the same workload, using the recorded token counts as a baseline. Useful when deciding whether to switch integrations for the next feature, or when justifying a switch in a tech-review.

## User Input

$ARGUMENTS

Argument format (all optional):

```
feature=<feature-id>             # default: current branch
phase=<phase>                    # restrict to one phase; default: all phases
models=<comma-separated-list>    # override which models to compare
```

If `models` is omitted, compare every model present in `pricing.rates`.

## Steps

### 1. Load ledger and pricing

Read the ledger and filter to the requested feature/phase. Read pricing rates from `cost-config.yml`.

If the filtered ledger is empty, print "No data to compare for <feature>[/<phase>]." and exit cleanly.

### 2. Sum baseline tokens

Sum `input_tokens` and `output_tokens` across the filtered entries. These are the tokens that *actually* moved through the system; the comparison is purely a re-pricing exercise.

### 3. Re-price under each model

For each model in `pricing.rates` (or the `models=` override):

```
projected_cost = input_tokens  / 1_000_000 * rates[model].input_per_mtok
              + output_tokens / 1_000_000 * rates[model].output_per_mtok
```

Also compute the delta against the current actual cost:

```
delta = projected_cost - actual_cost
delta_pct = delta / actual_cost * 100   # if actual_cost > 0
```

### 4. Render

Print a table sorted by `projected_cost` ascending, with the actual entry highlighted:

```
Feature: <feature>   Phase: <phase or 'all'>
Tokens:  input=<input>  output=<output>

MODEL                   PROJECTED COST    Δ vs ACTUAL    NOTE
---------------------------------------------------------------------
gemini-2-5-pro          $4.12             -$9.28 (-69%)
claude-haiku-4-5        $5.30             -$8.10 (-60%)
gpt-4o                  $7.04             -$6.36 (-47%)
claude-sonnet-4-6       $13.40            $0.00 (0%)     ← actual
claude-opus-4-7         $67.00            +$53.60 (+400%)
```

### 5. Caveats

After the table, print a short "Caveats" block — re-pricing is only an upper-bound estimate because:

- Different models produce different token counts for the same task; a cheaper model is not automatically a cheaper run end-to-end if it forces more retries or longer outputs.
- Cache discounts, batch-API discounts, and prompt-cache hits are not modeled here. Add `cache_input_per_mtok` to a model entry and the next revision will factor it in.
- This compares *price*, not *quality*. Use `/speckit.cost.compare` together with your own quality observations.

Keep the caveats short — three bullet points max.

## Notes

- This command is read-only. It never re-runs the workflow; it only re-prices the recorded tokens.
- For a true A/B, run the same spec on two integrations and compare actuals via `/speckit.cost.report group_by=integration`.
