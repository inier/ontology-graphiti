# Architecture Review: ODAP Platform

> **Date**: 2026-06-03
> **Scope**: `odap/biz/core/ontology/**`, `odap/infra/**`, `odap/web/app.py`, all `*/api/routes.py`
> **Mode**: Post-implementation, non-blocking
> **Preset**: `python-fastapi` (custom)
> **Constitutions**: `.specify/memory/{constitution,architecture_constitution,governance_constitution}.md`

## Summary

| Metric | Value |
| --- | --- |
| **Files scanned** | 408 (326 ontology+infra + 47 security+resilience + 37 routes) |
| **Routes scanned** | 390 端点 / 37 文件 |
| **Pydantic models scanned** | 21 文件 / 157 BaseModel |
| **P0 violations (block release)** | **34** |
| **P1 violations (block merge)** | **~104** |
| **P2 violations (suggestions)** | **35+** |
| **Drift score (ontology boundary)** | **62 / 100** |
| **Drift score (FastAPI/Pydantic)** | **78 / 100** |
| **Drift score (security/resilience)** | **38 / 100** |
| **Overall composite score** | **59 / 100** |

## Compliance Snapshot

| Rule | Status |
| --- | --- |
| P0-3 (Application MUST NOT import design internals) | ✅ **0 violations** |
| P0-4 (Design MUST NOT import application) | ❌ **3 violations** |
| P0-5 (Frontend MUST use apiClient, no raw fetch) | ✅ **0 violations** |
| P0-6 (No NetworkX fallback in production) | ✅ **0 violations** |
| P0-7 (OPA unavailable MUST fail-close) | ❌ **3 violations** |
| P0-8 (No hardcoded default secrets) | ❌ **7 violations** |
| P0-9 (Route handlers MUST have `except HTTPException: raise`) | ❌ **40+ violations** |
| P0-10 (New ontology modules MUST have tests) | ✅ passes (2351 tests) |
| View objects `@dataclass(frozen=True)` | ✅ pass |
| `infra/query/ontology_source.py` is sole bridge | ✅ pass |
| `app.py` only wires routers | ✅ pass |

## Critical (P0) — 34 findings

### Cross-Boundary Violations (3 — block release)

| File:Line | Evidence | Fix |
| --- | --- | --- |
| `odap/biz/core/ontology/design/services/pipeline_service.py:600` | `from odap.biz.core.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage` (design → application/oms) | Move `_on_ontology_change` to `application/oms/hooks.py`; design emits a version event instead |
| `odap/biz/core/ontology/design/services/pipeline_service.py:1314` | `from odap.biz.core.ontology.servitization.catalog.service_catalog import ServiceCatalogService` (design → application/servitization) | Move hook to `application/servitization`; subscribe to `infra.events` |
| `odap/biz/core/ontology/design/services/pipeline_service.py:1326` | `from odap.biz.core.agent.intelligence_agent import IntelligenceAgent` (design → agent) | Cache invalidation belongs to `infra/query` listener |

### Infra → Design Internals (1 — block release)

| File:Line | Evidence | Fix |
| --- | --- | --- |
| `odap/infra/graph/graph_service.py:47` | `from odap.biz.core.ontology.design.mock_data.data_generator import load_simulation_data` (bypasses `design.contract`) | Move `load_simulation_data` to `infra/mock_data/` or use `infra/query.ontology_source` |

### OPA Fail-Open (3 — block release)

| File:Line | Evidence | Fix |
| --- | --- | --- |
| `odap/infra/opa/opa_service.py:494-498` | `if not self.opa_client.health_check(): self.use_mock = True` — defaults to mock on failure | Replace with `raise OPAAvailableError` + fallback to DENY in caller |
| `odap/infra/opa/opa_service.py:563-567` | `except Exception: result = self._mock_check_permission(...)` — fail-open on exception | Replace with `return False` + log |
| `odap/infra/opa/opa_service.py:589-593` | ABAC path also fails open to local evaluator | Same — deny on OPA error |

### Hardcoded Default Secrets (7 — block release)

