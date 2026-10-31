---
id: odap.l14.docs-document-management
status: authoritative
owner: architect
version: 3.0.0
layer: L14
concern: doc-governance
lifecycle: living
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: 文档治理规范（front-matter 机制、防腐策略）唯一权威
governance_evidence: 本文件与 DOC-GOVERNANCE-POLICY.yaml、scripts/doc_governance.py 构成机制三件套
---

# 文档管理规范 — SDD 防腐文档体系维护指南

> **版本**: 3.0.0 | **日期**: 2026-10-17 | **状态**: 正式
> **用途**: 为 SDD（Software Design Document）层次化文档体系建立防腐机制，防止文档漂移 / 不一致 / 腐烂
> **上游**: ADR-097（文档治理与溯源机制） | **下游**: 所有层级文档
> **本版变更**: ① 层表据实更新（ADR 54→97 篇、新增 `12-evaluation/`、`ARCHITECTURE-v2` 与 `openapi-v2.yaml` 立为权威）；
> ② 新增 §1.3 机械校验机制（front-matter 唯一真相源 + R1~R14 + 索引脚本生成）；
> ③ 引入 layer/status/lifecycle 三元正交模型与三条裁决原则；
> ④ 修正层编号冲突（评估层 08→12）。
> **机器校验**: `python scripts/doc_governance.py audit --ci`（error 级即阻断）

---

## 1. SDD 文档体系总览

### 1.1 层次结构（11 层 + 评估/登记/存档三层）

```
文档流程: 需求 → 产品 → 架构 → 模块 → UI → 安全 → DFX → ADR → 任务 → 检查 → 契约
目录映射: 00 → 01 → 02 → 03 → 04 → 05 → 06 → 07 → 08 → 09 → 10
附加层:   12-evaluation（评估）  decisions（悬决登记）  11-archive（归档）
```

| 层级 | 目录 | 核心文档 | 权威级别 |
|------|------|---------|:--------:|
| 原始需求 | `00-requirements/` | `req-ok.md`（范围定稿） | ⭐⭐⭐ 唯一权威 |
| 开发规格 | `00-requirements/` | `SPEC-v2.md`（做法与验收） | ⭐⭐⭐ 唯一权威 |
| 产品需求 | `00-requirements/` | `PRD-v2.md` | ⭐⭐⭐ 唯一权威 |
| 产品设计 | `01-product-design/` | `ODAP综合优化设计文档.md` | ⭐⭐ |
| 目标架构 | `02-architecture/` | `ARCHITECTURE-v2.md` | ⭐⭐⭐ 唯一权威 |
| 分层详设 | `02-architecture/` | `ARCHITECTURE_{BIZ,WEB,INFRA,TOOLS,OPS,FULL_CHAIN}.md` | ⭐⭐ |
| API 契约 | `02-architecture/` | `openapi-v2.yaml` | ⭐⭐⭐ 唯一机器可验权威 |
| 模块设计 | `03-modules/` | 26 个 `DESIGN.md` | ⭐⭐ |
| UI/UX | `04-ui/` | `UIUX-DESIGN-v2.md` + `design-tokens.json` | ⭐⭐⭐ 唯一权威 |
| 安全设计 | `05-security/` | `SECURITY.md` | ⭐⭐⭐ |
| DFX 设计 | `06-dfx/` | `DFX_DESIGN.md` / `TEST_DESIGN.md` | ⭐⭐⭐ |
| ADR 决策记录 | `07-adr/` | **97 篇**（ADR-001~098，含 034/035 预留、087 待启用） | ⭐⭐ |
| 任务分解 | `08-tasks/` | `TASK_BREAKDOWN.md` | ⭐⭐⭐ |
| 检查清单 | `09-checklists/` | `CHECKLIST_v2.md` / `contract-rulings.md` | ⭐⭐⭐ |
| API 说明（人读） | `10-api/` | `API_SPEC.md` 等 4 篇 | ⭐⭐ |
| 评估报告 | `12-evaluation/` | `PRODUCT-EVALUATION.md` / `ARCHITECTURE-EVALUATION.md` | ⭐⭐⭐ |
| 悬决登记 | `decisions/` | `OPEN-DECISIONS.md` | ⭐⭐⭐ |
| 归档（历史依据） | `11-archive/` | specs/ + feature-specs/ + audit/ + legacy_code/ | ⭐ 参考 |

