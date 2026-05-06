# 事件模拟器模块 (Event Simulator) - 设计文档

> **模块 ID**: M-15 | **优先级**: P1 | **相关 ADR**: ADR-018, ADR-019
> **版本**: 2.0.0 | **日期**: 2026-04-19 | **架构层**: L2 领域技能层

---

## 1. 模块概述

### 1.1 模块定位

事件模拟器是 ODAP 平台的**场景驱动引擎**，负责自动/手动生成模拟事件并注入到知识图谱中，驱动本体状态演化。它是"推演"的前端——模拟器生成"发生了什么"，推演引擎分析"这意味着什么"和"该怎么做"。

与 M-14 模拟推演模块的关系：事件模拟器是推演引擎的数据供应商，M-14 负责沙箱环境管理和方案对比，M-15 负责事件生成和注入逻辑。

### 1.2 核心价值

| 维度 | 价值 | 说明 |
|------|------|------|
| **场景驱动** | 自动生成事件 | 按剧本/模板自动生成事件序列，驱动态势演化 |
| **可控注入** | 手动干预 | 支持手动注入关键事件（如突发打击） |
| **时间控制** | 加速/减速/暂停 | 模拟时钟独立于系统时钟，支持时间加速 |
| **模板复用** | 事件模板 | 预定义事件模板，一键生成标准事件序列 |
| **真实感** | 随机变异 | 事件参数支持随机扰动，避免机械重复 |

### 1.3 架构位置

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ L4  应用服务层                                                               │
│     SimulationService (编排)                                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ ★ L2  领域技能层 ★                                                            │
│     EventSimulator (核心)                                                    │
│         ├── EventGenerator (事件生成)                                          │
│         ├── TimelineEngine (时间线引擎)                                        │
│         ├── EventInjector (事件注入)                                           │
│         └── TemplateEngine (模板引擎)                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ L1  基础设施层                                                                │
│     GraphitiClient (图谱写入) / OntologyManager (实体校验)                     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 核心概念模型

### 2.1 模拟事件

```python
class SimEvent:
    """模拟事件 - 模拟器产生的最小事件单元"""
    id: str                         # 事件 ID
    event_type: SimEventType        # 事件类型
    name: str                       # 事件名称
    description: str                # 事件描述
    timestamp: SimTimestamp         # 模拟时间戳
    parameters: dict                # 事件参数
    effects: list[SimEffect]        # 事件效果
    source: EventSource             # 事件来源
    scenario_id: str                # 所属场景 ID
    priority: int                   # 优先级 (1-10)
    dependencies: list[str]         # 前置事件 ID

class SimEventType(str, Enum):
    # 军事类事件
    DEPLOYMENT = "deployment"               # 部署
    MOVEMENT = "movement"                   # 移动
    ENGAGEMENT = "engagement"               # 交战
    STRIKE = "strike"                       # 打击
    RECON = "recon"                         # 侦察

    # 通用事件
    STATUS_CHANGE = "status_change"         # 状态变更
    RESOURCE_CHANGE = "resource_change"     # 资源变更
    RELATION_CHANGE = "relation_change"     # 关系变更
    EXTERNAL_INPUT = "external_input"       # 外部输入
    ENVIRONMENT = "environment"             # 环境变化

    # 控制事件
    SCENARIO_START = "scenario_start"       # 场景开始
    SCENARIO_PAUSE = "scenario_pause"       # 场景暂停
    SCENARIO_RESUME = "scenario_resume"     # 场景恢复
    SCENARIO_END = "scenario_end"           # 场景结束

class SimTimestamp:
    """模拟时间戳"""
    sim_time: datetime              # 模拟时间（场景内时间）
    real_time: datetime             # 真实时间（系统时间）
    time_scale: float               # 时间缩放因子

class EventSource(str, Enum):
    AUTO = "auto"                   # 自动生成（按剧本/规则）
    MANUAL = "manual"               # 手动注入
    TEMPLATE = "template"           # 模板生成
    TRIGGERED = "triggered"         # 触发器生成（条件满足时）
    IMPORTED = "imported"           # 外部导入
```

### 2.2 事件效果

