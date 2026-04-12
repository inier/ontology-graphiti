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

## 2. Phase 0-Bridge: 现有代码修复（1 周）

> **目标**: 让现有代码能真正跑通，测试全部通过

### T0-1: 修复 5 个致命 Bug

| Bug | 文件 | 修复方式 |
|-----|------|---------|
| `add_entity()` 未定义 | `core/graph_manager.py` | 在 `BattlefieldGraphManager` 中添加方法，fallback 模式下往 `networkx` 图添加节点 |
| `get_entity_history()` 未定义 | 同上 | 返回空列表（fallback 模式不支持时态查询） |
| `search_hybrid()` 未定义 | 同上 | 委托给 `search()` 方法 |
| `reserve_task()` 未定义 | 同上 | 使用已有的 `self.reserved_tasks` 列表 |
| `get_reserved_tasks()` 未定义 | 同上 | 返回 `self.reserved_tasks` |
| `clear_reserved_tasks()` 未定义 | 同上 | 清空 `self.reserved_tasks` |

### T0-2: 修复测试断言

| 测试 | 当前 | 应修改为 |
|------|------|---------|
| `test_graph_manager` | `stats["node_count"]` | `stats["total_entities"]` |
| `test_graph_manager` | `stats["type_count"]` | `stats["entity_types"]` |

### T0-3: 修复 OPA import

- `core/opa_manager.py` 第 8 行 `from opa import OPAClient` 永远未使用
- `core/intelligence_collector.py` 同样 import 但未使用
- 修复：移除无用 import 或添加 `try/except`

### T0-4: 补全 `requirements.txt`

- 添加缺失的 `httpx`

**验收标准**:
```bash
python -m pytest tests/ -v  # 全部通过
python -c "from core.orchestrator import SelfCorrectingOrchestrator; o = SelfCorrectingOrchestrator(); print(o.run('分析战场态势'))"  # 正常输出
```

---

## 3. Phase 1-A: 基础设施验证（2 周）

> **目标**: 四大核心组件独立可运行，不追求集成

### Slice 1.1: OpenHarness 集成验证（Week 5）

| 任务 | 内容 | 产出 |
|------|------|------|
| 安装 OpenHarness | `pip install openharness`，验证 `oh` CLI | 运行 `oh --version` |
| 理解 Tool 接口 | 阅读 OpenHarness 源码中 Tool/Skill 定义 | 接口文档笔记 |
| 原型桥接 | 将现有 `SKILL_CATALOG` 的 `search_radar` 注册为 OpenHarness Tool | 概念验证代码 |

### Slice 1.2: Graphiti + Neo4j 集成验证（Week 5-6）

| 任务 | 内容 | 产出 |
|------|------|------|
| 部署 Neo4j | Docker Compose 起一个 Neo4j 实例 | `neo4j://localhost:7687` 可连 |
| Graphiti 连接 | 使用现有 `ZhipuAIClient` + Graphiti 连接 Neo4j | `build_indices_and_constraints()` 成功 |
| 写入 Episode | 将 `simulation_data` 写入 Graphiti | 至少 20 个 Episode 成功 |
| 查询验证 | 使用 `retrieve_episodes()` 查询 | 能检索到写入的数据 |
| 回退机制优化 | 当 Neo4j 不可用时优雅回退 networkx | 自动检测 + 日志 |

### Slice 1.3: OPA 真实集成验证（Week 6）

| 任务 | 内容 | 产出 |
|------|------|------|
| 部署 OPA | Docker Compose 起一个 OPA 实例 | `http://localhost:8181/v1/data` 可达 |
| 编写 Rego 策略 | 至少 3 个核心策略 (attack, command, view) | `.rego` 文件 |
| Python 客户端对接 | 用 `opa-python` 连接 OPA，替换 mock | `OPAManager.use_mock = False` |
| 策略测试 | 验证 pilot/commander 权限矩阵 | 单元测试 |

### Slice 1.4: Skill 基类重构（Week 6）

| 任务 | 内容 | 产出 |
|------|------|------|
| 定义 BaseSkill | 按 DESIGN.md 定义 `SkillInput/SkillOutput/BaseSkill` | `skills/base.py` |
| 逐步迁移 | 先迁移 `intelligence.py` (2 个 skill) 作为示范 | 示范代码 |
| 注册机制更新 | 适配新基类的 `SKILL_CATALOG` | 向后兼容 |

**验收标准**:
- OpenHarness 可以调用至少 1 个 Skill
- Graphiti 可以写入/查询 Episode（非 networkx 模式）
- OPA 策略检查通过（非 mock 模式）
- 至少 2 个 Skill 使用新基类

---

## 4. Phase 1-B: Intelligence Agent 单体闭环（2 周）

> **目标**: 一个 Intelligence Agent 能独立完成 "分析 B 区威胁" 并输出结构化报告

### Slice 1.5: Intelligence Agent 核心（Week 7-8）

| 任务 | 内容 | 涉及模块 |
|------|------|---------|
| Agent 定义 | 用 OpenHarness 定义 Intelligence Agent | openharness_bridge |
| 雷达搜索 Skill | 改造 `search_radar` 为 OpenHarness Tool | skills |
| 威胁评估 Skill | 改造 `analyze_threat_level` | skills |
| 态势分析 Skill | 改造 `analyze_battlefield` | skills |
| Graphiti 记忆 | Intelligence Agent 的分析结果写入 Graphiti | graphiti_client |
| OPA 集成 | 分析过程涉及敏感数据时触发 OPA 检查 | opa_policy |

### Slice 1.6: RAG 增强推理（Week 8-9）

| 任务 | 内容 | 涉及模块 |
|------|------|---------|
| 向量化 | 情报文本 Embedding 写入 Graphiti | graphiti_client |
| 历史模式匹配 | 基于历史 Episode 匹配当前态势 | graphiti_client |
| RAG 查询 | "类似 B 区雷达活动的历史案例" | graphiti_client |

### Slice 1.7: 端到端 Demo（Week 9-10）

| 任务 | 内容 |
|------|------|
| Demo 场景 | 用户输入 "分析 B 区威胁" → Intelligence Agent 输出结构化报告 |
| 性能基线 | 响应时间 < 10 秒 |
| 日志追踪 | 完整的请求链路追踪 |

**验收标准**:
```
输入: "分析 B 区威胁"
输出: {
  "threat_level": "high",
  "enemy_units": [...],
  "enemy_weapons": [...],
  "civilian_risk": [...],
  "recommendations": [...],
  "historical_patterns": [...]  // RAG 增强
}
```

---

## 5. Phase 2: 三 Agent 协同 OODA（2-3 月）

> 按照现有 ARCHITECTURE v3.1 Phase 2 路线图执行

### 依赖关系

```
Phase 1-B 完成
    │
    ├── Slice 2.1: Commander Agent (方案生成 + OPA 校验 + 人工确认)
    │       │
    ├── Slice 2.2: Operations Agent (attack_target + command_unit + 状态监控)
    │       │
    └── Slice 2.3: Swarm 编排 (三 Agent 协同 + 通信协议 + 错误处理)
            │
            └── Slice 2.4: 完整 OODA 闭环测试
```

> Phase 2 的详细拆分可以在 Phase 1 完成后再细化，当前的设计文档已经足够详细。

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

**关键路线**: 修复 Bug → Graphiti+Neo4j → OPA 集成 → Intelligence Agent → RAG 增强 → Demo
