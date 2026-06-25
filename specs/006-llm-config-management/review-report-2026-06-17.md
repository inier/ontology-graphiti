# Architecture Review Report

**Branch**: `006-llm-config-management`  
**Date**: 2026-06-17  
**Reviewer**: QoderWork (automated)  
**Scope**: 20 changed/new/deleted files on working tree

---

## 1. Spec Compliance

The branch spec (`specs/006-llm-config-management/spec.md`) defines a unified LLM/API key configuration management feature with requirements FR-001 through FR-012. The implementation plan places the backend module under `odap/biz/platform/config/` and the frontend under `frontend/src/modules/settings/`.

**Observations on spec alignment**:

The working tree changes are **not primarily about the LLM config feature**. Most of the 20 changed files belong to the ontology, audit, OPA policy, and workspace modules. The settings module itself (which the spec calls for) does not appear in the changed files list, suggesting either it was already committed in a prior commit or has not yet been implemented on this branch. The changes appear to be general improvements and fixes across the codebase rather than spec-driven work for FR-001 through FR-012.

**Verdict**: No spec violations detected, but also no spec-driven implementation visible in the current changeset. The spec remains unaddressed by these particular file changes.

---

## 2. Automated Checks (adapted for Python/TypeScript project)

The original automated check toolchain (`check-loc`, `check-fanout`, `check-state`, `cohesion`) targets Rust projects. The following manual analysis applies equivalent thresholds to the changed files.

### 2.1 File Size (LOC threshold: 1000 code lines)

| File | Approx. Lines | Status |
|------|---------------|--------|
| `odap/web/api/app.py` | 766 | WARNING (approaching threshold) |
| `frontend/src/modules/ontology/stores/ontologyStore.ts` | 955 | **FLAGGED** (near threshold, high complexity) |
| `frontend/src/modules/shared/components/AppLayout.tsx` | 790 | WARNING (approaching threshold) |
| `frontend/src/modules/ontology/pages/UnifiedManagementPage.tsx` | 822 | WARNING (new file, near threshold) |
| `odap/biz/core/ontology/ontology_api/api/routes.py` | 662 | WARNING |
| `frontend/src/modules/workspace/pages/WorkspacePage.tsx` | 493 | OK |
| `odap/biz/core/ontology/design/model/api/routes.py` | 432 | OK |
| `frontend/src/modules/audit/pages/PolicyPage.tsx` | 399 | OK |
| `odap/biz/core/ontology/extraction/services/extraction_service.py` | 394 | OK |
| `odap/infra/opa/markdown_routes.py` | 308 | OK |

**ontologyStore.ts** at 955 lines is the largest changed file and is flagged as a "God store" with approximately 40 actions managing 7 type definition categories, legacy entity types, ontology CRUD, schema versions, and graph data in a single monolithic store.

### 2.2 Fan-out (dependency count)

**AppLayout.tsx** has the highest fan-out: 4 React contexts defined inline, 18+ Ant Design imports, 11 icon imports, plus cross-module dependencies to `guide`, `shared`, `workspace`, and `config` modules. This component manages sidebar, header, right panel, workspace/scenario selection, theme, navigation, and user auth -- an excessive responsibility set.

**ontology_api/api/routes.py** imports `OntologyService`, `TypeRegistry`, multiple Pydantic models, auth dependencies, and various utility modules. The file has 28 type CRUD handlers that bypass the service layer to call `TypeRegistry` directly.

### 2.3 State Score

**ontologyStore.ts** has an extremely high state score: approximately 15 state properties managing 7 different type definition categories plus legacy entity types, ontology selection, schema versions, graph data, loading states, and error states. This far exceeds the threshold of 8.

**AppLayout.tsx** defines 4 React contexts (`WorkspaceContext`, `ScenarioContext`, `OntologyVersionContext`, `RightPanelContext`) plus multiple `useState`/`useRef` hooks for sidebar, theme, and panel state.

---

## 3. Independent Review

### 3.1 CRITICAL -- Rule 6 Violation: Layer Skipping (3 files)

**Rule 6 states**: Call chain must be `routes.py -> services/ -> impl/ -> storage/`. No layer skipping allowed.

#### Violation A: `ontology_api/api/routes.py` -- Route bypasses Service layer

For all type write operations (create/update/delete across 7 type categories, approximately 28 handlers), the route layer bypasses `OntologyService` entirely and calls `TypeRegistry` directly:

```python
registry = _get_type_registry()
result = registry.create_object_type(ontology_id, data)
```

Read operations correctly go through `service.list_object_types(...)`, making this an inconsistent split. **Recommendation**: Add write-through methods to `OntologyService` that internally delegate to `TypeRegistry`, then route all handlers through the service.

#### Violation B: `markdown_routes.py` -- Route bypasses Service, reaches Storage directly

Every handler accesses the storage layer through `markdown_service.version_storage`, bypassing the service layer:

```python
markdown_service.version_storage.save_policy_meta(...)
markdown_service.version_storage.list_policy_metas(...)
```

