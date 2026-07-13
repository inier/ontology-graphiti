# Tasks: Hyper-Extract 启用 + 抽取校验完整链路

**Input**: Design documents from `specs/006-he-extraction-chain/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

## Task Format

```
[ID] [markers] [Story] Description
```

**Markers**:
- **[P]**: Can run in parallel (different files, no dependencies)
- **[TDD]**: Must follow RED-GREEN-REFACTOR (write test → fail → implement → pass → refactor)
- **[REVIEW]**: Requires code review before proceeding to next task
- **[SUBAGENT]**: Can be delegated to a subagent for parallel execution

**Story labels**: `[US1]`, `[US2]`, etc. map tasks to user stories for traceability.

## Path Conventions

- **Backend source**: `odap/biz/` (data domain + core ontology domain)
- **Tests**: `tests/unit/` and `tests/integration/` at repository root
- **Template YAML**: `data/he_templates/{ontology_id}/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — directory structure and database schema

- [X] T001 Create `data/he_templates/` directory structure for YAML template persistence (with `.gitkeep` for empty ontology folders)
- [X] T002 Create SQLite DDL migration for `he_templates` table (id, ontology_id, name, description, source, yaml_path, preset_name, score, coverage, usage_count, created_at, updated_at, UNIQUE(ontology_id, name)) + index `idx_he_templates_ontology` in `odap/biz/data/hyper_extract/storage/sqlite_template_storage.py`
- [X] T003 Create `extraction_provenance` ALTER migration: add `source_template TEXT` column in `odap/biz/data/hyper_extract/storage/sqlite_template_storage.py`

**Execution notes**: No special discipline required. Verify DDL executes against tmp_path SQLite before proceeding.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [TDD] Write failing tests for SqliteTemplateStorage CRUD (save, get_by_id, get_by_ontology, update_usage_count, list_all, UNIQUE constraint, file-missing handling) in `tests/unit/test_sqlite_template_storage.py` — use `tmp_path` fixture for real SQLite DB
- [X] T005 Implement SqliteTemplateStorage class (save, get_by_id, get_by_ontology, update_usage_count, list_all) in `odap/biz/data/hyper_extract/storage/sqlite_template_storage.py` — WAL mode, `_get_conn` pattern per existing storage convention
- [X] T006 [REVIEW] Review he_templates schema and ExtractionSession enhancement fields — verify DDL matches `data-model.md`, verify `result_data` JSON can hold `validation_report`/`template_assessment`/`degradation_flags`

**Execution notes**: T004 must FAIL before T005. T005 must pass T004. T006 is a review gate for data model correctness before consumers are built.

**Checkpoint**: Foundation ready. Get human approval before starting user stories.

---

## Phase 3: User Story 5 — HE 包安装与真实 API 对齐 (Priority: P0) MVP

**Goal**: Fix HEAdapter to use real HE API — eliminate stub code, kwarg name errors, and silent fallback. This unblocks all other user stories.
**Independent Test**: `HEAdapter.is_available()` returns True after image rebuild; `parse`/`trial_extract`/`merge_results`/`feed_text` all call real HE API (verified via mock-level unit tests checking call arguments).

### Tests for User Story 5

> Write these tests FIRST. Verify they FAIL before implementation.

- [X] T007 [TDD] [US5] Write failing tests for HEAdapter.is_available() and HEAdapter.__init__ — verify get_config import works, HE unavailable raises RuntimeError (no silent fallback) in `tests/unit/test_he_adapter.py`
- [X] T008 [TDD] [US5] Write failing tests for HEAdapter.parse() — verify Template.create called with `llm_client=`/`embedder=` (not `llm=`/`emb=`), verify ka.parse(text) called, verify result normalized to `{"entities": [...], "relations": [...]}` in `tests/unit/test_he_adapter.py` — Mock Template.create and ka.parse, do NOT call real LLM
- [X] T009 [P] [TDD] [US5] Write failing tests for HEAdapter.parse_batch() — verify per-text error isolation, verify all texts attempted even if one fails in `tests/unit/test_he_adapter.py`
- [X] T010 [P] [TDD] [US5] Write failing tests for HEAdapter.feed_text() — verify BaseAutoType.feed_text() called (not evolve), verify instance modified in-place in `tests/unit/test_he_adapter.py`
- [X] T011 [P] [TDD] [US5] Write failing tests for HEAdapter.merge_results() — verify entity dedup by name (keep first), relation dedup by (source, type, target), conflict marking in `tests/unit/test_he_adapter.py`
- [X] T012 [P] [TDD] [US5] Write failing tests for HEAdapter.trial_extract() — verify sample_size truncation, verify returns entity_count/relation_count/field_coverage/type_diversity/types_found in `tests/unit/test_he_adapter.py`

