# 模拟推演引擎 (Simulator Engine) - 设计文档

> **优先级**: P0 | **相关 ADR**: ADR-018

**版本**: 1.0.0 | **日期**: 2026-04-16

---

## 1. 模块概述

模拟推演引擎是**沙箱式方案验证系统**，对选定方案进行推演验证，辅助决策支持。

**核心职责**:
- 方案版本管理与回退
- 沙箱状态控制（创建/运行/暂停/终止）
- 事件序列生成与执行
- 推演结果评估与对比

**与 Mock 数据生成的区别**:

| 概念 | 职责 | 模块位置 |
|------|------|---------|
| **Mock 数据生成** | 为构建领域本体生成样本数据（静态） | `odap/biz/ontology/mock_data/` |
| **模拟推演** | 对选定方案进行沙盘验证（动态） | `odap/biz/simulator/` |

---

## 2. 核心架构

### 2.1 系统分层

```
┌─────────────────────────────────────────────────────────────┐
│                    Simulator Engine                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 方案管理 (Scenario Management)                     │
│  - create_scenario: 创建推演方案                            │
│  - create_branch: 版本分支                                  │
│  - rollback_to_version: 版本回退                           │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: 沙箱控制 (Sandbox Control)                        │
│  - run_simulation: 执行推演                                 │
│  - pause/resume: 暂停/恢复                                  │
│  - terminate: 终止沙箱                                      │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: 事件引擎 (Event Engine)                            │
│  - 事件调度                                                 │
│  - 状态转移                                                 │
│  - 终止条件检测                                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: 结果评估 (Result Evaluation)                       │
│  - 指标计算                                                 │
│  - 版本对比                                                 │
│  - 结果存储                                                 │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 状态机

```
                    ┌─────────────┐
                    │  CREATED   │
                    └──────┬──────┘
                           │ run_simulation()
                           ▼
                    ┌─────────────┐
              ┌────►│  RUNNING   │◄────┐
              │     └──────┬──────┘     │
              │            │            │
  terminate() │   pause()  │  complete │ terminate()
              │            │            │
              │     ┌──────┴──────┐    │
              └─────│   PAUSED    │────┘
                    └─────────────┘
                           │
                    ┌──────┴──────┐
              ┌────►│  COMPLETED  │◄────┐
              │     └─────────────┘     │
              │                        │ error
              │     ┌─────────────┐    │
              └─────│   FAILED    │────┘
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    │ TERMINATED  │
                    └─────────────┘
```

---

## 3. 数据模型

### 3.1 SandboxState

```python
class SandboxState(str, Enum):
    """沙箱状态"""
    CREATED = "created"      # 已创建
    RUNNING = "running"      # 运行中
    PAUSED = "paused"        # 已暂停
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"       # 执行失败
    TERMINATED = "terminated" # 已终止
```

### 3.2 ScenarioVersion

```python
@dataclass
class ScenarioVersion:
    """方案版本"""
    version_id: str           # 版本 ID
    scenario_id: str          # 方案 ID
    parent_version: Optional[str]  # 父版本
    parameters: Dict[str, Any]     # 版本参数
    created_at: datetime      # 创建时间
    message: str = ""        # 版本说明
```

### 3.3 SimulationResult

```python
@dataclass
class SimulationResult:
    """推演结果"""
    result_id: str
    scenario_id: str
    version_id: str
    final_state: Dict[str, Any]   # 最终状态
    events: List[Dict[str, Any]]  # 事件序列
    metrics: Dict[str, float]     # 评估指标
    success: bool
    execution_time_ms: float
    error_message: Optional[str] = None
```

---

## 4. 核心接口

### 4.1 方案管理

```python
class SimulationEngine:
    async def create_scenario(self, name: str, initial_parameters: Dict[str, Any]) -> str:
        """创建新推演方案，返回 scenario_id"""

    async def create_branch(
        self,
        scenario_id: str,
        base_version_id: str,
        new_parameters: Dict[str, Any],
        branch_message: str
    ) -> str:
        """从指定版本创建分支，返回新版本 ID"""

    async def rollback_to_version(self, scenario_id: str, version_id: str) -> bool:
        """回退到指定版本"""
```

### 4.2 沙箱控制

```python
class SimulationEngine:
    async def run_simulation(
        self,
        scenario_id: str,
        version_id: str,
        max_steps: int = 100
    ) -> SimulationResult:
        """执行推演，返回推演结果"""

    async def terminate_sandbox(self, sandbox_id: str) -> bool:
        """终止沙箱"""

    def get_active_sandboxes(self) -> Dict[str, str]:
        """获取所有活跃沙箱及其状态"""
```

### 4.3 结果评估

```python
class SimulationEngine:
    def get_result(self, result_id: str) -> Optional[SimulationResult]:
        """获取推演结果"""

    def get_scenario_versions(self, scenario_id: str) -> List[Dict[str, Any]]:
        """获取方案的所有版本"""

    def compare_versions(
        self,
        scenario_id: str,
        version_a: str,
        version_b: str
    ) -> Dict[str, Any]:
        """对比两个版本的参数差异"""
