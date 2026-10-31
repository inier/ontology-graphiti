---
id: odap.l7.adr-085-shacl形状持久化与写路径校验不变量
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
governance_reason: 状态段声明部分落地，已在生效
---

# ADR-085: SHACL 形状持久化与写路径校验不变量（关 F7 / ADR-084 切片 S4）

## Status
**部分落地（2026-10-04）：S4a + S4c 已以 TDD 实现并验收通过（F7-a/b/c/f 测试绿、import-linter C1–C4 全 KEPT、ruff 新文件干净）；S4b（observe 模式写路径校验 + `sa_axiom_violation` 队列）与 S4d（enforce + 旁路收敛 + ADR-077 修订）暂缓，须获批/单独评审后落地。**

> 原提议（2026-10-04 提交，承接 ADR-084 D4 登记的方向与验收口径，作为其「后续独立 ADR」落地设计）

> 触发来源：架构评审 [REVIEW_ONTOLOGY_PIPELINE_2026-10-03.md](../02-architecture/reports/REVIEW_ONTOLOGY_PIPELINE_2026-10-03.md) 发现 **F7**——ADR-077 引入的 SHACL/OWL 双轨治理「形状校验未挂在任何写图路径上，约束停留在文档层」。
> 关联：ADR-084（open/typed 双层 + 写路径不变量，本 ADR 实现其 D4/S4）；ADR-077（SHACL/OWL 双轨，本 ADR 操作化其裁决 1 的「版本键控缓存」许可并扩展裁决 3 的校验入口）；ADR-061（质量闸）；ADR-082（语义候选抽取入口）；ADR-083（软删除语义）；AGENTS.md 规则 8（SQLite 无连接池）/ 规则 9（真实 tmp_path 测试）/ 规则 14（禁止未经评审的兜底逻辑）。
> 借鉴边界：沿用 ADR-084 的 utopia 借鉴边界——借**模式**（axiom_violations 队列、写路径不变量），**不借栈**（不引入 Rust/PG/Tantivy），**不照搬** "types never gate"（ODAP 保留 enforce 门为可达终态，observe-first 只是灰度策略）。

---

## Context

### 现状（证据见 ADR-084 评审 + 本轮代码勘验）

1. **SHACL 校验代码真实且已测，但无写路径调用方**。`biz/core/ontology/design/engine/shacl/`：
   - `shape_generator.py::ShapeGenerator.generate()` 从 ontology 类型定义生成 Turtle NodeShape（映射表 `DATA_TYPE_XSD`、`CARDINALITY_BOUNDS = {"1:1":(1,1),"1:N":(1,None),"N:1":(0,1),"N:N":(0,None)}`）。
   - `validator.py::SHACLValidator.validate(entity_types, instances)` 生成形状 → rdflib 建实例图 → `pyshacl.validate` → 结构化报告 `{conforms, results[], shape_count, instance_count, violation_count}`；rdflib/pyshacl 缺失时 `raise RuntimeError`（不静默放行）。
   - 依赖 `pySHACL>=0.25 / owlready2>=0.46 / rdflib>=7.0` 已在 `apps/api/pyproject.toml` 且已安装。
   - **唯一消费方是 2 个 HTTP 端点**（`POST /api/ontology/shacl/validate`、`GET /api/ontology/shacl/shapes`）与单测。`grep SHACLValidator` 在任一写图路径**零命中**——F7 成立。

2. **形状不持久化**。ADR-077 裁决 1 明确「派生**不持久化**——每次按需实时生成，杜绝陈旧副本」，但同时允许「任何缓存（如有）必须带 **Schema 版本号失效键**」。当前无任何 `.ttl`/表/rego 形态的持久化形状。

