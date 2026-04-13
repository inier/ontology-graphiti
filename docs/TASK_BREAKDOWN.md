# ODAP 任务拆分策略

> **版本**: 1.0 | **日期**: 2026-04-13 | **基于**: ARCHITECTURE v3.1 + 12 模块 DESIGN.md + 代码扫描

---

## 0. 现状诊断

### 文档 vs 代码差距

| 维度 | 文档 | 实际代码 | 差距 |
|------|------|---------|------|
| 架构文档 | 4928 行 (v3.1) | — | 已完成 |
| 模块设计 | 12 个 DESIGN.md (~15,000 行) | — | 已完成 |
| ADR | 29 条 | — | 已完成 |
| 核心代码 | — | 7 文件, ~1,666 行 | **68% 实现度** |
| Skills | 51 个函数, 9 文件 | — | 有逻辑但无基类/无 Pydantic |
| 测试 | — | 1 文件, 169 行 | **全部会失败** (字段名不匹配) |

### 6 个致命级差距 (P0)

| # | 差距 | 影响 |
|---|------|------|
| G1 | OPA 纯模拟 (`use_mock=True`)，从未连接 OPA 服务 | 策略治理层形同虚设 |
| G2 | Graphiti 双时态能力未使用，永远回退 networkx | 知识图谱核心能力为零 |
| G3 | OpenHarness 零集成，编排器自实现正则路由 | 架构基础不存在 |
| G4 | Skill 无基类、无 Pydantic、全同步函数 | 与设计文档接口不匹配 |
| G5 | 5 个方法被调用但未定义 (add_entity, get_entity_history, search_hybrid, reserve_task 等) | 运行时必崩 |
| G6 | 测试断言字段名与实际返回值不匹配 | 测试全部失败 |

---

## 1. 拆分策略：垂直切片，而非水平分层

### 核心原则

**不要按模块（OpenHarness / Graphiti / OPA / Skills）水平推进，而要按端到端功能垂直切片。**

原因：
- 水平分层导致每个模块都搭了架子但不能串联验证
- 垂直切片每次交付都能跑通一个完整功能链路
- 更早发现模块间接口不匹配问题
- 符合 Phase 路线图的设计意图

---

## 2. Phase 0-Bridge: 现有代码修复（1 周）✅ 已完成

> **目标**: 让现有代码能真正跑通，测试全部通过

### T0-1: 修复 5 个致命 Bug ✅

| Bug | 文件 | 修复方式 | 状态 |
|-----|------|---------|------|
| `add_entity()` 未定义 | `core/graph_manager.py` | 在 `BattlefieldGraphManager` 中添加方法，fallback 模式下往 `networkx` 图添加节点 | ✅ |
| `get_entity_history()` 未定义 | 同上 | 返回空列表（fallback 模式不支持时态查询） | ✅ |
| `search_hybrid()` 未定义 | 同上 | 委托给 `search()` 方法 | ✅ |
| `reserve_task()` 未定义 | 同上 | 使用已有的 `self.reserved_tasks` 列表 | ✅ |
| `get_reserved_tasks()` 未定义 | 同上 | 返回 `self.reserved_tasks` | ✅ |
| `clear_reserved_tasks()` 未定义 | 同上 | 清空 `self.reserved_tasks` | ✅ |

### T0-2: 修复测试断言 ✅

| 测试 | 当前 | 应修改为 | 状态 |
|------|------|---------|------|
| `test_graph_manager` | `stats["node_count"]` | `stats["total_entities"]` | ✅ |
| `test_graph_manager` | `stats["type_count"]` | `stats["entity_types"]` | ✅ |

### T0-3: 修复 OPA import ✅

- `core/opa_manager.py` 第 8 行 `from opa import OPAClient` → `try/except ImportError`
- 修复：移除无用 import 或添加 `try/except` | ✅

### T0-4: 补全 `requirements.txt` ✅

- 添加缺失的 `httpx` | ✅

**验收标准**: ✅ 全部通过
```bash
python -m pytest tests/ -v  # 4/4 全部通过
```

---

## 3. Phase 1-A: 基础设施验证（2 周）✅ 已完成

> **目标**: 四大核心组件独立可运行，不追求集成

### Slice 1.1: OpenHarness 推迟决策（Week 5）✅

> **实际调整**: 根据 ADR-030，Phase 1 不引入 OpenHarness，推迟到 Phase 2。

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| 决策记录 | 创建 ADR-030 记录推迟理由和 Phase 2 桥接方案 | `docs/adr/ADR-030_...md` | ✅ |

