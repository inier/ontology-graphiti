# ADR-069: 统一 AI 助手与智能问答后端服务

## 状态

- **状态**：提议中（Proposed）
- **日期**：2026-07-18
- **作者**：Software Architect
- **影响范围**：`core/assistant/` + `data/qa/` → 合并为 `core/chat/`

---

## 背景

### 当前问题

ODAP 平台存在两套独立的 AI 对话系统，虽然前端已部分统一（QAPage 复用 AIChatPanel），但后端仍严重分裂：

| 维度 | AI 助手 (`core/assistant/`) | 智能问答 (`data/qa/`) |
|------|---------------------------|---------------------|
| 对话引擎 | `ChatService`（900行） | `QAEngineV2`（3000行） |
| SSE 协议 | AG-UI 事件（RUN_STARTED, TEXT_MESSAGE_CONTENT, TOOL_CALL_*） | 自定义事件（content, sources, thinking, chart, temporal） |
| 检索方式 | QueryService DSL（通过工具） | 三支柱 RAG（BM25 + Vector + Graph） |
| 前端 Hook | `useAIChat`（422行） | `useQAI`（397行） |
| 路由前缀 | `/api/assistant/` | `/api/qa/` |
| 会话管理 | 依赖 QA 的 `/api/qa/sessions` | 自有 DialogManager |
| 读写能力 | 支持（16个工具，含8个写入） | 只读（不可修改本体） |

这种分裂带来以下具体问题：

1. **双 SSE 协议不兼容**：AG-UI 协议和自定义 SSE 使用了不同的事件类型和数据结构，前端需要两套解析逻辑
2. **能力孤立**：AI 助手有写入能力但无 RAG 检索，QA 有 RAG 检索但无写入能力——用户无法在一个对话中同时完成"查"和"改"
3. **维护负担**：两套引擎、两套路由、两套测试，任何一个共性问题的修复要改两处
4. **架构耦合脆弱**：AI 助手的会话管理依赖 QA 的 sessions API，形成了意外的循环依赖
5. **消息格式不统一**：`ChatMessage`（有 tool_calls、analysisResults）vs `QAMessage`（有 charts、temporal、reports）语义重叠但结构不同

### 业务驱动

用户期望：
- 在**同一个对话窗口**中完成"智能问答 → 本体分析 → 本体修改"
- AI 助手在任何页面（Header 入口、本体设计器、问答页面）表现一致
- 前端 UI 可以按场景定制（问答页有图表和报告、设计器有属性面板），但底层对话服务是同一套

这正是"**统一后端服务，前端 UI 可定制**"的需求。

---

## 决策

### 核心决策：合并为单一 `UnifiedChatService`

将 `ChatService` 和 `QAEngineV2` 合并为一个统一的 `UnifiedChatService`，对外暴露一组统一的 API 端点，对内组合工具执行、RAG 检索、会话管理等能力。

### 1. 新模块结构

```
odap/biz/core/chat/                    # 统一对话模块（新建）
├── __init__.py
├── api/
│   ├── routes.py                      # 统一 SSE 聊天 API  /api/chat/
│   └── schemas.py                     # 统一请求/响应模型
├── engine/
│   ├── unified_chat_service.py        # 统一对话引擎（聊天编排）
│   ├── pipeline.py                    # 五阶段 Pipeline（复用 QA Engine 逻辑）
│   └── session_manager.py             # 统一会话管理（取代两套实现）
├── retrieval/                         # 检索引擎（从 data/qa/retrieval/ 迁移）
│   ├── base.py                        # 检索器基类
│   ├── bm25_retriever.py
│   ├── vector_retriever.py
│   ├── graph_retriever.py
│   └── unified_retriever.py           # 三支柱融合
├── tools/                             # 工具注册（从 core/assistant/plugins/ 迁移）
│   ├── query_tools.py                 # 4 个查询工具
│   ├── design_tools.py                # 4 个设计工具
│   ├── write_tools.py                 # 8 个写入工具
│   └── registry.py                    # 统一工具注册表
├── renderers/                         # 内容渲染器（替代 QA 自定义 SSE 事件）
│   ├── chart_renderer.py
│   ├── temporal_renderer.py
│   ├── report_renderer.py
│   └── thinking_renderer.py
├── evaluation/                        # 评估（从 data/qa/evaluation/ 迁移）
│   ├── benchmark.py
│   └── audit_storage.py
└── ontology_assistant/                # 本体辅助设计（从 core/ontology/assistant/ 迁移）
    ├── type_inference.py
    ├── constraint_suggester.py
    └── completeness_check.py
```

