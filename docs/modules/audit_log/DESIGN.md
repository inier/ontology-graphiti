# 审计日志模块 (Audit Logger) - 设计文档

> **模块 ID**: M-07 | **优先级**: P0 | **相关 ADR**: ADR-008, ADR-042
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L1 基础设施层

---

## 1. 模块概述

### 1.1 模块定位

审计日志模块是 ODAP 平台的**操作溯源与合规保障**基础设施，记录系统中所有用户操作、Agent 行为和系统事件的完整轨迹，支持时间线回溯、操作溯源和合规审计。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **全链路追踪** | 100% 操作覆盖 | 用户操作、Agent 行为、系统事件全部记录 |
| **操作溯源** | 因果链追踪 | 支持从结果反推到根因操作 |
| **合规审计** | 不可篡改 | 日志追加写入，支持防篡改校验 |
| **实时可视** | 时间线展示 | 操作时间线、跳转定位、上下文还原 |
| **性能无损** | 异步写入 | 审计日志不影响业务请求延迟 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ 所有层                                                                       │
│   用户操作 (L6) → API 请求 (L5) → 应用服务 (L4)                              │
│   → Agent 行为 (L3) → Skill 调用 (L2) → 基础设施操作 (L1)                     │
│         │                                                                    │
│         ▼                                                                    │
│ ┌─────────────────────────────────────────────────────────────────┐         │
│ │                    AuditLogger (横切关注点)                       │         │
│ │  AuditEvent → Channel (async) → Writer → Storage               │         │
│ └─────────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念模型

### 2.1 审计事件模型

```python
class AuditEvent:
    """审计事件 - 最小审计单元"""
    id: str                         # 事件唯一标识 (UUID)
    timestamp: datetime             # 事件时间戳
    event_type: AuditEventType      # 事件类型
    severity: AuditSeverity         # 严重级别
    source: EventSource             # 事件来源
    actor: ActorInfo                # 操作者信息
    action: str                     # 操作动作
    resource: ResourceInfo          # 目标资源
    result: ActionResult            # 操作结果
    context: dict                   # 上下文信息
    workspace_id: str               # 工作空间 ID
    trace_id: str                   # 分布式追踪 ID
    parent_event_id: str | None     # 父事件 ID（因果链）
    duration_ms: int | None         # 操作耗时

class AuditEventType(str, Enum):
    # 用户操作
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"

    # 工作空间操作
    WORKSPACE_CREATE = "workspace.create"
    WORKSPACE_SWITCH = "workspace.switch"
    WORKSPACE_DELETE = "workspace.delete"
    WORKSPACE_EXPORT = "workspace.export"
    WORKSPACE_IMPORT = "workspace.import"

    # 本体操作
    ONTOLOGY_CREATE = "ontology.create"
    ONTOLOGY_UPDATE = "ontology.update"
    ONTOLOGY_VERSION = "ontology.version"
    ONTOLOGY_ROLLBACK = "ontology.rollback"

    # Agent 操作
    AGENT_EXECUTE = "agent.execute"
    AGENT_DECISION = "agent.decision"
    AGENT_ERROR = "agent.error"

    # Skill 操作
    SKILL_REGISTER = "skill.register"
    SKILL_EXECUTE = "skill.execute"
    SKILL_DISABLE = "skill.disable"

    # 策略操作
    POLICY_UPDATE = "policy.update"
    POLICY_EVALUATE = "policy.evaluate"
    POLICY_VIOLATION = "policy.violation"

    # 推演操作
    SIMULATION_START = "simulation.start"
    SIMULATION_COMPLETE = "simulation.complete"
    SIMULATION_ROLLBACK = "simulation.rollback"

    # 系统事件
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_CONFIG = "system.config"

class AuditSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"

class ActorInfo:
    """操作者信息"""
    actor_type: str     # "user" | "agent" | "system" | "skill"
    actor_id: str       # 用户 ID / Agent ID / 系统 ID
    actor_name: str     # 显示名称
    roles: list[str]    # 角色

class ResourceInfo:
    """目标资源"""
    resource_type: str  # "workspace" | "ontology" | "node" | "edge" | "policy" | "skill" | "simulation"
    resource_id: str    # 资源标识
    resource_name: str  # 资源名称
    attributes: dict    # 受影响的属性

class ActionResult:
    """操作结果"""
    status: str         # "success" | "failure" | "denied"
    message: str        # 结果描述
    error_code: str | None   # 错误码（失败时）
    changes: dict | None     # 变更详情（before/after）
```

