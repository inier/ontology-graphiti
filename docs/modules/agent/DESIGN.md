# Agent 模块 - 设计文档

> **优先级**: P0 | **相关 ADR**: ADR-004, ADR-005, ADR-006

**版本**: 1.1.0 | **日期**: 2026-04-16

---

## 1. 模块概述

Agent 模块是系统的**智能决策中枢**，负责协调各组件完成复杂任务。

**核心职责**:
- OODA 循环执行（Observe-Orient-Decide-Act）
- 多 Agent 协同（Swarm 编排）
- 任务规划与执行
- 链路追踪与日志

**核心组件**:

| 组件 | 位置 | 职责 |
|------|------|------|
| IntelligenceAgent | `odap/biz/agent/` | 情报收集与分析 |
| CommanderAgent | `odap/biz/agent/` | 决策制定 |
| OperationsAgent | `odap/biz/agent/` | 执行决策 |
| SelfCorrectingOrchestrator | `odap/biz/agent/` | 自校正编排器 |
| DomainSwarm | `odap/biz/agent/` | 多 Agent 协同 |

---

## 2. 架构分层

```
┌─────────────────────────────────────────────────────────────┐
│                        DomainSwarm                              │
│  - 多 Agent 协同                                             │
│  - OODA 循环协调                                            │
│  - 任务分配与结果聚合                                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ Intelligence  │  │  Commander    │  │  Operations   │
│    Agent      │  │    Agent      │  │    Agent      │
├───────────────┤  ├───────────────┤  ├───────────────┤
│ Observe       │  │ Orient        │  │ Act           │
│ 情报收集      │  │ 决策制定      │  │ 执行          │
└───────────────┘  └───────────────┘  └───────────────┘
```

---

## 3. IntelligenceAgent

### 3.1 类图

```python
class IntelligenceAgent:
    """
    情报分析 Agent - 负责 OODA 的 Observe 阶段

    职责:
    - 接收用户查询
    - 调用 Skill 收集情报数据
    - 综合分析生成报告
    - 支持 LLM 驱动的 ReAct 分析
    """

    def __init__(self, user_role: str = "intelligence_analyst"):
        self.user_role = user_role
        self.opa_manager = OPAManager()
        self.graph_manager = GraphManager()
        self.llm_api_key = os.getenv('OPENAI_API_KEY', '')
        self.llm_api_base = os.getenv('OPENAI_API_BASE', '')
        self.llm_model = os.getenv('OPENAI_MODEL', '')

    def analyze(self, query: str) -> dict:
        """
        分析查询

        流程:
        1. OPA 权限检查
        2. 调用 LLM 进行 ReAct 分析
        3. 返回结构化报告
        """

    async def a_analyze(self, query: str) -> dict:
        """异步分析版本"""

    def _build_system_prompt(self, query: str) -> str:
        """构建系统提示词"""

    def _call_llm(self, messages: list) -> dict:
        """调用 LLM API"""
```

### 3.2 核心方法

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `analyze()` | 同步分析查询 | dict (报告) |
| `a_analyze()` | 异步分析查询 | dict (报告) |
| `_build_system_prompt()` | 构建提示词 | str |
| `_call_llm()` | 调用 LLM | dict |

### 3.3 ReAct 分析流程

```
┌─────────────────────────────────────────────────────────────┐
│                      ReAct 循环                                    │
├─────────────────────────────────────────────────────────────┤
│  1. Thought: 分析当前状态，决定下一步行动                         │
│  2. Action: 调用 Skill (search_radar, analyze_domain, etc.)   │
│  3. Observation: 收集返回结果                                  │
│  4. 返回步骤 1 继续，直到达到最大迭代次数                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. SelfCorrectingOrchestrator

### 4.1 类图

```python
class SelfCorrectingOrchestrator:
    """
    自校正编排器 - 负责任务执行与自我修正

    职责:
    - 接收用户指令
    - 权限检查 (OPA)
    - 执行任务
    - 结果验证与修正
    """

    def __init__(self, user_role: str = "analyst"):
        self.user_role = user_role
        self.opa_manager = OPAManager()
        self.graph_manager = GraphManager()
        self._execution_history = []

    def run(self, instruction: str) -> dict:
        """
        执行指令

        流程:
        1. 权限检查
        2. 解析指令
        3. 执行任务
        4. 结果验证
        5. 必要时自我修正
        """
```

### 4.2 自校正机制

```python
# 自校正触发条件
SELF_CORRECTION_TRIGGERS = {
    "permission_denied": "OPA 权限不足时触发",
    "execution_error": "执行出错时触发",
    "result_invalid": "结果验证失败时触发",
    "timeout": "执行超时时触发",
}

# 校正策略
CORRECTION_STRATEGIES = {
    "retry": "重试执行",
    "fallback": "使用备用方案",
    "degrade": "降级到简化流程",
    "escalate": "上报给人工处理",
}
```

---

## 5. DomainSwarm

### 5.1 类图

```python
class DomainSwarm:
    """
    多 Agent 协同编排器 - 负责 OODA 完整闭环

    职责:
    - 初始化多个 Agent
    - 协调 OODA 循环
    - 阶段转换管理
    - 结果聚合
    """

    def __init__(self):
        self.intelligence_agent = IntelligenceAgent()
        self.commander_agent = CommanderAgent()
        self.operations_agent = OperationsAgent()
        self.current_phase = SwarmPhase.INITIAL
        self.phases_completed = []

    async def initialize(self):
        """初始化 Swarm"""

    async def execute_mission(self, mission: str) -> SwarmResult:
        """
        执行任务

        OODA 循环:
        1. Observe: IntelligenceAgent 收集情报
        2. Orient: CommanderAgent 分析态势
        3. Decide: 制定决策方案
        4. Act: OperationsAgent 执行
        """

    async def _observe(self, mission: str) -> dict:
        """Observe 阶段"""

    async def _orient(self, intel: dict) -> dict:
        """Orient 阶段"""

    async def _decide(self, analysis: dict) -> dict:
        """Decide 阶段"""

    async def _act(self, decision: dict) -> dict:
        """Act 阶段"""