### 2. 统一 API 端点

废弃 `/api/assistant/`、`/api/qa/`、`/api/ontology-assistant/`，统一为 `/api/chat/`：

| 端点 | 方法 | 说明 | 原对应端点 |
|------|------|------|-----------|
| `/api/chat/message` | POST | **统一 SSE 流式对话**（含 tool-calling + RAG） | `/api/assistant/chat` + `/api/qa/ask/stream` |
| `/api/chat/tools/execute` | POST | 直接执行工具（绕过 LLM） | `/api/assistant/tools/execute` |
| `/api/chat/sessions` | GET/POST/DELETE | 会话 CRUD | `/api/qa/sessions` |
| `/api/chat/sessions/{id}/history` | GET | 会话历史 | `/api/qa/sessions/{id}/history` |
| `/api/chat/evaluate` | POST | 基准评估 | `/api/qa/evaluate` |
| `/api/chat/audit` | GET | 审计列表/详情/统计 | `/api/qa/audit` |
| `/api/chat/retrieval/pillars` | GET | 三支柱检索状态 | `/api/qa/retrieval/pillars` |
| `/api/chat/ontology/suggestions` | GET/POST | 本体设计建议（类型推断、约束建议） | `/api/ontology-assistant/*` |

### 3. 统一 SSE 协议

在 AG-UI 协议基础上扩展，兼容 QA 专用渲染：

```
AG-UI 标准事件（兼容）：
  RUN_STARTED      → 运行开始
  TEXT_MESSAGE_*   → 文本内容流
  TOOL_CALL_*      → 工具调用（含参数/结果）
  CUSTOM           → 扩展事件

CUSTOM 扩展子类型（新增，替代 QA 的 content/sources/chart 等）：
  THINKING         → 推理过程（替代 thinking 事件）
  SOURCES          → 检索来源引用（替代 sources 事件）
  CHART            → 图表渲染数据（替代 chart 事件）
  TEMPORAL         → 时序推理结果（替代 temporal 事件）
  REPORT           → 分析报告（替代 report 事件）
  ONTOLOGY_CHANGED → 本体变更通知（已有，保留）
  CLARIFICATION    → 需要用户澄清（替代 clarification 事件）

事件结构：
{
  "type": "CUSTOM",
  "custom_type": "CHART",            // 新增字段
  "data": { "chart_type": "line", ... },
  "message_id": "msg_xxx",
  "timestamp": "2026-07-18T03:20:00Z"
}
```

**为什么不创建全新协议？** AG-UI 协议已经被 OpenHarness 原生支持，且前端已实现解析。从 AG-UI 扩展而非替换，可以最小化前端改动。

### 4. 统一对话引擎 `UnifiedChatService`

```python
class UnifiedChatService:
    """
    统一对话引擎 — 组合工具执行 + RAG 检索 + 内容渲染。
    
    决策路由：
    1. 需要修改本体？    → tool-calling path（16个工具）
    2. 需要知识检索？    → RAG path（三支柱）
    3. 两者都需要？      → 混合 path（先 RAG 检索 → 以结果为上下文 tool-calling）
    """
    
    def __init__(self):
        self.tool_registry = ToolRegistry()        # 16 个 BaseTool
        self.rag_pipeline = RAGPipeline()           # 五阶段：Understand→Plan→Exec→Fusion→Gen
        self.session_manager = SessionManager()
        self.renderers = RendererRegistry()         # chart / temporal / report / thinking
    
    async def chat_stream(self, request: ChatRequest) -> AsyncGenerator[AGUIEvent]:
        """
        统一聊天入口 — 根据 intent 自动路由到最佳处理路径。
        
        决策逻辑：
        - 快速意图分类（LLM 一次调用判断 category + entity_types）
        - 写操作路径：tool-calling agent
        - 读操作路径：RAG pipeline
        - 混合路径：RAG → tool-calling with RAG context
        """
    
    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        """直接执行工具（不经过 LLM 决策）"""
    
    # ... 会话管理、评估、审计方法
```

