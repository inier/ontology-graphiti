---
id: odap.l7.adr-097-docs-governance-provenance
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

# ADR-097: 文档治理与溯源机制（真相源 + 可机械校验）

## Status

**已接受（2026-10-17）**。本轮建立文档单一真相源与可机械校验的溯源机制。

---

## Background

用户核心需求：冗余文件与设计整理归档，**须给溯源证据**（需要可机械校验的技术手段）；文档治理与 LLM Wiki 双向打通。

**现状（文件:行证据）**：

- `docs/02-architecture/` 下 `ARCHITECTURE_*.md` **11 篇**，零 superseded 标记（评估报告 §1.1）。
- `docs/` 共 259 篇 md，无单一真相源。
- `docs/DOCUMENT_BASELINE_v1.0.0.md:1` 文件名(v1.0.0)与内容版本(v1.1.0)不一致；其 ADR 计数（`:19-21` 自述 001-054）落后实际（001-090）。
- ADR 重号：`ADR-061` 一号两文（`ADR-061-semantic-admin-suite-architecture.md` / `ADR-061_skill_plugin_packaging.md`）；跨目录撞号 `docs/02-architecture/reports/ADR-065_BULKHEAD_AUDIT.md` vs `docs/07-adr/ADR-065_microservice_extraction_playbook.md`。
- 已有治理脚本：`scripts/check_dangling_doc_links.py`、`scripts/lint_ontology_architecture.py`。

---

## Decision

1. **单一真相源**：本轮 `ARCHITECTURE-v2.md` 为唯一架构真相源；其余 10 篇 `ARCHITECTURE_*.md` 归档为 `status: superseded`（**不删除**，保留 git 可追溯），并在 front-matter 设 `superseded_by` 指向 v2。
2. **强制 front-matter**：所有纳管文档头部含 `id/status/owner/version/superseded_by/supersedes/last_verified/citations`（字段定义见 openapi-v2.yaml `GovernedDoc` 与架构 v2 §5.2）。
3. **可机械校验**（复用并扩展 `scripts/check_dangling_doc_links.py`）：
   - 悬空引用：`citations[].ref` 指向不存在的 id → error。
   - 缺 owner：`owner` 为空 → error。
   - 孤立文档：无任何出入引用且非索引 → warning。
   - 陈旧文档：`last_verified` 过期 → warning。
   - 重复哈希：`content_hash` 相同 → warning。
   - 校验以 `POST /docs/governance/verify` 暴露，并进 CI 门禁（error 即 FAIL）。
4. **去重合并**：`content_hash` 判重 + embedding 相似度提示合并；合并保留 canonical，被合并者置 `superseded`（`POST /docs/governance/documents/{doc_id}/supersede`）。
5. **ADR 编号治理**：新 ADR 自 `ADR-091` 起（任务书「009 起」与现状冲突，已在 `OPEN-DECISIONS.md` 登记并修正）；`ADR-061` 重号问题另立条目跟踪，重编须先核清引用方。
6. **编号基线核对表**：在 `docs/07-adr/README.md` 增补「编号基线核对表」，记录已用/缺失编号，防止再次撞号。

---

## Consequences

**正面**：
- 文档有单一真相源与可机械校验的溯源证据链。
- 冗余文档归档有据（superseded 链），不再「互相覆盖无标记」。
- 治理检查进 CI，防回归。

**负面**：
- 存量 259 篇补 front-matter 有工作量，须分批（优先 ADR 与核心架构）。
- `last_verified` 过期判定需人工核验，存在维护成本。
- 归档 10 篇架构文档需全面核对引用方，防断链。

---

## Related ADRs

- ADR-016（完备文档体系）
- ADR-054（规格与架构文档瘦身）
- ADR-096（LLM Wiki 存储与同步）

---

## 修订记录

### 2026-10-17 修订 A：第 1 条「其余 10 篇」收窄为「仅 ARCHITECTURE.md」

**触发**：本 ADR 进入实施阶段后，逐篇核对 11 篇 `ARCHITECTURE_*.md` 的实际内容，发现第 1 条
将「其余 10 篇」一并标 `superseded` 会造成**实质内容丢失**——v2 全文 462 行，无法承接
`ARCHITECTURE_BIZ.md`（1801 行）/`ARCHITECTURE_WEB.md`（1091 行）/`ARCHITECTURE_INFRA.md`（1052 行）
的分层详细设计。把它标为「已被取代」等于告诉读者这些内容不再有效，与实际不符。

**修订**：按「同一关注点才谈取代」重新裁决——