```python
class SimEffect:
    """事件效果 - 事件对图谱的影响"""
    effect_type: EffectType         # 效果类型
    target_type: str                # 目标实体类型
    target_id: str | None           # 目标实体 ID（None 表示待匹配）
    target_selector: dict | None    # 目标选择器（条件匹配）
    changes: dict                   # 变更内容
    delay_ms: int                   # 延迟执行（毫秒）
    probability: float              # 发生概率 (0-1)

class EffectType(str, Enum):
    CREATE_NODE = "create_node"             # 创建节点
    UPDATE_NODE = "update_node"             # 更新节点属性
    DELETE_NODE = "delete_node"             # 删除节点
    CREATE_EDGE = "create_edge"             # 创建边
    UPDATE_EDGE = "update_edge"             # 更新边属性
    DELETE_EDGE = "delete_edge"             # 删除边
    CREATE_EPISODE = "create_episode"       # 创建 Episode（记录事件）
```

### 2.3 事件模板

```python
class EventTemplate:
    """事件模板 - 预定义的事件生成规则"""
    id: str                         # 模板 ID
    name: str                       # 模板名称
    description: str                # 描述
    event_type: SimEventType        # 事件类型
    parameter_schema: dict          # 参数 JSON Schema
    effect_template: list[SimEffect]  # 效果模板
    default_parameters: dict        # 默认参数
    variation_rules: list[VariationRule]  # 随机变异规则
    tags: list[str]                 # 标签

class VariationRule:
    """变异规则 - 为模板参数添加随机扰动"""
    parameter_path: str             # 参数路径 (e.g. "effects[0].changes.strength")
    variation_type: str             # "gaussian" | "uniform" | "choice"
    parameters: dict                # 变异参数
        # gaussian: {"mean": 0, "std": 0.1}
        # uniform: {"min": 0, "max": 1}
        # choice: {"options": ["a", "b", "c"], "weights": [0.5, 0.3, 0.2]}
```

### 2.4 事件触发器

```python
class EventTrigger:
    """事件触发器 - 条件满足时自动生成事件"""
    id: str                         # 触发器 ID
    name: str                       # 触发器名称
    condition: TriggerCondition     # 触发条件
    event_template_id: str          # 关联的事件模板
    parameters: dict                # 生成事件的固定参数
    cooldown_ms: int                # 冷却时间（避免频繁触发）
    max_triggers: int | None        # 最大触发次数
    enabled: bool                   # 是否启用

class TriggerCondition:
    """触发条件"""
    condition_type: str             # "cypher" | "entity_state" | "time_elapsed" | "event_occurred"
    expression: str                 # 条件表达式
        # cypher: "MATCH (t:Target) WHERE t.threat_level > 0.8 RETURN count(t) > 0"
        # entity_state: "entity.type == 'Target' AND entity.threat_level > 0.8"
        # time_elapsed: "sim_elapsed > 3600"  # 模拟时间经过 1 小时
        # event_occurred: "event.type == 'ENGAGEMENT' AND event.parameters.result == 'success'"
```

---

## 3. 核心组件设计

### 3.1 EventSimulator

```python
class EventSimulator:
    """
    事件模拟器 - 核心入口

    职责：
    - 场景的创建/销毁/控制
    - 事件流的调度（自动/手动/触发器）
    - 模拟时钟管理
    - 事件注入到知识图谱
    """

    def __init__(
        self,
        generator: EventGenerator,
        timeline: TimelineEngine,
        injector: EventInjector,
        template_engine: TemplateEngine,
        graphiti_client: "GraphitiClient",
    ):
        self._generator = generator
        self._timeline = timeline
        self._injector = injector
        self._templates = template_engine
        self._graphiti = graphiti_client
        self._active_scenarios: dict[str, ScenarioState] = {}

    async def create_scenario(
        self,
        name: str,
        config: ScenarioConfig,
        workspace_id: str,
    ) -> ScenarioState:
        """
        创建模拟场景

        流程：
        1. 创建 ScenarioState
        2. 初始化模拟时钟
        3. 加载剧本/模板
        4. 注册触发器
        5. 发出 SCENARIO_START 事件
        """
        ...

    async def start_scenario(self, scenario_id: str) -> None:
        """启动场景（开始事件流）"""
        ...

    async def pause_scenario(self, scenario_id: str) -> None:
        """暂停场景"""
        ...

    async def resume_scenario(self, scenario_id: str) -> None:
        """恢复场景"""
        ...

    async def stop_scenario(self, scenario_id: str) -> None:
        """停止场景"""
        ...

    async def inject_event(
        self, scenario_id: str, event: SimEvent
    ) -> SimEvent:
        """
        手动注入事件

        用于突发情况模拟（如突然打击、意外变故）
        """
        ...

    async def set_time_scale(self, scenario_id: str, scale: float) -> None:
        """
        设置时间缩放

        scale > 1: 加速（如 scale=10 → 1秒真实时间=10秒模拟时间）
        scale < 1: 减速
        scale = 0: 暂停
        """
        ...

    async def advance_time(self, scenario_id: str, delta: timedelta) -> list[SimEvent]:
        """
        推进模拟时间

        触发该时间段内的所有待执行事件
        """
        ...
```

