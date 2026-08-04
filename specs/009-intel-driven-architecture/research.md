# Research 009: HE 与 Graphiti 的设计本意及当前用法偏差

## 研究方法

经十轮架构 grilling，基于代码事实和官方文档，重新审视 HE 和 Graphiti 的定位。

## 关键发现

### 1. Hyper-Extract 的设计本意

**核心概念**：Knowledge Abstract（知识摘要）—— 持久化、可预测、强类型的知识结构。

**三层架构**：
- Auto-Types（8 种强类型数据结构：AutoModel/AutoList/AutoSet/AutoGraph/AutoHypergraph/AutoTemporalGraph/AutoSpatialGraph/AutoSpatioTemporalGraph）
- Methods（10+ 抽取算法：GraphRAG/LightRAG/Hyper-RAG/KG-Gen 等）
- Templates（80+ 领域模板）

**核心能力**：
- `he parse` 创建 kb
- `he feed` 增量演化 kb（项目完全未使用）
- `he show` / `he search` / `he export obsidian` 独立查询

**当前用法偏差**：
- 只用 AutoGraph（浪费 7/8 的 Auto-Types）
- 每次抽取后丢弃 kb（未用 `he feed` 增量演化）
- spec 006 FR-017/FR-018 在应用层重新实现 HE 已有的模板沉淀逻辑

### 2. Graphiti 的设计本意

**核心概念**：双时态知识图谱——追踪事实的演化和系统认知。

**双时态模型**：
- `valid_at` / `invalid_at`：事实在真实世界何时为真/失效
- `created_at` / `expired_at`：系统何时记录/取代

**核心能力**：
- Edge invalidation：新事实推翻旧事实时，旧事实标记失效（不删除）
- Point-in-time query：查"在 T 时刻系统知道什么"
- Entity resolution：自动归一化"老王"和"王经理"
- Episode-based incremental ingestion

**add_episode 的 LLM 成本**：
- 每次调用至少 3 次 LLM 调用（节点抽取 + 边抽取 + 摘要）
- 典型场景 9 次（5 实体 + 3 边 + 2 类型 + 1 摘要）
- **没有禁用 LLM 抽取的开关**

**零 LLM 替代方案**：
- `EpisodicNode.save(driver)` —— 直接保存 Episode 节点，零 LLM
- `graphiti.nodes` / `graphiti.edges` 命名空间 API —— 直接 CRUD，绕过抽取 pipeline

**当前用法偏差**：
- DualChannelWriter Channel B 用 `add_episode`（每次 3-9 次 LLM）
- 把 HE 结果文本化后让 Graphiti 重抽取（双重抽取浪费）
- 完全未使用双时态和 edge invalidation

### 3. HE AutoTemporalGraph vs Graphiti 双时态

**不重叠，是互补的**：

| 维度 | HE AutoTemporalGraph | Graphiti 双时态 |
|---|---|---|
| 时间维度 | 单时态（valid_time only） | 双时态（valid_time + transaction_time） |
| 时间来源 | 从文本中抽取 | valid_time 从文本 + transaction_time 系统记录 |
| 冲突处理 | 视为不同边 | 旧边失效（invalid_at），新边覆盖 |
| 历史重建 | 无 | point-in-time queries |
| 核心场景 | 抽取文本中的时序关系 | AI Agent 长期记忆 + 事实演化追踪 |

### 4. 数据摄入与 HE 的职责重叠

**当前重叠点**：
- `NewsIngester._extract_with_llm`（[ingestion.py:327](file:///e:/DEMO/AI/ontology-graphiti/apps/api/odap/biz/core/ontology/design/ingestion_split/ingestion.py#L327)）和 HE 的 `extract_from_nl` 都在用 LLM 抽取实体/关系

**整合方案**：
- 摄入 = 纯采集（删除 `_extract_with_llm`）
- HE = 纯抽取（he feed 增量演化）
- 队列 = 两者之间的缓冲（Celery + Redis）
- MinIO = 原始数据持久化（支持原文回溯）

### 5. 审计体系现状

**五项审计需求**：

| 审计项 | 当前状态 | 承载层 |
|---|---|---|
| #1 数据采集审计 | 未实现 | Graphiti（EpisodicNode.save） |
| #2 抽取过程审计 | ProvenanceTracker 部分记录 | Graphiti（EpisodicNode.save） |
| #3 确认过程审计 | 缺失 | audit_helper（SQLite） |
| #4 推理过程审计 | 缺失 | Graphiti（EpisodicNode.save） |
| #5 查询审计 | 缺失 | audit_helper（SQLite） |

`audit_helper.py` 当前为占位实现，需要修正为真实实现。

## AG-UI 协议调研

**AG-UI（Agent-User Interaction Protocol）**：
- 由 CopilotKit 团队 2025 年 5 月发起
- 开放、轻量、事件驱动的协议
- 标准化 Agent 后端与前端应用的双向实时通信
- 已被 AWS Bedrock、Microsoft Agent Framework、Google ADK 采纳

**与 MCP/A2A 的关系**：
- MCP（Agent↔工具）：上下文与工具调用标准化
- A2A（Agent↔Agent）：跨框架 Agent 互操作
- AG-UI（Agent↔用户）：交互层，流式输出、状态同步、HITL

**核心事件类型**：
- `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR`
- `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END`
- `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END`
- `STATE_SNAPSHOT` / `STATE_DELTA`
- `STEP_STARTED` / `STEP_FINISHED`
- Interrupt（HITL）

## 结论

1. HE 和 Graphiti 不合并、不统一，但各归其位
   - HE = 持续情报抽取引擎（he feed 增量演化）
   - Graphiti = 事实审计层（EpisodicNode.save 零 LLM）
2. 当前两个工具的用法都偏离了设计初衷
3. 分层审计（Graphiti 事实演化 + audit_helper 操作审计）是唯一可行方案
4. AG-UI 协议适配使检索服务与主流 Agent 框架互操作