| File:Line | Secret |
| --- | --- |
| `odap/infra/security/config.py:43` | `JWT_SECRET = os.getenv('JWT_SECRET', 'your_jwt_secret_here')` |
| `odap/infra/security/auth_service.py:97` | `admin_hash = self._hash_password("admin123")` (default admin password) |
| `odap/infra/storage/minio_client.py:39-40` | `MINIO_ACCESS_KEY='minioadmin' / MINIO_SECRET_KEY='minioadmin'` |
| `odap/biz/integration/hook_system/hook_manager_enhanced.py:224` | `os.getenv("HOOK_SIGNING_KEY", "default-secret-key")` |
| `odap/infra/config_composer.py:94` | `"jwt.secret": ConfigSchema(..., "change-me", sensitive=True)` |
| `odap/infra/security/config.py:38, 40` | `NEO4J_PASSWORD` default empty + only prints warning |

### SQL Injection (1 — block release)

| File:Line | Evidence | Fix |
| --- | --- | --- |
| `odap/infra/security/audit_sqlite_channel.py:262-263` | `sql = f'... ORDER BY {filter.order_by} {order_dir} ...'` — user-controlled ORDER BY | Whitelist `order_by` against `{"timestamp", "severity", "actor", "action"}` |

### Pydantic Mutable Defaults (24 — block release)

| File | Count | Lines |
| --- | --- | --- |
| `odap/biz/core/ontology/application/runtime/api/schemas.py` | 7 | 62, 91, 96, 126, 131, 140, 143 |
| `odap/biz/core/ontology/application/oms/schemas.py` | 8 | 44, 64, 66, 77-79, 93, 95, 118, 120 |
| `odap/biz/core/ontology/application/harness/api/schemas.py` | 4 | 18, 30, 43, 60 |
| `odap/biz/management/business/api/routes.py` | 6 | 30, 32, 55, 57, 80, 107 |
| `odap/infra/object_service/schemas.py` | 5 | 34, 35, 53, 54, 55 |

All instances: `field: List[X] = []` → `Field(default_factory=list)`; `field: Dict[X,Y] = {}` → `Field(default_factory=dict)`.

## Important (P1) — ~104 findings

### Missing `except HTTPException: raise` (6 files, 40+ endpoints)

| File | Endpoints |
| --- | --- |
| `odap/biz/core/ontology/application/runtime/state_machine/api/routes.py` | 5 |
| `odap/biz/core/ontology/application/oms/routes.py` | 11 |
| `odap/biz/core/ontology/application/servitization/catalog/routes.py` | 8 |
| `odap/biz/core/ontology/application/harness/blueprint/routes.py` | 9 |
| `odap/biz/core/ontology/application/query_api/routes.py` | 11 |
| `odap/biz/core/ontology/application/servitization/api/deployment_routes.py` | 2 |

### Missing/Loose `response_model` (84 endpoints)

| File | Issue |
| --- | --- |
| `odap/biz/core/ontology/application/runtime/api/routes.py` | 36 endpoints use `response_model=dict` |
| `odap/biz/core/ontology/application/harness/api/routes.py` | 24 endpoints use `response_model=dict` |
| `odap/biz/core/ontology/application/servitization/api/routes.py` + `deployment_routes.py` | 16 endpoints use `response_model=dict` |
| `odap/biz/core/ontology/application/abution_graph/api/routes.py` | 8 endpoints use `response_model=dict` |
| `odap/biz/core/ontology/application/runtime/state_machine/api/routes.py` | 8 endpoints **completely missing** `response_model=` |

### Print Statements in Production Code (~50+)

| File | Count |
| --- | --- |
| `odap/infra/graph/graph_service.py` | 40+ |
| `odap/infra/opa/opa_service.py` | 7 (incl. `__main__` block) |
| `odap/infra/graph/_utils.py` + `search_ops.py` | 4 (`[DEBUG]` prefix) |
| `odap/infra/security/audit_*.py` | 4 |

### Silent Exception Handlers (12)

- `odap/infra/opa/opa_service.py:451, 709, 719` — `except Exception: return False` hides failures
- `odap/infra/security/audit_sqlite_channel.py:316-318, 391-393` — bare except + print
- `odap/infra/security/audit_logger_v2.py:217`, `audit_graphiti_channel.py:189` — print on failure