```

### 5.2 OODA 阶段定义

```python
class SwarmPhase(str, Enum):
    """Swarm 执行阶段"""
    INITIAL = "initial"           # 初始化
    OBSERVE = "observe"          # 情报收集
    ORIENT = "orient"            # 态势分析
    DECIDE = "decide"            # 决策制定
    ACT = "act"                  # 执行
    EVALUATE = "evaluate"        # 评估
    COMPLETED = "completed"       # 完成

@dataclass
class SwarmResult:
    """Swarm 执行结果"""
    mission_id: str
    success: bool
    phases_completed: List[SwarmPhase]
    final_state: dict
    execution_time_ms: float
    error_message: Optional[str] = None
```

---

## 6. Agent 协作流程

### 6.1 典型任务流程

```
用户查询: "分析 B 区威胁"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│              SelfCorrectingOrchestrator                          │
│  1. OPA 权限检查                                             │
│  2. 解析查询意图                                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  IntelligenceAgent                              │
│  1. 调用 Skill 收集数据 (search_radar, analyze_domain)        │
│  2. 调用 LLM 进行分析                                         │
│  3. 生成情报报告                                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   CommanderAgent                                │
│  1. 分析情报报告                                              │
│  2. 识别威胁和机会                                            │
│  3. 生成决策建议                                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  OperationsAgent                               │
│  1. 执行决策方案                                              │
│  2. OPA 权限再次检查                                          │
│  3. 返回执行结果                                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
                      返回结果
```

### 6.2 链路追踪

```python
class TraceSpan:
    """轻量级链路追踪 Span"""

    def __init__(self, name: str, parent=None):
        self.name = name
        self.parent = parent
        self.start_time = time.time()
        self.end_time = None
        self.metadata = {}

    def finish(self):
        """结束 Span"""
        self.end_time = time.time()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "name": self.name,
            "duration_ms": (self.end_time - self.start_time) * 1000,
            "metadata": self.metadata,
        }

# 追踪示例
with TraceSpan("intelligence_analysis") as span:
    result = agent.analyze(query)
    span.metadata["result_summary"] = result.get("summary", "")
```

---

## 7. 与其他模块的交互

```
┌─────────────────────────────────────────────────────────────┐
│                       Agent 模块                                    │
├─────────────────────────────────────────────────────────────┤
│  IntelligenceAgent ──► Skill Registry ──► Skills              │
│  SelfCorrectingOrchestrator ──► OPAManager ──► OPA            │
│  DomainSwarm ──► GraphManager ──► Graphiti                    │
│  All Agents ──► LLM Service ──► ZhipuAI / OpenAI             │
└─────────────────────────────────────────────────────────────┘
```

### 7.1 依赖注入

```python
class AgentFactory:
    """Agent 工厂类"""

    @staticmethod
    def create_intelligence_agent(config: dict = None) -> IntelligenceAgent:
        return IntelligenceAgent(
            user_role=config.get("user_role", "analyst"),
            opa_manager=config.get("opa_manager") or OPAManager(),
            graph_manager=config.get("graph_manager") or GraphManager(),
        )

    @staticmethod
    def create_swarm(config: dict = None) -> DomainSwarm:
        return DomainSwarm(
            intelligence_agent=AgentFactory.create_intelligence_agent(config),
            commander_agent=AgentFactory.create_commander_agent(config),
            operations_agent=AgentFactory.create_operations_agent(config),
        )
```

---

## 8. 配置与扩展

### 8.1 Agent 配置

```python
# Agent 配置
AGENT_CONFIG = {
    "max_iterations": 5,           # ReAct 最大迭代次数
    "timeout_seconds": 300,         # 执行超时
    "retry_count": 3,              # 重试次数
    "llm_temperature": 0.7,        # LLM 温度参数
    "enable_trace": True,          # 是否启用追踪
}
```

### 8.2 自定义 Agent

```python
# 注册自定义 Agent
class CustomAgent(BaseAgent):
    """自定义 Agent 示例"""

    async def execute(self, task: dict) -> dict:
        """执行任务"""
        # 实现自定义逻辑
        pass

# 注册到工厂
AgentFactory.register("custom", CustomAgent)
```

---

## 9. 相关文档

- [ADR-004: 统一 Skill 体系架构](../../adr/ADR-004_统一_skill_体系架构.md)
- [ADR-005: 分层 Agent 架构](../../adr/ADR-005_分层_agent_架构openharness_原生_领域扩展.md)
- [ADR-006: Agent 链路追踪系统](../../adr/ADR-006_agent_链路追踪系统.md)
- [Swarm 编排模块](../swarm_orchestrator/DESIGN.md)
- [OPA Policy 模块](../opa_policy/DESIGN.md)
- [Skills 模块](../skills/DESIGN.md)