### 5. 前端策略：一套 Hook，多层渲染

```
前端组件树：
                                   ┌─────────────────────┐
              各页面入口            │  AIChatPanel (唯一)   │
          ┌────────┬────────┐      │  mode: full|compact   │
     Header按钮  QAPage  本体设计器  │  persona: "qa"|        │
          │        │        │      │    "assistant"|        │
          └────────┼────────┘      │    "ontology-designer" │
                   │               └──────────┬──────────┘
                   ▼                          │
          ┌────────────────┐     ┌────────────▼───────────┐
          │  useUnifiedChat │────▶│  GET /api/chat/message │
          │  (统一 Hook)     │     │  (SSE, AG-UI + 扩展)   │
          └────────┬───────┘     └────────────────────────┘
                   │
          ┌────────▼───────────────────┐
          │  渲染器注册表 (Plugin 模式)  │
          │  ChatRenderer   (默认)      │
          │  ChartRenderer  (图表)      │
          │  TemporalRenderer (时序)    │
          │  ToolCallRenderer (工具调用) │
          │  ThinkingRenderer (推理链)  │
          │  SourceRenderer  (来源引用)  │
          └────────────────────────────┘
```

**关键点**：
- **一个 `useUnifiedChat` Hook**：取代 `useAIChat` + `useQAI`，统一 SSE 解析和状态管理
- **`AIChatPanel` 是唯一对话组件**：通过 `persona` prop 切换不同场景的渲染配置
- **渲染器插件化**：不同类型的响应内容（图表/时序/工具调用）通过注册渲染器扩展，而非写死在组件内
- **页面差异仅在于初始配置**：QAPage = `<AIChatPanel persona="qa" />`，设计器 = `<AIChatPanel persona="ontology-designer" onOntologyChanged={...} />`

### 6. 兼容性策略

向后兼容（渐进迁移，非大爆炸）：

```
Phase A（当前 ADR 接受后）：建立新模块 odap/biz/core/chat/
  ├── 复制 QA Engine 核心逻辑到 engine/pipeline.py
  ├── 复制工具注册到 tools/
  ├── 实现 UnifiedChatService（先简单桥接两个旧引擎）
  └── 统一路由 /api/chat/ 注册，保留旧路由 /api/assistant/ + /api/qa/

Phase B（2-3 个迭代）：逐步迁移
  ├── 前端 QAPage 切换为 /api/chat/message
  ├── AI 助手切换为 /api/chat/message
  ├── 统一会话管理
  └── 移除旧路由（标记 deprecated）

Phase C（稳定后）：清理
  ├── 删除 ChatService（已被 UnifiedChatService 取代）
  ├── 删除 QAEngineV2（已迁移到 pipeline）
  ├── 删除 useAIChat + useQAI（替换为 useUnifiedChat）
  └── 删除旧路由注册
```

---

## 替代方案

### 方案 A：仅统一前端，后端保持独立（不推荐）

- 统一 Hook 但继续调用两个不同的后端 API
- 优点：改动最小
- 缺点：没有解决双引擎、双协议、能力孤立等根本问题

### 方案 B：统一 SSE 协议但不合并引擎（折中）

- 让 ChatService 和 QAEngineV2 都输出 AG-UI 事件
- 优点：协议统一，前端简化
- 缺点：双引擎仍在，维护负担不减

### 方案 C：推荐的统一架构（本 ADR）