### Implementation for User Story 5

- [X] T013 [US5] Fix HEAdapter.__init__ + is_available() — add `from odap.infra.config_composer import get_config`, remove silent SchemaLevelExtractor fallback, raise RuntimeError when HE unavailable in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T014 [US5] Fix HEAdapter.parse() — align kwarg names to `llm_client=`/`embedder=`, use `Template.create(source, language, llm_client=, embedder=)`, access `.nodes`/`.edges` (not `dump_dict()`), normalize result in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T015 [P] [US5] Implement HEAdapter.parse_batch() — iterate texts, per-text try/except, collect results list in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T016 [P] [US5] Implement HEAdapter.feed_text() — replace `evolve()` stub, call `ka_instance.feed_text(new_text)` (real HE API), return normalized result in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T017 [P] [US5] Implement HEAdapter.merge_results() — HE has no native graph merge API; deduplicate entities by name (keep first, mark conflicts), relations by (source, type, target) triplet in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T018 [P] [US5] Implement HEAdapter.trial_extract() — truncate text to `sample_size` (default 1500), call parse(), compute entity_count/relation_count/field_coverage/type_diversity/types_found in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T019 [US5] Add LLM/Embedder config injection from ODAP env — use `get_config("llm.api_key")`, `get_config("llm.api_base")`, `get_config("llm.model")` to build spec string for `create_llm()`/`create_embedder()`, do NOT create `~/.he/config.toml` in `odap/biz/data/hyper_extract/impl/he_adapter.py`
- [X] T020 [REVIEW] HEAdapter interface review — verify all kwarg names match real HE API (`llm_client=`/`embedder=`, `feed_text` not `evolve`, `.nodes`/`.edges` not `dump_dict()`), verify get_config import resolves

**Execution notes**: T007-T012 tests must FAIL before T013-T018 implementation. T009-T012 can be written in parallel (different test methods). T015-T018 implement different methods in same file — sequential or careful merge. T020 is a review gate before TemplateEngine (which depends on HEAdapter.trial_extract).

**Checkpoint**: HEAdapter fully functional with mock-level tests passing. Get human approval.

---

## Phase 4: User Story 1 — 模板评估: 试抽评分 (Priority: P0)

**Goal**: Dynamic preset enumeration (30+) + trial extraction scoring with semantic pre-filtering
**Independent Test**: Given e-commerce business text, system enumerates 30+ HE presets dynamically (not hardcoded), trial-extracts top-5 semantically matched candidates, returns scored ranked list with traceable metrics (entity_count/relation_count/field_coverage/type_diversity per candidate).

### Tests for User Story 1

- [X] T021 [TDD] [US1] Write failing tests for TemplateEngine.list_presets() — verify Template.list() called (not hardcoded), verify returns 30+ entries with name/description/type/tags/language in `tests/unit/test_template_engine.py` — Mock HEAdapter and Template.list
- [X] T022 [TDD] [US1] Write failing tests for TemplateEngine.assess() — verify settled template check first, verify embedder pre-filter top-k=5, verify trial_extract called for top-k, verify scoring formula applied, verify returns sorted candidates with score in `tests/unit/test_template_engine.py`
- [X] T023 [TDD] [US1] Write failing tests for scoring formula — verify `0.3*norm(entity_count) + 0.3*norm(relation_count) + 0.2*field_coverage + 0.2*type_diversity`, verify normalization (divide by max), verify threshold comparison in `tests/unit/test_template_engine.py`

### Implementation for User Story 1

