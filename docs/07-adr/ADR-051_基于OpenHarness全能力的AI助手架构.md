# ADR-051: 基于 OpenHarness 全能力的 AI 助手架构

## 状态

- **状态**：提议中（Proposed）
- **日期**：2026-07-18
- **作者**：Software Architect
- **影响范围**：`core/chat/` + `infra/openharness/` — 全架构重构
- **取代**：ADR-050（统一后端服务 — 本 ADR 在 ADR-050 的统一端点基础上，明确以 OpenHarness 为唯一引擎）

---

## 背景

### 现状：OpenHarness 已集成但未充分发挥

经过深入审查，当前 ODAP 的 AI 能力存在一个关键矛盾：

| 维度 | 主路径（OpenHarness） | 降级路径（ChatService） |
|------|----------------------|------------------------|
| 引擎 | `QueryEngine.submit_message()` | 手动 HTTP 调用 LLM API |
| Agent Loop | 内置多轮循环 | 单次 tool-call + summary |
| 事件协议 | AG-UI 17 种标准事件 | 6 种自定义 SSE 事件 |
| 安全性 | OPA + WriteGuard | 无权限检查 |
| 韧性 | CircuitBreaker | 裸调用 |
| 会话恢复 | `SessionMemoryService` | 手动拼接 |

**问题**：主路径已经走 OpenHarness，但能力远未用足。OpenHarness 提供的 Swarm、.md Skills、MCP、Memory Auto-Compact 等能力全部闲置。ChatService 作为降级路径，自身就是一个需要维护的重复实现。

### OpenHarness 已用 vs 未用能力总览

| 能力 | 已用 | 未用 |
|------|------|------|
| QueryEngine Agent Loop | ✅ | — |
| ToolRegistry（自定义工具） | ✅ | — |
| AG-UI Transport | ✅ | — |
| PermissionChecker | ✅（FULL_AUTO + OPA 外层） | — |
| **Swarm / TeamLifecycleManager** | ❌ | OH 内置多 Agent 协同 |
| **.md Skills System** | ❌ | 声明式领域知识加载 |
| **MCP Client + Server** | ❌ | 外部工具互联 |
| **Memory Auto-Compact** | ❌ | 自动上下文压缩 |
| **CLI / TUI** | ❌ | 命令行调试入口 |
| **Channels（飞书/Slack 等）** | ❌ | IM 渠道接入 |
| **43 个内置工具** | ❌ | Bash/File/Search/Web 等 |

### 当前架构的三层分裂

```
/api/assistant/chat  ────→  chat_via_agui() → OpenHarness QueryEngine → AG-UI
                         ↘  ChatService.chat() → 手动 LLM + 自定义 SSE（降级）

/api/qa/ask/stream   ────→  QAEngineV2 → 五阶段 RAG Pipeline → 自定义 SSE

/api/ontology-assistant/run → OntologyAssistantService → AG-UI
```

三条独立的代码路径，三套不同的工具调用方式，三种不同的协议。

---

## 决策

### 核心理念：OpenHarness 是唯一的 Agent 运行时

```
┌──────────────────────────────────────────────────────────────┐
│  "Anything you can do in a chat, you can do through a tool."  │
│                                                                 │
│  QA 检索 → 一个工具 (QARetrieverTool)                          │
│  本体设计 → 一组工具 (16 BaseTool)                              │
│  领域知识 → .md Skills                                          │
│  外部系统 → MCP Tools                                           │
│  多 Agent → Swarm                                               │
│                                                                 │
│  唯一运行时：OpenHarness QueryEngine                            │
│  唯一协议：AG-UI (17 种事件 + CUSTOM 扩展)                       │
│  唯一端点：/api/chat/message                                    │
└──────────────────────────────────────────────────────────────┘
```

### 1. 工具化一切（"Everything is a Tool"）

当前 QA 的五阶段 RAG Pipeline 是独立引擎，约 3000 行代码不通过工具调用。在 OpenHarness 架构中，它应该是一个工具：

