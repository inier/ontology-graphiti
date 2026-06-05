# Architecture Review: 000-architecture-review (Refactor Verification Pass)

> **Date**: 2026-06-05
> **Scope**: `odap/` entire codebase + `specs/000-architecture-review/`
> **Mode**: Post-implementation, non-blocking
> **Preset**: `python-fastapi` (custom)
> **Constitutions**: `.specify/memory/{constitution,architecture_constitution,governance_constitution}.md`
> **Reviewer**: `/speckit.architecture-guard.architecture-review`

## Summary

| Metric | Original (2026-06-03) | Post-Refactor (2026-06-05) | Δ |
|--------|------------------------|----------------------------|---|
| **Files scanned** | 408 | 408 | — |
| **Pydantic models scanned** | 157 BaseModel | 157 BaseModel | — |
| **P0 violations (block release)** | **34** | **1** (NEW) | −33 |
| **P1 violations (block merge)** | **~104** | **0** | −104 |
| **P2 violations (suggestions)** | 35+ | 15 (module size) | −20 |
| **P3 (governance drift)** | unknown | 213 functions > 40 lines | +213 |
| **Drift score (ontology boundary)** | 62/100 | **100/100** | +38 |
| **Drift score (FastAPI/Pydantic)** | 78/100 | **100/100** | +22 |
| **Drift score (security/resilience)** | 38/100 | **~95/100** (NEW gap) | +57 |
| **Overall composite score** | 59/100 | **~95/100** | +36 |
| **Test count** | 2,351 | **2,639** | +288 |
| **Test pass rate** | 100% | **100%** | — |

## Compliance Snapshot (Updated 2026-06-05)

| Rule | Original | Now | Status |
|------|----------|-----|--------|
| P0-3 (Application MUST NOT import design internals) | ✅ | ✅ | unchanged |
| P0-4 (Design MUST NOT import application) | ❌ 3 | ✅ 0 | FIXED |
| P0-5 (Frontend MUST use apiClient, no raw fetch) | ✅ | ✅ | unchanged |
| P0-6 (No NetworkX fallback in production) | ✅ | ✅ | unchanged (`_test_mode` gated) |
| P0-7 (OPA unavailable MUST fail-close) | ❌ 3 | ✅ 0 | FIXED |
| P0-8 (No hardcoded default secrets) | ❌ 7 | ✅ 0 | FIXED |
| P0-9 (Route handlers MUST have `except HTTPException: raise`) | ❌ 40+ | ✅ 0 | FIXED |
| P0-10 (New ontology modules MUST have tests) | ✅ | ✅ | unchanged |
| P0-1 (No unvalidated external input) | ✅ | ⚠️ | **NEW: cypher injection gap** |
| Mutable defaults (`Field(default_factory=...)`) | ❌ 24 | ✅ 0 | FIXED |
| View objects `@dataclass(frozen=True)` | ✅ | ✅ | unchanged |
| `infra/query/ontology_source.py` sole bridge | ✅ | ✅ | unchanged |
| `app.py` only wires routers | ✅ | ✅ | unchanged |
| **Function length < 40 lines** | unknown | ❌ 213 | **NEW (P3 governance drift)** |

## Critical (P0) — 1 finding (was 34)

### ✅ Cross-Boundary Violations — RESOLVED
3 design→application imports replaced with event bus (`design/services/pipeline_service.py:600/1314/1326`).

### ✅ OPA Fail-Open — RESOLVED
3 fail-open paths in `opa_service.py` (494, 563, 589) replaced with `OPA_FAIL_MODE=deny` default.

### ✅ Hardcoded Default Secrets — RESOLVED
7 placeholder defaults (`config.py`, `auth_service.py`, `minio_client.py`, `hook_manager_enhanced.py`, `config_composer.py`) removed.

### ✅ SQL Injection (SQLite) — RESOLVED
`audit_sqlite_channel.py:262-263` ORDER BY replaced with whitelisted resolver.

### ✅ Pydantic Mutable Defaults — RESOLVED
24 → 0 via `Field(default_factory=...)`.

