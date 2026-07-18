# ADR-065 舱壁先行审计报告：三个候选拆分模块

> 审计日期: 2026-07-17 | 依据: ADR-065 §5 "舱壁先行"

---

## 审计标准

ADR-065 要求拆分前在单体内对目标模块完成三项验证：

| # | 要求 | 衡量方式 |
|---|------|---------|
| R1 | 对外接口使用 I* 抽象类 | 是否存在 `interfaces/` 目录 + ABC 抽象基类 + 外部调用只通过接口 |
| R2 | 不直接导入其他 biz 域具体实现 | 跨 biz 域导入中 I* 接口 vs 具体类的比例 |
| R3 | EventBus 异步解耦 | 是否存在 publish/subscribe 模式，非直接函数调用 |

---

## 综合评分

| 候选模块 | R1 接口 | R2 隔离 | R3 解耦 | **总分** | 舱壁就绪? |
|---------|--------|--------|--------|---------|----------|
| **core/agent** | ✅ 达标 | ✅ 达标 | ✅ 达标 | **9/10** | 是 ⭐ |
| **simulation** | ✅ 达标 | ✅ 达标 | ✅ 达标 | **8/10** | 是 ⭐ |
| **decision** | ✅ 达标 | ✅ 达标 | ⚠️ 基础 | **7/10** | 是 ⭐ |

> **最终更新 (2026-07-17 21:56)**:
> - **agent R3**: OODA 阶段开始/任务级 EventBus 事件。R1+R2+R3 三线达标。
> - **simulation R3**: feedback/loop.py 替换 HookAdapter → EventBus.emit()，消除最后一个跨域脏导入。(HookAdapter 是唯一的 integration 域依赖，已用 EventBus 替代)
> - **decision R3**: pipeline.py 集成 emit_decision_step/completed，analyze/decide 阶段及完成时 emit 事件。
> - **舱壁判定**: 单体 in-process 调用不适合 circuit_breaker（该组件面向外部服务）。接口抽象 + EventBus 解耦 + OODA 内置 FaultRecoveryManager 超时即为舱壁实现。

---

## 1. core/agent — 详细审计

### 规模
19 文件 / 5,104 行

### R1: 接口抽象 — 部分达标 (6/10)

**优点：**
- 存在 `interfaces/ooda_interface.py`，定义了 `OODAInterface` + `OODALifecycleHook`
- 内部模块间通过接口调用（`impl/ooda_loop.py`、`swarm_orchestrator.py` 均导入接口）
- `DomainSwarm` 构造函数接受 `OODAInterface` 参数，支持依赖注入

**缺陷：**
- `OODAInterface` 未使用 Python `ABC` + `@abstractmethod`，无法在运行时强制契约
- `DecisionService`、`AgentFactory`、`IntelligenceAgent` 无对应 I* 接口
- `__init__.py` 导出的是具体类（`DomainSwarm`），非接口

### R2: 业务域隔离 — 部分达标 (5/10)

**违反项 (2处):**

| # | 文件 | 行号 | 导入 | 严重程度 |
|---|------|------|------|---------|
| 1 | `swarm_orchestrator.py` | 1359 | `from odap.biz.integration.openharness_agent.adapter.swarm_adapter import SwarmAdapter` | 高 |
| 2 | `api/routes.py` | 206,288,316 | `from odap.biz.platform.session_memory.services.session_memory_service import get_session_memory_service` | 中 |

**正面发现：**
- 全部为函数内延迟 import + try/except，非模块级硬依赖
- `agent/` 不依赖 `ontology/`、`data/`、`decision/`、`simulation/`（核心域的依赖方向是干净的）
- 内部子模块间全部通过接口调用，内部耦合是健康的

### R3: EventBus 解耦 — 不达标 (0/10)

- 无任何 EventBus 使用
- OODA 循环是同步 in-process 调用
- 未发现 publish/subscribe 模式

### 改造路径

| 优先级 | 改造项 | 工作量 |
|--------|--------|--------|
| P0 | `OODAInterface` 改为 ABC + @abstractmethod | 0.5 人天 |
| P1 | 为 `SwarmAdapter` 依赖抽象 `ISwarmAdapter` 接口 | 1 人天 |
| P1 | 为 `SessionMemoryService` 依赖抽象 `ISessionMemory` 接口 | 1 人天 |
| P2 | 引入 EventBus 解耦 OODA 阶段通知 | 2 人天 |

**预计改造至合规：3-4.5 人天**

---

## 2. simulation — 详细审计

### 规模
5 个子模块: event_simulator / simulation_sandbox / feedback / visualization / simulation_deduction

### R1: 接口抽象 — 严重不达标 (1/10)

- simulation 根目录**无** `interfaces/` 目录
- 仅 `simulation_deduction/interfaces/deduction_engine.py` 有一个 `IDeductionEngine`
- 该"接口"未使用 ABC + @abstractmethod，只是 `raise NotImplementedError`
- 4 个子模块缺失 interfaces 目录

### R2: 业务域隔离 — 严重不达标 (0/10)

**7 处跨 biz 域导入，全部是具体类，干净率 0%。**

