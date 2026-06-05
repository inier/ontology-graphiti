---
description: "Export cost data as CSV or JSON for finance, dashboards, or RFP responses."
---

# /speckit.cost.export

Dump ledger or aggregate data to a file your finance team, BI tool, or procurement spreadsheet can ingest.

## User Input

$ARGUMENTS

Argument format:

```
format=<csv|json>                # required
source=<ledger|summary>          # default: ledger
out=<path>                       # default: ./cost-export.<format>
since=<ISO date>                 # optional, ledger source only
until=<ISO date>                 # optional, ledger source only
feature=<feature>                # optional, ledger source only
```

## Steps

### 1. Validate

- `format` must be `csv` or `json`. Reject anything else.
- `source` must be `ledger` or `summary`.
- If `out` exists, ask the user to confirm overwrite (or fail with a clear message in non-interactive mode and require an explicit different path).

### 2. Load source

- `ledger` → read `storage.ledger_path` and apply `since` / `until` / `feature` filters as in `/speckit.cost.report`.
- `summary` → read `storage.aggregate_path` and emit one row per `(feature, phase, integration, model)` group. The summary file is much smaller than the ledger and is what most dashboards want.

### 3. Render

#### CSV

Header row, then one record per row. Use `csv.writer` semantics — quote fields containing commas, escape embedded quotes by doubling them. Use `\n` line endings, UTF-8, no BOM.

Ledger header:
```
timestamp,feature,phase,integration,model,input_tokens,output_tokens,input_cost,output_cost,total_cost,currency,notes
```

Summary header:
```
feature,phase,integration,model,runs,input_tokens,output_tokens,total_cost,currency,first_recorded,last_recorded
```

#### JSON

For ledger: emit a JSON array of the filtered records (the same shape the ledger uses, just wrapped in `[...]`).

For summary: emit the aggregate object as-is.

Both formats: pretty-print with 2-space indent so diffs in version control are reviewable.

### 4. Print confirmation

```
Exported <N> records to <path> (<bytes> bytes).
```

If the export is empty (no records matched filters), exit cleanly with `No records matched — nothing exported.`

## Privacy notes

The ledger contains:

- `feature` (your branch / feature name)
- `model` and `integration` identifiers
- Token counts and costs
- Optional `notes` (free text — never auto-populated, only what the user passed to `/speckit.cost.track`)

It does **not** contain prompts, responses, file contents, or any user code. Still, treat the export as you would any internal financial data — don't paste the CSV into a public chat and don't commit it under `.specify/cost/exports/` if your repo is open source.

## Notes

- For continuous export to a BI tool, consider scheduling `/speckit.cost.export source=summary format=json` after each merge and committing the output to a private metrics repo.
