# 工具注册表模块 (Tool Registry) - 设计文档

> **模块 ID**: M-11 | **优先级**: P0 | **相关 ADR**: ADR-004, ADR-010, ADR-043
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L2 领域技能层

---

## 1. 模块概述

### 1.1 模块定位

工具注册表是 ODAP 平台的**工具发现与调度中枢**，统一管理所有可被 Agent 调用的工具（Skills、内置工具、MCP 工具、外部 API 封装）。它解决三个核心问题：工具从哪来、怎么找、怎么调。

与 M-08 Skill 模块的关系：Skill 是"领域工具的编写规范"，Tool Registry 是"所有工具的运行时注册表"。Skill 注册到 Registry 后才能被 Agent 发现和调用。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **统一注册** | 单一入口 | Skill/内置/MCP/外部 API 统一注册、统一发现 |
| **动态发现** | 运行时查找 | Agent 按能力描述动态发现可用工具 |
| **权限联动** | 调用前校验 | 工具调用前自动触发 OPA 权限校验 |
| **可观测** | 调用追踪 | 工具调用链路追踪、指标采集 |
| **热插拔** | 运行时增删 | 无需重启即可注册/注销工具 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L3  Agent 编排层                                                             │
│     Agent → ToolRegistry.discover() → 选择工具 → ToolRegistry.execute()      │
├─────────────────────────────────────────────────────────────────────────────┤
│ ★ L2  领域技能层 ★                                                            │
│     ToolRegistry (核心)                                                      │
│         ├── ToolDescriptor (工具描述)                                          │
│         ├── ToolExecutor (执行器)                                              │
│         ├── ToolPermissionBridge (权限桥接)                                     │
│         └── ToolHealthMonitor (健康监控)                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1  基础设施层                                                                │
│     Skill 加载器 / MCP Client / OPA Client                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念模型

### 2.1 工具描述符

```python
class ToolDescriptor:
    """
    工具描述符 - 工具的完整元数据

    遵循 OpenHarness Tool 接口规范（ADR-004），
    扩展了分类、权限、健康度等 ODAP 特有信息。
    """
    # 基础信息
    id: str                         # 工具唯一标识 (namespace.name)
    name: str                       # 显示名称
    description: str                # 自然语言描述（供 LLM 理解）
    version: str                    # 语义化版本
    category: ToolCategory          # 工具类别
    source: ToolSource              # 工具来源

    # 接口定义
    parameters: list[ToolParam]     # 参数定义
    return_type: str                # 返回值类型描述
    errors: list[ToolError]         # 可能的错误

    # 运行时信息
    permission_required: list[str]  # 所需权限
    timeout_ms: int                 # 超时时间 (default: 30000)
    retry_policy: RetryPolicy       # 重试策略
    rate_limit: RateLimit | None    # 速率限制

    # 元数据
    tags: list[str]                 # 标签（用于发现）
    examples: list[ToolExample]     # 使用示例（供 LLM few-shot）
    deprecated: bool                # 是否已弃用
    replacement_id: str | None      # 替代工具 ID

class ToolCategory(str, Enum):
    INTELLIGENCE = "intelligence"   # 情报采集
    OPERATIONS = "operations"       # 作战执行
    ANALYSIS = "analysis"           # 分析计算
    VISUALIZATION = "visualization" # 可视化
    SYSTEM = "system"               # 系统管理
    DATA = "data"                   # 数据操作

class ToolSource(str, Enum):
    SKILL = "skill"                 # 来自 Skill 模块
    BUILTIN = "builtin"             # 内置工具
    MCP = "mcp"                     # MCP 协议工具
    API_WRAPPER = "api_wrapper"     # 外部 API 封装
    COMPOSITE = "composite"         # 组合工具（工具链）

class ToolParam:
    """工具参数定义"""
    name: str                       # 参数名
    type: str                       # JSON Schema 类型
    description: str                # 参数描述
    required: bool                  # 是否必填
    default: Any | None             # 默认值
    enum: list[Any] | None          # 枚举值
    schema: dict | None             # JSON Schema（复杂类型）

class ToolError:
    """工具错误定义"""
    code: str                       # 错误码
    description: str                # 错误描述
    mitigation: str                 # 缓解建议

class ToolExample:
    """工具使用示例"""
    description: str                # 示例描述
    parameters: dict                # 示例参数
    expected_output: str            # 预期输出描述

class RetryPolicy:
    """重试策略"""
    max_retries: int = 3            # 最大重试次数
    backoff_ms: int = 1000          # 退避基数
    backoff_multiplier: float = 2.0 # 退避倍数
    retry_on: list[str] = ["timeout", "connection_error"]  # 触发重试的错误

class RateLimit:
    """速率限制"""
    calls_per_minute: int           # 每分钟调用数
    calls_per_hour: int             # 每小时调用数
    concurrent_calls: int           # 并发调用数
```