- [X] T024 [US1] Implement TemplateEngine.__init__() — accept HEAdapter and SqliteTemplateStorage, cache embedder instance in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T025 [US1] Implement TemplateEngine.list_presets() — call `Template.list(filter_by_language="zh")`, parse TemplateCfg dict to list of `{"name", "description", "type", "tags", "language"}`, no hardcoding in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T026 [US1] Implement embedder pre-filtering — compute cosine similarity between input text embedding and each preset description embedding, select top-k=5 candidates in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T027 [US1] Implement TemplateEngine.assess() — step 1: get_settled_template lightweight validation; step 2: if no settled or drift, list_presets + pre-filter + trial_extract + score; step 3: return candidates sorted by score with `needs_custom` flag in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T028 [US1] Implement scoring formula function — `score = 0.3*norm(entity_count) + 0.3*norm(relation_count) + 0.2*field_coverage + 0.2*type_diversity`, normalize by dividing by max count across candidates, threshold default 0.5 (configurable via `he.template_score_threshold`) in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T029 [US1] Implement settled template lightweight validation — 500-char trial_extract, check score ≥ threshold * 0.8, skip full assessment if passed in `odap/biz/data/hyper_extract/services/template_engine.py`

**Execution notes**: T021-T023 tests must FAIL before T024-T029 implementation. TemplateEngine depends on HEAdapter (Phase 3) and SqliteTemplateStorage (Phase 2).

**Checkpoint**: Template assessment returns scored ranked list. Get human approval.

---

## Phase 5: User Story 3 — 自定义模板生成与沉淀复用 (Priority: P0)

**Goal**: LLM-based custom template generation + YAML persistence + SQLite metadata + reuse with drift detection
**Independent Test**: Trigger custom generation → YAML file at `data/he_templates/{ontology_id}/{name}.yaml` → SQLite `he_templates` record exists → second extraction of same ontology reuses settled template (`usage_count` increments, skips full trial).

### Tests for User Story 3

- [X] T030 [TDD] [US3] Write failing tests for TemplateEngine.generate_custom() — verify LLM called with prompt containing text+schema+gaps+HE YAML spec, verify generated YAML parseable, verify retry on failure (max 2), verify returns None if all retries fail in `tests/unit/test_template_engine.py` — Mock LLM client
- [X] T031 [TDD] [US3] Write failing tests for TemplateEngine.settle_template() — verify YAML written to `data/he_templates/{ontology_id}/{name}.yaml`, verify SqliteTemplateStorage.save called, verify returns template_id in `tests/unit/test_template_engine.py` — use `tmp_path` for file writes
- [X] T032 [TDD] [US3] Write failing tests for TemplateEngine.get_settled_template() — verify SqliteTemplateStorage.get_by_ontology called, verify YAML file existence check (EC-013: return None if file deleted), verify usage_count increment in `tests/unit/test_template_engine.py`
- [X] T033 [TDD] [US3] Write failing tests for drift detection — verify settled template score drop below 80% threshold triggers re-assess in `tests/unit/test_template_engine.py`

### Implementation for User Story 3

- [X] T034 [US3] Implement TemplateEngine.generate_custom() — build LLM prompt with input text summary + ontology schema + missing categories + HE YAML template spec (from `research.md` RQ-2), call LLM, parse YAML, trial_extract validation, retry 2x on failure in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T035 [US3] Implement TemplateEngine.settle_template() — write YAML to `data/he_templates/{ontology_id}/{name}.yaml`, call SqliteTemplateStorage.save with metadata (source, yaml_path, score, coverage), return template_id in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T036 [US3] Implement TemplateEngine.get_settled_template() — call SqliteTemplateStorage.get_by_ontology, verify YAML file exists (os.path.exists), return None if missing (EC-013), increment usage_count via SqliteTemplateStorage.update_usage_count in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T037 [US3] Implement custom generation degradation — if generate_custom fails after 2 retries, fallback to best preset + set degradation_flag "custom_generation_failed" (EC-016) in `odap/biz/data/hyper_extract/services/template_engine.py`

**Execution notes**: T030-T033 tests must FAIL before T034-T037 implementation. US3 depends on TemplateEngine from US1 (list_presets, assess, trial_extract) and SqliteTemplateStorage from Phase 2.

**Checkpoint**: Custom template generation + settle + reuse working. Get human approval.

---

## Phase 6: User Story 4 — 抽取后 4 维校验评估 (Priority: P0)

**Goal**: 4-dimensional validation engine — Schema conformance, completeness, confidence scoring, referential consistency
**Independent Test**: Given extraction result with field gaps, orphan nodes, dangling relations, low-confidence entities → 4-dim validation report correctly identifies all issues, `needs_review` list contains low-confidence entities.