### Slice 1.2: Graphiti + Neo4j 集成验证（Week 5-6）✅

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| Neo4j 连接 | Docker Neo4j 已运行 | `bolt://localhost:7687` 可连 | ✅ |
| Graphiti 连接 | ZhipuAIClient + Graphiti 连接 Neo4j | `build_indices_and_constraints()` 成功 | ✅ |
| 写入 Episode | 56 条 Episode 写入 Graphiti | 15 locations + 8 units + 8 weapons + 10 infra + 10 events + 5 missions | ✅ |
| 查询验证 | `retrieve_episodes()` + `search()` | 能检索到写入的数据 | ✅ |
| 回退机制 | Neo4j 不可用时优雅回退 networkx | 15 秒超时 + 自动降级 | ✅ |

**关键适配**: ZhipuAIClient 三层适配（URL 拼接 + `_normalize_fields` + `_fill_missing_fields`）

### Slice 1.3: OPA 策略重写（Week 6）✅

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| Rego 策略 | 完整战场交战规则（ROE） | `core/opa_policy.rego` v2.0.0 | ✅ |
| Python 客户端 | REST API 客户端重写（自动检测 + mock fallback） | `core/opa_manager.py` | ✅ |
| 策略测试 | 单元测试通过 | `test_opa_manager` ✅ | ✅ |

> ⚠️ 真实 OPA Docker 连接未验证（代码有自动 health_check + fallback，不阻塞后续）

### Slice 1.4: Skill 基类重构（Week 6）✅

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| 定义 BaseSkill | SkillInput/SkillOutput/BaseSkill 抽象基类 | `skills/base.py` | ✅ |
| 逐步迁移 | 11 个 Skill 全部迁移到 BaseSkill | `skills/*.py` | ✅ |
| 注册机制 | SKILL_CATALOG 适配新基类 | 向后兼容 | ✅ |

**验收标准**: ✅ 全部达成
- ~~OpenHarness 可以调用至少 1 个 Skill~~ → ADR-030 推迟到 Phase 2
- Graphiti 可以写入/查询 Episode（非 networkx 模式）✅
- OPA 策略检查通过（mock 模式）✅
- 11 个 Skill 使用新基类 ✅

---

## 4. Phase 1-B: Intelligence Agent 单体闭环（2 周）✅ 已完成

> **目标**: 一个 Intelligence Agent 能独立完成 "分析 B 区威胁" 并输出结构化报告

### Slice 1.5: Intelligence Agent 核心（Week 7-8）✅

| 任务 | 内容 | 涉及模块 | 状态 |
|------|------|---------|------|
| Agent 定义 | LLM ReAct 循环 + Skill 调用 + OPA 集成 | `core/intelligence_agent.py` | ✅ |
| 工具注册 | 从 SKILL_CATALOG 自动构建 OpenAI function calling 格式 | `_build_tools()` | ✅ |
| 工具执行 | Skill 调用 + OPA 权限校验（operations 类） | `_execute_tool()` | ✅ |
| 报告解析 | LLM 输出 → JSON 结构化报告 | `_extract_report()` | ✅ |
| Graphiti 记忆 | 分析结果写入 Graphiti Episode | `_save_to_graphiti()` | ✅ |

### Slice 1.6: RAG 增强推理（Week 8-9）✅

| 任务 | 内容 | 涉及模块 | 状态 |
|------|------|---------|------|
| RAG 检索 | 三层降级（Graphiti 向量 → Neo4j 关键词 → 内存匹配） | `graph_manager.retrieve_rag_context()` | ✅ |
| 上下文注入 | 在 system prompt 中注入历史情报记忆 | `analyze()` 中的 RAG section | ✅ |
| 历史模式引用 | 报告中的 `historical_patterns` 字段 | LLM prompt 指令 | ✅ |

### Slice 1.7: 端到端 Demo（Week 9-10）✅

| 任务 | 内容 | 状态 |
|------|------|------|
| Demo 场景 | 用户输入 "分析 B 区威胁" → Intelligence Agent 输出结构化报告 | ✅ `main.py` 场景 7 |
| 结构化链路追踪 | TraceSpan + 轮次/工具/LLM 子 span | ✅ |
| 性能基线日志 | JSON 格式 logger.info（trace_id、耗时、RAG 状态） | ✅ |
| LLM 重试机制 | 指数退避 3 次重试（应对网络超时 Error 3003） | ✅ |
| main.py 集成 | 场景 7 演示 Intelligence Agent 完整闭环 | ✅ |

