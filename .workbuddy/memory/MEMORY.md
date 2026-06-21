# 项目长期记忆 — ODAP 本体驱动分析决策平台

## 项目概述
- **项目路径**: `E:\DEMO\AI\ontology-graphiti`
- **系统定位**: ODAP 本体驱动分析决策平台，参考 Palantir AIP 架构
- **核心流程**: WebUI 数据摄入 → 自动构建本体 → 本体查询问答 → 给出执行建议
- **技术核心**: OpenHarness + Graphiti + Python Skill + OPA

## 关键技术来源（2026-04-11 更新）
- **OpenHarness**: HKUDS（香港大学数据科学实验室）开源项目
  - GitHub: https://github.com/HKUDS/OpenHarness
  - 协议: MIT

## 架构设计 v2.0（2026-04-11）

### 核心架构：四层组件

| 层次 | 组件 | 职责 |
|------|------|------|
| L1 | OpenHarness | Agent Loop + Swarm + Tool 调度 + Permission |
| L2 | Graphiti | 双时态知识图谱 + 时序推理 + RAG 增强 |
| L3 | Python Skills | 领域工具（情报/作战/分析/可视化） |
| L4 | OPA | 策略治理 + 权限校验 + Fail-Close |

### OpenHarness 核心子系统

- `engine/`: Agent Loop
- `tools/`: 43+ 内置工具
- `plugins/`: 扩展点
- `permissions/`: 权限检查（桥接 OPA）
- `hooks/`: 生命周期事件
- `mcp/`: 外部系统集成
- `memory/`: 记忆管理（桥接 Graphiti）
- `coordinator/`: Swarm 多 Agent

### 三 Agent 角色

| Agent | 定位 | LLM | 职责 |
|-------|------|-----|------|
| Commander | 决策中枢 | 强推理模型 | 最终拍板，OPA 校验 |
| Intelligence | 感知+理解 | 快分析模型 | Observe + Orient |
| Operations | 执行中心 | 规划模型 | Act + 回写 |

### 关键设计决策

ADR 文档已独立化，存放在 `docs/adr/` 目录（共 48 个 ADR，ADR-001~047+1），详见 `docs/adr/README.md`。
核心 ADR：ADR-001(OpenHarness), ADR-002(Graphiti), ADR-003(OPA), ADR-004(Skill), ADR-005(分层Agent), ADR-006(复用策略), ADR-045(G6+Leaflet), ADR-046(模块化单体), ADR-047(工具注册表P0分步)

### OpenHarness 复用矩阵（2026-04-11）

| 类别 | 组件 | 复用方式 |
|------|------|----------|
| **✅ 完全复用** | Agent Loop、Tool框架、Skill格式、Plugin系统、Provider管理 | 开箱即用 |
| **⚠️ 适配复用** | Memory (→Graphiti)、Permissions (→OPA)、Coordinator (→三Agent) | 桥接适配 |
| **🔴 独立扩展** | 战场本体、56领域Skills、时序推理、态势可视化 | 自研 |

### Graphiti 集成经验（2026-04-14）

- **ZhipuAIClient 需三层适配**：URL 智能拼接（去尾部 `/chat/completions`）+ 字段名映射（`_normalize_fields`）+ 缺失字段填充（`_fill_missing_fields`）
- **EpisodicNode 字段**：`content`（不是 `episode_body`），`name`，`uuid`，`created_at`
- **EntityEdge 字段**：`name`，`fact`，`uuid`，`source_node_uuid`，`target_node_uuid`
- **Graphiti.search()** 返回 `list[EntityEdge]`，不是 Episode
- **Embedder 配置**：需要从 chat base_url 推导 embedding base_url（SiliconFlow 模型 `Pro/BAAI/bge-m3`）
- **Neo4j 驱动内置指数退避重试**，必须用 `asyncio.wait_for(timeout=15)` 做快速失败

### 演进路线

