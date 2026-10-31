---
id: odap.l7.adr-074-情报驱动架构-he与graphiti正确定位及分层审计
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

# ADR-074: 情报驱动架构——HE 与 Graphiti 的正确定位及分层审计

## Status

**Proposed** (2026-08-04)

## Context

ODAP 项目的根本需求是构建"基于外部动态数据实时响应的辅助决策平台（情报系统）"，核心特征包括：
- 搜罗关联信息，作为本体的背景知识、语义补充和事实数据补充
- 为智能体提供统一检索服务，覆盖结构化和非结构化数据
- 解决极度复杂的网状链式/多跳推理
- 事实 100%（零幻觉，可验证）
- 可审计 100%（来源可溯、过程可重现、历史可查）

经十轮架构 grilling 审查，发现当前对 Hyper-Extract 和 Graphiti 的使用方式偏离了两者的设计初衷，且与上述根本需求不匹配：

1. **HE 被当作"一次性抽取服务"**：每次 `Template.create + parse` 后丢弃 Knowledge Abstract，未使用 `he feed` 增量演化能力。spec.md FR-017/FR-018 在应用层重新实现了 HE 已有的模板沉淀复用逻辑。
2. **Graphiti 被当作"重抽取存储"**：DualChannelWriter 的 Channel B 把 HE 结果文本化后调用 `add_episode`，触发 3-9 次 LLM 调用重复抽取，且完全未使用 Graphiti 的双时态和 edge invalidation 能力。
3. **数据摄入与 HE 职责重叠**：`NewsIngester._extract_with_llm` 与 HE 的 `extract_from_nl` 都在做 LLM 结构化抽取，形成功能重复。
4. **审计体系缺失**：确认过程审计、推理过程审计、查询审计均缺失；现有 `audit_helper` 为占位实现。

本 ADR 重新定义 HE 和 Graphiti 的定位，建立分层审计体系，并明确统一检索服务的 AG-UI 协议适配方向。

## Decision

### 1. 核心定位重定义

#### 1.1 Hyper-Extract：持续情报抽取引擎

**从"一次性抽取服务"回归"知识摘要构建器"**：

| 维度 | 当前用法 | 调整后 |
|---|---|---|
| 使用方式 | `Template.create + parse` 后丢弃 kb | `he parse` 创建 kb + `he feed` 增量演化 |
| 持久化 | 无（每次全量重抽） | HE Knowledge Abstract 持久化到 MinIO/磁盘 |
| Auto-Types | 只用 AutoGraph | 按场景选用（AutoGraph/AutoTemporalGraph/AutoSpatialGraph/AutoHypergraph） |
| 模板沉淀 | 应用层重新实现（FR-017/FR-018） | 删除应用层实现，用 HE 原生 `he feed` 替代 |
| 检索 | 无 kb 查询能力 | `he search` 支持结构化查询 + 原文回溯（双路检索） |

**职责边界**：HE 负责非结构化 → 结构化的持续转换，产出 Knowledge Abstract 作为本体的"语义补充"和"事实补充"原料。HE kb 同时保留原文和结构化结果，支持双路检索（Q23:b 决策）。

**不依赖 ontology_id**：HE kb 的构建和演化不需要本体 Schema，只有 OntologyMapper 映射时才需要。这支持"数据先行，本体后建"场景。

#### 1.2 Graphiti：事实审计层（零 LLM）

**从"重抽取存储"收窄为"事实审计层"**：

| 维度 | 当前用法 | 调整后 |
|---|---|---|
| API | `add_episode`（3-9 次 LLM 调用/次） | `EpisodicNode.save(driver)`（零 LLM 调用） |
| 职责 | 重抽取实体/关系（与 HE 重叠） | 记录事实证据链和演化历史 |
| 双时态 | 未使用 | valid_time + transaction_time + edge invalidation |
| 存储内容 | HE 结果的文本化重抽取 | 审计事件（采集时间、数据源、模板、置信度、推理路径） |

**关键 API 转变**：

```python
# ❌ 当前（昂贵）：每次审计 3-9 次 LLM 调用
await gm.add_episode(name="audit", content=episode_body, ...)

# ✅ 调整后（零 LLM）：直接保存 Episode 节点
from graphiti_core.nodes import EpisodicNode
episode = EpisodicNode(
    name="audit:数据采集",
    content=json.dumps(audit_data),
    source=EpisodeType.text,
    source_description="audit_layer",
    valid_at=event_time,
)
await episode.save(graphiti.driver)  # 零 LLM 调用
```