**核心文件**: `core/intelligence_agent.py`（539 行）

**验收标准**: ✅ 全部达成
```
输入: "分析 B 区威胁"
输出: {
  "summary": "...",
  "threat_level": "high/medium/low/critical",
  "enemy_units": [...],
  "enemy_weapons": [...],
  "civilian_risk": [...],
  "recommendations": [...],
  "historical_patterns": [...],  // RAG 增强
  "_metadata": { "execution_time_ms": ..., "rag_context_provided": true, ... },
  "_trace": { "trace_id": ..., "spans": [...] }
}
```

---

## 5. Phase 2: 三 Agent 协同 OODA（2-3 月）🔄 进行中

> 按照现有 ARCHITECTURE v3.1 Phase 2 路线图执行

### 依赖关系

```
Phase 1-B 完成
    │
    ├── Slice 2.1: Commander Agent (方案生成 + OPA 校验 + 人工确认) ✅
    │       │
    ├── Slice 2.2: Operations Agent (attack_target + command_unit + 状态监控) ✅
    │       │
    └── Slice 2.3: Swarm 编排 (三 Agent 协同 + 通信协议 + 错误处理) ✅
            │
            └── Slice 2.4: 完整 OODA 闭环测试 ✅
```

### Slice 2.1: Commander Agent ✅

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| CommanderAgent 类 | 实现决策中枢逻辑 | `core/swarm_orchestrator.py` | ✅ |
| analyze_situation | 分析态势生成决策选项 | 根据情报数据生成多个行动方案 | ✅ |
| _generate_options | 生成打击/监控/协调选项 | options 列表 | ✅ |
| _select_best_option | 选择最佳决策 | 返回推荐行动 | ✅ |
| OPA 集成 | 高危操作需审批 | requires_opa_approval | ✅ |

### Slice 2.2: Operations Agent ✅

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| OperationsAgent 类 | 实现执行中枢逻辑 | `core/swarm_orchestrator.py` | ✅ |
| execute_order | 执行指挥官命令 | 执行结果 | ✅ |
| _execute_action | 执行单个行动 | 单个目标执行结果 | ✅ |
| pending_confirmations | 待确认命令队列 | 人工确认机制 | ✅ |

### Slice 2.3: Swarm 编排器 ✅

| 任务 | 内容 | 产出 | 状态 |
|------|------|------|------|
| BattlefieldSwarm 主类 | 三 Agent 协同编排 | `core/swarm_orchestrator.py` | ✅ |
| OODA 循环 | Observe→Orient→Decide→Act | 完整闭环执行 | ✅ |
| execute_streaming | 流式进度返回 | AsyncGenerator[OODAProgress] | ✅ |
| _initialize_agents | 初始化三 Agent | Agent 实例 | ✅ |
| _write_episodes | 结果写入 Graphiti | Episode 写入 | ✅ |

### Slice 2.4: OODA 闭环测试 ✅

| 测试 | 内容 | 结果 |
|------|------|------|
| 完整 OODA 循环 | "分析B区威胁" 任务 | ✅ 成功，4/4 阶段完成 |
| 流式进度 | execute_streaming | ✅ 正常 |
| 错误处理 | RAG 降级处理 | ✅ 修复 Neo4j 语法问题 |
| 状态持久化 | MissionResult | ✅ 记录历史 |

### 核心文件

- `core/swarm_orchestrator.py` (619 行) - Swarm 编排器核心实现

### 验收标准

```python
# OODA 闭环测试
swarm = BattlefieldSwarm()
result = await swarm.execute_mission("分析B区威胁并采取行动")
# result.mission_id: "xxx"
# result.success: True
# result.phases_completed: [OBSERVE, ORIENT, DECIDE, ACT]
# result.execution_time_ms: ~150ms
# result.final_decision: {situation_summary, threat_level, recommended_action, ...}
```

---

## 6. 任务优先级矩阵