| 文档 | 关注点 | 原判 | 收窄后 | 依据 |
|------|--------|------|--------|------|
| `ARCHITECTURE.md` | 总体架构 | superseded | **superseded**（不变） | 与 v2 同关注点，v2 取代 |
| `ARCHITECTURE_BIZ.md` | L3-L4 业务层详设 | superseded | **active** | v2 未承接其 1801 行深度 |
| `ARCHITECTURE_INFRA.md` | L1 基础设施层详设 | superseded | **active** | v2 未承接其 1052 行深度 |
| `ARCHITECTURE_WEB.md` | L5-L6 接口层详设 | superseded | **active** | v2 未承接其 1091 行深度 |
| `ARCHITECTURE_TOOLS.md` | L2 领域工具层 | superseded | **active** | 工具层唯一成篇描述 |
| `ARCHITECTURE_OPS.md` | 运维架构 | superseded | **active** | 运行态关注点，v2 未覆盖 |
| `ARCHITECTURE_FULL_CHAIN.md` | 端到端全链路 | superseded | **active** | 给链路视图，与 v2 契约视图互补 |
| `ARCHITECTURE_FOUR_STEPS.md` | 四步法菜单归集 | superseded | **reference**（frozen） | 过程产物，落地见 MENU_REFACTOR_PLAN |
| `ARCHITECTURE_EVOLVE.md` | 架构演进 | superseded | **reference**（historical） | 结论已由 ADR-091~098 承接 |
| `ARCHITECTURE_TARGET_PLAN.md` | 目标态规划 | superseded | **reference**（historical） | 目标态已由 v2 承接 |
| `ARCHITECTURE_ANALYSIS_REPORT.md` | 一次性分析 | superseded | **reference**（historical） | 报告类，非设计文档 |

**机械落地**：`docs/DOC-GOVERNANCE-SEED.yaml` 逐篇记录判定与证据；`scripts/doc_governance.py`
的 R3（权威唯一）/R4（取代闭环）会对新判定做持续校验。

**教训（写入裁决原则，防复发）**：
- **P1** 同关注点才谈取代。粒度不同的两份文档不是候选关系。
- **P2** 取代需双向证据：被取代方正文自认，或接任方明文声明覆盖范围。仅凭「文件名看起来更新」不构成证据。
- **P3** 声称覆盖但实际未覆盖的内容，不得标 superseded。同类问题另见：`docs/04-ui/UIUX-DESIGN-v2.md:14`
  要求把 7 篇 v1 UI 文档标为历史，但 v2 全文无组件 API 层，故 `COMPONENT_SPEC.md`（10 类组件规格）
  实际未被承接——本表据此只取代其色彩/动效/导航归属的两篇（`UI_DESIGN.md`、
  `05-ODAP-V2-DESIGN-SYSTEM.md`），其余保留 active/reference。

### 2026-10-17 修订 B：第 2 条 front-matter 落地范围与三元正交模型

**原状**：第 2 条接受后**零执行**——281 份 md 中仅 1 份（第三方 vendor 文件）带 front-matter。

**落地**：277 份纳管 md 全部补齐 front-matter（字段 `id/status/owner/version/layer/concern/
lifecycle/superseded_by/supersedes/last_verified/citations`，其中 `layer/concern/lifecycle`
为本次扩展，用于支撑 R3 权威唯一与 R7 层归属校验）；7 份产物文件（yaml/json/csv/css）
按 `DOC-GOVERNANCE-POLICY.yaml §四` 逐项登记，不进 front-matter（数据文件加 YAML 头会破坏解析）。

**三元正交模型**（解决「归档」既当状态又当位置的歧义）：
- `layer` = 文档**在哪**（目录归属）
- `status` = 文档**有多大权威**
- `lifecycle` = 文档**是否还在维护**

### 2026-10-17 修订 C：第 3 条校验规则扩展为 R1~R14

原第 3 条列 5 项检查（悬空引用/缺 owner/孤立文档/陈旧文档/重复哈希）。实施中按实际治理缺陷
补充为 14 条，并明确严重级别（error 进 CI 门禁）：

| 规则 | 级别 | 内容 | 对应原第 3 条 |
|------|------|------|--------------|
| R1 | error | 纳管文档 front-matter 字段齐全 | 新增（无疏漏） |
| R2 | error | superseded_by / 引用路径必须存在 | 悬空引用 |
| R3 | error | 同 (层, 关注点) 只能一个 authoritative | 新增（权威唯一） |
| R4 | error | 取代链不得悬空 | 新增（取代闭环） |
| R5 | error | archived 必须有 reason + evidence | 新增（归档溯源） |
| R6 | error | status/lifecycle/owner 枚举合法 | 新增 |
| R7 | error | 声明 layer 与目录归属一致 | 新增 |
| R8 | error | 层目录数字前缀不重复 | 新增（实证：08 双占） |
| R9 | warn | 版本声明一致 | 新增（实证：BASELINE 文件名/正文不一致） |
| R10 | error | citations 指向本地文档必须存在 | 悬空引用 |
| R11 | warn | 孤立文档 | 孤立文档 |
| R12 | warn | ADR 状态可解析 | 新增（28 篇未声明） |
| R13 | error | 产物文件必须登记 | 新增 |
| R14 | error | front-matter id 全局唯一 | 重复哈希的替代口径 |

**未实现并说明理由**：原第 3 条「重复哈希」与「last_verified 过期」两项——
① 实测 281 份文档**无字节级重复**（`sha256` 全量比对为空），冗余是语义级的，
需 embedding 相似度而非哈希，已推迟到 LLM Wiki 治理页的近似查重能力；
② `last_verified` 过期判定需人工核验基线，当前统一置为 2026-10-17，待首轮校验周期
（建议 180 天）后启用。两项均登记于 `docs/DOC-GOVERNANCE-SEED.yaml` 的 `known_debts`。