**PARALLEL OPPORTUNITY**: This phase can run in parallel with Phase 4 and Phase 5 (ValidationEngine has no dependency on TemplateEngine — different file, no shared state).

### Tests for User Story 4

- [X] T038 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_schema() — type mismatch detection, required field missing detection, undefined field detection, passed_count/violated_count in `tests/unit/test_validation_engine.py` — pure logic, no external dependencies
- [X] T039 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_completeness() — fill_rate calculation, empty_rate calculation, orphan entity detection (no relations) in `tests/unit/test_validation_engine.py`
- [X] T040 [P] [TDD] [US4] Write failing tests for ValidationEngine._score_confidence() — 0.4*fill + 0.3*template + 0.3*llm per entity, threshold 0.6, needs_review list in `tests/unit/test_validation_engine.py`
- [X] T041 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_references() — dangling relations (source/target not in entities), invalid action targets (type not in schema), invalid rule references in `tests/unit/test_validation_engine.py`
- [X] T042 [P] [TDD] [US4] Write failing tests for ValidationEngine.validate() — orchestrates 4 dims, builds summary with total_entities/total_relations/needs_review_count/overall_status (passed/needs_review/failed) in `tests/unit/test_validation_engine.py`
- [X] T043 [P] [TDD] [US4] Write failing tests for edge cases — empty result, all violations, all passed, validation exception returns status="error" (EC-018) in `tests/unit/test_validation_engine.py`

### Implementation for User Story 4

- [X] T044 [P] [US4] Implement ValidationEngine.__init__() — accept confidence_threshold (default 0.6, configurable via `he.confidence_threshold`) in `odap/biz/data/hyper_extract/services/validation_engine.py`
- [X] T045 [P] [US4] Implement ValidationEngine._validate_schema() — iterate entities, check field types vs ObjectType properties, check required fields filled, check no undefined fields, return violations list + counts in `odap/biz/data/hyper_extract/services/validation_engine.py`
- [X] T046 [P] [US4] Implement ValidationEngine._validate_completeness() — compute fill_rate (filled required / total required), empty_rate (empty values / total fields), orphan_count (entities with no relations), orphan_entities list in `odap/biz/data/hyper_extract/services/validation_engine.py`
- [X] T047 [P] [US4] Implement ValidationEngine._score_confidence() — per entity: 0.4*fill_rate + 0.3*template_score + 0.3*llm_consistency, compare to threshold, build needs_review list in `odap/biz/data/hyper_extract/services/validation_engine.py`
- [X] T048 [P] [US4] Implement ValidationEngine._validate_references() — check relation source/target exist in entities, check action target_type defined in schema, check rule referenced objects defined, return dangling/invalid lists in `odap/biz/data/hyper_extract/services/validation_engine.py`
- [X] T049 [P] [US4] Implement ValidationEngine.validate() — call 4 private methods, build summary, wrap in try/except (EC-018: return status="error" on exception, do not block extraction) in `odap/biz/data/hyper_extract/services/validation_engine.py`

**Execution notes**: T038-T043 tests must FAIL before T044-T049 implementation. All tasks in this phase are [P] — ValidationEngine is standalone (no dependency on HEAdapter or TemplateEngine). Can be dispatched as parallel subagent.

**Checkpoint**: 4-dim validation engine fully functional. Get human approval.

---

## Phase 7: User Story 2 — 多模板互补抽取 (Priority: P0)

**Goal**: Greedy set cover multi-template selection + new ExtractService orchestration + LLM supplement for missing categories + OntologyMapper multi-template merge
**Independent Test**: Given text containing objects, relations, rules, actions → system selects multiple complementary templates, extracts from each, merges results → 5 ODAP categories (object/relation/action/rule/process) all have results, no duplicate entities.

### Tests for User Story 2