### 2.2 工具调用上下文

```python
class ToolInvocation:
    """工具调用上下文"""
    invocation_id: str              # 调用唯一标识
    tool_id: str                    # 工具 ID
    parameters: dict                # 调用参数
    caller: ActorInfo               # 调用者
    workspace_id: str               # 工作空间
    trace_id: str                   # 追踪 ID
    parent_invocation_id: str | None  # 父调用（工具链）
    started_at: datetime            # 开始时间
    completed_at: datetime | None   # 完成时间
    status: InvocationStatus        # 调用状态
    result: Any | None              # 返回结果
    error: ToolError | None         # 错误信息
    permission_checked: bool        # 是否已权限校验
    audit_logged: bool              # 是否已记录审计

class InvocationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    DENIED = "denied"               # 权限拒绝
```

---

## 3. 核心组件设计

### 3.1 ToolRegistry（工具注册表）

```python
class ToolRegistry:
    """
    工具注册表 - 核心入口

    职责：
    - 工具注册/注销/查询
    - 工具发现（按能力/标签/分类）
    - 工具执行调度
    - 工具健康监控
    """

    def __init__(
        self,
        executor: ToolExecutor,
        permission_bridge: ToolPermissionBridge,
        health_monitor: ToolHealthMonitor,
        store: ToolStore,
    ):
        self._executor = executor
        self._permission_bridge = permission_bridge
        self._health_monitor = health_monitor
        self._store = store
        self._tools: dict[str, ToolDescriptor] = {}

    async def register(self, descriptor: ToolDescriptor) -> str:
        """
        注册工具

        流程：
        1. 验证工具 ID 唯一性（同工作空间内）
        2. 验证参数定义完整性
        3. 验证权限声明合法性
        4. 存储描述符
        5. 通知健康监控器
        6. 记录审计日志
        """
        ...

    async def unregister(self, tool_id: str, graceful: bool = True) -> bool:
        """
        注销工具

        参数：
        - graceful: 是否优雅注销（等待进行中调用完成）
        """
        ...

    async def discover(
        self,
        *,
        category: ToolCategory | None = None,
        tags: list[str] | None = None,
        keyword: str | None = None,
        capability: str | None = None,  # 自然语言能力描述
    ) -> list[ToolDescriptor]:
        """
        发现工具

        支持三种发现模式：
        1. 精确匹配：按 category/tags 过滤
        2. 关键词搜索：按 name/description 匹配
        3. 语义发现：用 embedding 匹配 capability 描述
        """
        ...

    async def get(self, tool_id: str) -> ToolDescriptor | None:
        """获取工具描述符"""
        ...

    async def execute(
        self,
        tool_id: str,
        parameters: dict,
        *,
        caller: ActorInfo,
        skip_permission: bool = False,
    ) -> ToolInvocation:
        """
        执行工具

        完整流程：
        1. 查找工具描述符
        2. 验证参数（类型/必填/枚举）
        3. 权限校验（OPA）— 除非 skip_permission
        4. 速率限制检查
        5. 创建 ToolInvocation
        6. 执行工具
        7. 记录审计日志
        8. 更新健康指标
        9. 返回结果
        """
        ...

    async def execute_chain(
        self,
        chain: list[ToolChainStep],
        *,
        caller: ActorInfo,
        fail_fast: bool = True,
    ) -> list[ToolInvocation]:
        """
        执行工具链

        支持串行执行多个工具，前一步的输出可作为后一步的输入。
        fail_fast: 任一工具失败则停止；否则跳过失败步骤继续。
        """
        ...

    def list_tools(
        self,
        category: ToolCategory | None = None,
        source: ToolSource | None = None,
    ) -> list[ToolDescriptor]:
        """列出已注册工具"""
        ...
```

### 3.2 ToolExecutor（工具执行器）