- 单一 `UnifiedChatService`，统一端点、协议、会话
- 前端一套 Hook + 渲染器插件
- 优点：根除所有分裂问题，长期维护成本最低
- 缺点：初期迁移工作量大，需要仔细处理兼容性

---

## 影响

### 正面影响

1. **能力融合**：同一对话中"查 + 改"无缝衔接——用户问"有哪些缺失属性的对象类型？"得到答案后直接说"帮我补全"即可
2. **维护简化**：一套引擎、一套路由、一套测试，bug 修复一次生效
3. **协议统一**：AG-UI 扩展协议满足所有场景，前端只需一套 SSE 解析器
4. **会话一致**：所有对话入口共享同一个会话系统，不再有循环依赖
5. **扩展性**：通过渲染器插件模式，新增响应类型（如"地图渲染"、"3D 可视化"）无需改动核心组件

### 负面影响与缓解

| 风险 | 缓解措施 |
|------|---------|
| 迁移期间可能引入回归 | Phase A/B/C 渐进迁移，旧路由保留到 Phase C |
| `UnifiedChatService` 可能成为"上帝类" | 通过组合模式拆分：`PipelineRunner`、`ToolExecutor`、`RendererRegistry`、`SessionManager` 各司其职 |
| QA 的 3000 行引擎重构风险高 | Phase A 先桥接而非重写，通过测试覆盖保证行为不变 |
| 团队需要学习新架构 | ADR + 架构文档 + C4 图；新模块结构与旧模块有明确对照表 |

### 对已有 ADR 的影响

- **ADR-048（本体管理引擎）**：不受影响，本体管理引擎是底层基础设施
- **ADR-049（用户认知引擎）**：本 ADR 的 `UnifiedChatService` 是认知引擎在对话层面的具体实现，不冲突
- **ADR-048/049 中提到的 AI 助手独立组件化**：`core/chat/` 作为独立模块，本身就是组件化设计

---

## 迁移路径检查清单

### Phase A：并行运行（不影响现有功能）

- [ ] 创建 `odap/biz/core/chat/` 模块骨架
- [ ] 复制工具注册到 `chat/tools/`
- [ ] 复制检索引擎到 `chat/retrieval/`
- [ ] 实现 `UnifiedChatService` 桥接层（内部委托给 ChatService + QAEngineV2）
- [ ] 注册 `/api/chat/` 路由（与旧路由并行）
- [ ] 编写统一端点集成测试

### Phase B：逐步切换

- [ ] 前端 `useUnifiedChat` Hook 实现
- [ ] 前端渲染器插件注册机制
- [ ] `AIChatPanel` 扩展 `persona` prop
- [ ] QAPage 切换到统一端点
- [ ] AI 助手 Header 入口切换到统一端点
- [ ] 本体设计器 AI 助手切换到统一端点
- [ ] 统一会话管理（不再依赖 QA sessions）
- [ ] 旧路由标记 `deprecated`

### Phase C：清理

- [ ] 删除 `ChatService`（确认无引用）
- [ ] 删除 `QAEngineV2`（确认已迁移）
- [ ] 删除 `useAIChat` + `useQAI`
- [ ] 删除旧路由注册
- [ ] 更新架构文档

---

## 结论

当前 AI 助手和智能问答的"一套前端、两套后端"架构是不可持续的。统一为 `core/chat/` 模块，对外提供单一 `/api/chat/` 端点，对内组合工具执行和 RAG 检索能力，是正确且必要的架构演化。

**代价**：3 个 Phase 的渐进迁移工作，约 2-3 个迭代周期。
**收益**：消除双引擎维护负担，实现"查改一体"的终极用户体验，为后续扩展（多模态渲染、Agent 自主决策）打下统一基础。

---

## 相关文档

- [ADR-048 本体管理引擎架构决策](./ADR-048_本体管理引擎架构决策.md)
- [ADR-049 用户认知引擎架构决策](./ADR-049_用户认知引擎架构决策.md)
- [AGENTS.md（项目工作规则）](../../AGENTS.md)
- [ARCHITECTURE.md（系统架构入口）](../02-architecture/ARCHITECTURE.md)