```python
class QARetrieverTool(BaseTool):
    """知识图谱 RAG 检索工具 — 三支柱检索。"""
    
    name = "qa_retrieve"
    description = "三支柱 RAG 检索：BM25 + 向量 + 图谱，返回融合后的知识片段"
    
    class InputModel(BaseModel):
        query: str = Field(..., description="自然语言查询")
        retrieval_mode: Literal["bm25", "vector", "graph", "hybrid"] = "hybrid"
        top_k: int = Field(10, ge=1, le=50)
        include_temporal: bool = Field(False)
    
    async def execute(self, args, ctx) -> ToolResult:
        result = await self.rag_pipeline.search(args.query, ...)
        return ToolResult(output=json.dumps(result))
```

**LLM 自主决策调用**：当用户问"帮我查一下最近的异常事件"，LLM 看到 `qa_retrieve` 工具可用，自主决定调用它。不再需要在代码层面预先分类意图和路由。

### 2. OpenHarness Swarm 替代自制 OODA 编排

当前 `DomainSwarm` 有自制的 OODA 循环和 `OHSwarmAgent`，但它不使用 OH 的 `TeamLifecycleManager`：

**变更**：使用 OH 原生 Swarm

```python
# 替代自制 OODA 循环
from openharness.swarm import InProcessBackend, TeamLifecycleManager
from openharness.coordinator import TeamConfig

team = TeamConfig(
    name="odap",
    agents=[
        AgentConfig(role="commander",   system_prompt=COMMANDER_PROMPT, tools=all_tools),
        AgentConfig(role="intelligence", system_prompt=INTELLIGENCE_PROMPT, tools=read_tools),
        AgentConfig(role="operations",   system_prompt=OPERATIONS_PROMPT, tools=write_tools),
    ],
    coordination="hierarchical",  # Commander 调度 Intelligence/Operations
)

swarm = InProcessBackend(team, lifecycle=TeamLifecycleManager())
result = await swarm.run(user_input, context)
```

**为什么选 OH Swarm 而非自制？**
- OH 的 `TeamLifecycleManager` 已实现 Agent 间消息路由、任务委托、结果回传
- OH 的 Swarm 支持分层（hierarchical）、对等（peer）和辩论（debate）三种模式
- 减少维护负担：不再需要维护 `swarm_orchestrator.py` 的 800+ 行 OODA 逻辑

### 3. .md Skills 替代硬编码 System Prompt

当前 `ChatService` 的 `SYSTEM_PROMPT` 是 120 行的硬编码字符串。OpenHarness 支持声明式 `.md` 技能文件，运行时按需加载：

```
odap/skills/
├── ontology-designer.md      # 本体设计领域知识
├── data-analyst.md           # 数据分析方法论
├── graph-query.md            # 图查询 DSL 参考
├── simulation-expert.md      # 仿真推演规则
└── platform-manual.md        # 平台使用手册
```

```markdown
# ontology-designer.md

## 能力
- 创建/修改/删除对象类型、属性、关系类型
- 检查本体完整性：缺失审计字段、孤立类型、缺少状态机

## 规则
- data_type 可选值: STRING, INTEGER, FLOAT, BOOLEAN, DATETIME, TEXT
- cardinality 可选值: ONE_TO_ONE, ONE_TO_MANY, MANY_TO_ONE, MANY_TO_MANY
- 用户用中文指代类型时（如「里程碑」），匹配后端实际类型名
```

**OpenHarness 的 Skill 加载机制**：
- QueryEngine 初始化时扫描 `skills/` 目录
- Agent 请求时按需注入相关 skill 内容到 system prompt
- 支持热更新：修改 `.md` 文件后立即生效，无需重启

### 4. MCP Tools：外部系统互联

ODAP 当前不支持 MCP（Model Context Protocol）。启用 OpenHarness 的 MCP 能力后：

```
ODAP AI Assistant
    ↓ MCP
┌───────────────────┬───────────────────┬────────────────────┐
│ Neo4j MCP Server  │ OPA MCP Server    │ 外部数据源 MCP      │
│ 原生图查询          │ 策略查询           │ REST API / SQL /   │
│ Cypher 直连        │ Rego 分析          │ 第三方服务          │
└───────────────────┴───────────────────┴────────────────────┘
```

