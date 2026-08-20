# 全 Spec 过期引用扫描报告

**日期**: 2026-08-07
**范围**: specs/ 下全部 9 个 spec 目录 + 顶层 REFACTORING 文档
**目的**: 扫描本次版块清理删除/移交/替换的所有实体引用，验证下游 spec 未受影响

## 1. 总览

| Spec | 命中数 | 风险等级 |
|------|:------:|:------:|
| _top-level | 56 | 合法（清理范围内） |
| 000-architecture-review | 0 | ✅ 无风险 |
| 001-odap-platform | 8 | ⚠️ 需核查 |
| 003-ontology-redesign | 7 | ⚠️ 需核查 |
| 004-microservice-split | 0 | ✅ 无风险 |
| 005-data-collection-opt | 0 | ✅ 无风险 |
| 006-he-extraction-chain | 170 | 合法（清理范围内） |
| 007-semantic-admin-suite | 71 | 合法（清理范围内） |
| 008-semantic-retrieval-bus | 0 | ✅ 无风险 |
| 009-intel-driven-architecture | 19 | 合法（清理范围内） |
## 2. 类别 x Spec 矩阵

| Spec | DELETED | REPLACED | DEPRECATED | STALE_COUNT |
|------|:------:|:------:|:------:|:------:|
| _top-level | 38 | 10 | 2 | 6 |
| 000-architecture-review | 0 | 0 | 0 | 0 |
| 001-odap-platform | 5 | 3 | 0 | 0 |
| 003-ontology-redesign | 0 | 6 |  | 0 |
| 004-microservice-split | 0 | 0 | 0 | 0 |
| 005-data-collection-opt | 0 | 0 | 0 | 0 |
| 006-he-extraction-chain | 141 | 4 | 25 | 0 |
| 007-semantic-admin-suite | 16 | 6 | 4 | 45 |
| 008-semantic-retrieval-bus | 0 | 0 | 0 | 0 |
| 009-intel-driven-architecture | 11 | 7 |  | 0 |
## 3. 关键发现

### 3.1 ✅ 完全无命中（无下游影响）

以下 spec 未引用任何已删除/已替换实体：

- **000-architecture-review** — 0 hits
- **004-microservice-split** — 0 hits
- **005-data-collection-opt** — 0 hits
- **008-semantic-retrieval-bus** — 0 hits ⭐ 检索服务总线完全独立于本次清理

### 3.2 ⚠️ 需核查的下游 spec 命中

以下 spec 有少量命中，需逐一核查是否为合法引用（如历史记录、跨 spec 描述）：

#### 001-odap-platform（8 hits）

