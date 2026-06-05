# Remediation Tasks: ODAP Review Findings (2026-06-02)

**Source**: SuperSpec Review Report (P0/P1 findings)
**Branch**: `001-odap-platform` | **Date**: 2026-06-02 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Total Tasks**: 28 | **Phases**: 5

> Tasks address gaps identified in the SuperSpec review. All existing 330 implementation tasks are already `[x]`. These tasks focus on **hardening** the implementation based on compliance and code-quality findings.

---

## Phase 10: Critical Security (P0) 🚨

**Purpose**: Address zero-authentication and hardcoded-secret findings that violate Constitution Security Boundaries.

**⚠️ CRITICAL**: These MUST be completed before any production deployment.

### 10.1 API Authentication Enforcement

- [ ] T313 [REVIEW] [P] [SEC] Add `Depends(get_current_user)` to all business routes in `odap/biz/**/*.py` (workspace, ontology, agent, audit, simulation, decision, knowledge, qa, role, skill modules)
- [ ] T314 [P] [SEC] Mark public endpoints with explicit `skipAuth` annotation in `odap/web/app.py` (only `/health`, `/api/auth/login`, `/api/auth/refresh`, `/docs`, `/openapi.json`)
- [ ] T315 [TDD] [P] [SEC] Create `tests/unit/test_auth_enforcement.py` verifying 401 response for unauthenticated requests on all protected routes
- [ ] T316 [P] [SEC] Update `odap/infra/security/middleware.py` to enforce auth at middleware level as defense-in-depth

### 10.2 Remove Hardcoded Default Secrets

- [ ] T317 [REVIEW] [P] [SEC] Fix JWT secret fallback in `odap/infra/security/config.py` line 43 — remove default, fail-fast on missing env var
- [ ] T318 [P] [SEC] Fix hook signing key fallback in `odap/biz/integration/hook_system/hook_manager_enhanced.py` line 224 — remove `"default-secret-key"` fallback
- [ ] T319 [P] [SEC] Fix MinIO credentials fallback in `odap/infra/storage/minio_client.py` line 40 — remove `"minioadmin"` default
- [ ] T320 [TDD] [P] [SEC] Create `tests/unit/test_secret_validation.py` verifying all secret-loading functions raise `RuntimeError` when env vars are missing

**Checkpoint**: All secrets fail-fast; all routes require auth.

---

## Phase 11: Frontend apiClient Enforcement (P0)

**Purpose**: Eliminate raw `fetch()` calls to ensure unified auth header injection, error handling, and 401 auto-redirect.

### 11.1 Replace fetch with apiClient

- [ ] T321 [P] [FE] Replace 5 raw `fetch()` calls in `frontend/src/modules/shared/stores/authStore.ts` with `apiClient.post/get`
- [ ] T322 [P] [FE] Replace raw `fetch()` in `frontend/src/modules/shared/stores/index.ts` (login, loadEvents) with `apiClient`
- [ ] T323 [P] [FE] Replace raw `fetch()` in `frontend/src/modules/qa/services/qaApi.ts` (askTemporalQuestion, renderChart) with `apiClient`
- [ ] T324 [P] [FE] Replace raw `fetch()` in `frontend/src/modules/qa/hooks/useSession.ts` (3 calls) with `apiClient`
- [ ] T325 [P] [FE] Replace raw `fetch()` in `frontend/src/modules/qa/hooks/useQAI.ts` (2 calls, including streaming endpoint) with `apiClient`
- [ ] T326 [P] [FE] Replace raw `fetch()` in `frontend/src/modules/shared/pages/LoginPage.tsx` (fetchSSOProviders, handleSSOLogin) with `apiClient`
- [ ] T327 [P] [FE] Add ESLint rule `@typescript-eslint/no-restricted-syntax` to block `fetch(` calls outside `apiClient.ts`

**Checkpoint**: Zero raw `fetch()` in application code; all API calls go through `apiClient` with auth header injection.

---

## Phase 12: Spec Compliance (P1)

**Purpose**: Address edge case violations and PARTIAL findings from the spec review.

### 12.1 LLM Unavailable — Clear Error

- [ ] T328 [TDD] [P] [US2] Add `llm_unavailable` flag to intent router result in `odap/biz/core/agent/impl/intent_router.py` (lines 88-100)
- [ ] T329 [P] [US2] Add `llm_unavailable` flag to swarm orchestrator's `IntentRouter` in `odap/biz/core/agent/swarm_orchestrator.py` (lines 298-305)
- [ ] T330 [P] [US2] Create `tests/unit/test_intent_router_llm_failure.py` verifying clear error returned when LLM is down

### 12.2 OPA Fail-Close in Production

- [ ] T331 [REVIEW] [P] [US3] Modify `OPAManager` in `odap/infra/opa/opa_service.py` (lines 469-501) — remove mock-mode fallback in production; default to `deny` when OPA unavailable
- [ ] T332 [P] [US3] Add `OPA_FAIL_OPEN=false` environment variable to `.env.example` with secure default
- [ ] T333 [TDD] [P] [US3] Create `tests/unit/test_opa_fail_close.py` verifying deny-by-default when OPA server is unreachable

