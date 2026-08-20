# 版块清理验证清单（Refactoring Verification Checklist）

**日期**: 2026-08-07
**范围**: 006-he-extraction-chain / 007-semantic-admin-suite / 009-intel-driven-architecture（A-F 类）+ 全部 9 个 spec 目录下游影响验证（G 类）
**目的**: 确认清理后的各版块按新设计正常工作，无残留重叠、无遗漏职责、无断裂引用、无下游破坏

---

## A. 文档一致性验证（可立即执行 · grep/search 自动化）

> 以下检查可通过 `Select-String` / `grep` 自动化执行，验证 spec/plan/contract 文档内部无矛盾。

### A1. 006 删除项无活跃残留

- [x] **A1.1** 006 spec.md 中 `settle_template` / `get_settled_template` 仅出现在删除标记（~~删除线~~ 或"已删除"上下文）中，无活跃 FR
- [x] **A1.2** 006 spec.md 中 `ValidationEngine` 仅出现在移交说明中，无活跃 FR-024~029
- [x] **A1.3** 006 spec.md 中 `SqliteTemplateStorage` 无活跃引用
- [x] **A1.4** 006 plan.md 项目结构中无 `storage/` 目录、无 `validation_engine.py`、无 `sqlite_template_storage.py`
- [x] **A1.5** 006 plan.md TDD Requirements 中无 `test_validation_engine.py` / `test_sqlite_template_storage.py`

### A2. 007 子指标计数一致

- [x] **A2.1** 007 plan.md 中所有"子指标"计数为 22（非 16），除版块清理说明中的过渡描述（16→19→22）
- [x] **A2.2** 007 plan.md 中 G1×10 / G2×7 / G3×5（非 G1×7 / G2×4）
- [x] **A2.3** 007 data-model.md §4 标题为"G1×10 / G2×7 / G3×5"
- [x] **A2.4** 007 data-model.md §4.3 Gate 1 有 10 行子指标（G1.1-G1.10）
- [x] **A2.5** 007 data-model.md §4.4 Gate 2 有 7 行子指标（G2.1-G2.7）
- [x] **A2.6** 007 contracts/quality-gate-approval.md 中"子指标"计数为 22 ⚠️ *顶部清理说明提及 22，但契约正文 `Quality22Submetrics` 类仍只定义 16 字段（见 D3.3）*

### A3. 009 委托关系明确

- [x] **A3.1** 009 spec.md FR-003 包含"唯一规范实现"声明
- [x] **A3.2** 009 spec.md FR-006 包含 007 审计委托说明
- [x] **A3.3** 009 spec.md 顶部有版块清理说明（从 006/007 移交职责表格）

### A4. 交叉引用闭环

- [x] **A4.1** 006 spec.md 版块清理说明引用 007 spec.md（校验移交）和 009 spec.md（HE kb 移交）
- [x] **A4.2** 007 spec.md 版块清理说明引用 006 spec.md Brainstorm Log 和 009 spec.md（审计委托）
- [x] **A4.3** 009 spec.md 版块清理说明引用 006/007 spec.md 和 REFACTORING-NOTES.md
- [x] **A4.4** REFACTORING-NOTES.md 文件变更清单与实际修改的文件一致

---

## B. 职责边界验证（无重叠 · 无遗漏）

> 验证每个职责有且仅有一个归属 spec，无三方争抢、无无人认领。

### B1. 模板持久化

- [x] **B1.1** 模板持久化与复用 → 唯一归属 009 FR-003 `he feed`
- [x] **B1.2** 006 无活跃的模板沉淀 FR（FR-017/018/019 标记删除）
- [x] **B1.3** 006 HEAdapter 提供 `feed_to_kb()` 作为委托入口，不自建持久化

### B2. 校验机制

- [x] **B2.1** 质量校验 → 唯一归属 007 QualityGateService（22 子指标）
- [x] **B2.2** 006 无活跃的 ValidationEngine FR（FR-024~029 标记删除/移交）
- [x] **B2.3** 006 抽取完成后直接产出 `raw_extraction_result`，不再执行校验
- [x] **B2.4** instance 模式下 QG 也调用，结果写入 `ExtractionSession.validation_report`

### B3. ExtractService 编排