| Phase | 时间 | 目标 | 状态 |
|-------|------|------|------|
| Phase 0 | 2-4周 | 基础设施搭建 | ✅ 已完成 |
| Phase 1-A | 1-2月 | 四大基础设施验证（Graphiti+Neo4j, OPA, Skill基类） | ✅ 已完成 |
| Phase 1-B | 1-2月 | 单 Agent 闭环（Intelligence Agent ReAct + RAG + 追踪） | ✅ 已完成 |
| Phase 2 | 2-3月 | 三 Agent 协同 OODA | ✅ 已完成 |
| Phase 3 | 3-6月 | 模拟器增强（Web 可视化 + 热写入 + 标准本体格式） | ✅ 已完成 |
| Phase 4 | 6-12月 | 生产化部署 | ⬜ |

## Phase 4 文档体系（2026-04-19 完成）

九步文档流程全部完成（Step 1-9），Phase 4 规划已就绪：

| Step | 产出 | 状态 |
|------|------|------|
| 1 | `docs/req-alpha.md` — 需求整合（26 FR + 29 NFR + 5 SI） | ✅ |
| 2 | 六层架构 + 专家角色识别 | ✅ |
| 3 | 18 模块划分 + ADR-007~010 | ✅ |
| 4 | 18 个 DESIGN.md + 索引更新 | ✅ |
| 5 | UI/DFX/测试设计文档 | ✅ |
| 6 | `docs/TASK_BREAKDOWN.md` v2.0 — 23 工作项 + 6 Sprint | ✅ |
| 7 | `docs/CHECKLIST.md` — 213 条验收项 | ✅ |
| 8 | `docs/COMPLETENESS_REPORT.md` — 100% 需求覆盖 | ✅ |
| 9 | `docs/ANOMALY_REPORT.md` — 39 条待确认项 | ✅ |

### 关键路径
WR-01→WR-03→WR-04→WR-05→WR-17→WR-18，预估 11.5 周

### 待人工确认的关键决策（ANOMALY_REPORT）
1. ~~**I-17** ReGraph vs G6~~ → ✅ ADR-045 已决策：G6
2. ~~**I-21** Phase 4 单体 vs 微服务~~ → ✅ ADR-046 已决策：模块化单体
3. **I-22** 审计日志存储 → ✅ ADR-042 已决策：SQLite + 文件哈希链锚点
4. **I-36** 🟡 M-11 工具注册表 P0/P1 优先级 → ✅ ADR-047 已决策：P0 分步实现
5. ~~ADR-039~044 待创建~~ → ✅ 已全部创建（2026-04-19）

## ANOMALY_REPORT 状态（2026-04-19 更新）

- **14 条亟需人工确认项 → 全部已关闭**
- 三大关键决策：ADR-045(G6+Leaflet)、ADR-046(模块化单体)、ADR-047(工具注册表P0分步)
- 代码清理已完成：biz/permission/ 删除、adapters/ 并入 infra/、web/legacy/ 归档、1~ 删除
- I-24（storage/非空）和 I-28（simulator_ui/不存在）为记录修正，非操作项
- Redis 和消息队列 Phase 4 不引入（YAGNI），Phase 5+ 再评估

## 重要文档
- `docs/architecture/ARCHITECTURE.md`（v4.1.0，2026-05-04，517行，入口索引）
- `docs/architecture/ARCHITECTURE_INFRA.md`（L1 基础设施层，776行）
- `docs/architecture/ARCHITECTURE_TOOLS.md`（L2 领域工具层，157行）
- `docs/architecture/ARCHITECTURE_BIZ.md`（L3-L4 业务层，1522行）
- `docs/architecture/ARCHITECTURE_WEB.md`（L5-L6 接口层，1048行）
- `docs/architecture/ARCHITECTURE_EVOLVE.md`（演进与决策，768行）
- `docs/architecture/ARCHITECTURE_VALIDATION_REPORT.md`（架构合理性验证报告，8.4/10）
- `docs/adr/README.md`（含优先级列，ADR-001~048，全部已创建）
- `docs/TASK_BREAKDOWN.md`（v3.0，Phase 4 工作项拆分）
- `docs/CHECKLIST.md`（v1.0，213 条验收 Checklist）
- `docs/COMPLETENESS_REPORT.md`（v1.0，范围完整性确认）
- `docs/ANOMALY_REPORT.md`（v1.0，39 条不相关/待确认信息）
- `docs/AUDIT_REPORT.md`（全量文档审计报告）
- `docs/RESTRUCTURE_PLAN.md`（项目目录重构方案）
- **需求文档三件套**：
  - `docs/req-alpha.md` — v1.0 原始技术研究（归档）
  - `docs/req-beta.md` — v1.1.0 早期需求规格（归档）
  - `docs/req-ok.md` — v2.0.0 需求定稿（⭐ 唯一权威来源）