3. **写路径无统一校验，且 chokepoint 不密闭**：
   - `infra/query/graph_write_proxy.py::GraphWriteProxy` 是 biz 模块的**意图性单一写入口**（约 15 处 biz 调用），但 `add_entity(entity_id, entity_type, properties, workspace_id="")` **对 entity_type 零语义校验**（仅 `_log_write` 审计文本 + 错误包装）；`get_raw_graph_manager()` 已是 `NotImplementedError` 墓碑（项目对逃生口的态度）。
   - **3 个 infra 级写方旁路 proxy**：`infra/security/audit_graphiti_channel.py`、`infra/storage/scenario_store.py`、`biz/data/hyper_extract/impl/dual_channel_writer.py` 的 Channel B（直调 `GraphManager`）。
   - **Graphiti episode 车道**（`GraphManager.add_episode` 的 LLM 抽取）产出的图内容在 proxy 层校验**看不见**（事实在调用后由 Graphiti 内部涌现）。
   - **上下文缺失硬约束**：`add_entity` 只有 `workspace_id`，**没有 ontology_id/domain_id**，无法在通用 proxy 层定位「该实体类型对应哪套形状」。

4. **约束定义已持久化，公理却被丢弃**：
   - `usl_disjoint_pairs(id, domain_id, term_a, term_b, reason)`、`usl_cardinalities(id, domain_id, rel_name, domain_term, range_term, min_card, max_card)` 已是 SQLite 真表 + 全 CRUD/API（`usl_manager`）。
   - `ol_pipeline/impl/l6_axiom_deriver.py::AxiomDeriver.derive()` 产出 `sub_class_of / disjoint_classes / object_property_domain|range / object_property_cardinality / data_property_cardinality` 公理，但 `pipeline_service.py` **只把计数写进 run stats**（`l6_axiom_total`、`l6_axioms_by_type`），**公理本身被丢弃**——形状生成的天然喂料被浪费。

5. **质量闸 G2.2/G2.3 是占位**：`quality_gate.rego` 的 `deny_gate2_2_cardinality ... if { false }`、`deny_gate2_3_isa_acyclic ... if { false }` 恒不 deny；Python 侧（ADR-084 S1 已落）标 `evaluated=False` 剔出均分。rego 注释把真值归因「待 L5 基数归纳 / L3 拓扑排序」。另有**死代码** `infra/query/sources/schema_source.py::validate_cardinality`（零调用方）。

6. **无 violation 队列**：全仓无 `axiom_violation*` 表/存储。`simulation_deduction` 的 `RuleViolation` 是内存分析结果、非持久队列。

### 问题陈述

约束（基数/不相交/签名/无环）有**定义**（usl 表）、有**校验器**（SHACLValidator）、有**占位门**（G2.2/G2.3），但三者**互不连通**：校验器不在写路径上、形状不持久化故无法高频校验、公理被丢弃、违规无处沉淀。结果是「约束停留在文档层」（F7），伪绿 KPI 靠 ADR-084 S1 的 `evaluated=False` 诚实化掩盖而非真正评估。

---

## Decisions

### D1. 形状持久化 = ADR-077 裁决 1「版本键控缓存」的操作化（非推翻）

裁决 1 禁止的是**无版本键的陈旧副本**，并明确允许「带 Schema 版本号失效键」的缓存。本 ADR 据此把形状落为**派生缓存表**，而非新的事实源：

- 新增 `sa_shacl_shape` 表（仿 `candidate_store` 约定，规则 8：每次 connect/close）：
  `shape_id, workspace_id, ontology_version_id, constraint_revision, target_type, shape_ttl(TEXT), source_type_defs(JSON), source_axioms(JSON), checksum, created_at`，主键 `shape_id`，唯一键 `(ontology_version_id, constraint_revision, target_type)`。
- **单一事实源不变**：形状永远由「ontology 类型定义 + `usl_cardinalities` + `usl_disjoint_pairs` + L6 公理」实时派生；持久化副本带 `(ontology_version_id, constraint_revision)` 复合失效键，版本/约束变更即重生成（幂等 upsert：DELETE-by-key 后 INSERT，同 `save_disjoint_pair` 模式）。
- **裁决 3 不被破坏**：校验输入仍是**显式传入的实例 JSON**（写路径把「即将写入的实例」显式递给校验器），**不读 Neo4j**。持久化的只是 shape，不是 instance data graph。

### D2. 形状生成喂料：扩展 ShapeGenerator 消费持久化约束 + 落地 L6 公理