### 3.2 EventGenerator（事件生成器）

```python
class EventGenerator:
    """
    事件生成器 - 按剧本/规则自动生成事件序列

    生成策略：
    1. 剧本驱动：预定义的事件序列，按时间推进
    2. 规则驱动：基于当前态势的规则推断
    3. 随机生成：基于概率分布的随机事件
    4. 触发器驱动：条件满足时触发
    """

    async def generate_from_script(
        self, script: EventScript, current_time: datetime
    ) -> list[SimEvent]:
        """
        从剧本生成事件

        剧本格式：
        [
            {"at": "T+1h", "type": "MOVEMENT", "params": {...}},
            {"at": "T+2h", "type": "ENGAGEMENT", "params": {...}},
            {"at": "T+3h", "type": "STRIKE", "params": {...}},
        ]
        """
        ...

    async def generate_from_rules(
        self, rules: list[EventRule], context: ScenarioContext
    ) -> list[SimEvent]:
        """
        从规则生成事件

        规则格式：
        {
            "condition": "avg_threat_level > 0.7",
            "generate": {"type": "STRIKE", "params": {...}},
            "probability": 0.3
        }
        """
        ...

    async def generate_random(
        self, distribution: EventDistribution, count: int
    ) -> list[SimEvent]:
        """
        随机生成事件

        基于指定的概率分布和事件类型权重
        """
        ...
```

### 3.3 TimelineEngine（时间线引擎）

```python
class TimelineEngine:
    """
    时间线引擎 - 管理模拟时钟和事件调度

    核心概念：
    - 模拟时钟 (SimClock)：独立于系统时钟
    - 事件队列 (EventQueue)：按模拟时间排序
    - 时间缩放 (TimeScale)：模拟时间/真实时间的比率
    """

    def __init__(self):
        self._sim_clock: SimClock
        self._event_queue: PriorityQueue[SimEvent]
        self._time_scale: float = 1.0
        self._running: bool = False

    async def tick(self) -> list[SimEvent]:
        """
        推进一个时间步

        1. 计算真实时间流逝 → 模拟时间推进
        2. 弹出所有 sim_time <= 当前模拟时间 的事件
        3. 返回待执行事件列表
        """
        ...

    async def schedule(self, event: SimEvent) -> None:
        """调度事件到事件队列"""
        ...

    async def cancel(self, event_id: str) -> bool:
        """取消已调度的事件"""
        ...

    def get_sim_time(self) -> datetime:
        """获取当前模拟时间"""
        ...

    def get_real_time(self) -> datetime:
        """获取当前真实时间"""
        ...
```

### 3.4 EventInjector（事件注入器）

```python
class EventInjector:
    """
    事件注入器 - 将事件效果写入知识图谱

    流程：
    1. 验证事件效果的合法性（本体约束）
    2. 将效果转化为 Graphiti 写入操作
    3. 执行写入（创建/更新/删除节点和边）
    4. 创建 Episode 记录事件
    5. 通知触发器检查
    """

    async def inject(self, event: SimEvent, scenario_id: str) -> InjectionResult:
        """
        注入事件到知识图谱

        返回：
        - 成功/失败状态
        - 实际写入的节点/边
        - 触发的后续事件
        """
        ...

    async def inject_batch(self, events: list[SimEvent], scenario_id: str) -> list[InjectionResult]:
        """批量注入事件（事务性）"""
        ...

    async def rollback(self, event_id: str) -> bool:
        """回滚已注入的事件"""
        ...

class InjectionResult:
    """注入结果"""
    event_id: str
    status: str                     # "success" | "partial" | "failed"
    nodes_created: int
    nodes_updated: int
    edges_created: int
    edges_updated: int
    episodes_created: int
    errors: list[str]
    triggered_events: list[str]     # 触发的后续事件 ID
```

---

## 4. 场景配置

### 4.1 ScenarioConfig

```python
class ScenarioConfig:
    """场景配置"""
    name: str                       # 场景名称
    description: str                # 描述
    domain: str                     # 领域
    time_config: TimeConfig         # 时间配置
    initial_state: dict             # 初始状态（实体/关系）
    event_scripts: list[str]        # 剧本文件路径
    templates: list[str]            # 模板 ID 列表
    triggers: list[EventTrigger]    # 触发器
    max_duration: timedelta         # 最大模拟时长
    auto_start: bool                # 是否自动开始

class TimeConfig:
    """时间配置"""
    start_time: datetime            # 模拟起始时间
    time_scale: float = 1.0         # 初始时间缩放
    tick_interval_ms: int = 1000    # 时间步间隔（真实时间毫秒）
    max_time_scale: float = 100.0   # 最大时间缩放
```