This affects approximately 8 handlers covering CRUD, compile, toggle, version history, and delete operations. Additionally, `list_markdown_policies` contains pagination logic (slicing `policies[start:end]`) and data aggregation that belongs in the service layer. **Recommendation**: Add corresponding methods to `MarkdownPolicyService` that encapsulate storage access.

#### Violation C: `model_service.py` -- Service bypasses Impl, reaches into private Storage

Three methods bypass the impl layer entirely by reaching through `self._repo._storage` (a private member) to call storage methods directly:

- `get_document` (line 188-193)
- `create_document` (line 195-204)
- `export_document` (line 206-213)

Each also has an unused local import `from ..storage.sqlite_model_storage import SQLiteModelStorage` that is imported but never called. **Recommendation**: Add document-related methods to `ModelRepositoryImpl` and call them through `self._repo`.

### 3.2 HIGH -- No Request Validation at API Boundary

`ontology_api/api/routes.py` accepts raw `dict` for all write endpoints instead of typed Pydantic request models:

```python
async def create_object_type(ontology_id: str, data: dict):
```

This means no request validation, no OpenAPI schema generation for request bodies, and no type safety at the API boundary. **Recommendation**: Define Pydantic request models for each write endpoint (at minimum `CreateObjectTypeRequest`, `UpdateObjectTypeRequest`, etc.).

### 3.3 HIGH -- God Objects Need Decomposition

| Object | Lines | Responsibility Count | Recommendation |
|--------|-------|---------------------|----------------|
| `ontologyStore.ts` | 955 | ~40 actions across 7 type categories + legacy | Decompose into sub-stores or use Zustand slices |
| `AppLayout.tsx` | 790 | 10+ concerns (sidebar, header, panel, contexts, theme, nav) | Extract contexts to dedicated files, decompose into sub-components |
| `app.py` (web/api) | 766 | 40+ router registrations + 15 inline route handlers | Extract inline handlers to dedicated route modules |
| `UnifiedManagementPage.tsx` | 822 | 4 tab components in one file | Split each tab into its own file |

### 3.4 MEDIUM -- Type Safety Gaps (Frontend)

**ontologyStore.ts** contains pervasive unsafe type casting:

```typescript
const result = await ontologyApi.listOntologies();
const ontologies = Array.isArray(result) ? result : (result as Record<string, unknown>)?.ontologies as Ontology[] || [];
```

Nearly every action uses `as unknown as SomeType` or `as Record<string, unknown>` casts, and the store guesses API response shapes at runtime. This indicates a mismatch between the API response types and the store's type definitions. **Recommendation**: Normalize response shapes in the API layer so the store receives consistently typed data.

**ontologyApi.ts** has many methods accepting `data: unknown` instead of typed request objects, defeating TypeScript's type safety at call sites.

### 3.5 MEDIUM -- Duplicate Type Definitions

| Type | Defined In | Issue |
|------|-----------|-------|
| `Policy` interface | `PolicyPage.tsx` AND `auditStore.ts` | Identical definitions; risk of divergence |
| `PropertyDefinition` | `ontologyApi.ts` AND `registryApi.ts` | Nearly identical; `classification_level` optional vs required |

**Recommendation**: Extract shared types to a `types/index.ts` file in each module and import from there.

### 3.6 MEDIUM -- OPA Policy Issues

**operations/allow.rego**: The director role has permissions `"authorize_engagements"` and `"approve_missions"` in the `role_permissions` map, but there are no `allow` rules that check for these actions. These are dead permissions -- they grant nothing unless matching allow rules are added. This is either an intentional placeholder or a policy bug.

**operations/allow.rego**: "withdraw" and "support" actions use direct role checks instead of going through the `has_permission` helper, creating a stylistic inconsistency.

### 3.7 MEDIUM -- Inline Route Handlers in Application Entry Point

`odap/web/api/app.py` defines approximately 15 route handlers directly inside the `_build_app` method (scenarios, ingestion, versions, stats, WebSocket). These handlers bypass the `routes.py -> services/` convention and mix application factory logic with business logic. **Recommendation**: Extract into dedicated route modules under `odap/biz/` or `odap/web/`.

### 3.8 LOW -- i18n Inconsistency

`AgentPage.tsx` uses `useI18n('agent')` for translations, while `PolicyPage.tsx`, `AppLayout.tsx`, and `WorkspacePage.tsx` have all UI strings hardcoded in Chinese. This is inconsistent and creates a maintenance burden if internationalization is ever needed.

### 3.9 LOW -- Import Style Inconsistency

Some files use `@/` aliases while others use relative paths for cross-module imports. The project rule (Rule 11) mandates `@` alias for cross-module imports. Most files comply, but the inconsistency within the same module (e.g., `ontologyStore.ts` uses relative paths) should be addressed.

### 3.10 LOW -- Settings Page Not in Sidebar Navigation