**使用场景**：
- 用户问"帮我在 Neo4j 中跑一个 Cypher 查询"→ MCP 工具直接执行
- 用户问"检查当前 OPA 策略覆盖了哪些写操作"→ MCP 工具查询策略引擎
- 用户问"从外部 API 拉取最新数据"→ MCP 工具调用第三方服务

### 5. 架构总图

```
                         ┌─────────────────────────────────────┐
                         │     POST /api/chat/message (唯一)     │
                         └─────────────────┬───────────────────┘
                                           │
                         ┌─────────────────▼───────────────────┐
                         │    UnifiedChatService (薄路由层)     │
                         │    路由到 OpenHarness Agent 基础设施  │
                         └─────────────────┬───────────────────┘
                                           │
           ┌───────────────────────────────┼───────────────────────────────┐
           │                               │                               │
  ┌────────▼────────┐            ┌────────▼────────┐            ┌────────▼────────┐
  │  AG-UI Transport │            │  OHQueryEngine  │            │  OH Swarm       │
  │  17 Event Types  │            │  Factory (单例)  │            │  (Multi-Agent)   │
  │  + CUSTOM ext    │            │                 │            │  TeamLifecycle   │
  └────────┬────────┘            └────────┬────────┘            └────────┬────────┘
           │                               │                             │
           │                    ┌──────────▼──────────┐                  │
           │                    │   ToolRegistry       │                  │
           │                    │                      │                  │
           │                    │  ┌────────────────┐  │                  │
           │                    │  │ 16 BaseTool     │  │ 本体 CRUD        │
           │                    │  │ (本体设计/查询)  │  │                  │
           │                    │  ├────────────────┤  │                  │
           │                    │  │ QA Retriever    │  │ 三支柱 RAG        │
           │                    │  │ (BM25+Vec+Graph)│  │                  │
           │                    │  ├────────────────┤  │                  │
           │                    │  │ .md Skills      │  │ 领域知识          │
           │                    │  │ (5+ skill files)│  │                  │
           │                    │  ├────────────────┤  │                  │
           │                    │  │ MCP Tools       │  │ 外部系统          │
           │                    │  │ (Neo4j/OPA/REST)│  │                  │
           │                    │  └────────────────┘  │                  │
           │                    └──────────────────────┘                  │
           │                                                              │
  ┌────────▼────────┐    ┌────────────┐    ┌────────────┐    ┌──────────┐│
  │  Permission      │    │  Memory     │    │  Config     │    │ Hooks    ││
  │  OPA Backend     │    │  Graphiti   │    │  Hot Reload │    │ pre/post ││
  │  WriteGuard      │    │  AutoCompact│    │  Subscribe  │    │ audit    ││
  └─────────────────┘    └────────────┘    └────────────┘    └──────────┘│
                                                                          │
  ┌──────────────────────────────────────────────────────────────────────┘│
  │    OpenAICompatClient (多提供商兼容)                                   │
  │    ┌──────────┬──────────┬──────────┬──────────┐                     │
  │    │ OpenAI   │ ZhipuAI  │ Silicon  │ Anthropic│ ...                 │
  │    └──────────┴──────────┴──────────┴──────────┘                     │
  └──────────────────────────────────────────────────────────────────────┘
```

### 6. 关键设计决策

| # | 决策 | 替代方案 | 理由 |
|---|------|---------|------|
| 1 | OpenHarness 为唯一 Agent 运行时 | 保留 ChatService 双路径 | 消除重复维护，统一能力模型 |
| 2 | QA 检索作为工具，而非独立 Pipeline | 保持 QA 独立引擎 | "一切皆工具" — LLM 自主决定何时检索 |
| 3 | .md Skills 加载领域知识 | 硬编码 System Prompt | 声明式、热更新、零代码扩展 |
| 4 | OH Swarm 替代自制 OODA 循环 | 保留 DomainSwarm | OH 原生支持分层/对等/辩论三种模式 |
| 5 | MCP 作为外部系统互联标准 | 自定义 HTTP 客户端 | 行业标准协议，生态工具丰富 |
| 6 | Graphiti Memory + OH Auto-Compact | 手动写入 Memory | 自动上下文压缩，避免 Token 爆炸 |
| 7 | OPA 作为 OH PermissionChecker 后端 | OH 内置权限检查 | OPA 提供 ABAC 策略，比 OH 规则更灵活 |