- [x] **B3.1** ExtractService 编排权 → 唯一归属 006 FR-037
- [x] **B3.2** 007 US4 描述为"通过 hook 调用 006"，非"直接实现 mode 参数"
- [x] **B3.3** 007 提供 `ConceptExtractor.run_l1_l2_hook()` 接口，006 调用
- [x] **B3.4** hook 异常不阻断 006 主流程（catch + 日志 warning）

### B4. 审计体系

- [x] **B4.1** 操作审计 → 唯一归属 009 FR-006 分层审计
- [x] **B4.2** 007 不直接调用 `UnifiedAudit.log_action`（NFR-009 声明委托 009）
- [x] **B4.3** 007 保留 `usl_outbox` 仅用于 TBox 双写
- [x] **B4.4** 006 Channel B 使用 009 `save_audit_episode`（零 LLM），不走 `add_episode`

---

## C. 接口契约验证

> 验证新增/删除/移交的接口在契约文档中有明确声明。

### C1. 新增接口

- [x] **C1.1** 006 contracts/he-adapter.md 包含 `feed_to_kb(kb_path, text, result)` 方法说明
- [x] **C1.2** 007 plan.md 项目结构包含 `concept_extractor.py`（run_l1_l2_hook 入口）
- [x] **C1.3** 009 spec.md FR-001 包含 `save_audit_episode(audit_data, valid_at)` 方法
- [x] **C1.4** 009 spec.md FR-003 包含 `feed_to_kb(kb_path, text)` 方法

### C2. 删除接口

- [x] **C2.1** 006 contracts/template-engine.md 标注 `settle_template()` 已删除
- [x] **C2.2** 006 contracts/template-engine.md 标注 `get_settled_template()` 已删除
- [x] **C2.3** 006 contracts/template-engine.md 标注 `SqliteTemplateStorage` 依赖已删除 ✅ **已修复（2026-08-08 复验）**：L24 签名改为 `def __init__(self, he_adapter: HEAdapter, embedder=None):`，无 `storage` 参数；L25-26 仅含 `self._adapter` / `self._embedder`，无 `self._storage` 赋值；L102 Dependencies 明确标注 `~~SqliteTemplateStorage~~ 已删除`
- [x] **C2.4** 006 contracts/validation-engine.md 顶部有⚠️已废弃声明

### C3. 移交接口映射

- [x] **C3.1** 006 contracts/validation-engine.md 废弃声明中有到 007 QG 的映射表
- [x] **C3.2** 007 contracts/quality-gate-approval.md 清理说明中有从 006 移交的 6 项子指标 ⚠️ *顶部说明列出 6 项移交子指标，但契约正文 `Quality22Submetrics` 类未定义这 6 个字段（见待修正项 #1）*
- [x] **C3.3** 006 data-model.md 废弃说明中有到 007/009 的移交目标

---

## D. 数据模型验证

> 验证质量闸子指标的完整性和一致性。

### D1. G1 完整性子指标（从 006 移交）

- [x] **D1.1** G1.8 fill_rate 有阈值（≥ 0.5）、失败动作（WARN）、扣分项（-0.10）
- [x] **D1.2** G1.9 empty_rate 有阈值（≤ 0.3）、失败动作（WARN）、扣分项（-0.08）
- [x] **D1.3** G1.10 orphan_count 有阈值（≤ 0.3）、失败动作（WARN）、扣分项（-0.05）

### D2. G2 引用一致性子指标（从 006 移交）

- [x] **D2.1** G2.5 dangling_relations 有阈值（布尔）、失败动作（WARN）、扣分项（-0.15）
- [x] **D2.2** G2.6 invalid_action_targets 有阈值（布尔）、失败动作（WARN）、扣分项（-0.10）
- [x] **D2.3** G2.7 invalid_rule_references 有阈值（布尔）、失败动作（WARN）、扣分项（-0.10）

### D3. 权重一致性

- [x] **D3.1** 007 data-model.md §4.1 权重为 0.35/0.40/0.25
- [x] **D3.2** 007 plan.md Complexity Tracking 权重为 0.35/0.40/0.25
- [x] **D3.3** ✅ **已修复（2026-08-08 复验）** — 007 contracts/quality-gate-approval.md 已更新：`Quality22Submetrics` 类定义 22 字段（L83-120）、权重 `0.35/0.40/0.25`（L187/195）、Section 4 标题"22 条 OPA Rego 规则"（L554）、`SubmetricThreshold` 22 常量（L40-71）。顶部说明 L3 标注"已完成 D3.3 修正"。