### 12.3 Batch Import Schema Validation

- [ ] T334 [P] [US1] Add `validate_against_schema()` method to `odap/biz/core/ontology/ingestion/impl/batch_importer.py` — validate CSV columns against entity type's defined attribute schema
- [ ] T335 [P] [US1] Update `import_csv()` to skip invalid rows, record validation errors, return partial-success report
- [ ] T336 [TDD] [P] [US1] Create `tests/unit/test_batch_import_validation.py` verifying partial-success on schema violations

**Checkpoint**: All spec edge cases handled with explicit error/validation logic.

---

## Phase 13: Code Quality & Type Safety (P1)

**Purpose**: Address mutable defaults, missing error handling, and type-safety violations.

### 13.1 Pydantic Mutable Defaults

- [ ] T337 [P] [QUALITY] Fix `= []` defaults in `odap/biz/management/business/api/routes.py` (lines 29, 31, 54, 56, 79, 106) — use `Field(default_factory=list)`
- [ ] T338 [P] [QUALITY] Fix `= []` and `= {}` defaults in `odap/biz/core/ontology/runtime/api/schemas.py` (lines 22-26, 44-48, 62, 91, 96) — use `Field(default_factory=...)`
- [ ] T339 [P] [QUALITY] Fix `= {}` in `odap/biz/management/agent_management/api/routes.py` line 13
- [ ] T340 [TDD] [P] [QUALITY] Create `tests/unit/test_pydantic_defaults.py` verifying no shared mutable state between instances

### 13.2 Route Error Handling

- [ ] T341 [P] [QUALITY] Add try/except with `except HTTPException: raise` to all 8 endpoints in `odap/biz/data/perception/routes.py`
- [ ] T342 [P] [QUALITY] Add try/except with `except HTTPException: raise` to 3 endpoints in `odap/biz/decision/decision_pipeline/routes.py`
- [ ] T343 [P] [QUALITY] Add try/except with `except HTTPException: raise` to 2 endpoints in `odap/biz/simulation/simulation_sandbox/routes.py`
- [ ] T344 [P] [QUALITY] Add try/except with `except HTTPException: raise` to `odap/biz/decision/action_service/routes.py`

### 13.3 SQL Injection Hardening

- [ ] T345 [P] [QUALITY] Add table-name whitelist in `odap/biz/platform/workspace/impl/isolation.py` line 215 before dynamic interpolation
- [ ] T346 [P] [QUALITY] Refactor `odap/biz/platform/i18n/storage/sqlite_i18n_storage.py` (lines 103, 108) to use parameterized WHERE clauses
- [ ] T347 [P] [QUALITY] Refactor `odap/biz/core/ontology/oms/storage/sqlite_oms_storage.py` (lines 211, 239, 301, 332) to whitelist column names

**Checkpoint**: Constitution Principle I (simplicity) and Rule 3 (error handling) and Rule 5 (container fields) all satisfied.

---

## Phase 14: Test Coverage (P1)

**Purpose**: Create test files for 6 uncovered modules and 7+ route files.

### 14.1 Create Test Files for Uncovered Modules

- [ ] T348 [TDD] [P] [TEST] Create `tests/unit/test_oms.py` — CRUD, schema validation, batch operations for OMS module
- [ ] T349 [TDD] [P] [TEST] Create `tests/unit/test_ontology_version.py` — version creation, rollback, comparison
- [ ] T350 [TDD] [P] [TEST] Create `tests/unit/test_frontend_compat.py` — route handlers, backward compatibility
- [ ] T351 [TDD] [P] [TEST] Create `tests/unit/test_ontology_schema.py` — OntologyDocument and Domain models
- [ ] T352 [TDD] [P] [TEST] Create `tests/unit/test_ingestion_split.py` — split ingestion pipelines
- [ ] T353 [TDD] [P] [TEST] Create `tests/unit/test_mock_data.py` — mock data generators

### 14.2 Route-Specific Test Files

- [ ] T354 [TDD] [P] [TEST] Create `tests/unit/test_agent_decision_routes.py` — decision chain endpoints
- [ ] T355 [TDD] [P] [TEST] Create `tests/unit/test_sandbox_parallel_routes.py` — parallel sandbox endpoints
- [ ] T356 [TDD] [P] [TEST] Create `tests/unit/test_ontology_decay_routes.py` — memory decay endpoints
- [ ] T357 [TDD] [P] [TEST] Create `tests/unit/test_consensus_routes.py` — consensus engine endpoints

**Checkpoint**: All `odap/biz/` modules with `routes.py` have corresponding test files; coverage of route handlers >= 80%.

---

## Phase 15: Polish & Refactoring (P2)

**Purpose**: Address code-quality suggestions, deprecated code, and architectural improvements.