**Graphiti 不做抽取**（HE 已做），只记录审计事件。Graphiti 的 `nodes`/`edges` 命名空间 API 支持直接 CRUD，完全绕过 episode ingestion pipeline。

#### 1.3 数据摄入：纯采集

**从"采集+抽取混合"改为"纯采集"**：

| 维度 | 当前 | 调整后 |
|---|---|---|
| `NewsIngester._extract_with_llm` | 做 LLM 结构化抽取 | 删除，摄入只采集+汇总文本 |
| 产出物 | `OntologyDocument`（含 entities/relations） | 原始数据 → MinIO 持久化 → 队列 |
| 与 HE 的关系 | 职责重叠 | 摄入 = 纯采集，HE = 纯抽取，职责清晰分离 |

**数据采集层职责**：只负责动态抓取数据（爬虫/用户主动发起），由数据通道对外提供原始数据。原始数据持久化到 MinIO，支持原文回溯。

### 2. 分层审计体系

#### 2.1 审计分层架构

```
┌─ Graphiti（EpisodicNode.save，零 LLM）─────────────┐
│  事实演化审计                                       │
│  ├── #1 数据采集审计：何时从哪个数据源采集了什么     │
│  ├── #2 抽取过程审计：用了哪个 HE 模板、置信度多少   │
│  └── #4 推理过程审计：推理路径、用了哪些事实         │
│  特性：双时态 + edge invalidation + point-in-time   │
└─────────────────────────────────────────────────────┘
┌─ audit_helper（轻量 SQLite）────────────────────────┐
│  操作审计                                           │
│  ├── #3 确认过程审计：谁确认的、何时、修改了什么     │
│  └── #5 查询审计：谁查了什么、返回了什么             │
│  特性：高并发、结构化查询、低延迟                   │
└─────────────────────────────────────────────────────┘
```

**分层依据**：Graphiti 的 `add_episode` 每次触发 3-9 次 LLM 调用，不适合高并发的操作审计（如查询审计）。操作审计用轻量级 SQLite（现有 `audit_helper` 修正后承担），事实演化审计用 Graphiti（零 LLM 的 `EpisodicNode.save`）。

#### 2.2 五项审计需求的具体实现

| 审计项 | 承载层 | 记录内容 | 实现方式 |
|---|---|---|---|
| **#1 数据采集审计** | Graphiti | 数据源、采集时间、原始数据地址（MinIO）、采集器类型 | `EpisodicNode.save`，valid_at=采集时间 |
| **#2 抽取过程审计** | Graphiti | HE 模板名、抽取方法、LLM 参数、置信度评分、4维校验结果 | `EpisodicNode.save`，content=JSON 元数据 |
| **#3 确认过程审计** | audit_helper | 操作者、确认时间、修改前后对比、确认/拒绝决策 | SQLite audit table，复用现有 `_extract_operator` 模式 |
| **#4 推理过程审计** | Graphiti | 推理引擎、输入事实列表、推理路径、输出结论 | `EpisodicNode.save`，content=推理路径 JSON |
| **#5 查询审计** | audit_helper | 查询者、查询参数、返回结果摘要、响应时间 | SQLite audit table，高频写入 |

**Graphiti 审计的零 LLM 保障**：所有 Graphiti 审计写入必须使用 `EpisodicNode.save(driver)` 或 `graphiti.nodes`/`graphiti.edges` 命名空间 API，**禁止使用 `add_episode`**（会触发 LLM 抽取）。

### 3. 数据队列与多模态处理

#### 3.1 数据队列（Celery + Redis）

**队列分层**：

| 队列 | 优先级 | 数据来源 | 响应要求 |
|---|---|---|---|
| `high_priority` | 高 | 用户主动发起 | 实时响应 |
| `normal` | 中 | 爬虫/订阅采集 | 尽快处理 |
| `batch` | 低 | 历史数据导入 | 批量处理 |