## 核心文件
- `odap/infra/graphiti/`: Graphiti 客户端
- `odap/infra/opa/`: OPA 策略管理
- `odap/biz/swarm/`: Swarm 编排器
- `odap/biz/ontology/`: 本体管理引擎
  - `schema/`: 本体 Schema 定义
  - `services/`: 服务层（IngestService 等）
  - `storage/`: 存储层
  - `ingestion_split/`: ⭐ 数据采集子模块（2026-05-04 拆分）
    - 包含 NewsIngester, ManualInputHandler, 各 Generator 等

## AI 助手统一架构设计（2026-06-21）

### 核心设计

1. **统一 AI 助手**：Header 入口和本体设计器中的 AI 助手是同一个，共享会话历史，都是"管理后台助手"
2. **双本体问答**：AI 助手基于两个本体问答：
   - 业务本体（用户设计的本体）→ 回答业务数据问题
   - 平台功能本体（新增，用本体描述平台本身）→ 回答平台使用问题
3. **操作手册知识库**：为平台各功能编写操作手册（Markdown），结构化为知识库，AI 可检索回答
4. **前端两种展示模式**：
   - 完全体模式：全屏，完整的历史会话、功能菜单
   - 简洁模式：侧边栏/对话框，历史会话折叠为图标，重点在对话框
5. **组件化开发**：`AIChatProvider` + 展示层组件，支持 full/compact 两种模式，便于独立迁移

### 后端分层架构

```
Knowledge Layer: 业务本体 + 平台功能本体 + 操作手册 + 可扩展知识
Service Layer: ChatService(扩展) + ToolRegistry + ContextManager(新增) + KnowledgeManager(新增)
API Layer: /api/assistant/chat + /api/assistant/tools/* + /api/assistant/knowledge/*(新增)
```

### 平台功能本体建模

- EntityType: `FunctionalModule`(功能模块), `Page`(页面), `Operation`(操作), `Concept`(概念), `Tutorial`(教程)
- RelationType: `contains`(模块→页面), `has_operation`(页面→操作), `related_to`(概念→概念), `explained_in`(概念→教程)
- 存储：`ontology_id = "platform"`（系统内置，复用 OntologyService）
- 定义文件：`docs/ai-assistant/platform-ontology.json`
- 同步 API：`POST /api/assistant/platform-ontology/sync`

### 操作手册知识库 Schema

- 格式规范：每个功能模块一个 Markdown 文件，存放于 `docs/user-manual/`
- 结构：`# 模块名称` → `## 概述` → `## 快速开始` → `## 详细操作` → `## 常见问题` → `## 相关概念` → `## 相关教程`
- 入库 Pipeline：Markdown → 结构化 JSON → 文本块拆分 → 向量索引 → 链接到平台功能本体
- JSON Schema：符合 `OperationsManual` 定义（见 `docs/ai-assistant/operations-manual-schema.md`）

### 前端组件化方案

```
AIChatProvider (Context Provider, 共享状态)
├── useAIChat (核心聊天逻辑 Hook)
├── useAIChatHistory (历史会话管理 Hook)
└── useAIChatTools (工具调用管理 Hook)

AIChatFullMode (完全体模式) → 用于独立页面
AIChatCompactMode (简洁模式) → 用于侧边栏/对话框

AIChatPanel (对外暴露的统一入口组件, mode="full"|"compact")
```

### 关键文档

- `docs/architecture/ARCHITECTURE_AI_ASSISTANT.md` — AI 助手统一架构设计（主文档）
- `docs/ai-assistant/platform-ontology.md` — 平台功能本体建模（支撑文档）
- `docs/ai-assistant/operations-manual-schema.md` — 操作手册知识库 Schema（支撑文档）