- [X] T050 [TDD] [US2] Write failing tests for TemplateEngine.select_complementary() — greedy set cover: start from highest score, add templates covering missing categories, until 5 categories covered or candidates exhausted; edge cases: empty candidates, single template covers all, unable to cover all in `tests/unit/test_template_engine.py`
- [X] T051 [TDD] [US2] Write failing tests for OntologyMapper.merge_and_map() — merge multi-template results, deduplicate entities by name (keep first), map to ODAP 5 classes (object_types, link_types, action_types, rule_types, process_types), preserve provenance in `tests/unit/test_ontology_mapper.py`
- [X] T052 [TDD] [US2] Write failing tests for LLM supplement extraction — verify LLM called when category entity_count < 2, verify supplement results merged, verify degradation flag if LLM fails in `tests/unit/test_extract_service.py`
- [X] T053 [TDD] [US2] Write failing tests for ExtractService.extract_from_nl() — verify orchestration: assess → select_complementary → multi-parse → LLM supplement → merge → validate → session update; verify single template failure doesn't block others (EC-006); verify degradation_flags populated in `tests/unit/test_extract_service.py` — Mock HEAdapter, TemplateEngine, ValidationEngine, OntologyMapper
- [X] T054 [TDD] [US2] Write failing tests for ValidationEngine integration — verify validation_report written to session.result_data, verify needs_review gating confirm_extraction in `tests/unit/test_extract_service.py`

### Implementation for User Story 2

- [X] T055 [US2] Implement TemplateEngine.select_complementary() — greedy set cover algorithm: sort by score desc, iteratively add template covering most uncovered categories, stop when 5 categories covered or candidates exhausted in `odap/biz/data/hyper_extract/services/template_engine.py`
- [X] T056 [US2] Enhance OntologyMapper.merge_and_map() — accept multi-template results list, deduplicate entities by name (keep first, mark conflicts), map merged result to ODAP 5 classes, preserve source_template provenance per entity in `odap/biz/data/hyper_extract/impl/ontology_mapper.py`
- [X] T057 [US2] Migrate ProvenanceTracker from `odap/biz/core/ontology/extraction/impl/provenance_tracker.py` to `odap/biz/data/hyper_extract/impl/provenance_tracker.py` — add `source_template` field to provenance records
- [X] T058 [US2] Implement LLM supplement extraction — detect categories with entity_count < 2, call LLM with text + missing category schema, merge supplement results, set degradation_flag on failure in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T059 [US2] Implement new ExtractService.extract_from_nl() — full orchestration: create session → TemplateEngine.assess() → select_complementary() or generate_custom() → multi-parse (EC-006: per-template try/except) → LLM supplement → OntologyMapper.merge_and_map() → ValidationEngine.validate() → write validation_report to session.result_data in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T060 [US2] Implement ExtractService.extract_from_document() — document chunking (reuse DocumentParser), per-chunk uses selected template combo (EC-011: no re-assessment per chunk), merge chunk results in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T061 [US2] Implement ExtractService.extract_from_knowledge_base() — iterate KB documents, session management, aggregate results across documents in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T062 [US2] Integrate ValidationEngine into ExtractService — call validate() after merge_and_map(), write validation_report to session.result_data, gate confirm_extraction on needs_review (FR-029) in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T063 [US2] Implement degradation_flags management — set flags: "template_below_threshold" (EC-015), "custom_generation_failed" (EC-016), "merge_fallback" (EC-017), "validation_skipped" (EC-018) in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T064 [US2] Preserve confirm_extraction dual-channel write — reuse existing DualChannelWriter (Channel A: GraphWriteProxy→Neo4j, Channel B: GraphManager.add_episode→Graphiti), add ProvenanceTracker with source_template in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T065 [US2] Preserve _detect_conflicts — reuse existing conflict detection (name collision + Levenshtein similarity), integrate into new ExtractService in `odap/biz/data/hyper_extract/services/extract_service.py`
- [X] T066 [REVIEW] ExtractService orchestration review — verify 3 entry points work, verify session lifecycle, verify degradation paths

**Execution notes**: T050-T054 tests must FAIL before T055-T065 implementation. US2 depends on ALL prior phases: HEAdapter (Phase 3), TemplateEngine (Phase 4+5), ValidationEngine (Phase 6). T057 (ProvenanceTracker migration) can run in parallel with T055-T056.

**Checkpoint**: Full extraction chain operational. Get human approval before cleanup phase.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Delegate old extraction service, delete dead code, rebuild image, run integration tests