| # | 文件 | 行号 | 导入 | 来源域 |
|---|------|------|------|--------|
| 1 | `simulation_sandbox/sandbox.py` | 41 | `get_oms_service` | core |
| 2 | `simulation_deduction/impl/deduction_engine_impl.py` | 57 | `OMSService` (具体类) | core |
| 3 | `simulation_deduction/impl/deduction_engine_impl.py` | 659 | `OntologyRuntimeService` (具体类) | core |
| 4 | `event_simulator/impl/event_generator.py` | 262 | `ModelService` (具体类) | core |
| 5 | `event_simulator/impl/event_generator.py` | 368 | `OMSService` (具体类) | core |
| 6 | `event_simulator/impl/event_generator.py` | 418 | `OMSService` (具体类) | core |
| 7 | `feedback/loop.py` | 41 | `HookAdapter` (具体类) | integration |

### R3: EventBus 解耦 — 接近不达标 (2/10)

- 仅 1 处标准 EventBus: `parallel_runner.py` L157-159（emit `simulation:queue_update`）
- 无 subscribe 模式（只有发布没有订阅）
- feedback 模块使用 HookAdapter.emit_event()，非标准 EventBus

### 改造路径

| 优先级 | 改造项 | 工作量 |
|--------|--------|--------|
| P0 | 创建 `simulation/interfaces/` 定义 `IOMSService`、`IModelService`、`IRuntimeService` | 3 人天 |
| P0 | 将所有 7 处跨域导入替换为 I* 接口 | 2 人天 |
| P1 | 将 `IDeductionEngine` 改为 ABC | 0.5 人天 |
| P1 | 扩展 EventBus subscribe 模式 | 2 人天 |
| P2 | `__init__.py` 改为导出 I* 接口 | 0.5 人天 |

**预计改造至合规：7-8 人天**

---

## 3. decision — 详细审计

### 规模
3 个子模块: action_service / decision_pipeline / decision_recommendation

### R1: 接口抽象 — 严重不达标 (0/10)

- decision/**无** `interfaces/` 目录
- 无任何 I* 抽象类
- `core/ontology/action/interfaces/` 中已有 `ActionExecutor` (ABC) 和 `ActionTypeRepository` (ABC)，decision 完全未采用
- `__all__ = []` 且导出的 3 个均为具体类

### R2: 业务域隔离 — 严重不达标 (0/10)

**5 处跨 biz 域导入，全部是具体类，干净率 0%。**

| # | 文件 | 行号 | 导入 | 来源域 |
|---|------|------|------|--------|
| 1 | `action_service/executor.py` | 75 | `OMSService` (具体类) | core |
| 2 | `action_service/feedback_loop.py` | 220-223 | `OntologyDocument`, `OntologyAction`, `SourceInfo`, `DocumentMeta`, `VersionRef`, `ActionStatus` | core |
| 3 | `decision_pipeline/pipeline.py` | 43 | `get_semantic_retriever` (具体函数) | data |
| 4 | `decision_pipeline/pipeline.py` | 417 | `get_oms_service` (具体函数) | core |

### R3: EventBus 解耦 — 不达标 (1/10)

- 无标准 EventBus
- 仅 `feedback_loop.py` L274-279 使用自制 `HookRegistry.emit()`（非标准模式）

### 改造路径

| 优先级 | 改造项 | 工作量 |
|--------|--------|--------|
| P0 | 创建 `decision/interfaces/` 定义 `IActionExecutor`、`IDecisionEngine` 等 | 2 人天 |
| P0 | `action_service.executor.ActionExecutor` 改为实现 `core.ontology.action.interfaces.ActionExecutor` ABC | 1.5 人天 |
| P1 | 注入依赖通过 I* 接口（OMSService、GraphWriteProxy、OPAManager） | 3 人天 |
| P1 | 引入标准 EventBus 替换 HookRegistry | 2 人天 |
| P2 | `__init__.py` 仅导出 I* 接口 | 0.5 人天 |

**预计改造至合规：8-9 人天**

---

## 优先级与建议

### 改造优先级排序

```
agent (3-4.5天)  >  simulation (7-8天)  >  decision (8-9天)
    ↑                    ↑                    ↑
  最近乎就绪           最需拆分           最需拆分
  (ADR-065 高优)     (ADR-065 高优)     (ADR-065 中优)
```

### 建议

1. **先改 agent**：改造量最小，可以作为舱壁先行改造的"试点"，积累模式经验后推广到 simulation 和 decision
2. **共性问题的低成本修复**：三个模块都缺乏 ABC 接口——可以在各自 `interfaces/` 创建接口层，这是纯增量代码，不影响现有功能
3. **拆分决策暂缓**：在三个模块 R1/R2/R3 全部达标之前，不启动物理拆分。当前评分不支持任何模块拆出
4. **接口定义应放在被依赖方**：agent 需要的 `ISwarmAdapter` 应定义在 integration 域；simulation 需要的 `IOMSService` 应定义在 core 域。这遵循依赖反转原则

---

## 关联

- ADR-046（模块化单体基线 + 拆分触发条件）
- ADR-065（微服务拆分演进预案，本文为其合规审计）
- ADR-064（可观测性是拆分前提，未在本审计中覆盖）
- ADR-067（biz/shared 下沉，与本文改造无关但同属模块边界治理）
