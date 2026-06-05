# Changelog

All notable changes to `spec-kit-cost` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-05-03

### Added

- `/speckit.cost.track` — append a token-and-cost record for the most recent SDD phase to `.specify/cost/ledger.jsonl` and update the rolled-up summary file.
- `/speckit.cost.report` — human-readable cost breakdown for the current feature or whole project, grouped by phase / integration / model / feature.
- `/speckit.cost.budget` — set, view, reset, and toggle warn-vs-block behavior on per-feature and per-phase caps.
- `/speckit.cost.compare` — re-price the same workload across every model in the pricing table, so you can estimate savings from switching integrations.
- `/speckit.cost.export` — emit ledger or summary as CSV / JSON for finance dashboards and RFP responses.
- Bundled pricing table covering Claude (Sonnet 4.6, Opus 4.7, Haiku 4.5), GPT-4o, and Gemini 2.5 Pro at May 2026 list rates. Edit `cost-config.yml` to override with your negotiated rates.
- Append-only JSONL ledger format — trivially diff-able and recoverable from a partial last line.