---

## E. 实现就绪验证

> 验证清理后的设计可直接进入 TDD 实现阶段。

### E1. TDD 覆盖

- [x] **E1.1** 007 plan.md TDD Requirements 包含 `ConceptExtractor.run_l1_l2_hook` 测试项
- [x] **E1.2** 007 plan.md TDD Requirements 中 QualityCalculator 测试包含 6 项新子指标
- [x] **E1.3** 006 plan.md TDD Requirements 中 `feed_to_kb` 有 mock 测试要求
- [x] **E1.4** 006 plan.md TDD Requirements 中无 ValidationEngine/SqliteTemplateStorage 测试项

### E2. 项目结构完整

- [x] **E2.1** 007 plan.md ol_pipeline/services/ 包含 `concept_extractor.py`
- [x] **E2.2** 006 plan.md 项目结构中 `extract_service.py` 包含 `mode=schema_learning hook` 注释
- [x] **E2.3** 006 plan.md 项目结构中 he_adapter.py 包含 `feed_to_kb 委托` 注释
- [x] **E2.4** 006 plan.md 项目结构中无 `storage/` 目录

### E3. 废弃标记完整

- [x] **E3.1** 006 data-model.md 顶部有废弃实体表格（HETemplate/ValidationReport/settle_template）
- [x] **E3.2** 006 contracts/validation-engine.md 顶部有⚠️已废弃声明 + 映射表
- [x] **E3.3** 006 contracts/template-engine.md 顶部有清理说明（删除项清单）
- [x] **E3.4** 006 contracts/he-adapter.md 顶部有 feed_to_kb 新增说明

---

## F. 实现阶段验证（代码实现后执行）

> 以下检查在代码实现阶段执行，验证实际代码符合新设计。
>
> **执行状态（2026-08-07）**：spec/plan 清理已完成，但代码重构尚未启动。006 旧代码仍含 ValidationEngine/SqliteTemplateStorage；007 新文件（quality_calculator.py / concept_extractor.py）尚未创建；009 基础设施已就绪。

### F1. 006 实现验证

- [x] **F1.1** `HEAdapter.feed_to_kb()` 调用 009 的 `feed_to_kb()`，不自建 SQLite 表 — `he_adapter.py:572` 已实现，持久化 HE kb，无 SQLite 表
- [x] **F1.2** `TemplateEngine` 无 `settle_template` / `get_settled_template` 方法 — 已确认缺失（符合预期）
- [x] **F1.3** ✅ **已修复（2026-08-08 复验）** — `TemplateEngine.__init__` 已移除 `SqliteTemplateStorage` 参数（`template_engine.py:61-65` 签名 `def __init__(self, he_adapter, embedder=None):`，L72-74 无 `self._storage` 赋值，文件头注释标注 ADR-074 settled template 移除）
- [x] **F1.4** ✅ **已修复（2026-08-08 复验）** — `ExtractService` 已移除 `ValidationEngine`（无 import、`__init__` 无 `validation_engine` 参数、原 `_run_validation` 被 `_run_schema_learning_hook` L926 取代）。注：L105/241 docstring 残留 "Validate via 4-dimensional ValidationEngine" 文字（stale 注释，建议清理）
- [x] **F1.5** ✅ **已修复（2026-08-08 复验）** — `ExtractService.extract(mode="schema_learning")` 调用 `_run_schema_learning_hook`（L168-170），L926-947 优先调用 007 `ConceptExtractor.run_l1_l2_hook()`，含 ImportError fallback 到内部 `_generate_schema_candidates`
- [x] **F1.6** ✅ **已验证（2026-08-08 复验）** — hook 异常处理已实现：`_run_schema_learning_hook` 含 try/except，ImportError 或异常时回退到内部 `_generate_schema_candidates(merged)`（L944/947）并 log warning，不阻断主流程（符合 B3.4 设计）
- [x] **F1.7** `dual_channel_writer` Channel B 调用 009 `save_audit_episode`，不走 `add_episode` — `dual_channel_writer.py:127` 调用 `gm.save_audit_episode()`，注释确认"零 LLM，ADR-074"