| File | Line | Category | Keyword | Context |
|------|------|----------|---------|---------|
| data-model.md | 1302 | REPLACED | add_episode | graph.add_episode( |
| plan.md | 106 | DELETED | validation_engine | │   │   │   │   │   │   └── validation_engine.py |
| plan.md | 110 | DELETED | validation_engine | │   │   │   │   │   │   └── validation_engine_impl.py |
| research.md | 219 | REPLACED | add_episode | - Graphiti 的 `add_episode()` 使用 `reference_time` 参数对应 valid_time |
| research.md | 224 | REPLACED | add_episode | - 需要在 `add_episode()` 时分别传入 `valid_time`（业务时间）和自动记录 `transaction_time`（系统时间） |
| tasks.md | 15 | DELETED | ValidationEngine | - [x] T025 [REVIEW]- [x] T026 本体模型层目录结构创建 — `odap/biz/core/ontology/model/` 创建 api/ models/ inter... |
| tasks.md | 15 | DELETED | validation_engine | - [x] T025 [REVIEW]- [x] T026 本体模型层目录结构创建 — `odap/biz/core/ontology/model/` 创建 api/ models/ inter... |
| tasks.md | 15 | DELETED | ValidationEngine | - [x] T025 [REVIEW]- [x] T026 本体模型层目录结构创建 — `odap/biz/core/ontology/model/` 创建 api/ models/ inter... |

#### 003-ontology-redesign（7 hits）

| File | Line | Category | Keyword | Context |
|------|------|----------|---------|---------|
| data-model.md | 315 | DEPRECATED | he_templates | 13. **he_templates** — HE 模板管理（新增） |
| research.md | 123 | REPLACED | add_episode | - 通道 B（graphiti.add_episode）：写入结构化摘要（OntologyDocument JSON），建立双时态索引和语义搜索 |
| spec.md | 54 | REPLACED | add_episode | 用户在本体设计器中选择"自然语言提取"方式，支持三种输入源：1）直接输入自然语言描述文本；2）上传文档（PDF/Word/TXT/Markdown/CSV/Excel/JSON/XML/图片 O... |
| spec.md | 68 | REPLACED | add_episode | 7. **Given** 用户确认提取结果，**When** 用户点击"确认导入"，**Then** 系统通过双通道写入：通道 A（GraphWriteProxy）写入完整属性到 Neo4j，通... |
| spec.md | 170 | REPLACED | add_episode | - **FR-029**: 系统必须通过双通道互补写入提取结果：通道 A（GraphWriteProxy）写入完整属性到 Neo4j，通道 B（graphiti.add_episode）写入结构... |
| spec.md | 227 | REPLACED | add_episode | - 双通道写入中 graphiti.add_episode 的输入格式需与 Graphiti 的 EpisodeInput 对齐 |
| spec.md | 286 | REPLACED | add_episode | \\| 8 \\| 写入通道策略 \\| 双通道互补写入（GraphWriteProxy + graphiti.add_episode） \\| 保证完整属性存储 + 双时态索引 + 语义搜索 \\| |

### 3.3 清理范围内 spec 命中（006/007/009 + REFACTORING 文档）

预期：所有命中都应出现在「删除标记 / 移交说明 / 过渡描述」上下文中。
完整命中清单见附录。

## 4. 结论

| 检查项 | 结果 |
|--------|:----:|
| 下游 spec（008 检索服务总线）零引用已删除实体 | ✅ |
| 下游 spec（000/004/005）零引用已删除实体 | ✅ |
| 001/003 下游命中需人工核查（少量历史性引用） | ⚠️ |
| 006/007/009 内命中均为清理标记（需抽样验证） | ⚠️ |

## 附录: 清理范围内 spec 完整命中清单

### A. 006-he-extraction-chain（170 hits）


#### data-model.md (12 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 12 | DEPRECATED | he_templates | > \\| `HETemplate`（he_templates 表） \\| **已删除** \\| 009 FR-003 `he feed` \\| HE kb 原生持久化，应用层不再维护模板表 \\| |
| 14 | DELETED | get_settled_template | > \\| `settle_template()` / `get_settled_template()` \\| **已删除** \\| 009 HE kb `he feed` 增量演化 \\| 应用层不再沉淀/复用模板 \\| |
| 14 | DELETED | settle_template | > \\| `settle_template()` / `get_settled_template()` \\| **已删除** \\| 009 HE kb `he feed` 增量演化 \\| 应用层不再沉淀/复用模板 \\| |
| 23 | DEPRECATED | he_templates | ### HETemplate (SQLite: he_templates) |
| 34 | DEPRECATED | he_templates | \\| yaml_path \\| TEXT \\| NOT NULL \\| YAML 文件路径 (如 `data/he_templates/{ontology_id}/{name}.yaml`) \\| |
| 44 | DEPRECATED | he_templates | **索引**: `idx_he_templates_ontology` ON `ontology_id` |
| 150 | DEPRECATED | he_templates | ### he_templates (新建) |
| 153 | DEPRECATED | he_templates | CREATE TABLE IF NOT EXISTS he_templates ( |
| 169 | DEPRECATED | he_templates | CREATE INDEX IF NOT EXISTS idx_he_templates_ontology ON he_templates(ontology_id); |
| 169 | DEPRECATED | he_templates | CREATE INDEX IF NOT EXISTS idx_he_templates_ontology ON he_templates(ontology_id); |
| 196 | DELETED | settle_template | [试抽评分] → score ≥ 阈值 → settle_template() → [沉淀] |
| 198 | DELETED | get_settled_template | get_settled_template() → [复用] |

#### plan.md (24 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 10 | DELETED | SqliteTemplateStorage | > **版块清理（2026-08-07）**：原 plan 中的 ValidationEngine（4 维校验）和 SqliteTemplateStorage（模板持久化）已整体移交/删除： |
| 10 | DELETED | ValidationEngine | > **版块清理（2026-08-07）**：原 plan 中的 ValidationEngine（4 维校验）和 SqliteTemplateStorage（模板持久化）已整体移交/删除： |
| 11 | DELETED | ValidationEngine | > - ValidationEngine → 移交 007 spec QualityGateService（QG-1 扩展完整性 + QG-2 扩展引用一致性） |
| 12 | DELETED | SqliteTemplateStorage | > - SqliteTemplateStorage → 删除，HE kb 持久化由 009 spec FR-003 `he feed` 承担 |
| 36 | DELETED | SqliteTemplateStorage | \\| IV. 避免过度设计 \\| PASS (post-design) \\| 版块清理后复杂度进一步降低：删除 ValidationEngine（移交 007 QG）、删除 SqliteTemplateStorage（移交 00... |
| 36 | DELETED | ValidationEngine | \\| IV. 避免过度设计 \\| PASS (post-design) \\| 版块清理后复杂度进一步降低：删除 ValidationEngine（移交 007 QG）、删除 SqliteTemplateStorage（移交 00... |
| 44 | DELETED | SqliteTemplateStorage | - **IV. 避免过度设计**: 版块清理后删除 ValidationEngine 和 SqliteTemplateStorage，复杂度进一步降低 ✓ |
| 44 | DELETED | ValidationEngine | - **IV. 避免过度设计**: 版块清理后删除 ValidationEngine 和 SqliteTemplateStorage，复杂度进一步降低 ✓ |
| 60 | DELETED | ValidationEngine | └── validation-engine.md # ValidationEngine 完整接口 |
| 77 | DELETED | validation_engine | │   (不再新建 validation_engine.py)    # 移交 007 QG |
| 92 | DELETED | validation_engine | │   (不再新建 test_validation_engine.py)  # 移交 007 QG |
| 93 | DELETED | sqlite_template_storage | │   (不再新建 test_sqlite_template_storage.py) # 移交 009 HE kb |
| 103 | DELETED | sqlite_template_storage | > **版块清理变更**：原 `services/validation_engine.py`（移交 007 QG）、原 `storage/sqlite_template_storage.py`（移交 009 HE kb）不再新建。 |
| 103 | DELETED | validation_engine | > **版块清理变更**：原 `services/validation_engine.py`（移交 007 QG）、原 `storage/sqlite_template_storage.py`（移交 009 HE kb）不再新建。 |
| 113 | DELETED | ValidationEngine | - ~~**ValidationEngine**: 4 维校验~~ **已移交 007 QG**（见 007 plan TDD Requirements） |
| 114 | DELETED | SqliteTemplateStorage | - ~~**SqliteTemplateStorage**: 持久化层~~ **已删除**（HE kb 原生承担，见 009） |
| 120 | DELETED | ValidationEngine | - ~~**TemplateEngine** 和 **ValidationEngine** 可并行~~ **已删除**（ValidationEngine 移交 007） |
| 120 | DELETED | ValidationEngine | - ~~**TemplateEngine** 和 **ValidationEngine** 可并行~~ **已删除**（ValidationEngine 移交 007） |
| 121 | DELETED | SqliteTemplateStorage | - ~~**SqliteTemplateStorage** 和 **HEAdapter 修复** 可并行~~ **已删除**（SqliteTemplateStorage 移交 009） |
| 121 | DELETED | SqliteTemplateStorage | - ~~**SqliteTemplateStorage** 和 **HEAdapter 修复** 可并行~~ **已删除**（SqliteTemplateStorage 移交 009） |
| 135 | DEPRECATED | he_templates | - [ ] **数据模型变更**: Review ExtractionSession 增强字段 before migration（~~he_templates 表~~ 已删除） |
| 162 | DELETED | ValidationEngine | 2. **contracts/**: 2 个接口契约文档（HEAdapter 含 feed_to_kb / TemplateEngine 不含 settle/get_settled），~~ValidationEngine 契约~~ 移... |
| 167 | DELETED | SqliteTemplateStorage | 由 `/speckit-tasks` 生成，按迁移顺序（先建新→修复→改写委托→删死代码→重建镜像）拆分为可独立验证的任务。**不再包含 ValidationEngine 和 SqliteTemplateStorage 相关任务**。 |
| 167 | DELETED | ValidationEngine | 由 `/speckit-tasks` 生成，按迁移顺序（先建新→修复→改写委托→删死代码→重建镜像）拆分为可独立验证的任务。**不再包含 ValidationEngine 和 SqliteTemplateStorage 相关任务**。 |

#### quickstart.md (7 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 9 | DELETED | ValidationEngine | > - §3 校验报告：006 不再执行 ValidationEngine 校验，由 007 QG 统一执行（instance 模式下也调用 QG，结果写入 session） |
| 10 | DELETED | SqliteTemplateStorage | > - §4 模板沉淀复用：SqliteTemplateStorage 已删除，改为 HE kb `feed_to_kb` 增量演化（委托 009 FR-003） |
| 11 | DELETED | sqlite_template_storage | > - §5 单元测试：移除 test_validation_engine.py / test_sqlite_template_storage.py |
| 11 | DELETED | validation_engine | > - §5 单元测试：移除 test_validation_engine.py / test_sqlite_template_storage.py |
| 77 | DELETED | SqliteTemplateStorage | # 注意：HE kb 持久化由 009 FR-003 管理，应用层不再维护 SqliteTemplateStorage |
| 85 | DELETED | sqlite_template_storage | # 运行全部单元测试（版块清理后移除 test_validation_engine.py / test_sqlite_template_storage.py） |
| 85 | DELETED | validation_engine | # 运行全部单元测试（版块清理后移除 test_validation_engine.py / test_sqlite_template_storage.py） |

#### spec.md (39 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 19 | REPLACED | add_episode | - `confirm_extraction` 双通道写入（Channel A: GraphWriteProxy→Neo4j, Channel B: GraphManager.add_episode→Graphiti） |
| 81 | DEPRECATED | he_templates | **Independent Test**: 触发自自定义生成后，验证生成的 YAML 符合 HE 模板规范且试抽评分达标；验证生成后**不**写 `data/he_templates/` 目录，**不**写 SQLite `he_te... |
| 81 | DEPRECATED | he_templates | **Independent Test**: 触发自自定义生成后，验证生成的 YAML 符合 HE 模板规范且试抽评分达标；验证生成后**不**写 `data/he_templates/` 目录，**不**写 SQLite `he_te... |
| 88 | DELETED | get_settled_template | 4. **Given** 同一本体再次抽取，**When** 系统进入模板评估，**Then** HE kb 已通过 `he feed` 增量演化（009 负责），评估时 HE 内部自动复用已有 kb 知识，应用层无 `get_set... |
| 95 | DELETED | ValidationEngine | > - 006 ValidationEngine **整体删除** |
| 146 | DELETED | get_settled_template | - **FR-012**: TemplateEngine.assess() 必须收集候选模板（本体生成 + 语义匹配预设），对每个候选调用 trial_extract 试抽，按加权评分排序。候选预筛选：对 30+ 预设先用 embed... |
| 151 | DELETED | settle_template | - **FR-017**: ~~TemplateEngine.settle_template()~~ **已删除**——模板持久化由 009 `HEAdapter.feed_to_kb()` 承担 |
| 152 | DELETED | get_settled_template | - **FR-018**: ~~TemplateEngine.get_settled_template()~~ **已删除**——模板复用由 HE kb 内部 `he feed` 增量演化承担 |
| 166 | DELETED | ValidationEngine | **~~ValidationEngine（4 维校验）~~ → 移交 007 QualityGateService** |
| 168 | DELETED | ValidationEngine | > **版块清理（2026-08-07）**：原 FR-025~030（ValidationEngine 4 维校验：Schema 一致性 / 完整性 / 置信度 / 引用一致性）整体移交 007 spec QualityGateSe... |
| 176 | DELETED | ValidationEngine | - **FR-025**: ~~ValidationEngine Schema 一致性校验~~ **已移交 007 QG-2** |
| 177 | DELETED | ValidationEngine | - **FR-026**: ~~ValidationEngine 完整性评估~~ **已移交 007 QG-1** |
| 178 | DELETED | ValidationEngine | - **FR-027**: ~~ValidationEngine 置信度评分~~ **已移交 007 QG-1** |
| 179 | DELETED | ValidationEngine | - **FR-028**: ~~ValidationEngine 引用一致性检查~~ **已移交 007 QG-2** |
| 184 | DEPRECATED | he_templates | > **版块清理（2026-08-07）**：原 FR-030/031（SQLite he_templates 表 + YAML 落盘）整体删除。HE kb 持久化由 009 FR-003 定义。 |
| 186 | DEPRECATED | he_templates | - **FR-030**: ~~SQLite he_templates 表~~ **已删除**——HE kb 内部持久化 |
| 221 | DELETED | validation_engine | └── (删除 validation_engine.py)      # 移交 007 QualityGateService |
| 222 | DELETED | sqlite_template_storage | (删除 sqlite_template_storage.py) # 移交 009 HE kb |
| 233 | DELETED | validation_engine | > - 删除 `services/validation_engine.py`（移交 007 QG） |
| 234 | DELETED | sqlite_template_storage | > - 删除 `storage/sqlite_template_storage.py`（移交 009 HE kb） |
| 235 | DELETED | get_settled_template | > - `template_engine.py` 不再包含 `settle_template` / `get_settled_template` |
| 235 | DELETED | settle_template | > - `template_engine.py` 不再包含 `settle_template` / `get_settled_template` |
| 249 | DELETED | ValidationEngine | 10. ~~ValidationEngine.validate()~~ **已移交 007 QG**——instance 模式下由 007 QG 做即时校验 |
| 276 | DELETED | get_settled_template | # 已删除: settle_template, get_settled_template（HE kb 原生承担，见 009 FR-003） |
| 276 | DELETED | settle_template | # 已删除: settle_template, get_settled_template（HE kb 原生承担，见 009 FR-003） |
| 279 | DELETED | ValidationEngine | ### ~~ValidationEngine 接口契约~~ → 已移交 007 QualityGateService |
| 281 | DELETED | ValidationEngine | > 原 `ValidationEngine.validate() / _validate_schema() / _validate_completeness() / _score_confidence() / _validate_re... |
| 293 | DELETED | ValidationEngine | \\| ~~ValidationEngine 异常~~ \\| ~~校验失败不阻断~~ **已移交 007 QG**（007 QG 异常时标记 qg_skipped，见 007 EC-018） \\| ~~EC-018~~ \\| |
| 307 | DELETED | validation_engine | \\| ~~test_validation_engine.py~~ \\| ~~4 维校验全路径~~ **已移交 007 QG**（见 007 test_quality_gate_1_2.py） \\| - \\| |
| 308 | DELETED | sqlite_template_storage | \\| ~~test_sqlite_template_storage.py~~ \\| ~~CRUD + 去重 + usage_count~~ **已删除**（HE kb 原生承担，见 009） \\| - \\| |
| 334 | DELETED | sqlite_template_storage | 1. 先建新组件（TemplateEngine）+ 单元测试（**不再建 ValidationEngine / sqlite_template_storage**） |
| 334 | DELETED | ValidationEngine | 1. 先建新组件（TemplateEngine）+ 单元测试（**不再建 ValidationEngine / sqlite_template_storage**） |
| 359 | DELETED | validation_engine | \\| ~~新建~~ \\| ~~data/hyper_extract/services/validation_engine.py~~ **不再新建**（移交 007 QG） \\| |
| 360 | DELETED | sqlite_template_storage | \\| ~~新建~~ \\| ~~data/hyper_extract/storage/sqlite_template_storage.py~~ **不再新建**（移交 009 HE kb） \\| |
| 420 | DELETED | ValidationEngine | - ~~**EC-018**: ValidationEngine 异常~~ **已移交 007 QG**（007 QG 异常时标记 qg_skipped） |
| 457 | DELETED | ValidationEngine | \\| 2 \\| ValidationEngine 4 维校验 \\| **整体移交 007 QG**（FR-024~029） \\| 与 007 的 3 关质量闸在置信度/结构/引用上高度重叠；QG-1 扩展完整性，QG-2 扩展... |
| 459 | REPLACED | add_episode | \\| 4 \\| Channel B 实现 \\| **规范统一归 009**（save_audit_episode 零 LLM） \\| 006 保留旧 add_episode 方案与 009 直接矛盾；009 research.... |
| 459 | REPLACED | add_episode | \\| 4 \\| Channel B 实现 \\| **规范统一归 009**（save_audit_episode 零 LLM） \\| 006 保留旧 add_episode 方案与 009 直接矛盾；009 research.... |
| 463 | DELETED | ValidationEngine | **影响范围**: 006 删除 ~30% 内容（模板沉淀 + ValidationEngine + Channel B 实现描述）；007 扩展 QG-1/QG-2；009 明确承接移交职责。 |

#### tasks.md (73 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 12 | DEPRECATED | he_templates | > \\| T002-T005 \\| `SqliteTemplateStorage` + `he_templates` 表 DDL \\| **删除** \\| 009 FR-003 `he feed` \\| |
| 12 | DELETED | SqliteTemplateStorage | > \\| T002-T005 \\| `SqliteTemplateStorage` + `he_templates` 表 DDL \\| **删除** \\| 009 FR-003 `he feed` \\| |
| 13 | DELETED | get_settled_template | > \\| T027, T031-T032, T035-T036 \\| `settle_template` / `get_settled_template` \\| **删除** \\| 009 HE kb 增量演化 \\| |
| 13 | DELETED | settle_template | > \\| T027, T031-T032, T035-T036 \\| `settle_template` / `get_settled_template` \\| **删除** \\| 009 HE kb 增量演化 \\| |
| 14 | DELETED | ValidationEngine | > \\| T038-T049 \\| `ValidationEngine` 4 维校验 \\| **移交** \\| 007 QG-1/QG-2（22 子指标） \\| |
| 15 | DELETED | ValidationEngine | > \\| T053-T054, T059, T062 \\| ExtractService 中 ValidationEngine 集成 \\| **移除** \\| 006 抽取后不再校验，由 007 QG 执行 \\| |
| 42 | DEPRECATED | he_templates | - **Template YAML**: `data/he_templates/{ontology_id}/` at repository root |
| 50 | DEPRECATED | he_templates | - [X] T001 Create `data/he_templates/` directory structure for YAML template persistence (with `.gitkeep` for empty o... |
| 51 | DELETED | sqlite_template_storage | - [X] T002 Create SQLite DDL migration for `he_templates` table (id, ontology_id, name, description, source, yaml_pat... |
| 51 | DEPRECATED | he_templates | - [X] T002 Create SQLite DDL migration for `he_templates` table (id, ontology_id, name, description, source, yaml_pat... |
| 51 | DEPRECATED | he_templates | - [X] T002 Create SQLite DDL migration for `he_templates` table (id, ontology_id, name, description, source, yaml_pat... |
| 52 | DELETED | sqlite_template_storage | - [X] T003 Create `extraction_provenance` ALTER migration: add `source_template TEXT` column in `odap/biz/data/hyper_... |
| 64 | DELETED | sqlite_template_storage | - [X] T004 [TDD] Write failing tests for SqliteTemplateStorage CRUD (save, get_by_id, get_by_ontology, update_usage_c... |
| 64 | DELETED | SqliteTemplateStorage | - [X] T004 [TDD] Write failing tests for SqliteTemplateStorage CRUD (save, get_by_id, get_by_ontology, update_usage_c... |
| 65 | DELETED | sqlite_template_storage | - [X] T005 Implement SqliteTemplateStorage class (save, get_by_id, get_by_ontology, update_usage_count, list_all) in ... |
| 65 | DELETED | SqliteTemplateStorage | - [X] T005 Implement SqliteTemplateStorage class (save, get_by_id, get_by_ontology, update_usage_count, list_all) in ... |
| 66 | DEPRECATED | he_templates | - [X] T006 [REVIEW] Review he_templates schema and ExtractionSession enhancement fields — verify DDL matches `data-mo... |
| 120 | DELETED | SqliteTemplateStorage | - [X] T024 [US1] Implement TemplateEngine.__init__() — accept HEAdapter and SqliteTemplateStorage, cache embedder ins... |
| 123 | DELETED | get_settled_template | - [X] T027 [US1] Implement TemplateEngine.assess() — step 1: get_settled_template lightweight validation; step 2: if ... |
| 127 | DELETED | SqliteTemplateStorage | **Execution notes**: T021-T023 tests must FAIL before T024-T029 implementation. TemplateEngine depends on HEAdapter (... |
| 136 | DEPRECATED | he_templates | **Independent Test**: Trigger custom generation → YAML file at `data/he_templates/{ontology_id}/{name}.yaml` → SQLite... |
| 136 | DEPRECATED | he_templates | **Independent Test**: Trigger custom generation → YAML file at `data/he_templates/{ontology_id}/{name}.yaml` → SQLite... |
| 141 | DELETED | SqliteTemplateStorage | - [X] T031 [TDD] [US3] Write failing tests for TemplateEngine.settle_template() — verify YAML written to `data/he_tem... |
| 141 | DEPRECATED | he_templates | - [X] T031 [TDD] [US3] Write failing tests for TemplateEngine.settle_template() — verify YAML written to `data/he_tem... |
| 141 | DELETED | settle_template | - [X] T031 [TDD] [US3] Write failing tests for TemplateEngine.settle_template() — verify YAML written to `data/he_tem... |
| 142 | DELETED | SqliteTemplateStorage | - [X] T032 [TDD] [US3] Write failing tests for TemplateEngine.get_settled_template() — verify SqliteTemplateStorage.g... |
| 142 | DELETED | get_settled_template | - [X] T032 [TDD] [US3] Write failing tests for TemplateEngine.get_settled_template() — verify SqliteTemplateStorage.g... |
| 148 | DELETED | SqliteTemplateStorage | - [X] T035 [US3] Implement TemplateEngine.settle_template() — write YAML to `data/he_templates/{ontology_id}/{name}.y... |
| 148 | DEPRECATED | he_templates | - [X] T035 [US3] Implement TemplateEngine.settle_template() — write YAML to `data/he_templates/{ontology_id}/{name}.y... |
| 148 | DELETED | settle_template | - [X] T035 [US3] Implement TemplateEngine.settle_template() — write YAML to `data/he_templates/{ontology_id}/{name}.y... |
| 149 | DELETED | SqliteTemplateStorage | - [X] T036 [US3] Implement TemplateEngine.get_settled_template() — call SqliteTemplateStorage.get_by_ontology, verify... |
| 149 | DELETED | SqliteTemplateStorage | - [X] T036 [US3] Implement TemplateEngine.get_settled_template() — call SqliteTemplateStorage.get_by_ontology, verify... |
| 149 | DELETED | get_settled_template | - [X] T036 [US3] Implement TemplateEngine.get_settled_template() — call SqliteTemplateStorage.get_by_ontology, verify... |
| 152 | DELETED | SqliteTemplateStorage | **Execution notes**: T030-T033 tests must FAIL before T034-T037 implementation. US3 depends on TemplateEngine from US... |
| 163 | DELETED | ValidationEngine | **PARALLEL OPPORTUNITY**: This phase can run in parallel with Phase 4 and Phase 5 (ValidationEngine has no dependency... |
| 167 | DELETED | validation_engine | - [X] T038 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_schema() — type mismatch detection, req... |
| 167 | DELETED | ValidationEngine | - [X] T038 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_schema() — type mismatch detection, req... |
| 168 | DELETED | validation_engine | - [X] T039 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_completeness() — fill_rate calculation,... |
| 168 | DELETED | ValidationEngine | - [X] T039 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_completeness() — fill_rate calculation,... |
| 169 | DELETED | validation_engine | - [X] T040 [P] [TDD] [US4] Write failing tests for ValidationEngine._score_confidence() — 0.4*fill + 0.3*template + 0... |
| 169 | DELETED | ValidationEngine | - [X] T040 [P] [TDD] [US4] Write failing tests for ValidationEngine._score_confidence() — 0.4*fill + 0.3*template + 0... |
| 170 | DELETED | validation_engine | - [X] T041 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_references() — dangling relations (sour... |
| 170 | DELETED | ValidationEngine | - [X] T041 [P] [TDD] [US4] Write failing tests for ValidationEngine._validate_references() — dangling relations (sour... |
| 171 | DELETED | validation_engine | - [X] T042 [P] [TDD] [US4] Write failing tests for ValidationEngine.validate() — orchestrates 4 dims, builds summary ... |
| 171 | DELETED | ValidationEngine | - [X] T042 [P] [TDD] [US4] Write failing tests for ValidationEngine.validate() — orchestrates 4 dims, builds summary ... |
| 172 | DELETED | validation_engine | - [X] T043 [P] [TDD] [US4] Write failing tests for edge cases — empty result, all violations, all passed, validation ... |
| 176 | DELETED | validation_engine | - [X] T044 [P] [US4] Implement ValidationEngine.__init__() — accept confidence_threshold (default 0.6, configurable v... |
| 176 | DELETED | ValidationEngine | - [X] T044 [P] [US4] Implement ValidationEngine.__init__() — accept confidence_threshold (default 0.6, configurable v... |
| 177 | DELETED | validation_engine | - [X] T045 [P] [US4] Implement ValidationEngine._validate_schema() — iterate entities, check field types vs ObjectTyp... |
| 177 | DELETED | ValidationEngine | - [X] T045 [P] [US4] Implement ValidationEngine._validate_schema() — iterate entities, check field types vs ObjectTyp... |
| 178 | DELETED | validation_engine | - [X] T046 [P] [US4] Implement ValidationEngine._validate_completeness() — compute fill_rate (filled required / total... |
| 178 | DELETED | ValidationEngine | - [X] T046 [P] [US4] Implement ValidationEngine._validate_completeness() — compute fill_rate (filled required / total... |
| 179 | DELETED | validation_engine | - [X] T047 [P] [US4] Implement ValidationEngine._score_confidence() — per entity: 0.4*fill_rate + 0.3*template_score ... |
| 179 | DELETED | ValidationEngine | - [X] T047 [P] [US4] Implement ValidationEngine._score_confidence() — per entity: 0.4*fill_rate + 0.3*template_score ... |
| 180 | DELETED | validation_engine | - [X] T048 [P] [US4] Implement ValidationEngine._validate_references() — check relation source/target exist in entiti... |
| 180 | DELETED | ValidationEngine | - [X] T048 [P] [US4] Implement ValidationEngine._validate_references() — check relation source/target exist in entiti... |
| 181 | DELETED | validation_engine | - [X] T049 [P] [US4] Implement ValidationEngine.validate() — call 4 private methods, build summary, wrap in try/excep... |
| 181 | DELETED | ValidationEngine | - [X] T049 [P] [US4] Implement ValidationEngine.validate() — call 4 private methods, build summary, wrap in try/excep... |
| 183 | DELETED | ValidationEngine | **Execution notes**: T038-T043 tests must FAIL before T044-T049 implementation. All tasks in this phase are [P] — Val... |
| 199 | DELETED | ValidationEngine | - [X] T053 [TDD] [US2] Write failing tests for ExtractService.extract_from_nl() — verify orchestration: assess → sele... |
| 200 | DELETED | ValidationEngine | - [X] T054 [TDD] [US2] Write failing tests for ValidationEngine integration — verify validation_report written to ses... |
| 208 | DELETED | ValidationEngine | - [X] T059 [US2] Implement new ExtractService.extract_from_nl() — full orchestration: create session → TemplateEngine... |
| 211 | DELETED | ValidationEngine | - [X] T062 [US2] Integrate ValidationEngine into ExtractService — call validate() after merge_and_map(), write valida... |
| 213 | REPLACED | add_episode | - [X] T064 [US2] Preserve confirm_extraction dual-channel write — reuse existing DualChannelWriter (Channel A: GraphW... |
| 217 | DELETED | ValidationEngine | **Execution notes**: T050-T054 tests must FAIL before T055-T065 implementation. US2 depends on ALL prior phases: HEAd... |
| 255 | DELETED | SqliteTemplateStorage | - **US1 (Phase 4)**: Depends on US5 (needs HEAdapter.trial_extract) + Foundational (needs SqliteTemplateStorage) |
| 258 | DELETED | ValidationEngine | - **US2 (Phase 7)**: Depends on US1 + US3 + US4 (needs select_complementary, OntologyMapper, ValidationEngine) |
| 271 | DELETED | SqliteTemplateStorage | - **Phase 2**: SqliteTemplateStorage (T004-T005) can parallel with Phase 1 DDL (T002-T003) if using stub DDL |
| 274 | DELETED | ValidationEngine | - **Phase 6 (US4)**: ENTIRE phase can run in parallel with Phase 4 (US1) and Phase 5 (US3) — ValidationEngine is stan... |
| 280 | DELETED | SqliteTemplateStorage | 1. ✅ Phase 2: Build new storage component (SqliteTemplateStorage) + unit tests |
| 282 | DELETED | ValidationEngine | 3. ✅ Phase 4-6: Build new service components (TemplateEngine, ValidationEngine) + unit tests |
| 312 | DELETED | SqliteTemplateStorage | **MVP = Phase 1 + Phase 2 + Phase 3 (US5)** — HEAdapter fixed with real API alignment, SqliteTemplateStorage ready, D... |
| 325 | DELETED | ValidationEngine | - **Phase 6 (US4 ValidationEngine)**: Ideal subagent candidate — standalone, pure logic, no external dependencies, we... |

#### template-engine.md (11 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 6 | DELETED | settle_template | > - `settle_template()` — 已删除（原 FR-017） |
| 7 | DELETED | get_settled_template | > - `get_settled_template()` — 已删除（原 FR-018） |
| 8 | DELETED | SqliteTemplateStorage | > - `SqliteTemplateStorage` 依赖 — 已删除（HE kb 原生管理） |
| 10 | DELETED | SqliteTemplateStorage | > `__init__` 不再接收 `storage: SqliteTemplateStorage` 参数。模板评估时 HE kb 内部已有的知识由 `he feed` 自动复用。 |
| 24 | DELETED | SqliteTemplateStorage | def __init__(self, he_adapter: HEAdapter, storage: SqliteTemplateStorage): |
| 50 | DELETED | get_settled_template | 1. get_settled_template(ontology_id) → 若有沉淀模板，轻量验证（500字符试抽，score≥阈值80%） |
| 84 | DELETED | settle_template | def settle_template(self, ontology_id: str, name: str, yaml_content: str, score: float, coverage: List[str]) -> str: |
| 91 | DEPRECATED | he_templates | - YAML 写入 data/he_templates/{ontology_id}/{name}.yaml |
| 92 | DEPRECATED | he_templates | - 元数据存入 he_templates 表 |
| 95 | DELETED | get_settled_template | def get_settled_template(self, ontology_id: str) -> Optional[Dict[str, Any]]: |
| 111 | DELETED | SqliteTemplateStorage | - SqliteTemplateStorage (settle/get_settled) |

#### validation-engine.md (4 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 1 | DELETED | ValidationEngine | # Contract: ValidationEngine |
| 5 | DELETED | ValidationEngine | > **ValidationEngine 已整体移交 007 spec QualityGateService**，本契约文件保留仅作历史参考。 |
| 20 | DELETED | validation_engine | **Location**: `odap/biz/data/hyper_extract/services/validation_engine.py`（**不再新建**） |
| 30 | DELETED | ValidationEngine | class ValidationEngine: |

### A. 007-semantic-admin-suite（71 hits）


#### data-model.md (2 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 288 | DELETED | ValidationEngine | > **版块清理（2026-08-07）**：G1 从 7 项扩展到 10 项（+3 完整性，从 006 ValidationEngine 移交），G2 从 4 项扩展到 7 项（+3 引用一致性，从 006 ValidationEn... |
| 288 | DELETED | ValidationEngine | > **版块清理（2026-08-07）**：G1 从 7 项扩展到 10 项（+3 完整性，从 006 ValidationEngine 移交），G2 从 4 项扩展到 7 项（+3 引用一致性，从 006 ValidationEn... |

#### plan.md (6 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 16 | STALE_COUNT | 16 子指标 | > 1. **QG-1 扩展**：质量闸第 1 关在原有置信度 + Jaccard 去重基础上，**新增完整性指标**（fill_rate/empty_rate/orphan_count），从 006 ValidationEngine... |
| 16 | DELETED | ValidationEngine | > 1. **QG-1 扩展**：质量闸第 1 关在原有置信度 + Jaccard 去重基础上，**新增完整性指标**（fill_rate/empty_rate/orphan_count），从 006 ValidationEngine... |
| 17 | DELETED | ValidationEngine | > 2. **QG-2 扩展**：质量闸第 2 关在原有结构一致性基础上，**新增引用一致性**（dangling_relations/invalid_action_targets/invalid_rule_references），从... |
| 19 | REPLACED | UnifiedAudit.log_action | > 4. **审计统一**：原 plan 中直接调用 `UnifiedAudit.log_action` 的地方，统一改为委托 009 分层审计（audit_helper）。usl_outbox 保留（TBox 双写专用） |
| 176 | DELETED | ValidationEngine | │   │   ├── gate1_syntactic_impl.py  # G1 × 10 子项: 名称合规/en_mapping可用/semantic_type枚举/同义词大小/去重率/环检测/USL冲突 + 完整性(fill_r... |
| 177 | DELETED | ValidationEngine | │   │   ├── gate2_semantic_impl.py   # G2 × 7 子项: Disjoint不相交/基数约束/is_a无环/LLM语义一致性Judge(默认关) + 引用一致性(dangling_relatio... |

#### quality-gate-approval.md (3 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 5 | DELETED | ValidationEngine | > 质量闸从 3 关 × 16 子指标扩展为 **3 关 × 22 子指标**（从 006 ValidationEngine 移交 6 项）： |
| 5 | STALE_COUNT | 16 子指标 | > 质量闸从 3 关 × 16 子指标扩展为 **3 关 × 22 子指标**（从 006 ValidationEngine 移交 6 项）： |
| 10 | DELETED | ValidationEngine | > 006 ValidationEngine 契约已废弃（见 `specs/006-he-extraction-chain/contracts/validation-engine.md` 顶部声明）。 |

#### quickstart.md (2 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 403 | STALE_COUNT | G2×4 | #   [Step 3] C4 质量闸 G1×7 + G2×4 + G3×5 = 16 submetrics 评估 |
| 403 | STALE_COUNT | G1×7 | #   [Step 3] C4 质量闸 G1×7 + G2×4 + G3×5 = 16 submetrics 评估 |

#### requirements.md (18 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 8 | STALE_COUNT | G2×4 | > 以下标记为 Done 的 FR-030/FR-031/NFR-004/检查项 #3 在清理前按 **16 子指标**（G1×7/G2×4/G3×5）验收。 |
| 8 | STALE_COUNT | G1×7 | > 以下标记为 Done 的 FR-030/FR-031/NFR-004/检查项 #3 在清理前按 **16 子指标**（G1×7/G2×4/G3×5）验收。 |
| 8 | STALE_COUNT | 16 子指标 | > 以下标记为 Done 的 FR-030/FR-031/NFR-004/检查项 #3 在清理前按 **16 子指标**（G1×7/G2×4/G3×5）验收。 |
| 9 | DELETED | ValidationEngine | > 版块清理后扩展为 **22 子指标**（G1×10/G2×7/G3×5，+6 项从 006 ValidationEngine 移交），需追加验收： |
| 48 | STALE_COUNT | G1×7 | \\| FR-030 \\| QualityReport JSON 结构：16 子指标 + 3 门总分 + running_time_ms + overall 1st_failed_gate \\| I3T2 QualityGateS... |
| 48 | STALE_COUNT | G2×4 | \\| FR-030 \\| QualityReport JSON 结构：16 子指标 + 3 门总分 + running_time_ms + overall 1st_failed_gate \\| I3T2 QualityGateS... |
| 48 | STALE_COUNT | 16 子指标 | \\| FR-030 \\| QualityReport JSON 结构：16 子指标 + 3 门总分 + running_time_ms + overall 1st_failed_gate \\| I3T2 QualityGateS... |
| 48 | STALE_COUNT | 16 子指标 | \\| FR-030 \\| QualityReport JSON 结构：16 子指标 + 3 门总分 + running_time_ms + overall 1st_failed_gate \\| I3T2 QualityGateS... |
| 49 | STALE_COUNT | 16 子指标 | \\| FR-031 \\| 16 子指标权重公式：总分=0.35*G1 + 0.40*G2 + 0.25*G3；总≥0.9 Auto-Skip-Admin \\| I3T2 加权公式 \\| US5 \\| tests/unit/t... |
| 50 | STALE_COUNT | G2×4 | \\| FR-032 \\| OPA 质量闸阈值 Rego 规则 16 条：quality_gate.rego（G1×7/G2×4/G3×5）deny 独立触发 \\| I3T6 \\| US5 \\| tests/unit/test... |
| 50 | STALE_COUNT | G1×7 | \\| FR-032 \\| OPA 质量闸阈值 Rego 规则 16 条：quality_gate.rego（G1×7/G2×4/G3×5）deny 独立触发 \\| I3T6 \\| US5 \\| tests/unit/test... |
| 82 | STALE_COUNT | G2×4 | \\| NFR-004 \\| 质量闸纯计算 P95 ≤ 100ms（16 子指标 G1×7+G2×4+G3×5，不含 QG-3 LLM）；批量 ≤ (100/4)*15s \\| I3T2 QualityGateService + ... |
| 82 | STALE_COUNT | G1×7 | \\| NFR-004 \\| 质量闸纯计算 P95 ≤ 100ms（16 子指标 G1×7+G2×4+G3×5，不含 QG-3 LLM）；批量 ≤ (100/4)*15s \\| I3T2 QualityGateService + ... |
| 82 | STALE_COUNT | 16 子指标 | \\| NFR-004 \\| 质量闸纯计算 P95 ≤ 100ms（16 子指标 G1×7+G2×4+G3×5，不含 QG-3 LLM）；批量 ≤ (100/4)*15s \\| I3T2 QualityGateService + ... |
| 118 | STALE_COUNT | G2×4 | \\| 3 \\| 质量闸 16 子指标（G1×7/G2×4/G3×5）+ 加权公式 \\| 16 子指标齐全；权重 0.35/0.40/0.25；总≥0.9 Auto-Skip \\| `pytest test_quality_ga... |
| 118 | STALE_COUNT | 16 子指标 | \\| 3 \\| 质量闸 16 子指标（G1×7/G2×4/G3×5）+ 加权公式 \\| 16 子指标齐全；权重 0.35/0.40/0.25；总≥0.9 Auto-Skip \\| `pytest test_quality_ga... |
| 118 | STALE_COUNT | 16 子指标 | \\| 3 \\| 质量闸 16 子指标（G1×7/G2×4/G3×5）+ 加权公式 \\| 16 子指标齐全；权重 0.35/0.40/0.25；总≥0.9 Auto-Skip \\| `pytest test_quality_ga... |
| 118 | STALE_COUNT | G1×7 | \\| 3 \\| 质量闸 16 子指标（G1×7/G2×4/G3×5）+ 加权公式 \\| 16 子指标齐全；权重 0.35/0.40/0.25；总≥0.9 Auto-Skip \\| `pytest test_quality_ga... |

#### spec.md (14 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 15 | DELETED | ValidationEngine | > \\| ValidationEngine 4 维校验 \\| 006 FR-024~029 \\| FR-027 (QG-1) + FR-028 (QG-2) \\| 置信度 + 完整性 → QG-1；Schema 一致性 + 引... |
| 17 | DELETED | ValidationEngine | > \\| instance 模式即时校验 \\| 006 ValidationEngine \\| FR-027/028 扩展 \\| instance 模式下也调用 QG 做即时校验，结果写入 ExtractionSession \\| |
| 55 | DEPRECATED | he_templates | - `data/he_templates/` 模板沉淀目录结构 + SQLite he_templates 表（SP1 已建） |
| 55 | DEPRECATED | he_templates | - `data/he_templates/` 模板沉淀目录结构 + SQLite he_templates 表（SP1 已建） |
| 56 | DEPRECATED | he_templates | - `he_templates` 表字段：id, ontology_id, name, description, source, yaml_path, preset_name, score, coverage, usage_count... |
| 57 | REPLACED | UnifiedAudit.log_action | - `UnifiedAudit.log_action()` 统一审计接口（`odap.infra.security.unified_audit`，可选导入） |
| 188 | REPLACED | UnifiedAudit.log_action | 4. **Given** status=l1_approved，**When** 全局管理员（role=semantic_global_admin）调用 `POST /api/semantic/approvals/merge`（bod... |
| 306 | REPLACED | UnifiedAudit.log_action | - **FR-034**: 审批流状态机（严格，非法转换抛 ValueError）：`proposed →(run QG)→ qg_passed / qg_failed`；`qg_passed →(L1 approve)→ l1_ap... |
| 406 | DELETED | ValidationEngine | \\| 1 \\| `biz/data/hyper_extract`（SP1） \\| 006-he-extraction-chain 合并后 \\| ExtractService / HEAdapter / TemplateEngi... |
| 448 | DEPRECATED | he_templates | - [ ] `/data/models/`、`/data/backups/semantic/`、`/data/he_templates/` 目录存在且可写（非只读挂载） |
| 731 | REPLACED | UnifiedAudit.log_action | 5. `UnifiedAudit.log_action` 写入不会阻塞主流程（异步队列 + 丢 data 容忍，NFR-009 要求） |
| 810 | DELETED | ValidationEngine | \\| 1 \\| QG-1 扩展 \\| 在置信度 + Jaccard 去重基础上，加入完整性指标（fill_rate/empty_rate/orphan_count） \\| 从 006 ValidationEngine 移交，避... |
| 811 | DELETED | ValidationEngine | \\| 2 \\| QG-2 扩展 \\| 在结构一致性基础上，加入引用一致性（dangling_relations/invalid_action_targets/invalid_rule_references） \\| 从 006 ... |
| 812 | DELETED | ValidationEngine | \\| 3 \\| instance 模式即时校验 \\| QG-1/QG-2 在 instance 模式下也调用，结果写入 ExtractionSession.validation_report \\| 006 不再有自己的 Val... |

#### tasks.md (26 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 8 | STALE_COUNT | G2×4 | > 以下标记为 `done` 的任务在清理前按 **16 子指标**（G1×7/G2×4/G3×5）实现。版块清理后扩展为 **22 子指标**（G1×10/G2×7/G3×5，+6 项从 006 ValidationEngine 移交）。 |
| 8 | DELETED | ValidationEngine | > 以下标记为 `done` 的任务在清理前按 **16 子指标**（G1×7/G2×4/G3×5）实现。版块清理后扩展为 **22 子指标**（G1×10/G2×7/G3×5，+6 项从 006 ValidationEngine 移交）。 |
| 8 | STALE_COUNT | 16 子指标 | > 以下标记为 `done` 的任务在清理前按 **16 子指标**（G1×7/G2×4/G3×5）实现。版块清理后扩展为 **22 子指标**（G1×10/G2×7/G3×5，+6 项从 006 ValidationEngine 移交）。 |
| 8 | STALE_COUNT | G1×7 | > 以下标记为 `done` 的任务在清理前按 **16 子指标**（G1×7/G2×4/G3×5）实现。版块清理后扩展为 **22 子指标**（G1×10/G2×7/G3×5，+6 项从 006 ValidationEngine 移交）。 |
| 85 | STALE_COUNT | G2×4 | \\| I3T2 \\| 在 `odap/biz/semantic_admin/quality_gate/services/` 下实现 `QualityGateService.evaluate(cand_id) -> QualityR... |
| 85 | STALE_COUNT | G1×7 | \\| I3T2 \\| 在 `odap/biz/semantic_admin/quality_gate/services/` 下实现 `QualityGateService.evaluate(cand_id) -> QualityR... |
| 85 | STALE_COUNT | 16 子指标 | \\| I3T2 \\| 在 `odap/biz/semantic_admin/quality_gate/services/` 下实现 `QualityGateService.evaluate(cand_id) -> QualityR... |
| 93 | STALE_COUNT | G2×4 | \\| I3T10 \\| 5 条 Quality+Approval API（统一前缀 `/api/semantic-admin/*`）：`GET /quality-gate/reports/{cand_id}`（返回 16 子指标 ... |
| 93 | STALE_COUNT | G1×7 | \\| I3T10 \\| 5 条 Quality+Approval API（统一前缀 `/api/semantic-admin/*`）：`GET /quality-gate/reports/{cand_id}`（返回 16 子指标 ... |
| 93 | STALE_COUNT | 16 子指标 | \\| I3T10 \\| 5 条 Quality+Approval API（统一前缀 `/api/semantic-admin/*`）：`GET /quality-gate/reports/{cand_id}`（返回 16 子指标 ... |
| 94 | STALE_COUNT | G1×7 | \\| I3T11 \\| 前端 Quality Tab（原 5 Tab 第 5 个）重命名为 "审核台"：左栏待办任务（按全局 role + ws_role 过滤）+ 中栏 Candidate 详情 + 右栏 16 指标雷达图（Re... |
| 94 | STALE_COUNT | G2×4 | \\| I3T11 \\| 前端 Quality Tab（原 5 Tab 第 5 个）重命名为 "审核台"：左栏待办任务（按全局 role + ws_role 过滤）+ 中栏 Candidate 详情 + 右栏 16 指标雷达图（Re... |
| 94 | STALE_COUNT | G1×7 | \\| I3T11 \\| 前端 Quality Tab（原 5 Tab 第 5 个）重命名为 "审核台"：左栏待办任务（按全局 role + ws_role 过滤）+ 中栏 Candidate 详情 + 右栏 16 指标雷达图（Re... |
| 94 | STALE_COUNT | G2×4 | \\| I3T11 \\| 前端 Quality Tab（原 5 Tab 第 5 个）重命名为 "审核台"：左栏待办任务（按全局 role + ws_role 过滤）+ 中栏 Candidate 详情 + 右栏 16 指标雷达图（Re... |
| 95 | STALE_COUNT | G2×4 | \\| I3T12 \\| 前端 16 指标详情面板（G1×7/G2×4/G3×5 分组折叠）：每个指标 hover tooltip 展示 rule_name / actual_value / threshold / reason；t... |
| 95 | STALE_COUNT | G1×7 | \\| I3T12 \\| 前端 16 指标详情面板（G1×7/G2×4/G3×5 分组折叠）：每个指标 hover tooltip 展示 rule_name / actual_value / threshold / reason；t... |
| 97 | STALE_COUNT | G2×4 | \\| I3T14 \\| Iter3 集成测试：启动 Pipeline → Candidates 生成 → evaluate（G1×7/G2×4/G3×5 新拆法，权重 0.35/0.40/0.25）→ 16 指标 ≥ 0.5 → ... |
| 97 | STALE_COUNT | G1×7 | \\| I3T14 \\| Iter3 集成测试：启动 Pipeline → Candidates 生成 → evaluate（G1×7/G2×4/G3×5 新拆法，权重 0.35/0.40/0.25）→ 16 指标 ≥ 0.5 → ... |
| 113 | REPLACED | add_episode | \\| I4T6 \\| 在 `odap/biz/semantic_admin/usl_writeback/services/` 下实现 `OntologyWritebackService`：接收 approved 状态的 candi... |
| 119 | STALE_COUNT | G2×4 | \\| I4T12 \\| 电商演示脚本：`examples/semantic_admin_ecommerce_demo.py` — ① Seed 电商 domain（产品/分类/属性/规格/品牌 200+ 术语，通过 usl_man... |
| 119 | STALE_COUNT | G1×7 | \\| I4T12 \\| 电商演示脚本：`examples/semantic_admin_ecommerce_demo.py` — ① Seed 电商 domain（产品/分类/属性/规格/品牌 200+ 术语，通过 usl_man... |
| 120 | STALE_COUNT | G2×4 | \\| I4T13 \\| Feature E2E 测试：`tests/e2e/test_semantic_admin_full.py` — ① 创建电商 domain ② Seed ③ 上传文本启动 Pipeline（`/api/s... |
| 120 | STALE_COUNT | G1×7 | \\| I4T13 \\| Feature E2E 测试：`tests/e2e/test_semantic_admin_full.py` — ① 创建电商 domain ② Seed ③ 上传文本启动 Pipeline（`/api/s... |
| 162 | STALE_COUNT | G2×4 | \\| Quality + Approval（quality_gate + approval_workflow，Iter3） \\| 15 \\| Gate 3×/16 子指标（拆法 G1×7/G2×4/G3×5；权重 0.35/0.... |
| 162 | STALE_COUNT | G1×7 | \\| Quality + Approval（quality_gate + approval_workflow，Iter3） \\| 15 \\| Gate 3×/16 子指标（拆法 G1×7/G2×4/G3×5；权重 0.35/0.... |
| 162 | STALE_COUNT | 16 子指标 | \\| Quality + Approval（quality_gate + approval_workflow，Iter3） \\| 15 \\| Gate 3×/16 子指标（拆法 G1×7/G2×4/G3×5；权重 0.35/0.... |

### A. 009-intel-driven-architecture（19 hits）


#### plan.md (5 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 9 | DELETED | SqliteTemplateStorage | > \\| HE kb 持久化（`he feed`） \\| 006 SqliteTemplateStorage \\| FR-003 \\| ✅ 已实现（Iter 2） \\| |
| 11 | REPLACED | UnifiedAudit.log_action | > \\| 操作审计统一（audit_helper） \\| 007 UnifiedAudit.log_action \\| FR-006 \\| ✅ 已实现（Iter 3） \\| |
| 13 | DELETED | ValidationEngine | > **注意**：006/007 的代码层面需按各自 spec.md 清理后版本删除应用层模板沉淀、ValidationEngine，并改为委托本 plan 已实现的能力。 |
| 95 | DELETED | get_settled_template | - [x] `settle_template` / `get_settled_template` / `_validate_settled` 已从 TemplateEngine 移除 |
| 95 | DELETED | settle_template | - [x] `settle_template` / `get_settled_template` / `_validate_settled` 已从 TemplateEngine 移除 |

#### research.md (2 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 42 | REPLACED | add_episode | **add_episode 的 LLM 成本**： |
| 52 | REPLACED | add_episode | - DualChannelWriter Channel B 用 `add_episode`（每次 3-9 次 LLM） |

#### spec.md (12 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 15 | DELETED | SqliteTemplateStorage | > \\| HE kb 持久化与复用 \\| 006 FR-017/018（settle_template / get_settled_template）+ SqliteTemplateStorage \\| FR-003 `he f... |
| 15 | DELETED | get_settled_template | > \\| HE kb 持久化与复用 \\| 006 FR-017/018（settle_template / get_settled_template）+ SqliteTemplateStorage \\| FR-003 `he f... |
| 15 | DELETED | settle_template | > \\| HE kb 持久化与复用 \\| 006 FR-017/018（settle_template / get_settled_template）+ SqliteTemplateStorage \\| FR-003 `he f... |
| 16 | REPLACED | add_episode | > \\| Channel B 实现规范 \\| 006 dual_channel_writer Channel B（原走 Graphiti `add_episode`，3-9 次 LLM 调用） \\| FR-001 `save_a... |
| 22 | REPLACED | UnifiedAudit.log_action | > \\| 操作审计统一 \\| 007 各子服务直接调用 `UnifiedAudit.log_action` \\| FR-006 分层审计（audit_helper SQLite 通道） \\| 007 保留 `usl_outbo... |
| 46 | REPLACED | add_episode | Graphiti 审计写入必须使用 `EpisodicNode.save(driver)`，**禁止使用 `add_episode`**。 |
| 64 | DELETED | get_settled_template | HE 回归"知识摘要构建器"，使用 `he feed` 增量演化。**本 FR 是 HE kb 持久化的唯一规范实现**——006 spec 的应用层模板沉淀（SqliteTemplateStorage + settle_templa... |
| 64 | DELETED | settle_template | HE 回归"知识摘要构建器"，使用 `he feed` 增量演化。**本 FR 是 HE kb 持久化的唯一规范实现**——006 spec 的应用层模板沉淀（SqliteTemplateStorage + settle_templa... |
| 64 | DELETED | SqliteTemplateStorage | HE 回归"知识摘要构建器"，使用 `he feed` 增量演化。**本 FR 是 HE kb 持久化的唯一规范实现**——006 spec 的应用层模板沉淀（SqliteTemplateStorage + settle_templa... |
| 68 | DEPRECATED | he_templates | - 删除 006 spec FR-017/FR-018 的应用层模板沉淀逻辑（SqliteTemplateStorage + he_templates 表应用层写入） |
| 68 | DELETED | SqliteTemplateStorage | - 删除 006 spec FR-017/FR-018 的应用层模板沉淀逻辑（SqliteTemplateStorage + he_templates 表应用层写入） |
| 98 | REPLACED | UnifiedAudit.log_action | - 验收：五项审计全部有记录；007 操作审计经 audit_helper 写入 SQLite，不经 `UnifiedAudit.log_action` |

### A. _top-level（56 hits）


#### REFACTORING-NOTES.md (31 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 15 | DELETED | SqliteTemplateStorage | \\| 1 \\| **模板持久化** \\| 006 vs 009 \\| 006 在应用层实现 `settle_template` / `get_settled_template` + `SqliteTemplateStorage... |
| 15 | DEPRECATED | he_templates | \\| 1 \\| **模板持久化** \\| 006 vs 009 \\| 006 在应用层实现 `settle_template` / `get_settled_template` + `SqliteTemplateStorage... |
| 15 | DELETED | settle_template | \\| 1 \\| **模板持久化** \\| 006 vs 009 \\| 006 在应用层实现 `settle_template` / `get_settled_template` + `SqliteTemplateStorage... |
| 15 | DELETED | get_settled_template | \\| 1 \\| **模板持久化** \\| 006 vs 009 \\| 006 在应用层实现 `settle_template` / `get_settled_template` + `SqliteTemplateStorage... |
| 16 | DELETED | ValidationEngine | \\| 2 \\| **校验机制** \\| 006 vs 007 \\| 006 的 `ValidationEngine`（4 维校验：Schema 一致性 / 完整性 / 置信度 / 引用一致性）与 007 的 3 关质量闸（QG... |
| 18 | REPLACED | UnifiedAudit.log_action | \\| 4 \\| **审计体系** \\| 006 vs 007 vs 009 \\| 006 Channel B 走 Graphiti `add_episode`（3-9 次 LLM）；007 各子服务直接调 `UnifiedAu... |
| 18 | REPLACED | add_episode | \\| 4 \\| **审计体系** \\| 006 vs 007 vs 009 \\| 006 Channel B 走 Graphiti `add_episode`（3-9 次 LLM）；007 各子服务直接调 `UnifiedAu... |
| 32 | DELETED | settle_template | \\| `settle_template()` \\| 006 FR-017 \\| 009 FR-003 `he feed` 自动持久化 \\| |
| 33 | DELETED | get_settled_template | \\| `get_settled_template()` \\| 006 FR-018 \\| 009 HE kb 内部自动复用 \\| |
| 34 | DELETED | SqliteTemplateStorage | \\| `SqliteTemplateStorage` \\| 006 plan/storage/ \\| 删除，不再新建 \\| |
| 35 | DEPRECATED | he_templates | \\| `he_templates` 表应用层写入 \\| 006 data-model.md \\| HE kb 原生管理，应用层不写 \\| |
| 42 | DELETED | ValidationEngine | **决策**：删除 006 `ValidationEngine`，4 维校验合并到 007 的 3 关质量闸。 |
| 55 | STALE_COUNT | 16 子指标 | **结果**：质量闸从 3 关 × 16 子指标扩展为 **3 关 × 22 子指标**（G1: 7→10, G2: 4→7, G3: 5 不变）。 |
| 77 | REPLACED | UnifiedAudit.log_action | **理由**：006 Channel B 走 Graphiti `add_episode`（3-9 次 LLM 调用）成本过高；007 各子服务直接调 `UnifiedAudit.log_action` 绕过 009 分层体系。统一后... |
| 77 | REPLACED | add_episode | **理由**：006 Channel B 走 Graphiti `add_episode`（3-9 次 LLM 调用）成本过高；007 各子服务直接调 `UnifiedAudit.log_action` 绕过 009 分层体系。统一后... |
| 102 | DELETED | ValidationEngine | \\| 4 维校验（ValidationEngine） \\| ❌ 已删 \\| ✅ 合并到 QG \\| \\| |
| 123 | DELETED | ValidationEngine | \\| `spec.md` \\| 修改 \\| 删除 FR-017/018/019（模板沉淀）、FR-024~029（ValidationEngine）；US3 改为用后即弃+feed_to_kb；US4 标记移交 007；新增 F... |
| 124 | DELETED | validation_engine | \\| `plan.md` \\| 修改 \\| 删除 ValidationEngine/SqliteTemplateStorage 任务；项目结构移除 storage/ 和 validation_engine.py；TDD 移除对应... |
| 124 | DELETED | SqliteTemplateStorage | \\| `plan.md` \\| 修改 \\| 删除 ValidationEngine/SqliteTemplateStorage 任务；项目结构移除 storage/ 和 validation_engine.py；TDD 移除对应... |
| 124 | DELETED | ValidationEngine | \\| `plan.md` \\| 修改 \\| 删除 ValidationEngine/SqliteTemplateStorage 任务；项目结构移除 storage/ 和 validation_engine.py；TDD 移除对应... |
| 125 | DELETED | settle_template | \\| `data-model.md` \\| 修改 \\| 顶部添加废弃说明（HETemplate/ValidationReport/settle_template 标记移交/删除） \\| |
| 127 | DELETED | SqliteTemplateStorage | \\| `contracts/template-engine.md` \\| 修改 \\| 顶部添加清理说明（settle/get_settled/SqliteTemplateStorage 已删除） \\| |
| 138 | STALE_COUNT | G2×4 | \\| `data-model.md` \\| 修改 \\| §4 质量闸公式 G1×7→G1×10、G2×4→G2×7；新增 G1.8-G1.10 + G2.5-G2.7 子指标行 \\| |
| 138 | STALE_COUNT | G1×7 | \\| `data-model.md` \\| 修改 \\| §4 质量闸公式 G1×7→G1×10、G2×4→G2×7；新增 G1.8-G1.10 + G2.5-G2.7 子指标行 \\| |
| 139 | REPLACED | Quality16Submetrics | \\| `contracts/quality-gate-approval.md` \\| 修改 \\| 顶部添加版块清理说明；16 子指标→22 子指标；Quality16Submetrics→Quality22Submetrics \\| |
| 139 | STALE_COUNT | 16 子指标 | \\| `contracts/quality-gate-approval.md` \\| 修改 \\| 顶部添加版块清理说明；16 子指标→22 子指标；Quality16Submetrics→Quality22Submetrics \\| |
| 140 | REPLACED | Quality16Submetrics | \\| `contracts/api-contracts.md` \\| 修改 \\| Quality16Submetrics→Quality22Submetrics；子指标列表扩展为 22 项 \\| |
| 162 | DELETED | ValidationEngine | - [ ] 006 spec.md 不再包含 `settle_template` / `get_settled_template` / `ValidationEngine` 的功能需求（仅保留删除标记） |
| 162 | DELETED | get_settled_template | - [ ] 006 spec.md 不再包含 `settle_template` / `get_settled_template` / `ValidationEngine` 的功能需求（仅保留删除标记） |
| 162 | DELETED | settle_template | - [ ] 006 spec.md 不再包含 `settle_template` / `get_settled_template` / `ValidationEngine` 的功能需求（仅保留删除标记） |
| 163 | DELETED | validation_engine | - [ ] 006 plan.md 项目结构中无 `storage/` 目录和 `validation_engine.py` |

#### REFACTORING-VERIFICATION-CHECKLIST.md (25 hits)

| Line | Category | Keyword | Context |
|------|----------|---------|---------|
| 15 | DELETED | get_settled_template | - [ ] **A1.1** 006 spec.md 中 `settle_template` / `get_settled_template` 仅出现在删除标记（~~删除线~~ 或"已删除"上下文）中，无活跃 FR |
| 15 | DELETED | settle_template | - [ ] **A1.1** 006 spec.md 中 `settle_template` / `get_settled_template` 仅出现在删除标记（~~删除线~~ 或"已删除"上下文）中，无活跃 FR |
| 16 | DELETED | ValidationEngine | - [ ] **A1.2** 006 spec.md 中 `ValidationEngine` 仅出现在移交说明中，无活跃 FR-024~029 |
| 17 | DELETED | SqliteTemplateStorage | - [ ] **A1.3** 006 spec.md 中 `SqliteTemplateStorage` 无活跃引用 |
| 18 | DELETED | sqlite_template_storage | - [ ] **A1.4** 006 plan.md 项目结构中无 `storage/` 目录、无 `validation_engine.py`、无 `sqlite_template_storage.py` |
| 18 | DELETED | validation_engine | - [ ] **A1.4** 006 plan.md 项目结构中无 `storage/` 目录、无 `validation_engine.py`、无 `sqlite_template_storage.py` |
| 19 | DELETED | sqlite_template_storage | - [ ] **A1.5** 006 plan.md TDD Requirements 中无 `test_validation_engine.py` / `test_sqlite_template_storage.py` |
| 19 | DELETED | validation_engine | - [ ] **A1.5** 006 plan.md TDD Requirements 中无 `test_validation_engine.py` / `test_sqlite_template_storage.py` |
| 24 | STALE_COUNT | G2×4 | - [ ] **A2.2** 007 plan.md 中 G1×10 / G2×7 / G3×5（非 G1×7 / G2×4） |
| 24 | STALE_COUNT | G1×7 | - [ ] **A2.2** 007 plan.md 中 G1×10 / G2×7 / G3×5（非 G1×7 / G2×4） |
| 58 | DELETED | ValidationEngine | - [ ] **B2.2** 006 无活跃的 ValidationEngine FR（FR-024~029 标记删除/移交） |
| 72 | REPLACED | UnifiedAudit.log_action | - [ ] **B4.2** 007 不直接调用 `UnifiedAudit.log_action`（NFR-009 声明委托 009） |
| 74 | REPLACED | add_episode | - [ ] **B4.4** 006 Channel B 使用 009 `save_audit_episode`（零 LLM），不走 `add_episode` |
| 91 | DELETED | settle_template | - [ ] **C2.1** 006 contracts/template-engine.md 标注 `settle_template()` 已删除 |
| 92 | DELETED | get_settled_template | - [ ] **C2.2** 006 contracts/template-engine.md 标注 `get_settled_template()` 已删除 |
| 93 | DELETED | SqliteTemplateStorage | - [ ] **C2.3** 006 contracts/template-engine.md 标注 `SqliteTemplateStorage` 依赖已删除 |
| 137 | DELETED | SqliteTemplateStorage | - [ ] **E1.4** 006 plan.md TDD Requirements 中无 ValidationEngine/SqliteTemplateStorage 测试项 |
| 137 | DELETED | ValidationEngine | - [ ] **E1.4** 006 plan.md TDD Requirements 中无 ValidationEngine/SqliteTemplateStorage 测试项 |
| 148 | DELETED | settle_template | - [ ] **E3.1** 006 data-model.md 顶部有废弃实体表格（HETemplate/ValidationReport/settle_template） |
| 162 | DELETED | get_settled_template | - [ ] **F1.2** `TemplateEngine` 无 `settle_template` / `get_settled_template` 方法 |
| 162 | DELETED | settle_template | - [ ] **F1.2** `TemplateEngine` 无 `settle_template` / `get_settled_template` 方法 |
| 163 | DELETED | SqliteTemplateStorage | - [ ] **F1.3** `TemplateEngine.__init__` 不接收 `SqliteTemplateStorage` 参数 |
| 164 | DELETED | ValidationEngine | - [ ] **F1.4** `ExtractService` 无 `ValidationEngine` 调用 |
| 167 | REPLACED | add_episode | - [ ] **F1.7** `dual_channel_writer` Channel B 调用 009 `save_audit_episode`，不走 `add_episode` |
| 173 | REPLACED | UnifiedAudit.log_action | - [ ] **F2.3** 007 各子服务操作审计委托 009 `audit_helper`，不直接调 `UnifiedAudit.log_action` |