```

---

## 5. 事件引擎

### 5.1 事件结构

```python
@dataclass
class SimulationEvent:
    """推演事件"""
    step: int                      # 步骤序号
    timestamp: datetime            # 事件时间戳
    state_changes: Dict[str, Any]  # 状态变更
    action_taken: str              # 执行的动作
    terminal: bool = False         # 是否为终止步骤
```

### 5.2 状态转移

事件引擎支持自定义状态转移逻辑：

```python
class SimulationEngine:
    async def _simulate_step(
        self,
        step: int,
        current_state: Dict[str, Any]
    ) -> SimulationEvent:
        """
        执行单步推演

        子类可重写此方法实现自定义状态转移逻辑：
        - 读取 current_state
        - 根据状态计算下一步变化
        - 返回包含 state_changes 的事件
        - 设置 terminal=True 表示推演结束
        """
```

### 5.3 默认实现

默认实现为**通用状态转移模型**：

```python
async def _simulate_step(
    self,
    step: int,
    current_state: Dict[str, Any]
) -> SimulationEvent:
    """
    默认状态转移逻辑：

    1. 读取当前状态中的通用指标
    2. 基于指标计算状态变化
    3. 生成事件记录变化

    状态字段（通用，不绑定特定领域）：
    - metrics: Dict[str, float]  # 通用指标
    - conditions: Dict[str, bool]  # 条件标志
    - counters: Dict[str, int]  # 计数器
    """
    metrics = current_state.get("metrics", {})
    conditions = current_state.get("conditions", {})

    # 基于当前状态计算下一步
    new_metrics = self._calculate_next_metrics(metrics, current_state)
    new_conditions = self._evaluate_conditions(conditions, new_metrics)

    # 检测终止条件
    terminal = self._check_termination(new_metrics, new_conditions, step)

    return SimulationEvent(
        step=step,
        timestamp=datetime.now(),
        state_changes={
            "metrics": new_metrics,
            "conditions": new_conditions,
        },
        action_taken=f"step_{step}_executed",
        terminal=terminal,
    )
```

---

## 6. 指标计算

### 6.1 通用指标

```python
def _calculate_metrics(
    self,
    events: List[Dict[str, Any]],
    final_state: Dict[str, Any]
) -> Dict[str, float]:
    """
    计算推演评估指标（通用）：

    - total_events: 总事件数
    - final_metrics.*: 最终状态中的各项指标
    - convergence_score: 收敛得分（状态变化趋于稳定的程度）
    - efficiency_score: 执行效率（实际步数 / 最大步数）
    """
```

### 6.2 版本对比

```python
def compare_versions(
    self,
    scenario_id: str,
    version_a: str,
    version_b: str
) -> Dict[str, Any]:
    """
    版本对比结果：

    {
        "version_a": "...",
        "version_b": "...",
        "differences": {
            "param_key": {
                "version_a": value_a,
                "version_b": value_b,
            },
            ...
        }
    }
    """
```

---

## 7. 存储设计

### 7.1 目录结构

```
{storage_path}/
└── {scenario_id}/
    └── {version_id}.json    # 版本快照
```

### 7.2 版本文件格式

```json
{
    "version_id": "abc123",
    "scenario_id": "scenario-001",
    "parent_version": null,
    "parameters": {
        "metrics": {...},
        "conditions": {...}
    },
    "created_at": "2026-04-16T10:00:00",
    "message": "初始版本"
}
```

---

## 8. 与其他模块的集成

### 8.1 与 mock_data 的关系

```
mock_data/ (数据准备)
    │
    │ 生成样本数据
    ▼
simulator/ (推演执行)
    │
    │ 加载方案
    ▼
SimulationEngine.run_simulation()
    │
    │ 输出结果
    ▼
分析 & 决策支持
```

### 8.2 与 Graphiti 的集成

```python
# 推演完成后，可选择将结果写入 Graphiti
async def run_and_persist(
    self,
    scenario_id: str,
    version_id: str,
    graph_manager: GraphManager = None
) -> SimulationResult:
    result = await self.run_simulation(scenario_id, version_id)

    if graph_manager:
        await graph_manager.add_episode(
            content=f"推演完成: {result.result_id}",
            episode_type="simulation_result",
            metadata=result.__dict__
        )

    return result
```

---

## 9. 实现计划

### Phase 1: 核心引擎

| 任务 | 产出 |
|------|------|
| 方案版本管理 | `SimulationEngine.create_scenario()`, `create_branch()` |
| 沙箱状态控制 | `run_simulation()`, `terminate_sandbox()` |
| 事件引擎 | `_simulate_step()`, 状态转移逻辑 |
| 结果存储 | 文件系统持久化 |

### Phase 2: 扩展能力

| 任务 | 产出 |
|------|------|
| 暂停/恢复 | `pause_sandbox()`, `resume_sandbox()` |
| 版本对比 | `compare_versions()` |
| 指标可视化 | 推演结果图表 |

---

## 10. 相关文档

- [ADR-018: 领域模拟推演引擎](../../adr/ADR-018_domain_simulator_engine.md)
- [Mock 数据生成模块](../../adr/README.md)
- [Graphiti 双时态知识图谱](../graphiti_client/DESIGN.md)
