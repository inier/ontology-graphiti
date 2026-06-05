# ODAP Architecture Constitution

> Source of truth for architecture enforcement by `architecture-guard` extension.
> Project-level governance rules are in `.specify/memory/constitution.md`.
> If a section does not apply, mark "Not applicable" rather than deleting it.

## Architecture Style

- **Style**: Modular Monolith
- **Primary stack**: Python (FastAPI) backend + React 19 + TypeScript + Ant Design 6 frontend
- **Preset guidance**: None (custom Python/FastAPI preset pending)

## Layer Boundaries

| Layer | Owns | May Depend On | Must Not Depend On |
| --- | --- | --- | --- |
| **Entry** (`odap/web/`) | HTTP routes, WebSocket, middleware | Application, Contracts | Domain internals, Persistence drivers |
| **Application** (`odap/biz/*/application/`) | Use cases, orchestration, runtime engines | Domain contracts via `design.contract` | Entry, framework runtime directly |
| **Domain** (`odap/biz/*/design/`) | Business rules, policies, invariants, lifecycle | Domain types only | Entry, HTTP, database, framework runtime |
| **Infrastructure** (`odap/infra/`) | Persistence, query, security, LLM, OPA | Domain contracts, persistence drivers | Entry, application decisions |
| **External** (`odap/integrations/`) | Third-party integrations | Integration contracts | Domain internals |

### Ontology Subsystem Boundary (P0 — strictly enforced)

| Subsystem | Owns | Public Surface | Must Not |
| --- | --- | --- | --- |
| **Design** (`odap/biz/core/ontology/design/`) | Schema, version, model, ingestion | `design/contract/*` (read-only views) | Import anything from `application/` |
| **Application** (`odap/biz/core/ontology/application/`) | Runtime, OMS, harness, runtime APIs | All module APIs | Import from `design/` except via `design/contract` |

**Bridge**: All cross-boundary data flow goes through `odap.biz.core.ontology.design.contract.OntologyDesignContract`. The contract returns `@dataclass(frozen=True)` view objects only.

## Business Logic Placement

- Entry points MUST validate, map, and delegate only
- Business decisions live in application services, agents, or domain policies
- UI components MUST NOT own durable business rules
- **Ontology design** owns schema lifecycle; **Ontology application** owns schema usage
- Any code that mutates ontology state MUST go through the design service layer (not the contract)

## Contracts and Validation

- **Request contracts**: Pydantic v2 models in `*/api/schemas.py`
- **Response contracts**: Frozen dataclasses (`@dataclass(frozen=True)`) for design views; Pydantic models elsewhere
- **Event contracts**: Pydantic event models in `*/events.py`
- **Validation boundary**: External input is validated in route layer via Pydantic BEFORE service calls
- **Cross-module contracts**: Public contracts MUST be in `contract/` or `api/` subdirectories

## Data Access Rules

- Data access MUST go through `*/storage/` modules
- Business logic MUST NOT depend on SQLAlchemy/Neo4j/ORM models directly
- **Cross-module data access MUST use public contracts** — direct SQL JOINs across modules are forbidden
- The unified query service `odap.infra.query` is the canonical entry point for read queries
- **Ontology schema queries** MUST go through `design.contract` (not through `model.services.*` directly)

## Async and Integration Rules

- Background jobs MUST delegate business decisions to application/domain logic
- Events MUST use explicit contracts with stable payloads
- External service calls MUST be isolated behind gateways/clients (LLM, OPA, Neo4j, MinIO, etc.)
- WebSocket connections MUST go through a unified session/connection manager

## Module Boundaries

| Module | Owns | Public Contracts | Must Not |
| --- | --- | --- | --- |
| `odap.biz.core.ontology.design` | Schema, version, model, ingestion | `design/contract/` | Import from `application/` |
| `odap.biz.core.ontology.application` | Runtime, OMS, harness | Per-module APIs | Import from `design/` except via `contract` |
| `odap.biz.core.agent` | Intent routing, decision chain, OODA | `agent/api/*` | Direct Neo4j/SQL access |
| `odap.biz.platform.workspace` | Workspace lifecycle, isolation | `workspace/api/*` | Direct cross-module data access |
| `odap.biz.decision.*` | Decision pipelines, action services | `decision/api/*` | Skip workspace isolation |
| `odap.infra.query` | Unified semantic query | `infra/query/__init__.py` | Mutate data |
| `odap.infra.opa` | Policy management | `infra/opa/markdown_routes.py` | Skip fail-close in production |
| `odap.infra.graph` | Graph database access | `infra/graph/graph_service.py` | NetworkX fallback in production |

## Framework-Specific Architecture Rules

- **FastAPI**: Routes MUST be in domain modules (`*/api/routes.py`); `odap/web/app.py` ONLY wires routers
- **React 19 + TS**: API calls MUST go through `apiClient`; raw `fetch()` is FORBIDDEN
- **Ant Design 6**: Components MUST NOT own business logic; pure presentational
- **Pydantic v2**: Container fields MUST use `Field(default_factory=...)`; `= []` and `= {}` are FORBIDDEN
- **SQLAlchemy 2.0**: Migrations MUST be reversible; schema changes require a Pydantic schema update

## Blocking Architecture Violations (P0)

> These violations MUST stop release.

- **P0-1**: NO public endpoint may process unvalidated external input
- **P0-2**: NO module may directly access another module's private database tables
- **P0-3**: **Ontology application code MUST NOT import from `design/` except via `design/contract`**
- **P0-4**: **Ontology design code MUST NOT import from `application/`**
- **P0-5**: NO raw `fetch()` in frontend — must use `apiClient`
- **P0-6**: Neo4j down → MUST return error; NetworkX fallback is FORBIDDEN in production
- **P0-7**: OPA unavailable in production → MUST default to DENY (fail-close)
- **P0-8**: NO hardcoded default secrets (JWT, hook signing, MinIO credentials)
- **P0-9**: Route handlers MUST have proper error handling with `except HTTPException: raise`
- **P0-10**: New ontology modules MUST have corresponding test files in `tests/unit/`

## Accepted Architecture Deviations

- `odap.biz.integration.frontend_compat` is a thin compatibility shim for legacy frontend code; it is allowed to be slightly larger than other route files
- `frontend/src/modules/qa/hooks/useQAI.ts` is allowed to be larger for streaming; refactor tracked as P2

## Architecture Evolution Policy

- Repeated drift should produce a Constitution Update Proposal
- Accepted new patterns require explicit approval before becoming standards
- Migration plans should be incremental and module-scoped
- New boundary violations MUST generate a P1 refactor task in the spec's `tasks.md`

## Refactor and Drift Handling

- **P1 drift** (boundary violations, security) → near-term refactor tasks
- **P2 drift** (style, structure) → scheduled technical debt
- **P3 cleanup** (naming, comments) → opportunistic, must not block feature delivery

## Auto-Enforcement

- `tests/unit/test_architecture_boundary.py` — enforces P0-3 and P0-4 (Design/Application boundary)
- `tests/unit/test_design_contract_integration.py` — verifies contract layer correctness
- Run all tests: `pytest tests/unit/`
- Architecture review: `/speckit.architecture-guard.architecture-review`
- Pre-merge verification: `/speckit.architecture-guard.architecture-verify`