> **层编号唯一**：曾出现 `08-tasks/` 与 `08-evaluation/` 同占 08 前缀，破坏目录映射。
> 2026-10-17 已将评估层改为 `12-evaluation/`，由 `scripts/doc_governance.py` 的 R8 持续校验。

### 1.2 唯一真相来源（Single Source of Truth）

| 权威文档 | 路径 | 回答什么问题 | 不可绕过 |
|----------|------|-------------|:--------:|
| 需求范围定稿 | `00-requirements/req-ok.md` | **做什么** | ✅ |
| 开发规格契约 | `00-requirements/SPEC-v2.md` | **怎么做、如何验收**（AC-01~AC-56） | ✅ |
| 产品需求与排序 | `00-requirements/PRD-v2.md` | **先做哪个、为什么** | ✅ |
| 目标架构 | `02-architecture/ARCHITECTURE-v2.md` | **系统长什么样** | ✅ |
| API 契约 | `02-architecture/openapi-v2.yaml` | **接口长什么样**（机器可验） | ✅ |
| 前端设计 | `04-ui/UIUX-DESIGN-v2.md` | **界面长什么样** | ✅ |
| 契约裁定 | `09-checklists/contract-rulings.md` | **前后端冲突谁说了算** | ✅ |
| 交付清单 | `09-checklists/CHECKLIST_v2.md` | **交付是否达标** | ✅ |
| ADR 索引 | `07-adr/README.md` | **为什么这么定** | ✅ |
| 悬决登记 | `decisions/OPEN-DECISIONS.md` | **哪些还没定** | ✅ |
| 文档索引 | `DOC-INDEX.md`（**脚本生成，勿手改**） | **有哪些文档、各是什么状态** | ✅ |
| **本文档** | `DOCUMENT_MANAGEMENT.md` | **治理机制怎么运转** | ✅ |

> **人读说明 vs 机器契约**：`10-api/*.md` 为人读说明，与 `openapi-v2.yaml` 冲突时**一律以 yaml 为准**；
> 由 `scripts/check_api_contract.py` 做三向对账，结果落 `09-checklists/api-contract-matrix.md`。

### 1.3 机械校验机制（ADR-097）

文档元数据的**唯一真相源是每份文档自己的 YAML front-matter**，不是中心登记表——
中心登记表会与文档正文各自演化，形成第二真相源，这正是本规范要消灭的反模式。

| 件 | 路径 | 职责 |
|----|------|------|
| 规则 | `DOC-GOVERNANCE-POLICY.yaml` | 层定义、状态推导、产物登记、R1~R14 与严重级别 |
| 事实 | 各文档 front-matter | `id/status/owner/version/layer/concern/lifecycle/superseded_by/supersedes/last_verified/citations` |
| 投影 | `DOC-INDEX.md` + `09-checklists/doc-inventory.csv` | **由脚本生成，禁止手改** |
| 校验 | `scripts/doc_governance.py audit --ci` | error 即阻断，可进 CI |
| 留痕 | `DOC-GOVERNANCE-SEED.yaml` | 一次性迁移的逐篇裁决理由（迁移后只读） |

**三元正交模型**（避免「归档」既当状态又当位置的歧义）：

- `layer` = 文档**在哪**（目录归属，物理位置）
- `status` = 文档**有多大权威**（authoritative > active > reference > superseded / archived / vendor）
- `lifecycle` = 文档**是否还在维护**（living / frozen / historical）

**三条裁决原则**（2026-10-17 从真实误判中总结，见 ADR-097 修订 A）：

