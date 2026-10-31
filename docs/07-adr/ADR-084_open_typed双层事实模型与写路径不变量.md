---
id: odap.l7.adr-084-open-typed双层事实模型与写路径不变量
status: proposed
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

# ADR-084: open/typed 双层事实模型与写路径不变量（借鉴 utopia）

## Status
**提议（2026-10-04 提交，设计已获用户口头认可，实现按 P0→P1 分片推进中）**

> 触发来源：架构评审 [REVIEW_ONTOLOGY_PIPELINE_2026-10-03.md](../02-architecture/reports/REVIEW_ONTOLOGY_PIPELINE_2026-10-03.md)（对照 Jessica Talisman《The Ontology Pipeline》六阶段/九工序）+ 外部参照系 `deeplethe/utopia`（commit 8de3988，Apache-2.0，Rust+Postgres/pgvector/Tantivy）。
> 关联：F1/F2/F3/F7（评审发现编号）；ADR-077（SHACL/OWL 双轨）；ADR-082（语义候选抽取入口）；ADR-083（软删除语义）；AGENTS.md 规则 14（禁止未经评审的兜底逻辑）。
> 借鉴边界：仅借**设计模式**（open/typed 分层、写路径不变量、violation 队列、competency questions、治理只读人类先例），**不借技术栈**（不引入 Rust/PG/Tantivy），**不照搬** utopia 的 "types never gate" 与 "embedding 缺失静默降级 BM25"（后者违反 ODAP 规则 14）。

---

## Context

### 问题 1（F1）：摄入车道绕过治理，未定义类型自由落图

ODAP 存在**两条并行的图谱写入车道**，强制力度不一致：

- **治理车道**（semantic_admin）：候选 → 质量闸 3 门 16 子指标 → 两级审批 → writeback → USL/Graphiti。类型受 USL 受控词表约束。
- **摄入车道**（knowledge_base / perception）：文档抽取实体 → `_write_to_graph` → `GraphWriteProxy.add_entity` 直写 Neo4j，**不经任何类型治理**。

摄入车道的类型处理是硬编码降级：

```python
# apps/api/odap/biz/data/knowledge_base/services/knowledge_base_service.py:337-339
entity_type_id = etype.lower().replace(' ', '_')
if re.search(r'[\u4e00-\u9fff]', entity_type_id):
    entity_type_id = "zh_type"          # ← 所有中文类型塌缩进一个垃圾桶
```

后果：任何含中文类型名的抽取实体都被塞进 `zh_type` 桶节点直写图谱（`GraphWriteProxy.add_entity` 对 `entity_type` 零校验，见 `apps/api/odap/infra/query/graph_write_proxy.py:66-96`）。这既污染类型空间（`zh_type` 是无语义的黑洞桶），又让未受治理的类型**绕过 USL/候选/审批**直接进入决策所依赖的图谱——违反 Talisman「④叙词表/⑤本体阶段必须经协调与强制工序」的核心主张。

### 问题 2（F2）：质量闸占位子项以 1.0 计入 KPI，度量完整性失真

```python
# apps/api/odap/biz/semantic_admin/quality_gate/services/quality_evaluator.py:389-405
# G2.2 基数约束占位
g2_2 = _mk(submetric="g2_cardinality_constraint", score=1.0,
           reason="待 L5 基数归纳后复核（当前无候选基数）", ...)
# G2.3 is_a 无环占位
g2_3 = _mk(submetric="g2_isa_acyclic", score=1.0,
           reason="待 L3 分类层级草稿就绪后做拓扑排序（当前无层级）", ...)
```

`_gate2_subscores` 用 4 子项简单平均（:421-423）得出 `gate2_score`，其中 G2.2/G2.3 恒为占位 1.0、G2.4 LLM Judge 在未接入时也恒为 1.0（:407-419）。即**未真正评估的子项以满分参与均分**，抬高 gate2 与 total_score，使 dashboard/KPI 呈现虚假绿。OPA 侧同样是空占位（`quality_gate/services/policies/quality_gate.rego:171-175` `deny_gate2_2_cardinality contains msg if { false }`）。这是 Talisman「⑨度量工序必须可估算、诚实」的反例。

### 问题 3（F3）：USL 归一器未接入写入链

`UslTermResolver`（真身 `apps/api/odap/biz/semantic_admin/usl_manager/services/usl_term_resolver.py`，`entity_resolution.py` 仅包装）提供 `canonical_of(expr, domain_id) -> Optional[str]`（命中返回 canonical，未命中返回 `None`）。但生产代码只有**检索侧**用它（`biz/data/qa/retrieval/vector_retriever.py:23-28`），**写入链完全不归一**：摄入车道写进图谱的实体名/类型名从未经 USL 受控词表映射，导致同义词分裂（"老刘"/"刘先生"落两个节点）、检索侧归一与写入侧不归一不对称。

### 问题 4（F7）：SHACL 不持久化、不在写图路径

ADR-077 引入 SHACL/OWL 双轨治理，但形状校验未挂在任何写图路径上（摄入车道直写、治理车道 writeback 也不校验基数/签名），约束停留在文档层。