### 15.1 Refactor Large Files

- [ ] T358 [P] [REFACTOR] Split `odap/biz/integration/frontend_compat/api/routes.py` (1700+ lines) into domain-specific route files (`qa_compat_routes.py`, `cognition_compat_routes.py`, etc.)
- [ ] T359 [P] [REFACTOR] Split `frontend/src/modules/qa/hooks/useQAI.ts` (376 lines) into smaller functions (`useStreamingResponse`, `useMessageBuilder`, `useErrorRecovery`)

### 15.2 Remove Deprecated Code

- [ ] T360 [P] [REFACTOR] Remove `ITeamAgentService` deprecated interface from `odap/biz/core/ontology/team_agent/interfaces/__init__.py`
- [ ] T361 [P] [REFACTOR] Remove empty `interfaces/__init__.py` in `odap/biz/core/ontology/runtime/state_machine/`
- [ ] T362 [P] [REFACTOR] Audit and remove single-implementation interfaces in `odap/biz/core/ontology/runtime/interfaces/`, `odap/biz/core/ontology/harness/`, `odap/biz/platform/ontology_memory/`

### 15.3 Login Page Hardcoded Credentials

- [ ] T363 [P] [REFACTOR] Remove default `admin/admin123` in `frontend/src/modules/shared/pages/LoginPage.tsx` line 210
- [ ] T364 [P] [REFACTOR] Add "Demo Account" toggle in LoginPage that shows/hides default credentials hint

### 15.4 Hardcoded URLs in Frontend

- [ ] T365 [P] [REFACTOR] Replace hardcoded `http://localhost:8000/docs` in `frontend/src/modules/guide/pages/GuidePage.tsx` (lines 98, 410) with `config.apiDocsUrl`

### 15.5 Final Quality Gate

- [ ] T366 [REVIEW] [TEST] Run `pytest tests/unit/ -v --tb=short` and ensure zero failures
- [ ] T367 [REVIEW] [TEST] Run `cd frontend && npm run lint && npm run typecheck` and ensure zero errors
- [ ] T368 [REVIEW] [TEST] Run `cd frontend && npm run build` and ensure successful production build
- [ ] T369 [REVIEW] Verify all Constitution principles (I-IV + Security Boundaries) satisfied via automated check

**Checkpoint**: All P2 suggestions addressed; code quality meets Constitution bar.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 10 (Security)**: No dependencies — URGENT, blocks production
- **Phase 11 (apiClient)**: No dependencies — URGENT, blocks production
- **Phase 12 (Spec)**: Depends on Phase 10 (auth needed for testing spec compliance)
- **Phase 13 (Code Quality)**: Independent — can run parallel to Phase 12
- **Phase 14 (Tests)**: Depends on Phase 13 (need stable code to test)
- **Phase 15 (Polish)**: Depends on Phases 10-14 — final cleanup

### Recommended Execution Order

1. **Phase 10** (T313-T320) — Security first, blocks all other work
2. **Phase 11** (T321-T327) — Frontend auth, parallel to Phase 10
3. **Phase 13.1** (T337-T340) — Mutable defaults are quick wins
4. **Phase 13.2** (T341-T344) — Error handling
5. **Phase 13.3** (T345-T347) — SQL injection hardening
6. **Phase 12** (T328-T336) — Spec compliance
7. **Phase 14** (T348-T357) — Test coverage
8. **Phase 15** (T358-T369) — Final polish

### Parallel Opportunities

- Phase 10 and Phase 11 can run fully in parallel (different files)
- Within Phase 10, all `[P]` tasks (secrets) can run in parallel
- Within Phase 13, all three sub-phases (defaults, error handling, SQL) can run in parallel
- Within Phase 14, all test-file creation tasks can run in parallel

---

## Execution Markers Reference

| Marker | Count | Tasks |
|--------|:-----:|-------|
| `[P]` (Parallel) | 24 | Most tasks — different files |
| `[TDD]` (Test-First) | 10 | Test creation must precede impl |
| `[REVIEW]` (Review Gate) | 5 | Security, architecture changes |
| `[SUBAGENT]` (Subagent) | 0 | None — all require code-level judgment |
| `[SEC]` (Security) | 8 | Phase 10 tasks |
| `[US1]`, `[US2]`, `[US3]` | 3+3+3 | Story-tagged tasks |

---

## Quality Gates (after each phase)

```bash
# Backend
pytest tests/unit/ -v --tb=short    # All tests pass
ruff check .                         # Zero warnings

# Frontend
cd frontend && npm run lint          # Zero warnings
cd frontend && npm run typecheck     # Zero errors
cd frontend && npm run build         # Successful build
```

---

## Notes

- Tasks are **remediation-focused**, not new feature work
- All `routes.py` modifications MUST register with `odap/web/app.py` if router prefix changes
- After each task, run `pytest tests/unit/test_{module}.py` for that specific module
- Phase 10-11 are P0 (production blockers); Phase 12-14 are P1; Phase 15 is P2