1. **同关注点才谈取代**。粒度不同的两份文档不是候选关系——462 行的 v2 不能取代 1801 行的分层详设。
2. **取代需双向证据**。被取代方正文自认，或接任方明文声明覆盖范围；「文件名看起来更新」不构成证据。
3. **声称覆盖但实际未覆盖的内容，不得标 superseded**。

---

## 2. 防腐机制

### 2.1 三层防腐策略

| 策略 | 说明 | 机制 |
|------|------|------|
| **预防 (Prevent)** | 防止文档与实现不一致 | 文档基线 + 变更前置检查 |
| **检测 (Detect)** | 发现已有不一致 | 定期完整性检查清单 §8 |
| **纠偏 (Correct)** | 修复文档漂移 | 归档废弃文档 + 更新路径引用 |

### 2.2 变更前置检查（每次文档变更必须）

1. 需求变更 → 更新 `00-requirements/req-ok.md` → 同步更新 `02-architecture/ARCHITECTURE-v2.md`
2. 架构决策 → 创建新 ADR → 更新 `ARCHITECTURE-v2.md` 引用
3. 模块变更 → 更新对应 `03-modules/*/DESIGN.md` → 同步更新 `ARCHITECTURE_FULL_CHAIN.md`
4. 废弃文档 → 移至 `11-archive/`，保留演进历史，**禁止直接删除**

### 2.3 路径变更影响链

```
需求 req-ok.md → 架构 ARCHITECTURE-v2.md → 模块 03-modules/
                                     ├── ADR 07-adr/
                                     ├── UI 04-ui/
                                     ├── 安全 05-security/
                                     └── DFX 06-dfx/
                                              ↓
                                      08-tasks/ TASK_BREAKDOWN.md
                                              ↓
                                      09-checklists/ CHECKLIST_v2.md
```

### 2.4 保真年限

| 文档层 | 最大无审阅间隔 | 过期标记 |
|--------|:------------:|---------|
| 需求 | 6 个月 | 需求变更时优先处理 |
| 架构 | 3 个月 | 架构审查时优先处理 |
| 模块 | 2 个月 | 模块迭代时更新 |
| ADR | 半年 | 被替代时标记为弃用 |

---

## 3. 文档生命周期管理

### 3.1 状态流转

```
草稿 → 评审中 → 正式 → 维护中 → 归档 → 弃用
```

### 3.2 状态定义

| 状态 | 标记方式 | 含义 |
|------|---------|------|
| 草稿 | `状态: 草稿` | 编写中，不完整 |
| 评审中 | `状态: 评审中` | 完成待审核 |
| 正式 | `状态: 正式` | 已通过评审，可引用 |
| 维护中 | `状态: 维护中` | 仍在用但需更新 |
| 归档 | `状态: 归档` | 移至 `11-archive/` |
| 弃用 | `状态: 弃用 - 被 [新文档] 取代` | 不可引用 |

### 3.3 新建文档流程

```
确定类型/位置 → 使用模板 → 填写元数据 → 编写内容
       ↓
更新 README.md 和本层索引 → 标记"评审中" → 团队评审 → 标记"正式"
```

---

## 4. 版本管理规范

### 4.1 语义化版本号：`MAJOR.MINOR.PATCH`

| 层级 | 触发条件 |
|------|---------|
| MAJOR | 架构重构、需求重大调整 |
| MINOR | 新增模块、功能增强 |
| PATCH | 修正错误、补充说明 |

### 4.2 文档元数据模板

```markdown
# [文档标题]

> **版本**: X.Y.Z | **日期**: YYYY-MM-DD | **状态**: 正式
```

### 4.3 变更日志

```markdown
| 版本 | 日期 | 变更内容 | 变更人 |
```

---

## 5. 文档依赖关系管理

### 5.1 关系类型