### F2. 007 实现验证

- [x] **F2.1** ✅ **已修复（2026-08-08 复验）** — `quality_calculator.py` 文件存在（`semantic_admin/quality_gate/services/`），22 子指标完整实现。文件头注释标注"22 子指标质量闸计算器（版块清理 2026-08-07）"。6 项 006 移交子指标方法：`_eval_g1_fill_rate`(L78) / `_eval_g1_empty_rate`(L115) / `_eval_g1_orphan_ratio`(L153) / `_eval_g2_dangling_relations`(L191) / `_eval_g2_invalid_action_targets`(L234) / `_eval_g2_invalid_rule_references`(L276)。主类 `QualityCalculator`(L322) + `G1_SUB_WEIGHTS_22` 22 项权重常量(L52-63)
- [x] **F2.2** ✅ **已修复（2026-08-08 复验）** — `concept_extractor.py` 文件存在（`semantic_admin/ol_pipeline/services/`，符合 007 plan.md I2T1 设计）。主类 `ConceptExtractor`(L63)，`run_l1_l2_hook()` 方法在 L99 实现，含 candidate_store 写入 + provenance 标记 `007_concept_extractor.run_l1_l2_hook`(L169)
- [ ] **F2.3** ⏳ 待验证 — `audit_helper.py` 已存在（`infra/security/audit_helper.py`），但 007 子服务是否委托需代码检查确认
- [ ] **F2.4** ⏳ 待验证 — `usl_outbox` 用途需代码检查确认
- [ ] **F2.5** ⏳ 待验证 — instance 模式 QG 调用需代码检查确认

### F3. 009 实现验证

- [x] **F3.1** `feed_to_kb(kb_path, text)` 方法存在且持久化 HE kb — `he_adapter.py:572` 已实现
- [x] **F3.2** `save_audit_episode(audit_data, valid_at)` 使用 `EpisodicNode.save(driver)`，零 LLM — `graph_service.py` 已实现
- [x] **F3.3** `audit_helper` SQLite 通道存在且 006/007 可委托 — `infra/security/audit_helper.py` + `audit_logger_v2.py` 已实现
- [x] **F3.4** 统一 `AuditEvent` schema 定义存在 — `infra/security/audit_models.py` 已定义

### F4. 集成验证

- [ ] **F4.1** ⏳ 待验证 — 006 抽取完成 → `feed_to_kb` → 009 HE kb 写入（端到端）
- [ ] **F4.2** ⏳ 待验证 — 006 schema_learning 模式 → hook → 007 Candidate 双写（端到端，依赖 F1.5/F2.2 修复）
- [ ] **F4.3** ⏳ 待验证 — 007 审批通过 → usl_outbox TBox 双写 + 009 audit_helper 操作审计（端到端，依赖 F2.1 修复）
- [ ] **F4.4** ⏳ 待验证 — 006 Channel B → 009 save_audit_episode 零 LLM 写入（端到端，token_tracker 验证）

---

## G. 下游影响验证（全 Spec 扫描 · 已执行 2026-08-07）

> 验证本次版块清理对未参与清理的下游 spec 无破坏性影响。
> 完整扫描报告见 [REFACTORING-SCAN-REPORT.md](./REFACTORING-SCAN-REPORT.md)。
>
> **扫描范围**：specs/ 下全部 9 个 spec 目录 + 顶层 REFACTORING 文档（共 67 个 .md 文件）。
>
> **扫描关键词**：`settle_template` / `get_settled_template` / `SqliteTemplateStorage` / `sqlite_template_storage` / `ValidationEngine` / `validation_engine` / `Quality16Submetrics` / `add_episode` / `UnifiedAudit.log_action` / `he_templates` / "16 子指标" / "G1×7" / "G2×4" / "16 sub-indicators"。
>
> **扫描结果**：总命中 331，其中清理范围内（006/007/009 + REFACTORING 文档）316，下游 spec 15（经核查全部合法）。

### G1. 检索服务总线（008）零引用 ⭐ 关键下游