- 扩展 `ShapeGenerator`：在现有「类型定义 → required/datatype/cardinality bounds」基础上，增补：
  - `usl_cardinalities(min_card,max_card)` → `sh:minCount/sh:maxCount`（按 `rel_name`+`domain_term`→`sh:path`/`sh:class`）。
  - `usl_disjoint_pairs(term_a,term_b)` → `sh:not { sh:class :term_b }`（或 `owl:disjointWith` 派生）。
  - L6 `AxiomDeriver` 的 `object_property_domain|range / *_cardinality / disjoint_classes / sub_class_of` → 对应 SHACL 约束。
- **L6 公理不再丢弃**：`pipeline_service.py` 在 L6 后把 `derive()` 的公理**持久化**（新增 `sa_derived_axiom` 表或并入 run snapshot 的结构化字段），作为形状生成与 G2.2/G2.3 真值的共同来源。

### D3. 写路径校验点 = 单一 `WritePathValidator` 实现 + 上下文感知「车道级」调用（不改 GraphWriteProxy 契约）

针对「proxy 无 ontology/domain 上下文」的硬约束，**不在通用 proxy 层插入校验**（那需要给 15 处调用加 context 参数、且仍盖不住旁路/episode），改为：

- 新增 `WritePathValidator`（`infra/query/` 或 `biz/core/ontology/design/engine/shacl/` 下）：单一实现「给定 (ontology_version_id/domain_id, 实例 dict) → 加载/生成持久化形状 → SHACLValidator.validate → 结构化违规列表」。
- **在已知上下文的车道调用**它（这些车道天然握有 domain/ontology）：
  - 摄入车道 `knowledge_base_service._write_to_graph`（ADR-084 S2/S3 已在此分流 typed/open，typed 实例写图前校验，上下文= kb→domain）。
  - 治理车道 `candidate_store.promote_to_usl` / `graphiti_writeback_adapter.write_term`（上下文= domain_id/ontology_id 已知）。
- **GraphWriteProxy 契约不变**（守 ADR-084「本分片不改 GraphWriteProxy 契约」）；proxy 仍是删除/软删的唯一合规通道（ADR-083）。
- **显式登记覆盖缺口（规则 14：失败/边界显式，不静默）**：3 个 infra 旁路写方 + Graphiti episode 车道**本分片不覆盖**，在 ADR 与代码注释中明列，并给出归口：episode 涌现的事实在 ADR-084 S2 已路由经 candidate/typed 边界，校验在该边界补（S4d）；旁路写方 S4d 收敛到 proxy 或各自接 `WritePathValidator`。

### D4. gate-vs-observe 灰度：observe-first，enforce 后置且按车道

- **Phase 1（本 ADR 实现）= OBSERVE / SHADOW 模式（默认）**：校验命中违规时——
  - 写一条 `sa_axiom_violation`（status=`pending`）；
  - 发 `graph_audit("write_path_violation", result_status="warning", ...)`（级别 ≥ warning，规则 14.3：不得 debug 级隐藏）；
  - **写入照常放行**（不阻断既有 15 条链路、不改行为）。
  - 这**不是静默兜底**：违规被显式沉淀到队列 + 审计，可观测、可测试、可审计（规则 14.2/14.3）。放行是**经评审的灰度策略**，非异常吞掉。
- **Phase 2（S4d，后置评审）= ENFORCE 模式**：按车道/工作空间 feature-flag，命中违规则**阻断写入** + 落 violation（status=`pending`）+ 显式 error 上抛（规则 2：服务层返回 `{"status":"error"}`，路由层翻译）。**先从摄入 typed 车道开**，待 observe 数据证明形状无误报再逐车道扩。
- **与 utopia 的区分**：utopia "types never gate" 是永久不设门；ODAP 的 enforce 是**可达终态**，observe-first 只是降误报风险的上线顺序。

### D5. violation 队列存储 `sa_axiom_violation`

仿 `SQLiteCandidateStorage` 约定（规则 8 connect/close、`_init_db` CREATE IF NOT EXISTS、dict 行、JSON 列、DELETE+INSERT upsert）：

