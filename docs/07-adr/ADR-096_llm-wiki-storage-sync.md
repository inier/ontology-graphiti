---
id: odap.l7.adr-096-llm-wiki-storage-sync
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

# ADR-096: LLM Wiki 存储与双向同步方案

## Status

**已接受（2026-10-17）**。本轮首建 LLM Wiki 模块（产品模块 + 仓库文档治理双向打通）。

---

## Background

用户核心需求：首建 LLM Wiki 模块，实现「产品模块 + 仓库工程文档治理双向打通」。

**现状（文件:行证据）**：

- LLM Wiki 模块**完全缺失**：`grep -rl "llm.wiki\|llm_wiki\|LlmWiki" apps/web/src apps/api/odap` 零命中。
- 已有存储基础设施：SQLite（TBox 真相源，`CONTEXT.md:11`）、Neo4j（ABox）、MinIO（对象存储）、Redis。
- 已有文档基线与治理脚本：`docs/DOCUMENT_BASELINE_v1.0.0.md`、`scripts/check_dangling_doc_links.py`。
- 既有存储决策：ADR-060（knowledge-base document storage）。
- 仓库文档共 259 篇 md，`docs/02-architecture/ARCHITECTURE_*.md` 11 篇无真相源（评估报告 §1.1）。

---

## Decision

**存储模型**（详见架构 v2 §5）：

- **纳管模型**：统一 front-matter 字段 `id/status/owner/version/source_ref/superseded_by/supersedes/content_hash/last_verified/citations`。
- **主存储**：SQLite（文档元数据 + 状态机）+ MinIO（正文/附件对象）+ Neo4j（引用关系图，可复用既有图库）。**不新增独立存储引擎**（复用现状）。
- **内容哈希**：`content_hash` 用于判重与版本锚定。
- **状态机**：`draft → review → published → superseded|archived`；`published` 必须有 owner 且未过期。

**双向同步**：

- 仓库 → Wiki：`POST /wiki/sync/import`，导入 `docs/` 文档为 wiki 条目，保留 `source_ref`。
- Wiki → 仓库：`POST /wiki/sync/export`，回写为仓库 md，受写权限与审批约束。
- 同步冲突：以 `content_hash` 检测，冲突时保留双侧 + 提示合并，不静默覆盖。

**与本体/USL 关系**：

- wiki 条目可挂 `concept_refs[]`（TBox 概念），成为本体的「人文解释层」。
- wiki 条目进语义检索服务总线（作为 `nl`/`chain` 证据源，带 `source_ref`）。
- USL 术语可挂权威文档链接。

**API**：见 `docs/02-architecture/openapi-v2.yaml` 的 LLM Wiki 端点组。

**备份方案**：若 SQLite 元数据规模增长超预期，迁移到 PostgreSQL（新增 ADR），模型不变。

---

## Consequences

**正面**：
- 产品与仓库文档统一纳管，双向可追溯。
- 复用现有存储，最小新增。
- 与本体/USL/语义检索打通，文档成为知识链一环。

**负面**：
- 双向同步存在一致性与权限复杂度，须审批与冲突检测。
- 仓库 md 需批量补 front-matter（存量 259 篇）才能纳入纳管，工作量不小。
- Wiki → 仓库回写触及代码仓库，须防误写（限路径白名单 + 审批）。

---

## Related ADRs

- ADR-060（knowledge-base document storage）
- ADR-094（本体约束编排层，文档作为检索证据源）
- ADR-097（文档治理与溯源机制）
