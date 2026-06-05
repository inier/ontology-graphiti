# ODAP Governance Constitution

> High-level engineering governance rules enforced by `architecture-guard`.
> Project principles are in `.specify/memory/constitution.md`.
> Architecture rules are in `.specify/memory/architecture_constitution.md`.

## Code Quality Standards

- **Functions over 40 lines**: MUST be split into smaller functions
- **Modules over 500 lines**: SHOULD be split by concern
- **Naming**: MUST be semantic; no cryptic abbreviations
- **Magic numbers**: MUST be named constants
- **Code duplication**: 3+ repetitions → MUST extract a shared function

## Testing Policy

- **New modules**: MUST have a corresponding test file before merge
- **Bug fixes**: MUST write a regression test that fails first
- **API endpoints**: MUST have integration tests covering happy path + error cases
- **Critical paths**: MUST have unit tests (state transitions, permission checks, etc.)
- **Coverage target**: 80% for `odap/biz/` modules

## Documentation Requirements

- **Public APIs**: MUST have docstrings with type hints
- **Cross-module contracts**: MUST have a README in the contract directory
- **Architectural decisions**: MUST be recorded in `docs/architecture/`
- **Breaking changes**: MUST be documented in the spec's `CHANGELOG.md`

## Security Standards

- **No hardcoded secrets**: All credentials MUST come from environment variables
- **No default credentials**: Production MUST fail fast on missing env vars
- **Input validation**: All external input MUST be validated at the route boundary
- **Auth enforcement**: All routes MUST require authentication except explicit public endpoints
- **SQL injection**: All table/column names MUST be whitelisted; no f-string interpolation

## Performance Standards

- **Database queries**: MUST use indexes; queries without index MUST be flagged
- **Batch operations**: MUST process in chunks (not all at once) for large datasets
- **Caching**: Long-running queries MUST be cached with explicit TTL
- **WebSocket**: MUST implement heartbeat/ping to detect dead connections

## Development Workflow

- **Pull requests**: MUST pass architecture boundary tests
- **Pre-merge**: MUST run `/speckit.architecture-guard.architecture-verify`
- **Pre-release**: MUST pass all 4 architecture boundary tests
- **Constitution changes**: MUST go through a Constitution Update Proposal (CUP)

## Communication

- **Spec compliance**: Every task MUST trace back to a spec requirement
- **Test traceability**: Every test MUST reference a User Story or Edge Case
- **Architecture decisions**: MUST be recorded as ADRs in `docs/architecture/`
- **Refactor tasks**: MUST include confidence score, file:line evidence, and fix

## Enforcement

These rules are enforced by:
- `pytest tests/unit/` — Unit tests including boundary tests
- `/speckit.architecture-guard.architecture-review` — Architecture review
- `/speckit.architecture-guard.architecture-verify` — Pre-merge gate
- `/speckit.architecture-guard.violation-detection` — Plan-time drift detection
- `/speckit.architecture-guard.refactor-generator` — Convert violations to tasks

## Severity Levels

- **P0** (block release): Security, data integrity, contract violations
- **P1** (block merge): Boundary violations, missing tests, error handling
- **P2** (block next sprint): Style, naming, comments
- **P3** (opportunistic): Minor improvements