> 008-semantic-retrieval-bus 是本体的主要下游消费方，本次清理对其零破坏。

- [x] **G1.1** 008-semantic-retrieval-bus 未引用 `settle_template` / `get_settled_template`（006 已删除的模板沉淀 API）
- [x] **G1.2** 008-semantic-retrieval-bus 未引用 `SqliteTemplateStorage` / `sqlite_template_storage`（006 已删除的存储类）
- [x] **G1.3** 008-semantic-retrieval-bus 未引用 `ValidationEngine` / `validation_engine`（006 已删除的校验引擎）
- [x] **G1.4** 008-semantic-retrieval-bus 未引用 `Quality16Submetrics`（007 已替换为 `Quality22Submetrics`，检索权重计算不受 22 子指标 schema 变更影响）

### G2. 其他下游 spec 零引用

- [x] **G2.1** 000-architecture-review 零命中（0 hits）
- [x] **G2.2** 004-microservice-split 零命中（0 hits）
- [x] **G2.3** 005-data-collection-opt 零命中（0 hits）

### G3. 001/003 少量命中经核查合法

> 001/003 有少量同名引用，经核查全部为**不同模块的同名实体**或**已完成 spec 的历史设计描述**，与本次清理无冲突。

- [x] **G3.1** **001 的 `validation_engine` / `ValidationEngine`（5 处）**：全部位于 `odap/biz/core/ontology/engine/` 模块（本体**管理**引擎：Version/Audit/Validation 三子模块之一），与 006 已删除的 `odap/biz/core/ontology/extraction/ValidationEngine`（HE 抽取链 4 维校验）**仅名称相同、代码路径不同**。证据：001/plan.md:96-115 目录树 + tasks.md T026/T040/T044/T076 任务描述明确指向 `engine/` 模块。
- [x] **G3.2** **001 的 `add_episode`（3 处）**：为合法 Graphiti API 文档引用（data-model.md:1302 / research.md:219,224），描述双时态索引 API 使用方式，与 006 Channel B 改用 `save_audit_episode` 无关。
- [x] **G3.3** **003 的 `add_episode`（6 处）**：为已完成 spec 的双通道写入设计描述（spec.md:54/68/170/227/286 + research.md:123），003 是已完成的先前分支，006 改造不要求 003 跟随修改。
- [x] **G3.4** **003 的 `he_templates`（1 处，data-model.md:315）**：为已完成 spec 的历史记录（描述 `he_templates` 表是"HE 模板管理（新增）"），属 003 完成时的设计快照，无需追溯修改。

### G4. 扫描可重复性

- [x] **G4.1** 扫描脚本已固化在 [REFACTORING-SCAN-REPORT.md](./REFACTORING-SCAN-REPORT.md) 的「按 spec 命中数」与「类别 x Spec 矩阵」章节，后续清理可重复执行比对

---

## 执行状态汇总

| 类别 | 总项数 | 已通过 | 失败 | 待验证 | 不适用 |
|------|:------:|:------:|:----:|:------:|:------:|
| A. 文档一致性 | 19 | 19 | 0 | 0 | 0 |
| B. 职责边界 | 15 | 15 | 0 | 0 | 0 |
| C. 接口契约 | 11 | 11 | 0 | 0 | 0 |
| D. 数据模型 | 9 | 9 | 0 | 0 | 0 |
| E. 实现就绪 | 11 | 11 | 0 | 0 | 0 |
| F. 实现阶段 | 20 | 13 | 0 | 7 | 0 |
| **G. 下游影响** | **12** | **12** | **0** | **0** | **0** |
| **合计** | **97** | **90** | **0** | **7** | **0** |

> **2026-08-08 复验更新**：6 项 FAIL 全部已修复（D3.3 + C2.3 + F1.3-F1.5 + F2.1-F2.2），F1.6 从 N/A 转为通过。执行状态从 `83 通过 / 6 失败 / 7 待验证 / 1 N/A` 更新为 **`90 通过 / 0 失败 / 7 待验证 / 0 N/A`**。
>
> **A-G 类全部通过（90/90 已决项）**：spec/plan/contract 文档层面 + 代码层面清理完整，职责边界清晰，交叉引用闭环，下游无破坏。
>
> **F 类剩余 7 项待验证**：依赖本次 FAIL 修复，现可推进（F2.3-F2.5 代码检查 + F4.1-F4.4 端到端集成测试）。