### 外部参照：utopia 如何解同类问题

utopia（同问题域、异栈异重心）用三个机制正面回应了 F1/F2/F7：

1. **open/typed 双层图**（`facts.layer` 列，migrations/0003；ADR-009/010）：抽取先进 `open` 层（诚实未知，predicate 可空），经采纳计数门（MIN_DOCS=2/MIN_SIGNALS=3，migrations/0018）与点头制（ADR-015）晋升到 `typed` 层。**"types guide and never gate"**（ADR-012）——类型引导而非硬拦截，未定义事实不丢、进 open 层可查。
2. **写路径不变量统一**：所有写图路径经同一 `judge_direction` + 签名公理（migrations/0019）校验，违规进 `axiom_violations` 队列（migrations/0012）四态出路（pending/accepted/rejected/deferred），公理变更时同事务重检（migrations/0093）。
3. **competency_questions**（migrations/0077；ADR-061）：以「本体应能回答的问题」作为可估算的度量锚，而非占位满分。

ODAP 已有 utopia 没有的优势（双时态 Graphiti、OPA 策略引擎、成熟审批飞轮），故本 ADR **只移植模式、不移植栈**。

---

## Decision

### D1. open/typed 双层事实模型（关 F1）

将图谱事实分为两层，替换 `zh_type` 垃圾桶：

- **typed 层**：类型已受 USL 治理（canonical 命中受控词表）的实体/关系。这是决策与检索依赖的权威投影，可由 open 层 + USL **重算**。
- **open 层**：类型未定义/未归一的抽取事实。**不自由落 typed 图**，而是显式暂存并转 candidate_store 候选队列，走既有治理车道（质量闸 → 审批 → writeback）。

**摄入车道不变量**：`_write_to_graph` 不得再产生 `zh_type` 桶节点。抽取实体按类型是否受治理二分：
- 受治理（ASCII 安全且经 USL 归一命中）→ 写 typed 层（`GraphWriteProxy.add_entity`）。
- 未治理（含中文/未命中 USL）→ **不写图**，转 candidate_store 建候选（`origin="llm"`、`source_type="ingest"` 的 pipeline run、`provenance` 标 `open_layer`/`unresolved_type`/`raw_type`），并 `logger.warning` 显式记录（规则 14：未定义必须显式，禁止静默塌缩）。

> 与 utopia 的差异（按车道 ADR 决策，不照搬 "never gate"）：ODAP 摄入车道对**未治理类型采取「暂存 + 转候选」而非「照写 open 层图」**。理由：ODAP 的 open 层载体已是 candidate_store（带 12 状态机 + 审批飞轮），比在图里再开一个 open layer 更省、且复用既有治理能力；typed 图保持「只含受治理事实」的强不变量，利于决策可信。

### D2. 度量诚实化：占位子项标 `not_evaluated` 并剔出均分（关 F2）

- `SubMetric` 增 `evaluated: bool`（默认 `True`）。未真正评估的子项（G2.2 基数、G2.3 is_a 无环、G2.4 LLM Judge 未接入时）标 `evaluated=False`，`reason` 前缀 `[未评估]`，**其 score 不计入 gate 均分**。
- `_gate2_subscores` 的均分改为「仅对 `evaluated=True` 的子项求平均」；分母为 0 时返回 0.0（不得回退满分）。
- API `SubMetricRow` 暴露 `evaluated` 字段，dashboard/报告据此显示占位标记（验收：响应含占位标记且均分不含占位项）。
- 真值实现（G2.2 基数归纳、G2.3 拓扑排序、G2.4 LLM Judge 接入）为后续独立分片；在未实现前，诚实标 `not_evaluated` 优于伪满分。
- OPA rego 占位规则保留 `if { false }`（永不 deny），但加注 `# not_evaluated: 待真值实现`，与 Python 侧语义对齐。

### D3. 写前 USL 归一 + `unresolved_term` 标记（关 F3）

- `_write_to_graph` 在分类前，对实体**类型名**尝试 USL 归一：经注入的 `UslTermResolver`（可脱离 Neo4j，用 `load_resolver_from_storage(domain_id)` 从 SQLite 构造）调 `canonical_of(type, domain_id)`。
- 命中 → 用 canonical 作为 typed 层类型；未命中（`None`）→ 归 open 层，`provenance.unresolved_term=True`。
- **不得静默降级**：resolver 不可用/无 domain 上下文时，视为「未归一」走 open 层并标记，而非假装归一成功（规则 14）。resolver 经构造函数可选注入，便于测试用真实 tmp_path USL 存储装配。

### D4. 写路径不变量收敛点（关 F7，方向性）

- 中期目标：所有写图路径（摄入车道 `GraphWriteProxy.add_entity`、治理车道 writeback、Graphiti episode）经**同一签名/形状校验点**（SHACL 形状持久化 + 挂写路径），违规进 violation 队列而非静默写入。
- 本 ADR 的分片先落 D1–D3（不改 GraphWriteProxy 契约）；D4 的 SHACL 持久化 + violation 队列为**后续 ADR/分片**，此处仅登记方向与验收口径，避免一次性大改。

