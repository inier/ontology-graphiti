---
id: odap.l7.adr-094-ontology-constraint-orchestration
status: active
owner: architect
version: ''
layer: L7
concern: adr
lifecycle: frozen
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
---

# ADR-094: 本体约束编排层（六步管线）选型

## Status

**已接受（2026-10-17）**。本轮在 `biz/core/ontology` 下新增「本体约束编排层」，作为端到端问答的核心编排能力。

---

## Background

用户核心需求：输入与输出**均受本体规则约束**（TBox 约束 + 公理 + 规则）；结果正确、完整、**可溯源**；后续执行给建议方案（Action/HITL）。

**现状（文件:行证据）**：

- 语义检索服务总线已存在：`apps/api/odap/biz/core/ontology/semantic_retrieval/`（`impl/{chain,nl,mdl,graph,metric}_engine.py` + `unified_router.py` + `hybrid_orchestrator.py`）。
- 规则侧基础设施已存在：OPA `.rego`（`infra/opa/policies/*.rego` 16+ 文件）、SHACL 形状（`semantic_admin/shacl_store`，ADR-085）、公理引擎（ADR-075/077）。
- 概念缺口回路已存在：`semantic_admin/gap_pool`（ADR-086）。
- **缺口**：上述能力分散，**无统一编排**把「意图 → 映射 → 校验 → 检索 → 生成 → 输出校验」串成一条受本体约束的管线，也无跨步 provenance。

**约束**：不新造 DSL（复用 HE YAML 与 UModel 语法，`CONTEXT.md:20`）；不新增存储引擎（复用 Neo4j/SQLite/OPA）。

---

## Decision

新增 `apps/api/odap/biz/core/ontology/orchestration/` 子包，实现**六步约束管线**（详见架构 v2 §2）：

1. `IntentRouter` → `OntologyAligner` → `RuleGuard` → `RetrievalExecutor` → `AnswerComposer` → `OutputContractGate`。
2. 每步定义为 Protocol（插槽），实现可替换；编排只依赖 Protocol。
3. **输入侧约束**：槽位必须落 TBox，映射不到进 `gap_pool`（缺口回路），禁止 LLM 幻觉补全后执行。
4. **输出侧约束**：`OutputContractGate` 用 SHACL 形状校验结构化输出，违约阻断/标注。
5. **规则校验**：`RuleGuard` 用 OPA evaluate；OPA 不可用则 **fail-closed**（仅放行只读并标 `degraded=true`）。
6. **溯源**：每步产出 `Prov`，聚合为 `Provenance`（`trace_id/steps/evidence/tbox_version/contract_ok`），落库并经 `GET /ontology/qa/{trace_id}/provenance` 暴露；新增 `scripts/verify_provenance.py` 做机械校验。
7. **降级链**：检索引擎失败走 `unified_router` 降级链并记 `degraded_engines[]`；证据不足返回 `no_answer` 不编造。
8. **暴露面**：经 `ontology.public` 门面暴露，遵守 C3 契约。

**选型理由**：复用既有检索总线/OPA/SHACL/gap_pool，仅新增「编排」这一缺失环节，符合增量重构；Protocol 化保证可组合性。

**备份方案**：若编排层与既有 `unified_retrieve.py` 职责重叠引发争议，可先合并为单一服务，再按 Protocol 拆出。

---

## Consequences

**正面**：
- 端到端问答统一受本体约束，可溯源、可机械校验。
- 六步均可替换（换 LLM/检索后端不改编排），可组合性强。
- 复用既有资产，最小新增。

**负面**：
- 编排层横跨检索、OPA、SHACL、gap_pool，集成复杂，须严格 Protocol 边界。
- Fail-closed 策略在 OPA 故障时会拒绝高风险动作，影响可用性（以安全换可用）。
- provenance 全量落库增加存储与性能开销，须设采样/保留策略。

---

## Related ADRs

- ADR-075（确定性推理引擎引入）
- ADR-077（SHACL/OWL 本体治理）
- ADR-080（ontology 门面封装与分层契约）
- ADR-081（infra 依赖倒置 provider 注册表）
- ADR-085（SHACL 形状持久化与写路径校验不变量）
- ADR-086（概念缺口回路）
- ADR-095（意图识别方案）