```
sa_axiom_violation(
  violation_id TEXT PK,
  workspace_id TEXT, domain_id TEXT, ontology_version_id TEXT,
  lane TEXT,                 -- ingest_typed / writeback / episode / ...
  mode TEXT,                 -- observe / enforce
  subject_ref TEXT,          -- entity_id 或 关系签名 src-rel-tgt
  shape_id TEXT, constraint_type TEXT,  -- cardinality/disjoint/signature/isa_acyclic/datatype
  severity TEXT,             -- error / warning
  message TEXT,
  status TEXT,               -- pending / accepted / rejected / deferred（对齐审批飞轮 + utopia axiom_violations）
  provenance TEXT,           -- JSON: kb_id/doc_id/run_id/raw instance 摘要
  created_at TEXT, resolved_at TEXT, resolved_by TEXT
)
```

- 消费方：质量闸报告、语义管理台仪表盘（违规趋势）、审批飞轮（accepted→修形状/修约束，rejected→放行该实例并记先例，喂 S5 治理只读人类先例）。

### D6. G2.2 基数 / G2.3 is_a 无环：用持久化约束真值替换占位

- **G2.2 基数**：`quality_evaluator` 从 `usl_cardinalities`（+ L6 `object_property_cardinality`）对候选的关系基数做真实评估；命中违规 → score 反映真违规（非占位 1.0），`evaluated=True`。rego 侧 `deny_gate2_2_cardinality` 由 Python 传入的 `cardinality_violations` input 驱动（同 G2.1 disjoint_pairs 的传入模式），删除 `if { false }` 占位。
- **G2.3 is_a 无环**：从 `usl_hierarchies` 做拓扑排序检测环；有环 → `evaluated=True` 且 deny，无环 → 通过。rego `deny_gate2_3_isa_acyclic` 由传入的 `isa_cycle_detected` input 驱动。
- **删除死代码** `schema_source.validate_cardinality`（零调用方），其 ONE_TO_ONE 计数逻辑若有用则并入 `WritePathValidator`/G2.2 真值，否则移除（规则 14：不留幻影/死码）。
- 这是 ADR-084 D2「度量诚实化」的**终局**：G2.2/G2.3 从 `evaluated=False` 占位转为真评估，伪绿 KPI 彻底消除。

---

## 验收口径（Acceptance）

| 编号 | 场景 | 期望 |
|------|------|------|
| F7-a（S4a） | 同一 ontology_version + constraint_revision 重复请求形状 | 命中持久化缓存（不重复生成）；版本/约束 bump 后重生成（失效键生效） |
| F7-b（S4a） | ShapeGenerator 消费 `usl_cardinalities(min=1,max=1)` | 产出含 `sh:minCount 1 / sh:maxCount 1` 的形状；`usl_disjoint_pairs` → `sh:not`/disjointWith |
| F7-c（S4a） | L6 `AxiomDeriver.derive()` 跑完 | 公理被持久化（可被形状生成/G2.2 读到），不再仅留计数 |
| F7-d（S4b） | observe 模式摄入一个违反基数的 typed 实体 | 写入**放行** + `sa_axiom_violation`(status=pending, mode=observe) 落库 + `write_path_violation` warning 审计 |
| F7-e（S4b） | observe 模式摄入一个合规实体 | 无 violation 行、无 warning 审计 |
| F7-f（S4c） | 候选命中真实基数约束 | G2.2 `evaluated=True` 且 score 反映违规（≠ 占位 1.0）；is_a 有环 → G2.3 deny |
| F7-g（S4d） | enforce 模式车道摄入违规实例 | 写入**被阻断** + violation 落库 + 服务层返回 `{"status":"error"}`；observe 车道不受影响 |

测试守规则 9：`sa_shacl_shape`/`sa_axiom_violation`/`sa_derived_axiom` 用真实 `tmp_path` SQLite，禁 MagicMock；`WritePathValidator` 走真实 `SHACLValidator`（pyshacl 已装），至少一条用例执行真实函数体（规则 14.6）。

---

## Alternatives Considered