| 优先级 | 任务 | 依赖 | 工期 | 风险 |
|--------|------|------|------|------|
| 🔴 P0 | T0-1 修复致命 Bug | 无 | 1 天 | 低 |
| 🔴 P0 | T0-2 修复测试 | T0-1 | 0.5 天 | 低 |
| 🔴 P0 | T0-3 修复 import | 无 | 0.5 天 | 低 |
| 🟡 P1 | Slice 1.1 OpenHarness | 无 | 3 天 | 中 |
| 🟡 P1 | Slice 1.2 Graphiti+Neo4j | 无 | 5 天 | 高 |
| 🟡 P1 | Slice 1.3 OPA 集成 | 无 | 3 天 | 中 |
| 🟡 P1 | Slice 1.4 Skill 基类 | 无 | 3 天 | 低 |
| 🟢 P2 | Slice 1.5 Intel Agent | 1.1-1.4 | 7 天 | 中 |
| 🟢 P2 | Slice 1.6 RAG 增强 | 1.2, 1.5 | 5 天 | 高 |
| 🟢 P2 | Slice 1.7 Demo | 1.5, 1.6 | 3 天 | 低 |
| ⚪ P3 | Phase 2 全部 | Phase 1 | 8-12 周 | 高 |

---

## 7. 关键决策点

### D1: 是否现在就引入 OpenHarness？

**建议**: Phase 1 先用现有编排器 + 手动集成，Phase 2 再正式引入 OpenHarness。

理由：
- OpenHarness 文档/稳定性还在验证中
- 现有 `SelfCorrectingOrchestrator` 满足 Phase 1 单 Agent 需求
- 过早引入可能增加不必要的复杂度

### D2: Graphiti 是否必须先有 Neo4j？

**建议**: 是。Phase 1-B 的 RAG 增强依赖 Graphiti 的向量检索能力，networkx 回退模式无法替代。

最低要求：一个本地 Docker Neo4j + Ollama/OpenAI Embedding。

### D3: Skill 基类是否现在就重构？

**建议**: 是，但要渐进式迁移。

策略：
- 定义 `BaseSkill` 抽象类
- 新 Skill 必须继承 `BaseSkill`
- 旧 Skill 保持兼容，逐步迁移
- `SKILL_CATALOG` 同时支持新旧两种格式

---

## 8. 总结

**一句话**: 现有代码有 ~5,000 行实现但存在致命 Bug 和架构偏差。建议先花 1 周修桥补路（Phase 0-Bridge），再用 4 周验证四大基础设施（Phase 1-A），最后用 2-3 周打通 Intelligence Agent 端到端（Phase 1-B）。Phase 2 等Phase 1 完成后再细化。

**当前进度**:
- ✅ Phase 0-Bridge: 现有代码修复（T0-1~T0-4）
- ✅ Phase 1-A: 基础设施验证（Slice 1.1~1.4）
- ✅ Phase 1-B: Intelligence Agent 单体闭环（Slice 1.5~1.7）
- ✅ Phase 2: 三 Agent 协同 OODA（Slice 2.1~2.4）

**关键路线**: 修复 Bug → Graphiti+Neo4j → OPA 集成 → Intelligence Agent → RAG 增强 → Demo ✅ **Phase 1 全部完成**
**Phase 2 关键成果**: 实现 BattlefieldSwarm 编排器，完成三 Agent（Intelligence/Commander/Operations）OODA 闭环协同

### Phase 2 扩展: 故障恢复与状态管理 ✅

| 功能模块 | 文件 | 状态 |
|---------|------|------|
| FaultTolerance | `core/fault_tolerance.py` | ✅ |
| StatePersistenceManager | `core/state_persistence.py` | ✅ |
| HealthMonitor | `core/health_monitor.py` | ✅ |
| 单元测试 | `tests/test_swarm.py` | ✅ (18 tests) |
| Swarm 集成 | `core/swarm_orchestrator.py` | ✅ |

#### 核心功能

- **FaultTolerance**: 6 种故障分类、断路器模式、指数退避重试、降级模式
- **StatePersistenceManager**: Agent 状态持久化、任务检查点保存/恢复
- **HealthMonitor**: Swarm 健康监控、指标收集、阈值告警
- **Swarm 集成**: 每个 OODA 阶段自动保存检查点、启动/停止健康监控

### Phase 2 扩展: 模拟推演引擎 ✅

| 功能模块 | 文件 | 状态 |
|---------|------|------|
| SimulationEngine | `core/simulation_engine.py` | ✅ |
| 单元测试 | `tests/test_simulation_engine.py` | ✅ (9 tests) |

#### 核心功能

- **SimulationSandbox**: 沙箱隔离推演环境
- **ScenarioVersion**: 方案版本管理、创建分支、回退
- **run_simulation**: 步进式推演执行
- **compare_versions**: 版本参数对比