---

## 3. 核心组件设计

### 3.1 AuditLogger

```python
class AuditLogger:
    """
    审计日志器 - 全局入口

    特性：
    - 异步写入，不阻塞业务线程
    - 支持批量聚合（减少 I/O）
    - 内置采样（DEBUG 级别可采样）
    - 与 WorkspaceContext 自动绑定
    """

    def __init__(
        self,
        channel: AuditChannel,
        sampler: AuditSampler | None = None,
        enrichers: list[AuditEnricher] | None = None,
    ):
        self._channel = channel
        self._sampler = sampler
        self._enrichers = enrichers or []

    async def log(
        self,
        event_type: AuditEventType,
        action: str,
        resource: ResourceInfo,
        result: ActionResult,
        *,
        severity: AuditSeverity = AuditSeverity.INFO,
        context: dict | None = None,
        parent_event_id: str | None = None,
        duration_ms: int | None = None,
    ) -> AuditEvent:
        """
        记录审计事件

        流程：
        1. 构造 AuditEvent
        2. 自动填充 actor（从上下文获取当前用户/Agent）
        3. 自动填充 workspace_id（从 WorkspaceContext 获取）
        4. 自动填充 trace_id（从分布式追踪获取）
        5. 执行 Enricher 链（补充额外信息）
        6. 采样检查（决定是否记录）
        7. 异步写入 Channel
        """
        ...

    async def log_batch(self, events: list[AuditEvent]) -> None:
        """批量记录审计事件"""
        ...

    def start_span(self, event_type: AuditEventType, action: str, **kwargs) -> AuditSpan:
        """
        创建审计跨度（用于追踪耗时操作）

        用法：
        async with audit_logger.start_span("agent.execute", "IntelligenceAgent.analyze") as span:
            # ... 执行操作 ...
            span.set_result(status="success")
        """
        ...
```

### 3.2 AuditSpan（审计跨度）

```python
class AuditSpan:
    """
    审计跨度 - 追踪耗时操作

    自动记录开始/结束时间，计算耗时，
    支持嵌套（形成因果链）。
    """

    def __init__(self, logger: AuditLogger, event_type: AuditEventType, action: str):
        self._logger = logger
        self._event_type = event_type
        self._action = action
        self._start_time: datetime
        self._result: ActionResult | None = None
        self._children: list[AuditSpan] = []

    async def __aenter__(self) -> "AuditSpan":
        self._start_time = datetime.now()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        duration = (datetime.now() - self._start_time).total_seconds() * 1000
        if exc_type:
            self._result = ActionResult(
                status="failure",
                message=str(exc_val),
                error_code=exc_type.__name__,
            )
        await self._logger.log(
            event_type=self._event_type,
            action=self._action,
            resource=ResourceInfo(resource_type="span", resource_id=self._span_id, resource_name="", attributes={}),
            result=self._result or ActionResult(status="success", message=""),
            duration_ms=int(duration),
            parent_event_id=self._parent_id,
        )

    def child_span(self, event_type: AuditEventType, action: str) -> "AuditSpan":
        """创建子跨度"""
        ...

    def set_result(self, status: str, message: str = "", **kwargs) -> None:
        """设置操作结果"""
        ...
```

### 3.3 AuditChannel（审计通道）