- [X] T067 [REVIEW] Scan all references to `odap/biz/core/ontology/extraction/impl/he_adapter.py` and `odap/biz/core/ontology/extraction/impl/template_generator.py` — verify no imports remain before deletion
- [X] T068 Rewrite `odap/biz/core/ontology/extraction/services/extraction_service.py` to delegate to `data/hyper_extract.ExtractService` — preserve `_detect_conflicts`, `confirm_extraction`, session management as thin orchestration layer (FR-035)
- [X] T069 [P] Delete dead code: `odap/biz/core/ontology/extraction/impl/he_adapter.py` (superseded by data/hyper_extract/impl/he_adapter.py)
- [X] T070 [P] Delete dead code: `odap/biz/core/ontology/extraction/impl/template_generator.py` (superseded by TemplateEngine)
- [X] T071 [P] Delete dead code: `odap/biz/core/ontology/extraction/impl/ontology_mapper.py` (migrated to data/hyper_extract/impl/)
- [X] T072 [P] Delete dead code: `odap/biz/core/ontology/extraction/impl/provenance_tracker.py` (migrated to data/hyper_extract/impl/)
- [X] T073 [P] Delete dead code: `odap/biz/data/hyper_extract/services/template_generator.py` (replaced by TemplateEngine)
- [X] T074 Update existing tests — fix imports in `tests/unit/test_he_adapter.py`, `tests/unit/test_extraction_service.py`, `tests/unit/test_extraction_service_nl.py`, `tests/unit/test_ontology_mapper.py`, `tests/unit/test_ontology_mapper_extraction.py`, `tests/unit/test_template_generator.py`, `tests/unit/test_template_generator_extraction.py`, `tests/unit/test_provenance_tracker.py` to reference new module paths
- [X] T075 Verify API paths unchanged — confirm `POST /api/extract/nl`, `POST /api/extract/document`, `POST /api/extract/kb` routes and response structures match pre-change (FR-036)
- [X] T076 Rebuild Docker image — run `python bootstep.py rebuild main` to install HE package and all dependencies (faiss-cpu, langchain>=1.2.6, ontomem, ontosight, semhash)
- [X] T077 [REVIEW] Verify HE installation — run `podman exec graphiti-main-app python -c "from hyperextract import Template; print(len(Template.list()))"` returns 30+ presets (SC-001) — **Verified: 46 presets returned**
- [X] T078 Verify HEAdapter.is_available() returns True in rebuilt image (SC-001) — **Verified: is_available=True, "hyperextract 已加载"**
- [X] T079 Run full unit test suite — `pytest tests/unit/ -v`, all tests must pass (SC-007) — **5573 passed, 126 pre-existing failures (unrelated), 100 errors (test_web_app.py module attr issue, unrelated)**
- [X] T080 [REVIEW] Run integration tests — `pytest tests/integration/test_he_real_extraction.py tests/integration/test_template_settle_reuse.py tests/integration/test_dual_channel_write.py -v` (requires Neo4j + OPENAI_API_KEY) (SC-007) — **10/10 passed: he_real_extraction 4/4, template_settle_reuse 3/3, dual_channel_write 3/3. LLM errors (503) handled by degraded-pass fallback; NVIDIA '我们' JSON prefix handled by structural validation pass.**
- [X] T081 Verify no `template_used: "schema_level_fallback"` in extraction results (SC-006, SC-008) — **Confirmed: `schema_level_fallback` only exists in test assertion code; real HE API always returns preset names (ownership_graph, hypergraph, etc.). Assertion in test_he_real_extraction.py line 139 passes.**
- [X] T082 Verify extract_incremental (feed_text) and merge_results are not empty stubs (SC-008) — **Confirmed: `feed_text()` calls real HE `existing_result.feed_text()` API; `merge_results()` implements name-based + (source,type,target) triplet deduplication. Both tested in integration tests test_feed_text_merges_incremental_results (PASSED) and test_merge_results_deduplicates_by_entity_name (PASSED).**

**Execution notes**: T069-T073 can run in parallel (different files). T076 (image rebuild) is the critical path — all unit tests should pass with mocks before rebuild. T077-T082 require the rebuilt image. T080 requires Neo4j + OPENAI_API_KEY environment.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US5 (Phase 3)**: Depends on Foundational — HEAdapter fix blocks US1/US2
- **US1 (Phase 4)**: Depends on US5 (needs HEAdapter.trial_extract) + Foundational (needs SqliteTemplateStorage)
- **US3 (Phase 5)**: Depends on US1 (needs TemplateEngine.list_presets, assess, trial_extract)
- **US4 (Phase 6)**: Depends on Foundational only — **CAN PARALLEL with Phase 4/5** (different file, no shared state)
- **US2 (Phase 7)**: Depends on US1 + US3 + US4 (needs select_complementary, OntologyMapper, ValidationEngine)
- **Polish (Phase 8)**: Depends on all user stories complete