```python
class ToolExecutor:
    """
    工具执行器

    路由到不同的执行策略：
    - Skill 工具 → SkillExecutor
    - 内置工具 → BuiltinExecutor
    - MCP 工具 → MCPExecutor
    - API 封装 → APIWrapperExecutor
    - 组合工具 → CompositeExecutor
    """

    def __init__(self, executors: dict[ToolSource, IToolExecutor]):
        self._executors = executors

    async def execute(self, invocation: ToolInvocation) -> ToolInvocation:
        """
        执行工具调用

        1. 根据 tool.source 选择执行器
        2. 设置超时控制
        3. 执行并捕获结果/异常
        4. 应用重试策略
        """
        ...

class IToolExecutor(ABC):
    """工具执行器接口"""

    @abstractmethod
    async def execute(self, descriptor: ToolDescriptor, invocation: ToolInvocation) -> Any:
        """执行工具"""
        ...

    @abstractmethod
    async def validate(self, descriptor: ToolDescriptor) -> bool:
        """验证工具可用性"""
        ...

class SkillExecutor(IToolExecutor):
    """Skill 工具执行器"""
    ...

class MCPExecutor(IToolExecutor):
    """MCP 工具执行器 — 桥接 MCP 协议"""
    ...

class CompositeExecutor(IToolExecutor):
    """
    组合工具执行器

    执行预定义的工具链，支持：
    - 串行执行
    - 条件分支
    - 循环（有限次）
    - 并行执行（fan-out/fan-in）
    """
    ...
```

### 3.3 ToolPermissionBridge（权限桥接）

```python
class ToolPermissionBridge:
    """
    工具权限桥接

    在工具执行前，将工具所需的权限声明
    转换为 OPA 查询请求，执行权限校验。
    """

    def __init__(self, opa_client: "OPAClient"):
        self._opa = opa_client

    async def check_permission(
        self,
        tool_id: str,
        caller: ActorInfo,
        parameters: dict,
        workspace_id: str,
    ) -> PermissionResult:
        """
        校验工具调用权限

        输入：
        - tool_id: 工具标识 → 获取所需权限列表
        - caller: 调用者 → 角色与身份
        - parameters: 参数 → 可能影响权限判断（如目标资源 ID）
        - workspace_id: 工作空间 → 确定策略 Bundle

        OPA 查询：
        input = {
            "action": f"tool:{tool_id}:execute",
            "subject": {"roles": caller.roles, "id": caller.actor_id},
            "resource": {"type": "tool", "id": tool_id, "params": parameters},
            "context": {"workspace_id": workspace_id}
        }
        """
        ...

    async def check_chain_permission(
        self,
        chain: list[ToolChainStep],
        caller: ActorInfo,
        workspace_id: str,
    ) -> list[PermissionResult]:
        """批量校验工具链权限"""
        ...
```

### 3.4 ToolHealthMonitor（健康监控）

```python
class ToolHealthMonitor:
    """
    工具健康监控

    跟踪每个工具的运行状态和性能指标：
    - 调用次数（分钟/小时/天）
    - 成功率
    - 平均耗时
    - 超时次数
    - 最近错误
    - 熔断状态
    """

    async def record_invocation(self, invocation: ToolInvocation) -> None:
        """记录一次调用结果"""
        ...

    async def get_health(self, tool_id: str) -> ToolHealth:
        """获取工具健康状态"""
        ...

    async def is_available(self, tool_id: str) -> bool:
        """检查工具是否可用（未熔断）"""
        ...

    async def get_metrics(self, tool_id: str, window: str = "1h") -> ToolMetrics:
        """获取工具性能指标"""
        ...

class ToolHealth:
    """工具健康状态"""
    tool_id: str
    status: str              # "healthy" | "degraded" | "unhealthy" | "circuit_open"
    success_rate: float      # 成功率
    avg_duration_ms: float   # 平均耗时
    error_count: int         # 最近 1h 错误数
    last_error: str | None   # 最近错误信息
    last_success_at: datetime | None
    circuit_open_since: datetime | None  # 熔断开始时间

class ToolMetrics:
    """工具性能指标"""
    tool_id: str
    window: str
    total_calls: int
    success_calls: int
    failed_calls: int
    timeout_calls: int
    p50_duration_ms: float
    p95_duration_ms: float
    p99_duration_ms: float
    rate_limited_calls: int
    permission_denied_calls: int
```

---

## 4. 组合工具（工具链）