### D5.（后续，登记不实现）competency questions 度量 + 治理只读人类先例

- competency_questions 作为语义完备度的可估算锚（替换部分占位 KPI）。
- 治理决策只读人类先例（utopia ADR-025）+ 二次 revert 熔断（0037）馈入 ODAP 审批飞轮。
- 二者不在本分片实现，登记为演进方向。

---

## 联动验收标准（沿用评审报告反向探针）

| 发现 | 验收标准（可测） |
|------|-----------------|
| F1 | 摄入含新类型（中文类型名）文档后，Neo4j **无新增 `zh_type` 节点**，且 candidate_store 出现对应候选（`origin=llm`、`provenance.open_layer=True`）。单测：`_partition_entities_by_type` 把中文类型实体归 open 层、ASCII 类型归 typed 层，且不产生 `zh_type`；`_stage_open_layer_entities` 用真实 tmp_path 候选库断言候选落库。 |
| F2 | 含 disjoint 命中（g2_1=0）的候选，其 `gate2_score == 0.0`（而非旧的 0.75）；G2.2/G2.3/G2.4 子项 `evaluated==False` 且不进均分；dashboard 响应含占位标记。 |
| F3 | 注入含术语的 resolver 后，命中类型走 typed 层用 canonical；未命中类型归 open 层且 `provenance.unresolved_term=True`。 |
| F7 | （后续分片）SHACL 形状持久化并挂写图路径，违规进 violation 队列。本分片不改 GraphWriteProxy 契约。 |

---

## Alternatives Considered

1. **照搬 utopia open 层入图（在 Neo4j 里开 `:OpenFact` 标签层）**：更贴近 utopia 原设计，但 ODAP 已有 candidate_store 承载「未治理事实 + 状态机 + 审批」，再开图层 open 层是重复建设，且弱化「typed 图只含受治理事实」的强不变量。**否决**。
2. **保留 zh_type 桶但加告警**：治标不治本，类型空间仍被污染，未定义类型仍绕过治理。**否决**（正是本 ADR 要消除的）。
3. **F2 直接实现 G2.2/G2.3 真值**：最彻底，但依赖 L5 基数归纳与 L3 拓扑排序，属独立大分片；先诚实标 `not_evaluated` 消除伪绿，真值随后补。**采纳分步**。
4. **照搬 utopia "types never gate"**：与其开放层哲学一致，但 ODAP 决策链依赖 typed 图可信度，摄入车道对未治理类型「暂存转候选」比「照写不拦」更契合 ODAP 治理重心。**部分否决**（按车道差异化决策）。

## Consequences

**正面**：
- 消除 `zh_type` 黑洞桶，typed 图成为「只含受治理事实」的可信投影，决策/检索可信度提升。
- KPI 去伪绿，度量诚实（Talisman ⑨工序）。
- 摄入车道与治理车道强制力度收敛（未治理事实统一进候选飞轮）。
- 写前归一减少同义词分裂，检索侧与写入侧对称。

**负面/成本**：
- 摄入车道新增对 candidate_store 的跨子域依赖（`biz.data.knowledge_base → biz.semantic_admin.candidate_store`）。经核实 import-linter 无契约禁止 biz 子域互引（已有先例 `biz.data.qa → biz.semantic_admin.usl_manager`），合法；但需在 DOC_SYNC_CHECKLIST 记录该依赖边。
- 含大量新类型的文档摄入会产生较多候选，增加审批负载（可后续用采纳计数门/点头制批量晋升缓解，见 D5）。
- gate2 均分口径变更会使历史 KPI 与新版不可直接比较，dashboard 需标注口径版本。

**中性**：
- 本分片不改 `GraphWriteProxy` 契约、不引入新存储表（复用 candidate_store + pipeline_runs）；D4/D5 留待后续 ADR。

---

## 实现分片

| 分片 | 范围 | 优先级 | 状态 |
|------|------|:--:|------|
| S1 | F2 度量诚实化（quality_evaluator `_gate2_subscores` + SubMetric.evaluated + rego 注记 + 单测） | P0 | 本轮落地 |
| S2 | F1 open 层暂存（`_partition_entities_by_type` + `_stage_open_layer_entities` 转候选，消除 zh_type） | P0 | 本轮落地 |
| S3 | F3 写前 USL 归一 + unresolved_term 标记（resolver 可选注入） | P1 | 本轮落地 |
| S4 | F7 SHACL 形状持久化 + 挂写图路径 + violation 队列 | P1 | 后续独立 ADR |
| S5 | D5 competency questions 度量 + 治理只读人类先例/熔断 | P2 | 后续独立 ADR |

> 测试遵循 AGENTS.md 规则 9（新增/改动模块补真实 tmp_path SQLite 测试，禁 MagicMock 模拟 DB）、规则 14（失败显式、禁静默降级、测试执行真实函数体）。