1. **在 GraphWriteProxy.add_entity 内联校验（通用 chokepoint）**：被否。proxy 无 ontology/domain 上下文，需给 15 处调用加 context 参数（大改契约，违 ADR-084「不改 proxy 契约」），且仍盖不住 3 个 infra 旁路与 episode 车道；pyshacl 逐实体同步校验在 agent/simulation 热路径上性能不可接受。
2. **直接上 enforce 硬门（一步到位）**：被否。形状若有误报会阻断合法写入，波及 15 条链路；ADR-084 明确「避免一次性大改」。observe-first 用真实数据先验证形状正确性。
3. **推翻 ADR-077 裁决 1、把形状当新事实源持久化**：被否。会制造陈旧副本风险。改为「版本键控派生缓存」，既满足写路径高频校验的性能需求，又守住裁决 1 的单一事实源精神（裁决 1 本就允许带版本失效键的缓存）。
4. **violation 直接复用 candidate_store**：被否。语义不同（候选=待治理术语，违规=约束冲突），状态机与消费方不同；独立 `sa_axiom_violation` 表更清晰，但复用其存储约定。

---

## Consequences

**正面**：F7 关闭——约束从「文档层」变为「写路径可观测/可阻断」；G2.2/G2.3 伪绿 KPI 消除（ADR-084 D2 终局）；L6 公理不再浪费；违规沉淀为治理飞轮与 S5「只读人类先例」的输入；形状缓存让高频校验可行。

**负面/风险**：
- **性能**：SHACL 校验非廉价。缓解：持久化形状缓存（D1）+ 只校验 typed 车道实例写（不碰自由文本 episode）+ 车道级批量。
- **覆盖缺口**：S4b 不盖 3 个 infra 旁路 + episode 车道（D3 显式登记，S4d 收敛）。在缺口收敛前，「所有写路径经同一校验点」是**渐进达成**而非一步到位——文档与代码注释须如实标注，不得宣称「全路径已守卫」（规则 12/14：ADR 宣称与现实对齐）。
- **修订已接受 ADR**：本 ADR 扩展 ADR-077 裁决 1/裁决 3 的适用边界，须在 ADR-077 加「Superseded in part by ADR-085」批注 + README 台账登记，避免双 ADR 冲突。
- **误报治理成本**：observe 期需人工分诊 violation 队列（accepted/rejected/deferred），新增审批负载；可后续用采纳计数/点头制批量缓解（衔接 S5）。

---

## Implementation Slices

| 切片 | 内容 | 优先级 | 风险/blast radius | 依赖 | 落地状态 |
|------|------|:--:|------|------|------|
| **S4a** | `sa_shacl_shape` + `sa_derived_axiom` 存储；扩展 ShapeGenerator 消费 usl 约束；L6 公理持久化（不再丢弃）；形状版本键控缓存 | P1 | **低**（纯新增，无写路径行为变更，有真实消费方=S4b/S4c） | — | ✅ 已落地（2026-10-04，TDD；F7-a/b/c 验收测试绿） |
| **S4b** | `WritePathValidator` + `sa_axiom_violation` 队列；**observe 模式**接入摄入 typed 车道 + 治理 writeback 车道；warning 审计 | P1 | **中**（写路径新增旁路观测，但放行不改行为；缺 pyshacl 时 RuntimeError 不静默） | S4a | ⏸ 暂缓（须获批后落地） |
| **S4c** | G2.2 基数 / G2.3 is_a 无环真值替换 rego 占位 + `evaluated=True`；删除 `schema_source.validate_cardinality` 死代码 | P1 | **低**（限于质量闸，无写路径变更） | S4a（公理/约束真值源） | ✅ 已落地（2026-10-04，TDD；F7-f 验收测试绿） |
| **S4d** | **enforce 模式**按车道 feature-flag 阻断；收敛 3 个 infra 旁路 + episode 车道到校验点；ADR-077 加 Superseded-in-part 批注 | P2 | **高**（改写入行为、波及多链路、修订已接受 ADR）→ **须评审后实现** | S4b observe 数据 | ⏸ 暂缓（须单独评审） |

> **推进策略**：S4a/S4c 为纯新增/局部、低风险、有真实消费方，可在本 ADR 获批后即以 TDD 落地；S4b 改写入观测路径（虽放行）建议获批后落地；**S4d 改写入行为 + 修订已接受 ADR-077，blast radius 大，须单独评审后再实现**（守 ADR-084「避免一次性大改」与规则 14「先确认再实现」）。