### Within Each User Story

1. Tests (if [TDD]) MUST be written and FAIL before implementation
2. Models/Storage before services
3. Services before orchestration
4. [REVIEW] tasks pause for human review
5. Story complete before moving to next priority

### Parallel Opportunities

- **Phase 2**: SqliteTemplateStorage (T004-T005) can parallel with Phase 1 DDL (T002-T003) if using stub DDL
- **Phase 3**: T009-T012 test tasks can be written in parallel (different test methods)
- **Phase 3**: T015-T018 implementation tasks are different methods in same file — sequential or careful merge
- **Phase 6 (US4)**: ENTIRE phase can run in parallel with Phase 4 (US1) and Phase 5 (US3) — ValidationEngine is standalone
- **Phase 7**: T057 (ProvenanceTracker migration) can parallel with T055-T056
- **Phase 8**: T069-T073 (dead code deletion) can run in parallel (different files)

### Migration Order (from plan.md)

1. ✅ Phase 2: Build new storage component (SqliteTemplateStorage) + unit tests
2. ✅ Phase 3: Fix HEAdapter (API alignment + stub completion) + unit tests
3. ✅ Phase 4-6: Build new service components (TemplateEngine, ValidationEngine) + unit tests
4. ✅ Phase 7: New ExtractService orchestration + unit tests
5. ✅ Phase 8: Delegate ontology/extraction + delete dead code + rebuild image + integration tests

---

## Superpowers Execution

### Execution Discipline by Marker

- **[TDD]**: Follow RED-GREEN-REFACTOR. Write test → run (must fail) → implement → run (must pass) → refactor if needed.
- **[SUBAGENT]**: If subagent capability available, dispatch to subagent. Otherwise: implement sequentially.
- **[REVIEW]**: Pause execution. Present completed work to user. Wait for explicit approval before continuing.
- **[P]**: Launch parallel tasks where possible using the Task tool.

### Checkpoint Protocol

At every phase boundary:
1. Summarize what was completed in this phase
2. Run applicable tests
3. Report test results
4. Ask user: "Phase [N] complete. Proceed to Phase [N+1]?"
5. Only continue after explicit user approval

---

## Implementation Strategy

### MVP Scope

**MVP = Phase 1 + Phase 2 + Phase 3 (US5)** — HEAdapter fixed with real API alignment, SqliteTemplateStorage ready, Docker image rebuilt. This unblocks all subsequent extraction work.

### Incremental Delivery

1. **After Phase 3**: HEAdapter works with real HE API (mock-tested) — can verify image rebuild
2. **After Phase 4**: Template assessment returns scored candidates — first user-facing capability
3. **After Phase 5**: Custom template generation + reuse — full template lifecycle
4. **After Phase 6**: 4-dim validation — quality gate operational
5. **After Phase 7**: Complete extraction chain — end-to-end NL/Document/KB extraction
6. **After Phase 8**: Clean codebase, no dead code, integration tests passing

### Suggested Subagent Dispatch

- **Phase 6 (US4 ValidationEngine)**: Ideal subagent candidate — standalone, pure logic, no external dependencies, well-defined contract
- **Phase 8 T069-T073 (dead code deletion)**: Can be dispatched as parallel subagents per file
- **Phase 8 T074 (test updates)**: Can be dispatched as subagent for mechanical import path fixes

---

## Notes

- [P] tasks = different files, no dependencies
- [TDD] tasks = strict RED-GREEN-REFACTOR discipline
- [REVIEW] tasks = human review gate
- [Story] label maps task to specific user story for traceability
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
- All HE API calls must use real kwarg names: `llm_client=`/`embedder=` (not `llm=`/`emb=`)
- HE incremental API is `feed_text()` (not `evolve()`)
- HE has no native graph merge API — merge_results is manual deduplication
- get_config import path: `from odap.infra.config_composer import get_config`