**选型理由**：Celery + Redis 足够覆盖情报系统的吞吐需求（每秒数百~数千任务），无需引入 Kafka（适用于每秒数万~数百万消息的场景）。Celery 内置重试、优先级队列、定时任务，Redis 已是项目现有依赖。

**队列职责**：缓冲 + 背压 + 失败重试 + 有序消费。保证源头不停采集，后端有序处理。

#### 3.2 多模态处理（MultimodalRouter）

**统一多模态数据处理模块**：

```
MultimodalRouter
├── 输入：混合内容（图文/文本视频混合）
├── 路由规则：按 MIME 类型分派
├── 解析器：
│   ├── TextParser  → HE feed（文本直接进 HE）
│   ├── ImageParser → OCR（Tesseract/PaddleOCR）→ 文本 → HE
│   ├── AudioParser → ASR（Whisper）→ 文本 → HE
│   └── VideoParser → VLM + ASR（待推荐，可用 Gemini/Qwen-VL）→ 文本 → HE
├── 归集器：合并各解析器结果
└── 输出：统一文本流 → 队列 → HE feed
```

**混合内容路由机制**：对于图文混合或文本视频混合的信息，MultimodalRouter 按内容类型分派给不同解析器，分别处理后归集数据结果，流转到下一阶段（HE feed）。

**历史结构化数据**：DB/CSV/JSON 不走 HE 抽取，由 OntologyMapper 直接映射到本体 Instance。但采集审计仍记录到 Graphiti。

### 4. 统一检索服务与 AG-UI 协议适配

#### 4.1 SemanticRetrievalService（扩展 ADR-073）

在 ADR-073 定义的语义检索服务总线基础上，扩展为情报系统的统一检索入口：

| 检索类型 | 数据源 | 适用场景 |
|---|---|---|
| 结构化查询 | Cypher on Neo4j ABox | 本体实例查询 |
| 背景知识查询 | `he search` on HE kb + 原文回溯 | 非结构化背景检索 |
| 时序审计查询 | Graphiti point-in-time query | "在 T 时刻系统知道什么" |
| 多跳推理 | 图遍历 + 链式推理引擎 | 网状链式推理 |
| 混合检索 | components 编排（ADR-073） | 复杂场景 |

#### 4.2 AG-UI 协议适配

**检索服务输出满足 AG-UI（Agent-User Interaction Protocol）协议**，支持：

| AG-UI 能力 | 检索服务适配 | 用途 |
|---|---|---|
| 流式输出（TEXT_MESSAGE_*） | 检索结果分块流式返回 | 智能体对话式检索 |
| 工具调用渲染（TOOL_CALL_*） | 检索过程可视化（"正在查询 Neo4j..."） | 透明化检索过程 |
| 共享状态（STATE_SNAPSHOT/DELTA） | 检索上下文状态同步 | 多轮对话上下文保持 |
| 步骤事件（STEP_*） | 多跳推理步骤可视化 | 推理过程可审计 |
| 人机协同（Interrupt） | 低置信度事实确认 | 事实 100% 保障 |
| 生成式 UI | 检索结果动态渲染（表格/图/卡片） | 前端 UI 自适应 |

**三种消费模式**：
1. **智能体直接消费**：智能体通过统一检索服务开展会话检索，输出 AG-UI 事件流，前端实时渲染
2. **前端 UI 适配**：AG-UI 事件流驱动前端动态生成 UI（表格、图表、卡片、推理路径可视化）
3. **外部应用查询**：外部应用通过 RESTful API 查询，返回结构化 JSON（非 AG-UI 事件流）

**AG-UI 协议选型理由**：AG-UI 是 2025 年由 CopilotKit 发起的开放协议，已被 AWS Bedrock、Microsoft Agent Framework、Google ADK 采纳。它与 MCP（Agent↔工具）和 A2A（Agent↔Agent）互补，填补 Agent↔用户交互层的标准化空白。采用 AG-UI 确保检索服务与主流 Agent 框架互操作。

### 5. 完整架构视图