```python
class AuditChannel(ABC):
    """审计通道抽象基类"""

    @abstractmethod
    async def write(self, event: AuditEvent) -> None:
        """写入单个事件"""
        ...

    @abstractmethod
    async def write_batch(self, events: list[AuditEvent]) -> None:
        """批量写入事件"""
        ...

    @abstractmethod
    async def query(self, filter: AuditFilter) -> list[AuditEvent]:
        """查询审计事件"""
        ...

class SQLiteAuditChannel(AuditChannel):
    """
    SQLite 审计通道（默认实现）

    适用于单机部署，追加写入，WAL 模式提升并发。
    """
    ...

class PostgresAuditChannel(AuditChannel):
    """
    PostgreSQL 审计通道

    适用于生产环境，支持分区表、TTL 自动清理。
    """
    ...

class FileAuditChannel(AuditChannel):
    """
    文件审计通道

    追加写入 JSON Lines 文件，适用于离线分析。
    每日滚动，自动压缩。
    """
    ...
```

### 3.4 AuditEnricher（审计丰富器）

```python
class AuditEnricher(ABC):
    """审计丰富器 - 自动补充事件信息"""

    @abstractmethod
    async def enrich(self, event: AuditEvent) -> AuditEvent:
        """丰富审计事件"""
        ...

class WorkspaceEnricher(AuditEnricher):
    """自动填充工作空间信息"""
    ...

class TraceEnricher(AuditEnricher):
    """自动填充分布式追踪信息"""
    ...

class GeoEnricher(AuditEnricher):
    """填充地理位置信息（来源 IP 解析）"""
    ...

class PolicyEnricher(AuditEnricher):
    """关联 OPA 策略评估结果"""
    ...
```

---

## 4. 存储设计

### 4.1 SQLite Schema（默认）

```sql
CREATE TABLE audit_events (
    id              TEXT PRIMARY KEY,
    timestamp       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type      TEXT NOT NULL,
    severity        TEXT NOT NULL DEFAULT 'info',
    actor_type      TEXT NOT NULL,
    actor_id        TEXT NOT NULL,
    actor_name      TEXT NOT NULL,
    action          TEXT NOT NULL,
    resource_type   TEXT NOT NULL,
    resource_id     TEXT NOT NULL,
    result_status   TEXT NOT NULL,
    result_message  TEXT DEFAULT '',
    workspace_id    TEXT NOT NULL,
    trace_id        TEXT NOT NULL,
    parent_event_id TEXT,
    duration_ms     INTEGER,
    context         TEXT,  -- JSON
    changes         TEXT,  -- JSON
    checksum        TEXT NOT NULL  -- 防篡改校验
);

-- 索引
CREATE INDEX idx_audit_timestamp ON audit_events(timestamp);
CREATE INDEX idx_audit_event_type ON audit_events(event_type);
CREATE INDEX idx_audit_actor ON audit_events(actor_id);
CREATE INDEX idx_audit_workspace ON audit_events(workspace_id);
CREATE INDEX idx_audit_resource ON audit_events(resource_type, resource_id);
CREATE INDEX idx_audit_trace ON audit_events(trace_id);

-- 分区（PostgreSQL）
-- PARTITION BY RANGE (timestamp)
```

### 4.2 数据保留策略

| 严重级别 | 保留时间 | 存储位置 |
|----------|---------|---------|
| DEBUG | 7 天 | SQLite / 内存 |
| INFO | 90 天 | SQLite / PostgreSQL |
| WARN | 180 天 | PostgreSQL + 冷存储 |
| ERROR | 365 天 | PostgreSQL + 冷存储 |
| CRITICAL | 永久 | PostgreSQL + 归档 |

---

## 5. 查询与可视化接口

### 5.1 REST API

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| GET | /api/audit/events | 查询审计事件 | audit:read |
| GET | /api/audit/events/{id} | 获取事件详情 | audit:read |
| GET | /api/audit/timeline | 时间线视图 | audit:read |
| GET | /api/audit/trace/{trace_id} | 追踪链查询 | audit:read |
| GET | /api/audit/stats | 审计统计 | audit:stats |
| POST | /api/audit/export | 导出审计日志 | audit:export |