---

## 关键发现与待修正项

> **2026-08-08 复验**：以下 4 项待修正项全部已修复（修复证据见 [REFACTORING-NOTES.md](./REFACTORING-NOTES.md) Part 1 §1.3.1）。原问题描述保留作为历史记录。

| # | 待修正项 | 编号 | 状态 | 修复日期 |
|---|---------|------|:----:|:--------:|
| 1 | 007 契约正文未同步 22 子指标 | D3.3 | ✅ 已修复 | 2026-08-08 |
| 2 | 006 契约 `__init__` 仍含 SqliteTemplateStorage | C2.3 | ✅ 已修复 | 2026-08-08 |
| 3 | 006 代码未重构（TemplateEngine + ExtractService） | F1.3-F1.5 | ✅ 已修复 | 2026-08-08 |
| 4 | 007 新文件未创建（quality_calculator + concept_extractor） | F2.1-F2.2 | ✅ 已修复 | 2026-08-08 |

---

### 待修正项 #1（历史记录）：007 契约正文未同步 22 子指标（D3.3 · 文档级 · 高优先级）

**文件**: `specs/007-semantic-admin-suite/contracts/quality-gate-approval.md`

**问题**: 顶部清理说明已声明"扩展为 22 子指标"，但契约正文未更新：
1. `Quality22Submetrics` 类仅定义 16 个字段（G1×4/G2×6/G3×6），缺少 G1.8-G1.10 和 G2.5-G2.7
2. `SubmetricThreshold` 仅定义 16 个阈值常量
3. 权重仍为 `0.3*g1 + 0.4*g2 + 0.3*g3`（line 109/116/663），应为 `0.35/0.40/0.25`
4. Section 4 标题仍为"OPA Rego 16 条规则"，应为 22 条
5. OPA Rego 规则仅定义 16 条 deny 规则

**影响**: data-model.md（权威定义）与 contract 不一致；代码实现时若参考 contract 会产生歧义。

**修正方案**: 以 `data-model.md §4` 为权威源，更新 contract 的 `Quality22Submetrics` 类、`SubmetricThreshold`、权重公式、Rego 规则。

### 待修正项 #2（历史记录）：006 TemplateEngine 契约正文仍含 SqliteTemplateStorage（C2.3 · 文档级 · 中优先级）

**文件**: `specs/006-he-extraction-chain/contracts/template-engine.md`

**问题**: 顶部清理说明声明"`__init__` 不再接收 `storage: SqliteTemplateStorage` 参数"，但 line 24 的 Interface 代码仍为 `def __init__(self, he_adapter: HEAdapter, storage: SqliteTemplateStorage):`。

**修正方案**: 更新契约正文 `__init__` 签名，移除 `storage` 参数及 `self._storage` 赋值。

### 待修正项 #3（历史记录）：006 代码未重构（F1.3-F1.5 · 代码级 · 实现阶段）

**文件**: `apps/api/odap/biz/data/hyper_extract/services/`

**问题**:
- `template_engine.py` 仍接收 `SqliteTemplateStorage` 参数（F1.3）
- `extract_service.py` 仍 import 并调用 `ValidationEngine`（F1.4）
- `extract_service.py` schema_learning 模式调用内部 `_generate_schema_candidates()`，未调用 007 hook（F1.5）

**修正方案**: 按版块清理设计重构 006 代码——移除 ValidationEngine 依赖、移除 SqliteTemplateStorage 参数、schema_learning 模式改为调用 007 `ConceptExtractor.run_l1_l2_hook()`。

### 待修正项 #4（历史记录）：007 新文件未创建（F2.1-F2.2 · 代码级 · 实现阶段）

**文件**: `apps/api/odap/biz/semantic_admin/quality_gate/`

**问题**:
- `quality_calculator.py` 不存在（F2.1）——22 子指标计算未实现
- `concept_extractor.py` 不存在（F2.2）——`run_l1_l2_hook()` 接口未实现

**修正方案**: 按 007 plan.md TDD Requirements 创建这两个文件，实现 22 子指标计算和 hook 接口。