```
┌─ 数据采集层（只负责抓取）─────────────────────────────┐
│  动态采集（爬虫/订阅）  用户主动发起（高优先级）       │
│  历史数据导入（批量）                                  │
│       ↓                                               │
│  原始数据通道 → MinIO 持久化                           │
└───────────────────────────────────────────────────────┘
                    ↓ Celery + Redis 队列
┌─ 多模态处理层 ─────────────────────────────────────────┐
│  MultimodalRouter                                     │
│  文本 → HE | 图片 → OCR | 音频 → ASR | 视频 → VLM     │
│  混合内容 → 路由分派 → 分别处理 → 归集                 │
└───────────────────────────────────────────────────────┘
                    ↓ 统一文本流
┌─ 情报抽取层（HE 持续引擎）─────────────────────────────┐
│  HE Knowledge Abstract（he feed 增量演化）             │
│  AutoGraph / AutoTemporalGraph / AutoSpatialGraph     │
│  4维校验 + 置信度评分 + 原文保留                       │
└───────────────────────────────────────────────────────┘
                    ↓ OntologyMapper 映射
┌─ 本体建设层（HITL）────────────────────────────────────┐
│  TBox（SQLite）+ ABox（Neo4j）+ 背景知识（HE kb 引用） │
│  结构化数据直接映射（不走 HE）                         │
└───────────────────────────────────────────────────────┘
                    ↓ 确认后触发审计
┌─ 审计层（分层）────────────────────────────────────────┐
│  Graphiti（EpisodicNode.save，零 LLM）                 │
│  ├── 数据采集审计 + 抽取过程审计 + 推理过程审计        │
│  └── 双时态 + edge invalidation + point-in-time       │
│  audit_helper（轻量 SQLite）                           │
│  ├── 确认过程审计 + 查询审计                           │
└───────────────────────────────────────────────────────┘
                    ↓ 统一查询接口
┌─ 统一检索服务（AG-UI 协议）────────────────────────────┐
│  SemanticRetrievalService                             │
│  结构化 / 背景知识 / 时序审计 / 多跳推理 / 混合检索    │
│  输出：AG-UI 事件流 → 智能体/前端/外部应用             │
└───────────────────────────────────────────────────────┘
```

### 6. 历史架构调整点

| # | 调整项 | 优先级 | 影响范围 |
|---|---|---|---|
| 1 | Graphiti 用法修正（add_episode → EpisodicNode.save） | P0 | dual_channel_writer.py, graph_service.py |
| 2 | 数据摄入纯采集化（删除 _extract_with_llm） | P0 | ingestion.py, ingestion_split/ |
| 3 | HE 持续引擎化（he feed 增量演化，持久化 kb） | P1 | he_adapter.py, extract_service.py |
| 4 | 数据队列引入（Celery + Redis，三级优先级） | P1 | 新增模块 |
| 5 | MinIO 原始数据持久化 | P2 | 新增存储层 |
| 6 | 审计层分层实现（Graphiti + audit_helper 修正） | P2 | audit_helper.py, 新增审计写入器 |
| 7 | 多模态处理模块（MultimodalRouter + 解析器） | P3 | 新增模块 |
| 8 | 统一检索服务 AG-UI 适配 | P3 | 新增 AG-UI 事件层 |

## Consequences

### 正面影响

- **HE 回归设计初衷**：使用 `he feed` 增量演化，支持实时响应，避免全量重抽的浪费
- **Graphiti 零 LLM 审计**：用 `EpisodicNode.save` 替代 `add_episode`，审计成本从每次 3-9 次 LLM 调用降为零
- **职责清晰分离**：摄入=纯采集，HE=纯抽取，Graphiti=纯审计，无功能重叠
- **事实 100% 保障**：HE 4维校验 + HITL确认 + Graphiti溯源，形成完整证据链
- **可审计 100% 保障**：分层审计覆盖数据生命周期全环节
- **AG-UI 标准化**：检索服务与主流 Agent 框架互操作，支持生成式 UI

### 负面影响与缓解

- **HE kb 持久化增加存储成本**：缓解——MinIO 已有，kb 按本体/工作空间分区管理，定期归档
- **Celery + Redis 增加运维复杂度**：缓解——Redis 已是现有依赖，Celery 是 Python 生态成熟方案
- **Graphiti API 转变的学习成本**：缓解——`EpisodicNode.save` 比 `add_episode` 更简单（无需理解抽取 pipeline）
- **AG-UI 协议引入前端改造**：缓解——AG-UI 是增量适配，现有 RESTful API 保留，AG-UI 作为新层叠加
- **多模态处理模块的新增工作量**：缓解——P3 优先级，先支持文本（HE），逐步扩展 OCR/ASR/VLM

