---
name: speckit-cost-report
description: Show a cost breakdown for the current feature or the whole project.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: github-spec-kit
  source: cost:commands/report.md
---

# /speckit.cost.report

Print an aggregated cost report from the ledger. Useful before merging a feature, during sprint reviews, or whenever someone in finance asks "what did this cost?"

## User Input

$ARGUMENTS

Argument format (all optional):

```
scope=<feature|project>          # default: feature (current branch)
feature=<feature-id>             # override the inferred feature
group_by=<phase|integration|model|feature>   # default: phase
since=<ISO date>                 # filter ledger entries on or after this date
until=<ISO date>                 # filter ledger entries on or before this date
```

## Steps

### 1. Load ledger

Read `storage.ledger_path`. If it doesn't exist, print "No cost data recorded yet — run `/speckit.cost.track` after each phase to populate the ledger." and exit cleanly.

Stream-parse line by line. Skip blank lines and lines that fail JSON decode (warn, but don't abort — append-only ledgers are robust to a partial last line).

### 2. Filter

- If `scope=feature` (default), keep entries where `feature` equals the resolved feature (current git branch unless overridden).
- If `scope=project`, keep all entries.
- Apply `since` / `until` filters against `timestamp` if provided.

### 3. Aggregate by group

Sum `input_tokens`, `output_tokens`, `total_cost` per group key. Also count the number of phases recorded per group and track first/last timestamp.

### 4. Render

Print a header showing the scope and any filters in effect, then a table with these columns:

```
GROUP                        RUNS    INPUT TOK    OUTPUT TOK    COST (<currency>)
-----------------------------------------------------------------------------
specify                      1       12,345       3,210         $0.0858
plan                         1       28,400       9,150         $1.2375
tasks                        1       15,000       4,800         $0.4350
implement                    4       180,000      52,000        $11.6400
-----------------------------------------------------------------------------
TOTAL                        7       235,745      69,160        $13.3983
```

Use right-aligned numeric columns, comma-separate token counts, and round costs to 4 decimal places.

If a budget cap is set for the active scope, append a "Budget" line:

```
Budget:    $20.00 cap   $13.3983 spent   $6.6017 remaining (67% used)
```

Color the percentage red if ≥ 100%, yellow if ≥ 80%, otherwise green.

### 5. Suggest next actions

If cost is heavily skewed (one group > 70% of total), append a one-line suggestion. Examples:

- "implement is 87% of total — consider running `/speckit.cost.compare` to see if a cheaper integration would save spend on that phase."
- "Most spend is on `claude-opus-4-7` — `/speckit.cost.compare integration=claude-haiku-4-5` to estimate switching."

Keep this advisory; don't be pushy.

## Notes

- The report is read-only. It never modifies the ledger or summary file.
- For machine consumption, use `/speckit.cost.export` instead — this command is meant to be skimmed by humans.