# 问答引擎模块 (QA Engine) - 设计文档

> **模块 ID**: M-12 | **优先级**: P0 | **相关 ADR**: ADR-002, ADR-044
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L4 应用服务层

---

## 1. 模块概述

### 1.1 模块定位

问答引擎是 ODAP 平台的**智能交互核心**，将用户自然语言问题转化为结构化知识图谱查询与 LLM 推理的协同流程。它是用户与平台知识的主要交互界面——用户提问，引擎从 Graphiti 双时态知识图谱检索事实、结合 LLM 推理生成答案，并附带完整的溯源链路。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **自然语言理解** | 用户友好 | 无需学习查询语言，自然语言即问即答 |
| **知识图谱增强** | 事实精准 | RAG 架构确保答案基于知识图谱事实 |
| **双时态推理** | 时间感知 | 利用 Graphiti 双时态能力，支持"当时发生了什么"类问题 |
| **溯源可信** | 答案可追溯 | 每个答案附带来源节点/边，支持跳转验证 |
| **上下文记忆** | 多轮对话 | 维护会话上下文，支持追问和澄清 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L6  用户交互层                                                               │
│     对话界面 / 问答面板                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ L5  API 网关                                                                 │
│     /api/qa/*  路由                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ ★ L4  应用服务层 ★                                                            │
│     QAEngine (核心)                                                          │
│         ├── QueryUnderstanding (查询理解)                                      │
│         ├── RetrievalOrchestrator (检索编排)                                   │
│         ├── AnswerGenerator (答案生成)                                        │
│         └── SourceTracker (溯源追踪)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ L3  Agent 编排层                                                              │
│     Intelligence Agent (复杂推理场景)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ L2  领域技能层                                                                │
│     ToolRegistry (工具调用)                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1  基础设施层                                                                │
│     GraphitiClient (图谱检索) / LLM Provider (推理)                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念模型

### 2.1 问答会话

```python
class QASession:
    """问答会话 - 一次对话的上下文容器"""
    id: str                         # 会话 ID
    workspace_id: str               # 工作空间
    user_id: str                    # 用户 ID
    created_at: datetime            # 创建时间
    updated_at: datetime            # 更新时间
    messages: list[QAMessage]       # 消息列表
    context: SessionContext         # 会话上下文
    status: SessionStatus           # 会话状态

class SessionStatus(str, Enum):
    ACTIVE = "active"               # 活跃
    IDLE = "idle"                   # 空闲（超时未操作）
    CLOSED = "closed"               # 已关闭

class SessionContext:
    """会话上下文 - 维护对话状态"""
    active_entities: list[str]      # 当前关注的实体 ID
    active_time_range: TimeRange | None  # 当前讨论的时间范围
    topic_stack: list[str]          # 话题栈（支持回退）
    mentioned_resources: list[str]  # 提及的资源 ID
    pending_clarifications: list[str]  # 待澄清问题
```

### 2.2 问答消息

```python
class QAMessage:
    """问答消息 - 单轮对话"""
    id: str                         # 消息 ID
    session_id: str                 # 会话 ID
    role: MessageRole               # 角色
    content: str                    # 内容
    timestamp: datetime             # 时间戳
    metadata: QAMetadata | None     # 元数据（答案相关）

class MessageRole(str, Enum):
    USER = "user"                   # 用户提问
    ASSISTANT = "assistant"         # 系统回答
    SYSTEM = "system"               # 系统消息（澄清/提示）
    TOOL = "tool"                   # 工具调用结果

class QAMetadata:
    """答案元数据"""
    query_intent: QueryIntent       # 查询意图
    retrieved_facts: list[FactRef]  # 检索到的事实
    confidence: float               # 置信度 (0-1)
    latency_ms: int                 # 响应延迟
    llm_model: str                  # 使用的 LLM 模型
    token_usage: TokenUsage         # Token 用量
    source_nodes: list[str]         # 来源节点 ID
    source_edges: list[str]         # 来源边 ID
    tool_calls: list[str]           # 调用的工具 ID
```

### 2.3 查询意图

```python
class QueryIntent:
    """查询意图 - 理解用户问题的结构化表示"""
    intent_type: IntentType         # 意图类型
    entities: list[EntityRef]       # 提及的实体
    relations: list[str]            # 提及的关系
    time_expression: TimeExpression | None  # 时间表达
    filters: dict                   # 过滤条件
    original_query: str             # 原始问题
    rewritten_query: str            # 改写后的问题

class IntentType(str, Enum):
    ENTITY_LOOKUP = "entity_lookup"         # 实体查询："XX部队在哪"
    RELATION_QUERY = "relation_query"       # 关系查询："A和B什么关系"
    TIME_SERIES = "time_series"             # 时序查询："过去3天的变化"
    COMPARISON = "comparison"               # 对比查询："A和B的实力对比"
    AGGREGATION = "aggregation"             # 聚合查询："总共有多少XX"
    CAUSALITY = "causality"                 # 因果查询："为什么XX会发生"
    HYPOTHETICAL = "hypothetical"           # 假设查询："如果XX会怎样"
    CLARIFICATION = "clarification"         # 澄清请求
    GENERAL = "general"                     # 通用问答

class TimeExpression:
    """时间表达"""
    raw: str                        # 原始表达（"过去3天"、"昨天"）
    resolved_start: datetime        # 解析后的起始时间
    resolved_end: datetime          # 解析后的结束时间
    temporal_type: str              # "point" | "range" | "relative"

class EntityRef:
    """实体引用"""
    name: str                       # 原始名称
    resolved_id: str | None         # 解析后的实体 ID
    entity_type: str | None         # 实体类型
    confidence: float               # 解析置信度
```

### 2.4 事实引用

```python
class FactRef:
    """事实引用 - 答案中的单条事实来源"""
    fact_content: str               # 事实内容
    source_type: str                # "node" | "edge" | "episode"
    source_id: str                  # 来源 ID
    valid_at: datetime | None       # 有效时间
    transaction_at: datetime | None # 事务时间
    relevance_score: float          # 相关度分数
```

---

## 3. 核心组件设计

### 3.1 QAEngine

```python
class QAEngine:
    """
    问答引擎 - 核心入口

    处理流程：
    Question → QueryUnderstanding → RetrievalOrchestrator → AnswerGenerator → Answer
    """

    def __init__(
        self,
        query_understanding: QueryUnderstanding,
        retrieval: RetrievalOrchestrator,
        answer_generator: AnswerGenerator,
        source_tracker: SourceTracker,
        session_manager: QASessionManager,
    ):
        self._understanding = query_understanding
        self._retrieval = retrieval
        self._generator = answer_generator
        self._tracker = source_tracker
        self._sessions = session_manager

    async def ask(
        self,
        question: str,
        session_id: str | None = None,
        workspace_id: str | None = None,
        stream: bool = False,
    ) -> QAResponse:
        """
        问答主入口

        流程：
        1. 获取/创建会话
        2. 查询理解（意图识别 + 实体链接）
        3. 检索编排（图谱检索 + 向量检索 + 工具调用）
        4. 答案生成（LLM + RAG）
        5. 溯源追踪
        6. 更新会话上下文
        7. 记录审计日志
        """
        session = await self._sessions.get_or_create(session_id, workspace_id)

        # Step 1: 查询理解
        intent = await self._understanding.analyze(question, session.context)

        # Step 2: 检索编排
        retrieval_result = await self._retrieval.retrieve(intent, session.context)

        # Step 3: 答案生成
        if stream:
            return self._generator.generate_stream(intent, retrieval_result, session)
        else:
            answer = await self._generator.generate(intent, retrieval_result, session)

        # Step 4: 溯源追踪
        answer = await self._tracker.annotate_sources(answer, retrieval_result)

        # Step 5: 更新会话
        await self._sessions.add_message(session.id, "user", question)
        await self._sessions.add_message(session.id, "assistant", answer.content, answer.metadata)

        return answer

    async def ask_with_tools(
        self,
        question: str,
        allowed_tools: list[str] | None = None,
        **kwargs,
    ) -> QAResponse:
        """
        带工具调用的问答

        当查询意图需要工具辅助时（如实时数据、计算），
        自动编排工具调用流程。
        """
        ...
```

### 3.2 QueryUnderstanding（查询理解）

```python
class QueryUnderstanding:
    """
    查询理解 - 将自然语言问题转化为结构化查询意图

    流程：
    1. LLM 意图分类
    2. 实体识别与链接
    3. 时间表达式解析
    4. 查询改写（结合上下文）
    5. 歧义检测与澄清
    """

    async def analyze(self, question: str, context: SessionContext) -> QueryIntent:
        """
        分析查询意图

        实现策略：
        - 使用 LLM 做意图分类（few-shot）
        - 结合知识图谱做实体链接
        - 使用规则引擎解析时间表达式
        - 利用会话上下文做共指消解
        """
        ...

    async def detect_ambiguity(self, intent: QueryIntent) -> list[Ambiguity]:
        """
        检测歧义

        场景：
        - 实体名称冲突（同名不同实体）
        - 意图模糊（可能是查询也可能是操作）
        - 时间表达模糊
        """
        ...

    async def rewrite_with_context(self, question: str, context: SessionContext) -> str:
        """
        结合上下文改写查询

        示例：
        - Q1: "东风21D的射程是多少" → "东风21D弹道导弹的射程"
        - Q2: "它呢？" → "东风21D弹道导弹的[上一问题遗漏的属性]"
        """
        ...
```

### 3.3 RetrievalOrchestrator（检索编排器）

```python
class RetrievalOrchestrator:
    """
    检索编排器 - 协调多源检索

    检索策略：
    1. 图谱检索（Graphiti search）— 事实级
    2. 向量检索（embedding 相似度）— 语义级
    3. 结构化查询（Cypher）— 精确级
    4. 工具调用（实时数据）— 增补级

    检索结果去重、融合、重排序。
    """

    def __init__(
        self,
        graphiti_client: "GraphitiClient",
        llm_provider: "LLMProvider",
        tool_registry: "IToolRegistry",
    ):
        self._graphiti = graphiti_client
        self._llm = llm_provider
        self._tools = tool_registry

    async def retrieve(self, intent: QueryIntent, context: SessionContext) -> RetrievalResult:
        """
        执行检索编排

        策略选择逻辑：
        - ENTITY_LOOKUP → 图谱检索 + 向量检索
        - RELATION_QUERY → Cypher 查询 + 图谱检索
        - TIME_SERIES → Cypher 时序查询 + Graphiti 双时态
        - COMPARISON → 多实体并行检索
        - AGGREGATION → Cypher 聚合查询
        - CAUSALITY → 图谱路径查询 + LLM 推理
        - HYPOTHETICAL → 交由 Agent 推理 + 模拟推演
        """
        ...

    async def _graph_search(self, intent: QueryIntent) -> list[FactRef]:
        """图谱检索"""
        ...

    async def _vector_search(self, query: str, top_k: int = 10) -> list[FactRef]:
        """向量检索"""
        ...

    async def _cypher_search(self, intent: QueryIntent) -> list[dict]:
        """结构化 Cypher 查询"""
        ...

    async def _tool_augmented_search(self, intent: QueryIntent) -> list[FactRef]:
        """工具增强检索（实时数据）"""
        ...

    async def _merge_and_rerank(
        self,
        results: dict[str, list],
        intent: QueryIntent,
    ) -> RetrievalResult:
        """多源结果融合与重排序"""
        ...

class RetrievalResult:
    """检索结果"""
    facts: list[FactRef]             # 事实列表
    nodes: list[dict]                # 相关节点
    edges: list[dict]                # 相关边
    tool_results: list[dict]         # 工具调用结果
    total_retrieved: int             # 总检索条数
    retrieval_latency_ms: int        # 检索延迟
    sources_used: list[str]          # 使用的检索源
```

### 3.4 AnswerGenerator（答案生成器）

```python
class AnswerGenerator:
    """
    答案生成器 - 基于检索结果生成自然语言答案

    策略：
    - RAG: 检索增强生成（默认）
    - Direct: 检索结果直接格式化（事实查询）
    - ChainOfThought: 链式推理（复杂问题）
    - ToolAugmented: 工具辅助（需要计算/实时数据）
    """

    async def generate(
        self,
        intent: QueryIntent,
        retrieval: RetrievalResult,
        session: QASession,
    ) -> QAAnswer:
        """
        生成答案

        流程：
        1. 选择生成策略
        2. 构造 LLM Prompt（System + Context + Question + Facts）
        3. 调用 LLM 生成
        4. 后处理（格式化、溯源标记）
        """
        ...

    async def generate_stream(
        self,
        intent: QueryIntent,
        retrieval: RetrievalResult,
        session: QASession,
    ) -> AsyncIterator[str]:
        """流式生成答案（SSE 推送）"""
        ...

    def _build_prompt(
        self,
        intent: QueryIntent,
        retrieval: RetrievalResult,
        session: QASession,
    ) -> list[dict]:
        """
        构造 LLM Prompt

        结构：
        - System: 角色设定 + 约束（必须基于事实回答、标注来源）
        - Context: 会话历史摘要 + 当前关注的实体
        - Facts: 检索到的事实列表（编号标注）
        - Question: 用户问题
        """
        ...
```

### 3.5 SourceTracker（溯源追踪器）

```python
class SourceTracker:
    """
    溯源追踪器 - 为答案中的每条断言标注来源

    功能：
    - 答案中的事实性断言标注来源节点/边
    - 支持点击跳转到图谱对应位置
    - 双时态信息展示（"此信息有效于 X 至 Y"）
    """

    async def annotate_sources(
        self, answer: QAAnswer, retrieval: RetrievalResult
    ) -> QAAnswer:
        """
        为答案标注来源

        实现方式：
        1. 提取答案中的事实性断言
        2. 与检索结果匹配
        3. 插入来源标注 [1], [2]...
        4. 生成来源列表
        """
        ...

    def _match_claim_to_fact(self, claim: str, facts: list[FactRef]) -> FactRef | None:
        """将断言匹配到事实来源"""
        ...
```

---

## 4. 会话管理

### 4.1 QASessionManager

```python
class QASessionManager:
    """问答会话管理器"""

    async def create_session(self, workspace_id: str, user_id: str) -> QASession:
        """创建新会话"""
        ...

    async def get_session(self, session_id: str) -> QASession | None:
        """获取会话"""
        ...

    async def get_or_create(self, session_id: str | None, workspace_id: str | None) -> QASession:
        """获取或创建会话"""
        ...

    async def add_message(self, session_id: str, role: str, content: str, metadata: QAMetadata | None = None) -> None:
        """添加消息"""
        ...

    async def update_context(self, session_id: str, context: SessionContext) -> None:
        """更新会话上下文"""
        ...

    async def close_session(self, session_id: str) -> None:
        """关闭会话"""
        ...

    async def list_sessions(self, user_id: str, workspace_id: str | None = None) -> list[QASession]:
        """列出用户的会话"""
        ...
```

### 4.2 会话存储

```python
# SQLite Schema
CREATE TABLE qa_sessions (
    id          TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    context     TEXT NOT NULL,  -- JSON
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE qa_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES qa_sessions(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    TEXT,  -- JSON
    timestamp   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES qa_sessions(id)
);

CREATE INDEX idx_qa_messages_session ON qa_messages(session_id, timestamp);
```

---

## 5. REST API

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| POST | /api/qa/sessions | 创建会话 | qa:session:create |
| GET | /api/qa/sessions | 列出会话 | qa:session:list |
| GET | /api/qa/sessions/{id} | 获取会话 | qa:session:read |
| DELETE | /api/qa/sessions/{id} | 关闭会话 | qa:session:delete |
| POST | /api/qa/ask | 问答（非流式） | qa:ask |
| POST | /api/qa/ask/stream | 问答（SSE 流式） | qa:ask |
| GET | /api/qa/sessions/{id}/history | 获取会话历史 | qa:session:read |
| POST | /api/qa/sessions/{id}/feedback | 提交反馈 | qa:feedback |

---

## 6. 双时态问答增强

### 6.1 时态查询模式

```python
class TemporalQueryHandler:
    """
    双时态查询处理器

    利用 Graphiti 的 valid_time + transaction_time，
    支持以下时态查询模式：
    """

    async def point_in_time_query(
        self, question: str, as_of: datetime
    ) -> QAResponse:
        """
        "截至 X 时间，Y 是什么状态？"

        Graphiti 查询：
        - valid_at <= as_of
        - 取最新的 valid_time 事实
        """
        ...

    async def time_range_query(
        self, question: str, start: datetime, end: datetime
    ) -> QAResponse:
        """
        "X 到 Y 期间，发生了什么变化？"

        Graphiti 查询：
        - valid_at >= start AND valid_at <= end
        - 返回变化序列
        """
        ...

    async def evolution_query(
        self, entity_id: str
    ) -> list[TimePoint]:
        """
        "XX 的时间演变历程"

        Graphiti 查询：
        - 获取实体的所有 Episode
        - 按 valid_at 排序
        - 生成演变时间线
        """
        ...

    async def as_known_at_query(
        self, question: str, known_at: datetime
    ) -> QAResponse:
        """
        "根据 X 时的信息，Y 是什么？"

        Graphiti 查询：
        - transaction_at <= known_at
        - 返回"当时已知"的信息（区别于 point_in_time）
        """
        ...
```

---

## 7. 与 Agent 层的协作

```python
class QAAgentBridge:
    """
    问答引擎与 Agent 层的桥接

    复杂问题升级策略：
    - 简单查询 → QAEngine 直接处理
    - 中等复杂 → QAEngine + Tool 调用
    - 高复杂 → 升级到 Intelligence Agent

    升级判断标准：
    - 需要多步推理 → Agent
    - 需要跨领域关联 → Agent
    - 需要自主判断 → Agent
    - 查询理解置信度 < 0.6 → Agent
    """

    def should_escalate_to_agent(self, intent: QueryIntent, confidence: float) -> bool:
        """判断是否需要升级到 Agent"""
        ...

    async def escalate(self, question: str, session: QASession) -> QAResponse:
        """升级到 Agent 处理"""
        ...
```

---

## 8. 非功能设计

| 维度 | 指标 | 实现方式 |
|------|------|---------|
| 简单问答响应 | < 3s (P95) | 检索缓存 + 预计算 |
| 复杂问答响应 | < 10s (P95) | 流式输出 + 并行检索 |
| 检索延迟 | < 500ms (P95) | Graphiti 缓存 + 索引优化 |
| 并发会话 | > 100 | 异步处理 + 连接池 |
| 答案准确率 | > 85% (事实性问题) | RAG + 溯源验证 |
| Token 效率 | < 4K tokens/question | 检索剪枝 + 摘要压缩 |

---

## 9. 实现路径

### Phase 0 (当前)

- [x] QAEngine 核心模型定义
- [x] QAEngine.ask() 主流程设计
- [ ] QueryUnderstanding LLM 集成
- [ ] Graphiti 检索适配

### Phase 1

- [ ] RetrievalOrchestrator 多源检索
- [ ] 双时态查询处理器
- [ ] 会话管理与持久化
- [ ] SSE 流式输出

### Phase 2

- [ ] Agent 升级机制
- [ ] 工具增强检索
- [ ] 答案质量评估与反馈闭环
- [ ] 语义缓存（相似问题命中）

---

## 10. 前端架构设计

### 10.1 前端模块定位

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L6  用户交互层                                                               │
│     对话界面 / 问答面板                                                      │
│     ├── Sidebar (侧边栏)                                                    │
│     │   ├── NewChatButton (新对话)                                          │
│     │   ├── SessionList (会话列表)                                          │
│     │   └── QuickActions (快捷操作)                                         │
│     ├── ChatHeader (头部导航)                                                │
│     ├── MessageList (消息列表)                                               │
│     └── ChatInput (输入组件)                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ L5  状态管理层                                                              │
│     ├── useQAI (问答状态管理)                                                │
│     ├── useSession (会话管理)                                                │
│     └── useChatStorage (持久化)                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ L4  服务层                                                                  │
│     ├── API 适配层 (fetch)                                                   │
│     └── OpenHarnessProvider (上下文)                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.2 前端组件层次

```typescript
// 组件层次结构（参考千问APP设计风格）
QAChatPage (Layout)
├── Sidebar (左侧边栏 - 可折叠)
│   ├── SidebarHeader     // 标题栏
│   ├── NewChatButton     // 新对话按钮
│   ├── SessionList       // 会话列表
│   │   └── SessionItem   // 会话项（头像、标题、时间）
│   └── QuickActions      // 快捷操作按钮
└── Content (主内容区)
    ├── ChatHeader        // 头部导航栏
    ├── MessageList       // 消息列表容器
    │   ├── WelcomeSection // 欢迎页面（空状态）
    │   └── MessageItem   // 单条消息
    └── ChatInput         // 输入区域
        ├── TextArea      // 文本输入
        └── SendButton    // 发送/停止按钮
```

### 10.3 布局设计规范

| 区域 | 宽度 | 样式特征 |
|------|------|----------|
| Sidebar | 280px (展开) / 60px (折叠) | 深色渐变背景 (#1a1a2e → #16213e) |
| Content | 剩余空间 | 浅色背景 (#fafafa) |
| MessageWrapper | 最大 900px | 居中对齐 |

### 10.4 交互设计规范

**侧边栏交互**：
- 悬停显示删除按钮
- 点击会话项切换会话
- 支持折叠/展开切换
- 双击会话项可重命名（预留）

**消息列表交互**：
- 自动滚动到底部
- 加载状态显示思考动画
- 支持消息来源卡片展开
- 支持快捷问题按钮

**输入区域交互**：
- Enter 发送，Shift+Enter 换行
- 加载状态显示停止按钮
- 输入框聚焦状态高亮边框

### 10.5 状态管理架构

```
┌──────────────────────────────────────────────┐
│                      React Component Tree                     │
│                                                               │
│  QAChatPage                                                  │
│  ├── useQAI() ────────────► Messages, Status, SessionId     │
│  ├── useSession() ────────► Sessions, CRUD Operations       │
│  └── useChatStorage() ───► LocalStorage Persistence         │
│                                                               │
└──────────────────────────────────────────────────────┘
```

**状态分类**：

| 状态类型 | 管理方式 | 说明 |
|---------|---------|------|
| 消息列表 | useState + useQAI | 内存状态，随会话变化 |
| 加载状态 | useState | idle/submitting/streaming/error |
| 会话 ID | useState + localStorage | 持久化到本地 |
| 历史会话 | useState + useSession | 从 API 加载 |
| 用户输入 | useState | 临时状态 |

---

## 11. 前端会话管理设计

### 11.1 会话生命周期

```
┌─────────────┐    sendMessage     ┌──────────────┐    API     ┌─────────────┐
│   NEW       │ ─────────────────► │   ACTIVE     │ ─────────► │  BACKEND    │
│   (初始)    │                    │   (进行中)   │            │   Session   │
└─────────────┘                    └──────────────┘            └─────────────┘
       ▲                                   │
       │                                   │ close/delete
       │                                   ▼
       │                            ┌──────────────┐
       └────────────────────────────│    CLOSED    │
                                    │    (已关闭)  │
                                    └──────────────┘
```

### 11.2 前端会话管理组件

```typescript
// 会话管理 Hook 接口
export interface UseSessionReturn {
  sessions: Session[];              // 会话列表
  loading: boolean;                // 加载状态
  error: Error | null;             // 错误状态
  fetchSessions: () => Promise<void>;      // 刷新列表
  loadSession: (id: string) => Promise<Session | null>;  // 加载详情
  deleteSession: (id: string) => Promise<boolean>;       // 删除会话
}

// 会话数据模型
export interface Session {
  session_id: string;        // 会话 ID
  summary: string;          // 摘要（自动生成或手动）
  message_count: number;    // 消息数量
  model: string;           // 使用的 LLM 模型
  created_at: number;       // 创建时间戳
}
```

### 11.3 本地存储策略

```typescript
interface ChatStorageData {
  sessionId: string | null;      // 当前会话 ID
  messages: QAMessage[];         // 消息列表
  currentSessionId: string | null;
  lastUpdated: number;            // 最后更新时间
}

// 存储键生成策略
function getStorageKey(sessionId: string | null): string {
  return sessionId
    ? `qa_chat_state_${sessionId}`
    : 'qa_chat_state_default';
}

// 防抖策略：500ms
const DEBOUNCE_MS = 500;
```

### 11.4 多会话支持

```typescript
// 切换会话流程
async function switchSession(targetSessionId: string) {
  // 1. 保存当前会话到本地
  persistMessages(currentMessages, currentSessionId);

  // 2. 更新当前会话 ID
  setSessionId(targetSessionId);

  // 3. 从本地加载目标会话
  const stored = loadState(targetSessionId);
  if (stored) {
    setMessages(stored.messages);
  } else {
    // 4. 如果本地没有，从 API 加载历史
    const session = await loadSession(targetSessionId);
    if (session) {
      setMessages(session.messages);
    }
  }
}
```

---

## 12. OpenHarness 集成设计

### 12.1 Provider 配置

```typescript
// QAIProvider.tsx
import { OpenHarnessProvider } from '@openharness/react';

export function QAIProvider({ children }: QAIProviderProps) {
  return (
    <OpenHarnessProvider>
      {children}
    </OpenHarnessProvider>
  );
}
```

### 12.2 API 端点配置

```typescript
// 后端 API 端点
const API_ENDPOINT = 'http://localhost:8000/api/qa/ask';
const SESSIONS_ENDPOINT = 'http://localhost:8000/api/qa/sessions';
```

### 12.3 错误处理流程

```
┌─────────────┐    fetch    ┌──────────────┐
│   UI       │ ──────────► │   Backend    │
│  Component │             │   API        │
└─────────────┘             └──────────────┘
       ▲                           │
       │                           │ Error Response
       │                           ▼
       │                    ┌──────────────┐
       │                    │  Error       │
       │                    │  Handler     │
       │                    └──────────────┘
       │                           │
       │         ┌─────────────────┼─────────────────┐
       │         ▼                 ▼                 ▼
       │   ┌──────────┐     ┌──────────┐     ┌──────────┐
       │   │ Network  │     │  Server  │     │ Timeout  │
       │   │ Error    │     │  Error   │     │ Error    │
       │   └──────────┘     └──────────┘     └──────────┘
       │         │                 │                 │
       │         └────────┬────────┴────────┬────────┘
       │                  ▼                 ▼
       │           ┌──────────────┐  ┌──────────────┐
       └──────────►│  Retry/      │  │  Show Error  │
                    │  Abort       │  │  Message     │
                    └──────────────┘  └──────────────┘
```

---

## 13. 性能优化策略

### 13.1 渲染优化

| 策略 | 实现方式 | 效果 |
|------|---------|------|
| 虚拟列表 | react-window | 支持 1000+ 消息 |
| 懒加载 | React.lazy | 首屏加载优化 |
| 备忘录化 | useMemo/useCallback | 减少重渲染 |
| 防抖存储 | 500ms debounce | 减少 IO 操作 |

### 13.2 网络优化

| 策略 | 实现方式 | 效果 |
|------|---------|------|
| 请求取消 | AbortController | 停止冗余请求 |
| 请求缓存 | SWR/React Query | 减少重复请求 |
| 超时控制 | timeout 配置 | 避免长时间等待 |
| 重试机制 | 指数退避 | 临时故障恢复 |

### 13.3 内存优化

| 策略 | 实现方式 | 效果 |
|------|---------|------|
| 消息截断 | 保留最近 N 条 | 控制内存占用 |
| 图片压缩 | 缩略图展示 | 减少内存占用 |
| 及时清理 | useEffect cleanup | 防止内存泄漏 |
| 会话压缩 | 历史摘要 | 减少存储占用 |

---

**相关文档**:
- [全链路架构设计](../../02-architecture/ARCHITECTURE_FULL_CHAIN.md) — Phase 3 用户问答架构
- [全链路深入实现设计 v2.0](../../02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md) — Phase 3 会话记忆/上下文窗口/引用溯源
- [OPA 策略模块设计](../opa_policy/DESIGN.md)
- [知识图谱模块设计](../graphiti_client/DESIGN.md)
- [安全策略文档](../../05-security/SECURITY.md)