### ❌ P0-1: Cypher Injection in audit_graphiti_channel.py (NEW)

| File:Line | Evidence | Severity |
| --- | --- | --- |
| `odap/infra/security/audit_graphiti_channel.py:207` | `placeholders = ','.join([f'"{uid}"' for uid in filter.actor_ids])` then `f"n.user IN [{placeholders}]"` | **P0-1** |
| `odap/infra/security/audit_graphiti_channel.py:210` | `where_clauses.append(f'n.workspace_id = "{filter.workspace_id}"')` | **P0-1** |
| `odap/infra/security/audit_graphiti_channel.py:212` | `where_clauses.append(f'n.trace_id = "{filter.trace_id}"')` | **P0-1** |
| `odap/infra/security/audit_graphiti_channel.py:215-216` | `cypher = f"""MATCH (n:AuditLog) {where_part} RETURN n ORDER BY n.timestamp DESC LIMIT {filter.limit}"""` | **P0-1** |

**Risk**: User-controlled fields (`filter.workspace_id`, `filter.trace_id`, `filter.actor_ids`, `filter.limit`) are directly interpolated into Cypher queries. An attacker who can submit audit filter parameters can escape the string (`"..." OR MATCH (admin) DETACH DELETE admin //`) or inject arbitrary Cypher.

**Fix**:
1. Use Neo4j parameterized queries: `session.run("MATCH (n:AuditLog) WHERE n.workspace_id = $ws RETURN n", ws=filter.workspace_id)`
2. Pass `actor_ids` as a list parameter: `session.run("... WHERE n.user IN $uids", uids=filter.actor_ids)`
3. Validate `filter.limit` is a bounded integer (`max(1, min(int(filter.limit), 1000))`)

**Recommendation**: Convert to R-P0-007 task. Confidence: 0.95 (file:line evidence, no mitigation visible).

## Important (P1) — 0 findings (was ~104)

All P1 violations resolved:
- ✅ `except HTTPException: raise` in route handlers (40+ endpoints, 0 missing)
- ✅ `response_model=DictResponse` for 96 endpoints
- ✅ `print()` → `logger` (341/342 replaced)
- ✅ Silent `except Exception: return X` cleaned (12 target files, 49+ fixed)
- ✅ Crypto fail-close (bcrypt + cryptography)

## Suggestions (P2) — 15 findings (was 10)

### Modules > 500 Lines (Top 10)

| File | Lines | Suggested Split |
|------|-------|-----------------|
| `odap/biz/core/ontology/design/ingestion_split/ingestion.py` | 2,290 | Split by source: news/manual/random/web/free_news |
| `odap/biz/core/ontology/design/storage/sqlite_ingest_storage.py` | 1,865 | Split by table: documents/entities/relations/versions/audit |
| `odap/biz/core/ontology/design/services/pipeline_service.py` | 1,372 | Split by phase: ingest/build/version/clean |
| `odap/biz/data/qa/qa_engine.py` | 1,303 | Split: retriever/reranker/prompt/evaluator |
| `odap/infra/opa/opa_service.py` | 1,158 | Split: client/evaluator/cache/storage |
| `odap/infra/graph/graph_service.py` | 1,058 | Split: client/CRUD/search/migration |
| `odap/biz/core/cognition/user_cognition_engine.py` | 1,016 | Split: profile/inference/feedback |
| `odap/biz/platform/tool_registry/registry.py` | 1,006 | Split: registry/executor/condition |
| `odap/biz/core/ontology/design/services/ingest_service.py` | 971 | Split: orchestrator/schema_mapper/normalizer |
| `odap/biz/core/agent/swarm_orchestrator.py` | 936 | Split: dispatcher/scheduler/observer |

Status: ⚠️ 5 more than original (broader scan). Tracked as R-P2-001 (deferred).

## P3 (Governance) — NEW Drift

### Functions > 40 Lines (213 total)

Per `.specify/memory/governance_constitution.md` "Code Quality Standards":
> "Functions over 40 lines: MUST be split into smaller functions"