| 类型 | 含义 | 元数据 |
|------|------|--------|
| 上游 | 本文档依赖的 | `上游文档: [xxx]` |
| 下游 | 依赖本文档的 | `下游文档: [xxx]` |
| 相关 | 关联但不依赖 | `相关文档: [xxx]` |

### 5.2 变更影响分析

| 变更文档 | 需同步更新 |
|----------|:-----------|
| `00-requirements/req-ok.md` | `02-architecture/ARCHITECTURE-v2.md` → `08-tasks/TASK_BREAKDOWN.md` |
| `02-architecture/ARCHITECTURE-v2.md` | `03-modules/*/DESIGN.md` → `07-adr/*` |
| ADR | `07-adr/README.md` → `DOCUMENT_RELATIONSHIP.md` |
| 模块 DESIGN.md | `ARCHITECTURE-v2.md` → 相关 ADR |

---

## 6. 文档归档机制

### 6.1 归档触发条件

- 被新文档完全取代
- 相关功能已移除
- 超过 6 个月未更新且不再使用

### 6.2 归档流程

```
确认归档 → 更新状态为"归档" → 添加替代文档链接
       ↓
移至 11-archive/ → 更新 README 索引
```

### 6.3 归档目录

```
11-archive/
├── specs/          # 已完成的特性规格（7个子规格）
└── legacy_code/    # 旧代码（dialog/web）
```

---

## 7. 文档模板库

### 7.1 ADR 模板

```markdown
# ADR-XXX: [决策标题]

## 状态
提议 | 已接受 | 已弃用 | 被 ADR-XXX 取代

## 上下文

## 决策

## 后果

## 可逆性
```

→ [ADR 模板与编号规则](07-adr/README.md)

### 7.2 模块设计模板

```markdown
# [模块名称] 设计文档

> **版本**: 1.0.0 | **日期**: YYYY-MM-DD | **状态**: 正式
> **上游文档**: [ARCHITECTURE-v2.md 相关章节]

## 1. 模块概述
## 2. 核心职责
## 3. 架构设计
## 4. 接口定义
## 5. 数据模型
## 6. 错误处理
## 7. 测试策略
## 变更日志
```

→ [模块 README](03-modules/README.md)

---

## 8. 文档完整性检查清单

### 8.1 每次提交前

- [ ] 文档元数据完整（版本、日期、状态）
- [ ] 相关层 README.md 索引已更新
- [ ] 变更日志已记录
- [ ] 下游文档是否需要同步

### 8.2 周度检查

- [ ] 评审中文档是否有进展
- [ ] 维护中文档是否需要更新
- [ ] 是否有可归档文档

### 8.3 月度检查

- [ ] 文档关系图路径是否有效（所有 `../` 相对路径）
- [ ] ADR 编号是否连续无冲突
- [ ] 是否有版本冲突风险
- [ ] `req-ok.md` 和 `ARCHITECTURE-v2.md` 是否一致

---

## 9. 最佳实践

### DOs
✅ 每个文档明确负责人
✅ 变更时检查下游文档并同步更新
✅ 使用相对路径引用（防止目录移动后断裂）
✅ 定期归档废弃文档
✅ 新增文档后更新对应层的 README.md

### DON'Ts
❌ 不创建无人负责的文档
❌ 不让文档状态长期停在"草稿"
❌ 不直接删除文档（应归档 → `11-archive/`）
❌ 不在多处重复维护相同信息
❌ 不让需求文档与架构文档产生不一致

---

## 10. 相关文档

- [文档关系图](./DOCUMENT_RELATIONSHIP.md) — 完整索引
- [文档基线 v1.0.0](./DOCUMENT_BASELINE_v1.0.0.md) — 首个可信基线
- [SDD 总入口](./README.md) — 文档中心首页
- [ADR 索引](./07-adr/README.md) — 架构决策记录
- [需求定稿](./00-requirements/req-ok.md) — 唯一需求真相
- [核心架构](./02-architecture/ARCHITECTURE-v2.md) — 唯一架构真相