## Considered Options

1. **合并 HE 和数据摄入**：否决——HE 依赖 ontology_id，摄入不依赖，触发时机不兼容。且 HE 产出 Schema 候选（建本体），摄入产出 Instance 数据（用本体），层级不同。

2. **统一 HE 和 Graphiti**：否决——HE 输出强类型 Schema 约束的结构化知识，Graphiti 输出松散时序 Episode，数据模型根本不同。DualChannelWriter 的双通道设计已承认不可互替。

3. **Graphiti 完全移除**：否决——Graphiti 的双时态和 edge invalidation 是"可审计 100%"的独特保障，无轻量替代方案。OpenHarness 会话记忆也依赖 Graphiti。

4. **Kafka 作为数据队列**：否决——情报系统吞吐量（每秒数百~数千任务）不需要 Kafka（适用于每秒数万~数百万消息）。Celery + Redis 足够且运维成本更低。

5. **全部审计塞进 Graphiti**：否决——`add_episode` 每次触发 3-9 次 LLM 调用，查询审计高频写入会导致成本爆炸。分层审计（Graphiti 事实演化 + audit_helper 操作审计）是唯一可行方案。

## 增补（2026-08-18，Phase 3 扩展 PROV-O 溯源）

在既有分层审计（§2）基础上，增加 **W3C PROV-O 标准溯源导出**能力，使审计数据可被标准溯源工具链消费：

### 1. 目标设计

```
infra/security/
├── unified_audit.py              # (现有)
└── provenance/                   # ★新增
    ├── prov_o_mapper.py          #   Episode → PROV-O Entity/Activity/Agent
    └── audit_exporter.py         #   导出 JSON-LD / CSV / RDF
        # API: GET /api/audit/export?format=prov-o&workspace_id=...
```

### 2. PROV-O 映射规则

Graphiti Episode / 审计事件映射为 PROV-O 三类核心对象：

| 审计项（§2.2） | PROV-O 映射 | 说明 |
|---|---|---|
| #1 数据采集审计 | `prov:Activity`（采集）+ `prov:Entity`（原始数据）+ `prov:Agent`（采集器） | `prov:wasGeneratedBy` 关联 |
| #2 抽取过程审计 | `prov:Activity`（抽取）+ `prov:Entity`（HE kb） | `prov:used` 关联模板/原文 |
| #3 确认过程审计 | `prov:Activity`（确认）+ `prov:Agent`（操作者） | `prov:wasAssociatedWith` |
| #4 推理过程审计 | `prov:Activity`（推理）+ `prov:Entity`（结论） | `prov:wasDerivedFrom` 关联输入事实 |
| #5 查询审计 | `prov:Activity`（查询） | 轻量，仅导出摘要 |

决策记录（ADR-076 `DecisionRecord`）天然纳入 PROV-O 的 `Activity` 体系：决策作为 `prov:Activity`，推荐选项作为 `prov:Entity`，`prov:wasInformedBy` 关联先例。

### 3. 零侵入原则

映射**仅发生在导出层**（`audit_exporter`），Graphiti 写入路径、`unified_audit` 写入路径均不变。导出为**只读旁路**，按需触发。

### 4. 导出格式

| 格式 | 序列化 | 用途 |
|---|---|---|
| JSON-LD | `rdflib`（`application/ld+json`） | 机器可读、Linked Data |
| RDF/Turtle | `rdflib`（`text/turtle`） | 标准 RDF 工具链 |
| CSV | 简化扁平导出 | 人工审计/Excel |

API 按 `workspace_id` 过滤（安全要求：隔离），`format` 参数指定导出格式。

## References

- [ADR-073: 基于本体的数据服务四步落地架构](./ADR-073_基于本体的数据服务四步落地架构.md)
- [Hyper-Extract 官方文档](https://yifanfeng97.github.io/Hyper-Extract/latest/)
- [Graphiti 官方文档](https://help.getzep.com/graphiti/)
- [AG-UI 协议规范](https://docs.ag-ui.com/introduction)
- [Graphiti Data Processing Pipeline](https://deepwiki.com/getzep/graphiti/5-data-processing-pipeline)
- 十轮架构 grilling 记录（本会话）