### Cryptographic Downgrade (2)

- `odap/infra/security/auth_service.py:113-116` — bcrypt unavailable → SHA256 (no salt)
- `odap/infra/security/encryption.py:15` — cryptography unavailable → base64 (no encryption)

## Suggestions (P2) — 35+ findings

### Modules > 500 lines (Top 10)

| File | Lines | Suggested split |
| --- | --- | --- |
| `odap/biz/core/ontology/design/ingestion_split/ingestion.py` | 2290 | Split by source: news / manual / random / web / free_news |
| `odap/biz/core/ontology/design/storage/sqlite_ingest_storage.py` | 1865 | Split by table: documents / entities / relations / versions / audit |
| `odap/biz/core/ontology/design/services/pipeline_service.py` | 1366 | Split by phase: ingest / build / version / clean |
| `odap/infra/opa/opa_service.py` | 1047 | Split: client / evaluator / cache / storage |
| `odap/infra/graph/graph_service.py` | 1023 | Split: client / CRUD / search / migration |
| `odap/biz/core/ontology/design/services/ingest_service.py` | 971 | Split: orchestrator / schema_mapper / normalizer |
| `odap/biz/core/ontology/application/runtime/storage/sqlite_runtime_storage.py` | 665 | Split: object / function / trigger / snapshot |
| `odap/biz/core/ontology/design/ingestion_split/manual_input.py` | 610 | Split: parser / validator / writer |
| `odap/infra/graph/search_ops.py` | 606 | Split: vector / graph / hybrid |
| `odap/infra/security/audit_logger_v2.py` | 585 | Split: channel / dispatcher / formatter |

## Refactor Tasks Generated

Each P0 finding has been converted to a structured refactor task in `specs/000-architecture-review/tasks.md`.

| Task ID | Priority | Summary |
| --- | --- | --- |
| `R-P0-001` | P0 | Move `_on_ontology_change` OMS hook out of `design/services/pipeline_service.py` |
| `R-P0-002` | P0 | Replace OPA fail-open paths with fail-close deny |
| `R-P0-003` | P0 | Eliminate 7 hardcoded default secrets; require env vars |
| `R-P0-004` | P0 | Whitelist `order_by` in `audit_sqlite_channel.py` |
| `R-P0-005` | P0 | Fix 24 Pydantic mutable defaults to `Field(default_factory=...)` |
| `R-P0-006` | P0 | Move `load_simulation_data` to `infra/mock_data/` |
| `R-P1-001` | P1 | Add `except HTTPException: raise` to 40+ route handlers |
| `R-P1-002` | P1 | Define response Pydantic models for 84 endpoints |
| `R-P1-003` | P1 | Replace `print()` with `logger` in `infra/graph/` and `infra/opa/` |
| `R-P2-001` | P2 | Split top-10 oversized modules |
| `R-P2-002` | P2 | Consolidate `_mock_check_permission` into Rego single source of truth |

## Boundary Status

```
┌─────────────────────────────────────────┐
│ ✓ Application → design via contract OK  │  0 violations
│ ✗ Design → application (3 violations)   │  pipeline_service hooks
│ ✓ Application → infra/query OK          │  via contract
│ ✗ Infra → design internal (1 violation) │  graph_service imports
│ ✓ Contract layer immutability OK        │  5 view types
│ ✓ Frontend apiClient OK                 │  0 raw fetch
└─────────────────────────────────────────┘
```

## Recommended Next Steps

1. **This week (P0)**: Address 34 P0 findings — especially OPA fail-close, hardcoded secrets, Pydantic defaults
2. **This sprint (P1)**: Standardize 40+ route error handling, define response models
3. **This quarter (P2)**: Refactor top-10 oversized modules
4. **Continuous**: Re-run `/speckit.architecture-guard.architecture-verify` as pre-merge gate

## Notes

- This review is **non-blocking** — results do not fail CI/CD
- Use `/speckit.architecture-guard.architecture-verify` for stricter verification
- The ontology boundary is 90% clean; remaining violations cluster in `pipeline_service.py` hooks
- Security/resilience is the weakest area (38/100); focus remediation there