### 4.2 ScenarioState

```python
class ScenarioState:
    """场景运行时状态"""
    id: str
    config: ScenarioConfig
    status: ScenarioStatus          # "created" | "running" | "paused" | "stopped" | "completed"
    sim_clock: SimTimestamp         # 当前模拟时钟
    event_count: int                # 已生成事件数
    events_injected: int            # 已注入事件数
    last_event_at: datetime | None  # 最后事件时间
    created_at: datetime
    workspace_id: str
```

---

## 5. REST API

| 方法 | 路径 | 描述 | 权限 |
|------|------|------|------|
| POST | /api/simulations/scenarios | 创建场景 | simulation:scenario:create |
| GET | /api/simulations/scenarios | 列出场景 | simulation:scenario:list |
| GET | /api/simulations/scenarios/{id} | 获取场景状态 | simulation:scenario:read |
| DELETE | /api/simulations/scenarios/{id} | 删除场景 | simulation:scenario:delete |
| POST | /api/simulations/scenarios/{id}/start | 启动场景 | simulation:scenario:control |
| POST | /api/simulations/scenarios/{id}/pause | 暂停场景 | simulation:scenario:control |
| POST | /api/simulations/scenarios/{id}/resume | 恢复场景 | simulation:scenario:control |
| POST | /api/simulations/scenarios/{id}/stop | 停止场景 | simulation:scenario:control |
| POST | /api/simulations/scenarios/{id}/inject | 手动注入事件 | simulation:event:inject |
| PUT | /api/simulations/scenarios/{id}/timescale | 设置时间缩放 | simulation:scenario:control |
| GET | /api/simulations/scenarios/{id}/events | 获取事件列表 | simulation:event:read |
| POST | /api/simulations/scenarios/{id}/advance | 推进模拟时间 | simulation:scenario:control |
| GET | /api/simulations/templates | 列出事件模板 | simulation:template:list |
| POST | /api/simulations/templates | 创建事件模板 | simulation:template:create |

---

## 6. 与其他模块的交互

| 依赖模块 | 交互方式 | 说明 |
|----------|---------|------|
| M-01 Graphiti | 调用 | 事件效果写入图谱、创建 Episode |
| M-03 本体管理 | 调用 | 注入前验证实体/关系合法性 |
| M-04 工作空间 | 调用 | 确定图谱写入的目标数据库 |
| M-07 审计日志 | 调用 | 记录场景控制操作 |
| M-14 模拟推演 | 被调用 | 推演引擎使用事件模拟器生成数据 |
| M-18 可视化 | 被调用 | 事件流实时可视化 |

### 事件流交互图

```
EventSimulator → EventGenerator → 事件队列
                                    ↓
TimelineEngine.tick() → 弹出到时事件
                            ↓
EventInjector.inject() → Graphiti 写入
                            ↓
                    → 触发器检查 → 可能生成新事件
                            ↓
                    → 通知 Visualization（SSE）
                            ↓
                    → 通知 Agent（OODA 触发）
```

---

## 7. 非功能设计

| 维度 | 指标 | 实现方式 |
|------|------|---------|
| 事件生成吞吐 | > 100 events/s | 批量生成 + 异步队列 |
| 注入延迟 | < 100ms/event | 批量写入 Graphiti |
| 时间精度 | 毫秒级 | 高精度模拟时钟 |
| 最大时间缩放 | 100x | 事件预生成 + 缓冲队列 |
| 并发场景 | > 10 | 每场景独立 TimelineEngine |
| 可靠性 | 注入可回滚 | 事务性写入 + Episode 记录 |

---

## 8. 实现路径

### Phase 0 (当前)

- [x] SimEvent / SimEffect 模型定义
- [x] EventSimulator 基础接口
- [ ] TimelineEngine 模拟时钟实现
- [ ] EventInjector Graphiti 写入适配

### Phase 1

- [ ] EventGenerator 剧本驱动
- [ ] 事件模板引擎
- [ ] 事件触发器
- [ ] 时间缩放与暂停/恢复

### Phase 2

- [ ] 随机事件生成（概率分布）
- [ ] 规则驱动事件生成
- [ ] 事件回滚机制
- [ ] 场景快照与恢复