### 5.2 AuditFilter（查询过滤器）

```python
class AuditFilter:
    """审计事件查询过滤器"""
    start_time: datetime | None
    end_time: datetime | None
    event_types: list[AuditEventType] | None
    severities: list[AuditSeverity] | None
    actor_ids: list[str] | None
    actor_types: list[str] | None
    resource_types: list[str] | None
    resource_ids: list[str] | None
    workspace_id: str | None
    trace_id: str | None
    result_status: list[str] | None
    keyword: str | None           # 全文搜索
    limit: int = 50               # 分页大小
    offset: int = 0               # 偏移量
    order_by: str = "timestamp"   # 排序字段
    order_desc: bool = True       # 降序
```

---

## 6. 防篡改设计

### 6.1 校验链

```python
class AuditIntegrityChecker:
    """
    审计日志完整性校验

    策略：每个事件记录时计算 checksum，
    checksum = SHA256(prev_checksum + event_json)
    形成链式校验，任何篡改都能被检测。
    """

    async def compute_checksum(self, event: AuditEvent, prev_checksum: str) -> str:
        """计算事件校验和"""
        event_json = event.model_dump_json(exclude={"checksum"})
        return hashlib.sha256(f"{prev_checksum}|{event_json}".encode()).hexdigest()

    async def verify_chain(self, start_id: str, end_id: str) -> IntegrityReport:
        """
        验证校验链完整性

        返回：
        - valid: 是否完整
        - broken_at: 破断点（如有）
        - total_events: 校验的事件数
        """
        ...
```

---

## 7. 与 Hook 系统集成

```python
class AuditHook:
    """
    审计 Hook - 自动拦截并记录操作

    通过 Hook 系统（M-05）自动注入审计能力，
    无需业务代码显式调用 AuditLogger。
    """

    @hook("pre", "*")  # 拦截所有操作的 Pre 钩子
    async def on_pre(self, context: HookContext) -> None:
        """操作前：记录开始时间"""
        context.set("_audit_start", datetime.now())

    @hook("post", "*")  # 拦截所有操作的 Post 钩子
    async def on_post(self, context: HookContext) -> None:
        """操作后：记录审计事件"""
        start = context.get("_audit_start")
        duration = (datetime.now() - start).total_seconds() * 1000
        await self.audit_logger.log(
            event_type=self._map_to_event_type(context.action),
            action=context.action,
            resource=ResourceInfo(
                resource_type=context.target_type,
                resource_id=context.target_id,
                resource_name=context.target_name,
                attributes=context.changed_attributes,
            ),
            result=ActionResult(
                status="success" if context.success else "failure",
                message=context.result_message,
            ),
            duration_ms=int(duration),
        )
```

---

## 8. 非功能设计

| 维度 | 指标 | 实现方式 |
|------|------|---------|
| 写入延迟 | < 5ms (异步) | 内存 Channel 缓冲 + 批量落盘 |
| 查询延迟 | < 200ms (P95) | 分区索引 + 时间范围剪枝 |
| 吞吐量 | > 10K events/s | 批量写入 + WAL 模式 |
| 存储效率 | 压缩率 > 60% | JSON 列压缩 + 冷数据归档 |
| 可靠性 | 零丢失 | WAL + 同步写入（CRITICAL 级别） |

---

## 9. 实现路径

### Phase 0 (当前)

- [x] AuditEvent 模型定义
- [x] AuditLogger 基础接口
- [ ] SQLiteAuditChannel 实现
- [ ] AuditSpan 耗时追踪

### Phase 1

- [ ] AuditHook 自动拦截
- [ ] 防篡改校验链
- [ ] 时间线可视化 API
- [ ] 追踪链查询

### Phase 2

- [ ] PostgresAuditChannel
- [ ] 数据保留策略自动执行
- [ ] 审计统计与报表
- [ ] 跨工作空间审计查询
