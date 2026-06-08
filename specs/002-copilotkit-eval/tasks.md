---
description: "Tasks list for AG-UI + OpenHarness pure-extension integration"
---

# Tasks: AG-UI ↔ OpenHarness 纯扩展集成（v2.0）

**Input**: Design documents from `specs/002-copilotkit-eval/`
**Prerequisites**: plan.md (v2.0 — 纯扩展架构), spec.md (3 user stories), data-model.md, contracts/*
**Architecture Invariant**: **0 修改** `openharness/**` · **0 新增** `odap/biz/core/qa/**` · **0 新表**

---

## Task Format

```
[ID] [markers] [Story] Description
```

**Markers**:
- **[P]**: Can run in parallel (different files, no dependencies)
- **[TDD]**: RED-GREEN-REFACTOR (write test → fail → implement → pass → refactor)
- **[REVIEW]**: Pause for human review before next task
- **[SUBAGENT]**: Delegate to subagent for parallel execution

**Story labels**: `[US1]` architect decision · `[US2]` frontend dev work · `[US3]` product user value

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Validate v2.0 architecture decisions and prepare workspace

- [ ] T001 [REVIEW] Read openharness stream_events.py + query_engine.py + hooks/events.py + permissions/checker.py to confirm 0-modification invariant (no file edits)
- [ ] T002 [REVIEW] Validate v2.0 plan.md architecture: 0 modifications to OpenHarness, 0 new biz module, 0 new SQLite table
- [ ] T003 [P] Create directory `odap/infra/openharness/agui/` (extension point, not biz module)
- [ ] T004 [P] Verify AG-UI Python SDK availability in `requirements.txt` — if missing add `ag-ui-protocol>=0.1.0` (informational only; Phase 2 will use FastAPI direct encoding)

**Execution notes**: This phase is validation only. No code changes. Stop and confirm with human before proceeding to implementation.

**Checkpoint**: Architecture invariant validated. Get human approval before Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pydantic models + Pydantic AG-UI event mirror (required by all user stories)

**CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T005 [P] Create Pydantic models in `odap/infra/openharness/agui/agui_models.py`: `AGUIEventBase`, `RunStartedEvent`, `RunFinishedEvent`, `RunErrorEvent`, `StepStartedEvent`, `StepFinishedEvent`, `TextMessageStartEvent`, `TextMessageContentEvent`, `TextMessageEndEvent`, `ToolCallStartEvent`, `ToolCallArgsEvent`, `ToolCallEndEvent`, `ToolCallResultEvent`, `StateSnapshotEvent`, `StateDeltaEvent`, `MessagesSnapshotEvent` (16 classes)
- [ ] T006 [P] Create request/response models in same file: `RunAgentInput`, `ResumeEntry`, `ResumeStatus` (str, Enum), `Interrupt` (Pydantic), `InterruptReason` (str, Enum)
- [ ] T007 [P] Add unit test scaffold `tests/unit/test_agui_models.py` with imports + enum validation (run, must pass)
- [ ] T008 [REVIEW] Verify Pydantic models conform to AG-UI v0.x spec (https://docs.ag-ui.com/concepts/events) — pause for human review

**Execution notes**: Pure data modeling. No business logic. All containers use `Field(default_factory=...)` (AGENTS.md 规则 5). All enums use `(str, Enum)` (规则 4).

**Checkpoint**: Models validated against AG-UI spec. Get human approval before Phase 3.

---

## Phase 3: User Story 1 - 架构师快速判断集成价值 (Priority: P1) MVP

**Goal**: 决策文档齐全，架构师能在 1 次会议内做出"采纳/部分采纳/拒绝"决议
**Independent Test**: 阅读 spec.md + research.md + plan.md 决策矩阵，能独立得出结论

### Decision Artifacts (already complete in v2.0)

- [ ] T009 [P] [US1] spec.md — 评估 spec（CopilotKit 加权 3.06 分 → 部分采纳修订为"不集成 CopilotKit 包 + 对接 AG-UI 标准协议"）
- [ ] T010 [P] [US1] research.md — Phase 0 协议选型（AG-UI 加权 4.3 vs OAUIP 1.9 vs SSE 扩展 2.4）
- [ ] T011 [P] [US1] plan.md — 实施计划 v2.0（**纯扩展架构**：0 修改 OpenHarness、0 翻译层、0 新表、0 独立业务模块）
- [ ] T012 [P] [US1] data-model.md — 数据模型（0 新表，复用 qa_sessions/qa_messages）
- [ ] T013 [P] [US1] contracts/ag-ui-bridge.md — 事件映射契约（OpenHarness 7 类 StreamEvent ↔ AG-UI 17 类 Event 完整映射表）
- [ ] T014 [P] [US1] contracts/hitl-flow.md — HITL 流程契约（5 个时序图：confirmation/input_required/cancellation/timeout/并发）
- [ ] T015 [P] [US1] contracts/generative-ui-card.md — 卡片注册契约（7 类内置卡片：chart/graph/temporal/report_link/action/confirm/input）

**Execution notes**: US1 is **document deliverable**, not code. All tasks already complete from v2.0 architecture work. Verification = decision documents exist and are coherent.

**Checkpoint**: US1 decision artifacts complete. Architect can make decision based on this evidence. **MVP scope ends here.**

---

## Phase 4: User Story 2 - 前端开发识别"集成需要改什么" + 后端扩展 (Priority: P2)

**Goal**: Backend 5 个文件落地，前端 2 个文件落地，全部在 OpenHarness 之上扩展
**Independent Test**: `curl POST /api/ag-ui/run` 返回 AG-UI SSE 事件流，OpenHarness 源码 0 修改

### Tests for User Story 2 (TDD)

> Write these tests FIRST. Verify they FAIL before implementation.

- [ ] T016 [P] [TDD] [US2] Transport unit test in `tests/unit/test_agui_transport.py`: 7 cases (AssistantTextDelta → TextMessageContent, ToolExecutionStarted → 3-piece, ToolExecutionCompleted → TOOL_CALL_RESULT, ErrorEvent → RunError, StatusEvent → StepStarted, CompactProgressEvent → StateDelta, run lifecycle events)
- [ ] T017 [P] [TDD] [US2] Handler unit test in `tests/unit/test_agui_handler.py`: 4 cases (new run emits RunStarted+success, ask_user_question triggers RunFinished.interrupts, permission_prompt triggers tool_call reason, resume resolves future)
- [ ] T018 [P] [TDD] [US2] Pydantic serialization test in `tests/unit/test_agui_models.py`: verify AG-UI event JSON schema matches spec (camelCase fields, outcome.interrupts structure)

### Backend Implementation for User Story 2

- [ ] T019 [P] [US2] StreamEvent 派生扩展 in `odap/infra/openharness/agui/agui_extensions.py`: 6 new dataclasses inheriting `openharness.engine.stream_events.StreamEvent` (RunStartedEvent, RunFinishedEvent, StepFinishedEvent, TextMessageStartEvent, TextMessageEndEvent, MessagesSnapshotEvent, StateSnapshotEvent) — **0 修改 OpenHarness 源文件**
- [ ] T020 [US2] Transport layer in `odap/infra/openharness/agui/agui_transport.py`: `to_agui_event()` function with 13 isinstance branches (depends on T019)
- [ ] T021 [US2] Run agent handler in `odap/infra/openharness/agui/agui_handler.py`: `run_agent()` FastAPI endpoint with SSE response (depends on T020, T005)
- [ ] T022 [US2] HITL callback injection in same file: `_create_agui_ask_user_callback()` wraps OpenHarness `ask_user_prompt` → emit `RunFinished.interrupts[reason="confirmation"]` (depends on T021)
- [ ] T023 [US2] Permission callback injection in same file: `_create_agui_permission_callback()` wraps OpenHarness `permission_prompt` → emit `RunFinished.interrupts[reason="tool_call"]` (depends on T021)
- [ ] T024 [US2] Resume handler in same file: `_handle_resume()` resolves pending `ask_user_prompt` future from `RunAgentInput.resume[]` (depends on T021)
- [ ] T025 [US2] Append method `create_agui_session()` to `odap/infra/openharness/v2_adapter.py` (zero-touch to existing methods) — wires QueryEngine with AG-UI callbacks (depends on T022, T023, T024)
- [ ] T026 [US2] Register router in `odap/web/app.py`: add `from odap.infra.openharness.agui.agui_handler import agui_router` + `app.include_router(agui_router)` (depends on T021)
- [ ] T027 [P] [US2] Add OPA policy file `odap/infra/opa/policies/ag_ui_run.rego`: allow `ag_ui:run` action when user has workspace role (depends on T026)
- [ ] T028 [TDD] [US2] Run `pytest tests/unit/test_agui_transport.py tests/unit/test_agui_handler.py tests/unit/test_agui_models.py -v` — all tests must pass (depends on T016-T028)

### Frontend Implementation for User Story 2

- [ ] T029 [P] [US2] Add `@ag-ui/core` to `frontend/package.json` dependencies (NOT `@copilotkit/*`) — size budget < 5KB gzip
- [ ] T030 [P] [TDD] [US2] Frontend types test in `frontend/src/modules/qa/agui/__tests__/agui_types.test.ts`: verify AG-UI event types match server contract
- [ ] T031 [US2] SSE client provider in `frontend/src/modules/qa/providers/AGUIProvider.tsx`: `EventSource` wrapper + `runAgent(input)` function + auto-reconnect (~80 lines)
- [ ] T032 [US2] React hook in `frontend/src/modules/qa/hooks/useAGUI.ts`: `useAGUI()` returns `{ events, isRunning, resume, cancel }` (~60 lines) (depends on T031)
- [ ] T033 [P] [TDD] [US2] Frontend unit test `frontend/src/modules/qa/agui/__tests__/useAGUI.test.tsx`: 4 cases (initial state, event accumulation, resume on interrupt, error handling)
- [ ] T034 [US2] Wire `AGUIProvider` into existing `QAPanel` in `frontend/src/modules/qa/components/QAChatPage.tsx` (zero breaking change to existing flow — wraps but doesn't replace)

**Execution notes**:
- T019 must precede T020 (transport depends on dataclasses)
- T020-T024 can run in sequence but T026-T027 can parallel after T025
- T029-T030 can run in parallel with T022-T024
- Verify invariant after T019: `git diff openharness/ --stat` should show 0 changes

**Checkpoint**: US2 implementation complete. Backend has AG-UI endpoint at `POST /api/ag-ui/run`. Frontend has `useAGUI()` hook. All unit tests pass.

---

## Phase 5: User Story 3 - 产品经理理解"用户可感知的新能力" (Priority: P3)

**Goal**: 3 大可演示能力（Generative UI / HITL / Shared State）
**Independent Test**: 演示页面 `/qa/copilot` 展示 3 大能力 + 工作空间隔离

### Generative UI 演示 (卡片渲染)

- [ ] T035 [P] [US3] Create `frontend/src/modules/qa/cards/registry.ts` (already exists per plan, verify 7 cards registered: chart/graph/temporal/report_link/action/confirm/input)
- [ ] T036 [P] [US3] Create `frontend/src/modules/qa/components/GenerativeMessageBubble.tsx` — 解析 `TOOL_CALL_RESULT.content` JSON，渲染 card 或降级 Alert
- [ ] T037 [P] [TDD] [US3] Test `frontend/src/modules/qa/cards/__tests__/registry.test.ts`: verify 7 cards registered + unknown card_type fallback
- [ ] T038 [US3] Wire `GenerativeMessageBubble` into `QAChatPage` (depends on T031, T036)

### HITL 演示 (AskUserQuestion)

- [ ] T039 [P] [US3] Create `ConfirmCard` component in `frontend/src/modules/qa/cards/ConfirmCard.tsx` (yes/no buttons) (depends on T036)
- [ ] T040 [P] [US3] Create `InputCard` component in `frontend/src/modules/qa/cards/InputCard.tsx` (text/select/multiselect) (depends on T036)
- [ ] T041 [US3] Create `HITLPanel` in `frontend/src/modules/qa/components/HITLPanel.tsx` — 监听 `RunFinished.interrupts`，渲染对应 card，点击触发 `resume()` (depends on T039, T040, T032)

### Shared State 演示 (Memory 快照)

- [ ] T042 [P] [US3] Backend memory snapshot in `agui_handler.py`: emit `StateSnapshot` at run start with `{memory: {facts: [...]}, active_skills: [...], recent_sessions: [...]}` from OpenHarness `engine.memory` and `engine.skills` (depends on T025)
- [ ] T043 [P] [US3] Frontend memory viewer in `frontend/src/modules/qa/components/StatePanel.tsx` — 渲染 `StateSnapshot.snapshot.memory.facts` (depends on T032)

### 工作空间隔离演示 (Acceptance)

- [ ] T044 [P] [TDD] [US3] E2E test `tests/e2e/test_ag_ui_ws_isolation.py`: 2 users in 2 workspaces, verify no cross-tenant event leak (OPA-enforced)
- [ ] T045 [US3] Demo page `frontend/src/modules/qa/pages/QACopilotDemoPage.tsx` at route `/qa/copilot` — 集成 GenerativeMessageBubble + HITLPanel + StatePanel (depends on T038, T041, T043)

**Execution notes**:
- T039-T040 can run in parallel (different files)
- T044 is acceptance gate — must pass before MVP can be demonstrated

**Checkpoint**: US3 demoable at `/qa/copilot`. 3 capabilities visible. Workspace isolation verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end verification + performance + documentation

- [ ] T046 [P] [SUBAGENT] Documentation update: add "AG-UI 集成" 章节 to `docs/03-modules/qa_engine/DESIGN.md`
- [ ] T047 [P] [SUBAGENT] Update `specs/002-copilotkit-eval/quickstart.md` for v2.0 architecture (replace OAUIP commands with AG-UI commands; new file paths under `odap/infra/openharness/agui/`)
- [ ] T048 [SUBAGENT] Performance benchmark: SSE TTFB < 200ms (P95) — measure with `time curl -N -X POST /api/ag-ui/run` over 100 runs
- [ ] T049 [REVIEW] Security review: verify OPA policy enforces workspace_id on all AG-UI endpoints (T027), JWT auth required, no PII leakage in events
- [ ] T050 [P] [TDD] E2E test: `tests/e2e/test_ag_ui_full_flow.py` — full journey (ask → tool_call → AG-UI stream → HITL confirm → tool_call_result → done) for the 3 capability areas
- [ ] T051 [P] [SUBAGENT] Code cleanup: remove dead code paths, add docstrings to new functions, verify all new files have `__init__.py` exports per AGENTS.md 规则
- [ ] T052 Run full test suite: `pytest tests/unit/ tests/integration/ -v` + `cd frontend && npm test` — all tests must pass
- [ ] T053 [REVIEW] Final architecture audit: `git diff openharness/ --stat` returns 0; `ls odap/biz/core/qa/` returns NotFound; `git log odap/infra/openharness/agui/ --stat` shows 3 new files + 1 modified (v2_adapter.py append-only)

**Execution notes**:
- T046, T047, T048, T051 can run in parallel
- T049, T053 are mandatory review gates
- T052 is final acceptance

**Checkpoint**: All phases complete. AG-UI + OpenHarness integrated via pure extension. v2.0 architecture invariants preserved.

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup) ──► Phase 2 (Foundational) ──► Phase 3 (US1) ──► Phase 4 (US2) ──► Phase 5 (US3) ──► Phase 6 (Polish)
   validation          models                [MVP: stop       backend+frontend    demos+ws          verify+doc
                                                  here]        5 days              isolation
```

- **Phase 1 → 2**: Pydantic models require understanding of OpenHarness events (T001)
- **Phase 2 → 3**: US1 doc artifacts reference the model names from T005-T006
- **Phase 3 → 4**: US2 implementation uses the same `RunAgentInput` schema defined in US1 artifacts
- **Phase 4 → 5**: US3 frontend cards consume `TOOL_CALL_RESULT` events emitted by US2 transport
- **Phase 5 → 6**: E2E tests need all 3 capabilities working

### Within User Story 2 (Phase 4)

1. **T016-T018 (tests)** MUST be written and FAIL before T019-T024 (implementation) — TDD discipline
2. **T019 (extensions)** before T020 (transport) — transport imports extensions
3. **T020 (transport)** before T021-T024 (handler) — handler uses transport
4. **T025 (v2_adapter)** after T022-T024 — adapter wires callbacks
5. **T026-T027 (routes/OPA)** after T021 — routes depend on handler
6. **T029-T033 (frontend)** can parallel with T022-T024 — independent stack
7. **T034 (wire)** after T031-T033 — wires frontend to existing QAPanel

### Within User Story 3 (Phase 5)

- **T035-T038 (Generative UI)** independent of T039-T041 (HITL) — parallel
- **T042-T043 (Shared State)** independent of T039-T041 — parallel
- **T044 (E2E isolation test)** can run anytime after T027 (OPA policy) — partial parallel
- **T045 (demo page)** after T038, T041, T043 — wires all 3 capabilities

### Parallel Opportunities

- All tasks marked **[P]** within same phase can run in parallel
- All tasks marked **[SUBAGENT]** can be dispatched to subagents
- T019-T020 sequential; T021-T024 sequential; **T025-T028 can parallel with T029-T033**
- T035-T037 (Generative UI group) can parallel with T039-T041 (HITL group) and T042-T043 (State group)

### Cross-Story Parallelism (subagent strategy)

```
Subagent A: T019-T026 (backend core)            [2.5 days]
Subagent B: T029-T034 (frontend core)           [1 day]
Subagent C: T035-T045 (US3 demos) [P-tagged]    [1.5 days] — starts after A and B
```

---

## Implementation Strategy

### MVP Scope (Suggested)

**Phase 1 + Phase 2 + Phase 3 + Phase 4 minimal**:
- T001-T015 (decision artifacts + model scaffolds) — **0.5 day**
- T016-T018 (TDD test scaffolds) — **0.5 day**
- T019-T024 (backend core) — **1.5 days**
- T025-T028 (adapter + route + OPA) — **0.5 day**
- T029-T034 (frontend minimal hook + QAPanel wire) — **0.5 day**

**MVP Total: 3.5 days** — Architect decision + minimal end-to-end AG-UI flow working

### Incremental Delivery (recommended for v2.0)

| Day | Phase | Deliverable |
|-----|-------|------------|
| 1 | Phase 1-3 | Architect decision documents complete |
| 2 | Phase 4 (backend) | AG-UI endpoint at `/api/ag-ui/run`, transport + handler working |
| 3 | Phase 4 (frontend) | `useAGUI` hook wired into QAPanel, basic chat working |
| 4 | Phase 5 | Demo page with 3 capabilities visible |
| 5 | Phase 6 | Tests, docs, performance verified, architecture audit passed |

### Architecture Invariants (MUST be verified at each phase)

1. **0 modifications** to `openharness/src/openharness/**`
2. **0 new** `odap/biz/core/qa/**` module
3. **0 new** SQLite table
4. **0 modification** to existing OpenHarness `StreamEvent` base class
5. Reuse: `ask_user_prompt` + `permission_prompt` + `HookExecutor` + `Memory` + `ConversationMessage`

Run `git diff openharness/ --stat` and `ls odap/biz/core/qa/ 2>/dev/null || echo "OK: no qa/ module"` after each phase to verify.

---

## Notes

- All tasks follow checklist format: `- [ ] [ID] [markers] [Story] Description`
- **[P] tasks** = different files, no dependencies
- **[TDD] tasks** = RED-GREEN-REFACTOR discipline (test fails first)
- **[REVIEW] tasks** = human review gate before proceeding
- **[SUBAGENT] tasks** = candidate for parallel subagent dispatch
- **[Story] label** = US1/US2/US3 traceability to spec.md
- Commit after each task or logical group (atomic commits)
- Stop at each CHECKPOINT to validate independently with user
- v1.0 tasks (translation layer + independent biz module) are **OBSOLETE** — do not execute

---

**Version**: 2.0 (FINAL) | **Date**: 2026-06-08 | **MVP**: 3.5 days | **Full**: 5 days