### 4.1 工具链定义

```python
class ToolChainStep:
    """工具链步骤"""
    step_id: str                     # 步骤 ID
    tool_id: str                     # 工具 ID
    parameters: dict | str           # 固定参数 或 引用前步输出的表达式
    condition: str | None            # 执行条件（CEL 表达式）
    timeout_ms: int | None           # 步骤级超时
    on_failure: FailureStrategy      # 失败策略

class FailureStrategy(str, Enum):
    FAIL_FAST = "fail_fast"          # 立即停止
    SKIP = "skip"                    # 跳过，继续下一步
    RETRY = "retry"                  # 重试
    FALLBACK = "fallback"            # 使用备用工具
    DEFAULT_VALUE = "default_value"  # 使用默认值

class CompositeToolDescriptor(ToolDescriptor):
    """组合工具描述符"""
    chain: list[ToolChainStep]       # 工具链步骤
    output_mapping: dict             # 输出映射（从最后一步提取结果）
```

### 4.2 参数传递表达式

```python
# 引用前步输出的表达式语法
# ${{steps.{step_id}.output.{field}}}

# 示例：情报分析工具链
chain = [
    ToolChainStep(
        step_id="collect",
        tool_id="intelligence.radar_scan",
        parameters={"region": "north_sector"},
    ),
    ToolChainStep(
        step_id="analyze",
        tool_id="analysis.threat_assess",
        parameters={"targets": "${{steps.collect.output.targets}}"},
    ),
    ToolChainStep(
        step_id="recommend",
        tool_id="decision.generate_plan",
        parameters={"threats": "${{steps.analyze.output.threats}}"},
    ),
]
```

---

## 5. 与其他模块的交互

### 5.1 依赖关系

| 依赖模块 | 交互方式 | 说明 |
|----------|---------|------|
| M-02 OPA | 调用 | 工具调用前权限校验 |
| M-05 Hook | 被调用 | 工具注册/注销/执行触发 Hook |
| M-06 MCP | 调用 | MCP 工具的执行桥接 |
| M-07 审计日志 | 调用 | 工具调用记录审计 |
| M-08 Skill | 被调用 | Skill 注册到 Registry |

### 5.2 对外提供接口

```python
class IToolRegistry(Protocol):
    """工具注册表接口 - 供 Agent 层使用"""

    async def discover(self, **kwargs) -> list[ToolDescriptor]: ...
    async def execute(self, tool_id: str, parameters: dict, **kwargs) -> ToolInvocation: ...
    async def get(self, tool_id: str) -> ToolDescriptor | None: ...
```

---

## 6. REST API

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/tools | 列出已注册工具 | tool:list |
| POST | /api/tools | 注册工具 | tool:register |
| GET | /api/tools/{id} | 获取工具详情 | tool:read |
| DELETE | /api/tools/{id} | 注销工具 | tool:unregister |
| POST | /api/tools/{id}/execute | 执行工具 | tool:execute |
| GET | /api/tools/{id}/health | 获取工具健康状态 | tool:read |
| GET | /api/tools/{id}/metrics | 获取工具性能指标 | tool:metrics |
| POST | /api/tools/discover | 语义发现工具 | tool:discover |

---

## 7. 非功能设计

| 维度 | 指标 | 实现方式 |
|------|------|---------|
| 注册延迟 | < 100ms | 内存缓存 + 异步持久化 |
| 发现延迟 | < 50ms (精确) / < 500ms (语义) | 索引 + embedding 缓存 |
| 执行延迟 | 工具自身耗时 + < 10ms 调度开销 | 权限校验并行化 |
| 并发执行 | > 100 并发调用 | 异步执行器 + 连接池 |
| 可用性 | 工具熔断不影响注册表 | 熔断器隔离 |

---

## 8. 实现路径

### Phase 0 (当前)

- [x] ToolDescriptor 模型定义
- [x] ToolRegistry 基础接口
- [ ] SkillExecutor 实现
- [ ] 基础权限校验集成

### Phase 1

- [ ] MCPExecutor（桥接 MCP 协议）
- [ ] CompositeExecutor（工具链）
- [ ] ToolHealthMonitor + 熔断器
- [ ] 语义发现（embedding 匹配）

### Phase 2

- [ ] 工具版本管理
- [ ] 工具灰度发布
- [ ] 跨工作空间工具共享
- [ ] 工具调用链路追踪