### 7. 降级路径设计

当 OpenHarness 不可用时（极少发生），不降级到 ChatService，而是：

```
主路径:  QueryEngine.submit_message()  →  AG-UI SSE
降级 1:  OpenAICompatClient 直接调用     →  AG-UI SSE (无 tool-calling)
降级 2:  规则引擎 (关键词匹配)            →  AG-UI SSE (预定义回答)
```

所有降级路径输出相同的 AG-UI 事件格式，前端无需感知降级。

---

## 影响

### 正面

| 影响 | 量化 |
|------|------|
| 消除 ChatService 维护 | -900 行代码 |
| 消除自制 OODA 循环 | -800 行代码 |
| .md Skills 替代硬编码 Prompt | 零代码扩展领域知识 |
| MCP 打通外部系统 | Neo4j/OPA/REST 统一接入 |
| AG-UI 协议覆盖所有场景 | 前端只需一套解析器 |
| OH Auto-Compact 记忆管理 | 自动上下文压缩 |

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| OH Swarm 迁移可能引入回归 | Phase A 并行运行，AB 对比 |
| .md Skills 格式 LLM 理解度不确定 | 小范围试点（单 skill），效果验证后推广 |
| QA 工具化后 RAG 检索可能不如独立 Pipeline 精准 | 保留 QAEngineV2 作为降级工具的内部实现 |
| MCP 增加运维复杂度 | 先在本地 MCP Server 试点，逐步扩展 |

### 对已有 ADR 的影响

- **ADR-050**：本 ADR 是其"基于 OpenHarness"的深化实现，不冲突
- **ADR-048/049**：本体引擎和认知引擎的底层不��，仅运行时改为 OpenHarness
- **ChatService**：标记为 Deprecated，Phase C 移除

---

## 实施路线

### Phase A：OpenHarness 深度集成（当前迭代）

- [ ] `QARetrieverTool` — QA Pipeline 工具化
- [ ] `skills/*.md` — 创建 3-5 个 .md Skill 文件
- [ ] OH Swarm 配置 — Commander/Intelligence/Operations 三 Agent
- [ ] `OpenAICompatClient` 多提供商支持
- [ ] Graphiti Memory Auto-Compact 启用

### Phase B：MCP 与扩展能力

- [ ] MCP Server for Neo4j
- [ ] MCP Server for OPA Policy
- [ ] MCP Client 集成到 ToolRegistry
- [ ] Channels 适配器（飞书/Slack 预留）

### Phase C：清理

- [ ] 移除 `ChatService`（确认无引用）
- [ ] 移除 `sswarm_orchestrator.py` 自制 OODA 循环
- [ ] 移除 `data/qa/qa_engine.py` 独立 Pipeline
- [ ] 统一为 `core/chat/` + `infra/openharness/`

---

## 结论

OpenHarness 是 ODAP AI 助手的**正确运行时**。当前集成只用了 QueryEngine + ToolRegistry 两个能力，而 Swarm、Skills、MCP、Auto-Compact 等才是 OpenHarness 真正的差异化价值。本 ADR 将 AI 助手从"OpenHarness 可用但不充分"升级为"OpenHarness 是唯一引擎"，以工具化、声明式、标准化的原则，构建可扩展的 AI 助手架构。

---

## 相关文档

- [ADR-050 统一 AI 助手与智能问答服务](./ADR-050_统一AI助手与智能问答服务.md)
- [ADR-048 本体管理引擎架构决策](./ADR-048_本体管理引擎架构决策.md)
- [ADR-049 用户认知引擎架构决策](./ADR-049_用户认知引擎架构决策.md)
- [OpenHarness README](../../packages/openharness/README.md)
- [Engine Adapter 核心实现](../../apps/api/odap/infra/openharness/engine_adapter.py)