### 实施路线图

- Phase 1（2周）：知识层 + 后端抽象（平台功能本体 JSON Schema、KnowledgeManager、ChatService 扩展、新增 API）
- Phase 2（2周）：操作手册编写 + 入库（各模块操作手册、Markdown→JSON→向量索引 Pipeline、链接到平台功能本体）
- Phase 3（1周）：前端组件化（抽象 AIChatProvider+Hooks、实现 Full/Compact 模式、重构现有 AIChatPanel）
- Phase 4（后续）：知识扩展（接入 FAQ、版本变更日志、用户反馈）

---

## AI 助手工具开发经验（2026-06-21）

### 关键文件
- `odap/biz/core/assistant/tools.py` — 工具注册表 + 实现（查询/建议/写操作/批量写入）
- `odap/biz/core/assistant/services/chat_service.py` — LLM 聊天服务（function-calling + 规则回退）
- `odap/biz/core/assistant/api/routes.py` — API 路由（含直接工具调用端点）
- `frontend/src/modules/shared/components/AIChatPanel.tsx` — AI 聊天面板组件

### 名称泛化匹配引擎
- `_resolve_type_name()` 五级匹配：精确→中英文别名→包含→description→编辑距离
- `TYPE_NAME_ALIASES` 别名表 50+ 条（里程碑→milestone 等）
- 所有写操作工具和 suggest 工具都通过此函数解析类型名

### 批量写入模式
- `add_properties` 工具支持两种 JSON 格式：对象数组 + 简化键值对
- 原子性一次 `update_object_type` 调用，返回 added/skipped 列表
- `_classify_intent` 检测 JSON 或 3+ 字段名 → 识别为批量写入

### 上下文自动注入
- `_llm_chat()` 在 LLM 调用前自动获取本体上下文注入 system message
- 前端 AIChatPanel mount 时自动获取本体概览显示在欢迎消息中

### 写操作联动刷新
- 写操作返回 `_ontology_changed: True` → 后端发出 `ONTOLOGY_CHANGED` SSE 事件
- 前端收到事件 → 调用 `onOntologyChanged` 回调 → `selectOntology()` 重新加载

---

## AI 助手独立组件化架构（2026-06-21）

### 架构设计：Host-Plugin 分层
- **OHMO = Host**：统一入口（12+ IM 渠道 + Web）、会话管理、RuntimeBundle 生命周期
- **OpenHarness = Framework**：Agent Loop、ToolRegistry、HookExecutor、PermissionChecker
- **AG-UI = Protocol**：17 类事件 wire format，Web 和 IM 共享
- **AI Assistant = Plugin**：独立组件，提供领域工具/技能/钩子

### 关键发现
- **双轨并行问题**：`assistant/`（自建非 OH）与 `agui/`（OH AG-UI）两套独立实现
- **OHMO Gateway** 已有完整 IM 接入能力（飞书/Slack/Telegram/Discord/钉钉等 12 渠道）
- **会话路由**：session_key = `channel:chat_id:thread_id:sender_id`
- ODAP 适配层 `odap/infra/openharness/` 已有完整适配器（engine/swarm/skill/hook/memory/permission）

### 独立组件结构
- 后端：`odap/plugins/ai_assistant/`（plugin.json + tools/ + skills/ + hooks/ + prompts/ + api/）
- 前端：`frontend/src/modules/ai-assistant/`（hooks/ + components/ + adapters/）
- Web UI 作为 OHMO 的 "web" 渠道（WebChannelAdapter），与 IM 渠道并列

### 依赖关系
- OHMO 依赖 Plugin 获取领域能力；Plugin 依赖 OHMO 获取运行时
- Plugin 不直接依赖 OHMO Gateway — 只声明工具，由 OHMO 加载注册
- 工具通过 ToolExecutionContext 注入 OntologyService，消除直接导入耦合

### 关键文档
- `docs/architecture/ARCHITECTURE_AI_ASSISTANT_STANDALONE.md` — 完整架构设计（12 章 + ADR-048/049）
- 4 Phase 迁移路线（6-9 周）：插件化 → OHMO 集成 → AG-UI 统一 → 死代码清理