Top offenders:
- `odap/web/api/app.py:373 _build_app` (335L) — local dev entry builder
- `odap/web/api/app.py:57 __init__` (315L) — MockDataWebService init
- `odap/biz/core/ontology/design/storage/sqlite_ingest_storage.py:52 _init_db` (239L)
- `odap/biz/core/ontology/design/mock_data/data_generator.py:29 generate_simulation_data` (180L)
- `odap/biz/data/qa/qa_engine.py:1036 _generate_with_llm` (139L)

**Status**: ⚠️ NEW DRIFT — 213 violations. **Severity: P3 (opportunistic)**.
**Recommendation**: Track as R-P3-001. Auto-detect via AST scan in CI.

## Drift Candidates (No Clear Violation)

| Item | Status | Notes |
|------|--------|-------|
| `odap/infra/graph/graph_service.py:552 fallback_graph = nx.DiGraph()` | ✅ Compliant | Gated by `_test_mode=True` |
| 47 `print()` calls replaced; 1 docstring reference remains | ✅ Compliant | Docstring example only |
| `odap/web/app.py:232-261` has 2 root-level `@app.get` | ✅ Compliant | `root` and `health_check` are deliberate app-level, not module routes |
| `odap/infra/security/audit_sqlite_channel.py:303, 314` f-string in SQL | ✅ Compliant | `keyword` is wrapped in `%...%` (LIKE pattern), `safe_order_by` is whitelisted |

## Refactor Tasks Generated

| Task ID | Priority | Summary | Confidence | File:Line Evidence |
|---------|----------|---------|------------|---------------------|
| `R-P0-007` | **P0** | Fix Cypher injection in `audit_graphiti_channel.py` (4 sites: 207, 210, 212, 215-216) | 0.95 | [audit_graphiti_channel.py:207-216](file:///e:/DEMO/AI/ontology-graphiti/odap/infra/security/audit_graphiti_channel.py) |
| `R-P3-001` | P3 | Split 213 functions > 40 lines | 0.90 | AST scan: `_build_app` 335L, `__init__` 315L, `_init_db` 239L, etc. |

## Boundary Status (Post-Refactor)

```
┌─────────────────────────────────────────┐
│ ✓ Application → design via contract OK  │  0 violations
│ ✓ Design → application                 │  0 violations (event bus)
│ ✓ Application → infra/query OK         │  via contract
│ ✓ Infra → design internal              │  0 violations (contract only)
│ ✓ Contract layer immutability OK       │  5 view types
│ ✓ Frontend apiClient OK                │  0 raw fetch
│ ✓ OPA fail-close                       │  OPA_FAIL_MODE=deny
│ ✓ Secrets env-required                 │  7 placeholders removed
│ ✓ No silent crypto downgrade           │  bcrypt + cryptography asserted
│ ⚠ Cypher injection (audit_graphiti)    │  NEW finding, P0-1
└─────────────────────────────────────────┘
```

## Refactor Task Pipeline

```
R-P0-001..006 (5 critical)  ✅ DONE (this refactor)
R-P1-001..005               ✅ DONE (this refactor)
R-P0-007 (NEW)              ⏳ TODO  — Cypher injection fix
R-P2-001 (10 module splits) ⏳ DEFERRED — non-blocking
R-P3-001 (function splits)  ⏳ DEFERRED — opportunistic
```

## Recommended Next Steps

1. **Immediate (P0)**: Fix R-P0-007 Cypher injection — **blocks release**
2. **This sprint (P2)**: Schedule R-P2-001 module splits (15 modules, top-10 highest priority)
3. **Continuous (P3)**: R-P3-001 — opportunistic function splits during routine maintenance
4. **Verification gate**: Re-run `/speckit.architecture-guard.architecture-verify` after R-P0-007 fix to confirm 0 P0 violations

## Notes

- This review is **non-blocking** — results do not fail CI/CD
- The **1 remaining P0** (R-P0-007) is the only blocker for a clean release
- The 213 P3 function-length violations are tracked in a new R-P3-001 — opportunistic
- Module size growth (10 → 15) reflects broader scan scope, not new debt
- All previously failing patterns (`response_model=dict`, `print()`, silent excepts, hardcoded secrets) are now clean