The `/settings` route is registered in `AppRoutes.tsx` but is **not** present in the `primaryMenus` sidebar array in `AppLayout.tsx`. This means the settings page is only accessible by direct URL. If this is intentional (admin-only, hidden feature), it should be documented. If not, it should be added to the navigation.

### 3.11 LOW -- Stub Logic in New Page

`UnifiedManagementPage.tsx` contains placeholder extraction logic (lines 488-499) with hardcoded draft types `[{ name: 'extracted_type_1', status: 'draft' }]`. This is clearly a stub that needs real implementation before merge.

### 3.12 INFO -- `policy_version_storage.py` Latent Bug

`deactivate_version` (line 117) uses `conn.total_changes > 0` to determine if a row was updated. `conn.total_changes` is cumulative over the connection's lifetime, so it could theoretically return a false positive if any prior operation modified rows. Should use `conn.execute(...).rowcount` instead, as `delete_policy_meta` correctly does at line 211.

### 3.13 INFO -- Design Document Concerns

The new `2026-06-16-hyper-extract-integration-design.md` is well-structured but contains two items worth flagging:

1. **Cypher injection risk**: The `UnifiedGraphWriter` uses string interpolation for Neo4j node labels (`MERGE (n:Entity:\`{type}\` ...)`) which is a potential injection vector if ontology type names contain special characters.
2. **Graphiti schema coupling**: The writer creates Episode nodes directly in Neo4j and expects Graphiti's `search()` to query them, creating a tight implicit coupling to Graphiti's internal schema.

---

## 4. Check Improvement Suggestions

The automated check scripts (`check-loc`, `check-fanout`, `check-state`, `cohesion`) are designed for Rust and cannot be applied to this Python/TypeScript project. The following suggestions would make equivalent checks possible:

### 4.1 Rule 6 Violation Detection (NEW CHECK)

The three Rule 6 violations (layer skipping) found in this review are the highest-severity findings. A static analysis script could detect them by:

- Scanning route files for direct storage/registry access patterns (e.g., `self._repo._storage`, `service.version_storage`, `_get_type_registry()`)
- Scanning service files for private member reach-through patterns (e.g., `self._xxx._yyy`)
- This would have caught all three violations automatically.

**Suggested threshold**: Any occurrence of `_storage` access outside a `storage/` directory file, or any `_get_*_registry()` call in a `routes.py` file, should flag.

### 4.2 File Size Check Adaptation

The LOC threshold of 1000 is appropriate for Python/TypeScript as well. The following files are approaching or exceeding it and would benefit from automated flagging:

- `ontologyStore.ts` (955) -- would flag at threshold 900
- `UnifiedManagementPage.tsx` (822) -- would flag at threshold 800
- `AppLayout.tsx` (790)
- `app.py` (766)

**Suggested threshold for frontend components**: 500 lines (React components above this size typically contain multiple components that should be split).

### 4.3 Type Safety Check (NEW CHECK)

A TypeScript-specific check could flag:

- `as unknown as` casts (type safety bypass)
- `data: unknown` parameters in API methods
- `(result as Record<string, unknown>)` response shape guessing

**Suggested threshold**: More than 5 `as unknown as` casts per file should flag. `ontologyStore.ts` has approximately 20+.

### 4.4 False Positive Suppression

The `check-fanout` equivalent for frontend components should suppress Ant Design icon imports, as these are leaf dependencies that don't indicate architectural coupling. The 11 icon imports in `PolicyPage.tsx` inflate its fan-out score without representing a real concern.

---

## 5. Summary by Severity

| Severity | Count | Key Issues |
|----------|-------|------------|
| **CRITICAL** | 3 | Rule 6 layer skipping in `ontology_api/routes.py`, `markdown_routes.py`, `model_service.py` |
| **HIGH** | 2 | No Pydantic request validation; God objects (4 files) |
| **MEDIUM** | 4 | Type safety gaps; duplicate types; OPA dead permissions; inline handlers in app.py |
| **LOW** | 5 | i18n inconsistency; import style; settings not in sidebar; stub logic; import style |
| **INFO** | 3 | Storage latent bug; Cypher injection risk; Graphiti schema coupling |

**Total**: 17 findings across 20 reviewed files.

---

## 6. Recommended Priority Actions

1. **Fix Rule 6 violations** (CRITICAL): Add write-through methods to `OntologyService` and `MarkdownPolicyService`; fix private member access in `ModelService`.
2. **Add Pydantic request models** to `ontology_api/api/routes.py` write endpoints.
3. **Decompose `ontologyStore.ts`** into Zustand slices or sub-stores by type category.
4. **Extract inline route handlers** from `odap/web/api/app.py` into dedicated route modules.
5. **Fix OPA dead permissions** in `operations/allow.rego` -- either add matching allow rules or remove the unused permissions.
6. **Extract React contexts** from `AppLayout.tsx` into dedicated context files.
7. **Fix `policy_version_storage.py`** `deactivate_version` to use `rowcount` instead of `total_changes`.
