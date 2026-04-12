# ADR-025: 基于 OpenHarness 实现多智能体协同

## 状态
已接受 | **创建日期**: 2026-04-11 | **最后更新**: 2026-04-13

## 上下文

### 问题陈述

Phase 2 的目标是实现多智能体协作（Commander / Intelligence / Operations Agent），当前的单编排器（`SelfCorrectingOrchestrator`）是纯规则驱动的关键词匹配，无法处理：

- **复杂任务分解**：用户说"评估 B 区威胁等级并给出打击方案"需要分解为感知→分析→决策→执行多个子任务
- **跨 Agent 状态共享**：情报 Agent 发现的新目标需要同步给指挥官和作战 Agent
- **动态路由**：同一条用户意图在不同战场态势下需要不同 Agent 处理
- **OODA 闭环**：Perceive → Understand → Decide → Act 的循环协同

### 技术选项

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A. 纯自研（LangGraph / 自写 FSM）** | 用 LangGraph 重写编排层 | 完全可控，无依赖 | 大量基建工作，多 Agent 协调从零做起 |
| **B. OpenHarness 内核** | 以 OpenHarness engine 为底层，上层保留 Graphiti+OPA | Swarm 协调内置，工具/技能/Permission 全家桶，与现有 Skill 体系可桥接 | 框架锁定，11K LOC 学习曲线，与现有 Skill 系统有两套并存的代价 |
| **C. 混合方案（OpenHarness 工具 + 自研编排）** | 保留现有 orchestrator，引入 OpenHarness 的 Swarm/Coordinators 作为子模块 | 渐进迁移，风险可控 | 两套协调机制并存，增加复杂度 |

---

## 决策

**采用方案 B 的渐进式落地策略**：

### 核心思路

```
OpenHarness Engine (Agent Loop)
    │
    ├── Memory ──────────────► Graphiti (双时态知识图谱)
    ├── Skills ──────────────► 现有 56 Skills (桥接 Adapter)
    ├── Permissions ─────────► OPA (现有策略引擎)
    ├── Coordinator ──────────► Commander/Intelligence/Operations Agent
    └── Tools ───────────────► MCP Server (地理空间/雷达模拟等)
```

### 三 Agent 角色定义

```
┌─────────────────────────────────────────────────────────────────┐
│                     Commander Agent                              │
│  角色: 战术指挥官，负责最终打击决策                                │
│  LLM: 强推理模型（如 Claude-3.5/GPT-4）                           │
│  输入: Intelligence Agent 的威胁评估 + Operations Agent 的可行性报告 │
│  输出: 最终打击命令（带 OPA 权限校验）                            │
│  权限: 最高（commander），可批准高危操作                           │
└─────────────────────────────────────────────────────────────────┘
                              ▲
           ┌─────────────────┴─────────────────┐
           │           OPA 策略门控              │
           │  • 高危目标必须指挥官确认           │
           │  • 民用设施黑名单                   │
           │  • 交战规则（ROE）实时校验          │
           └─────────────────┬─────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Intelligence Agent                             │
│  角色: 战场感知 + 态势理解                                        │
│  LLM: 快速分析模型（如 Kimi/DeepSeek）      │
│  输入: 原始传感器数据（雷达/卫星/友军）       │
│  技能: search_radar, analyze_battlefield, threat_assessment      │
│  输出: 结构化威胁报告 → Commander                                 │
│  记忆: Graphiti 时序图谱（实时写入 + 历史查询）                    │
└─────────────────────────────────────────────────────────────────┘
           ▲
           │ 命令执行结果 + 新发现情报
           │
┌─────────────────────────────────────────────────────────────────┐
│                   Operations Agent                               │
│  角色: 行动计划生成 + 执行                                        │
│  LLM: 规划模型                                                   │
│  输入: Commander 的打击命令                                       │
│  技能: attack_target, command_unit, route_planning              │
│  输出: 执行状态 → 回写 Graphiti + 通知 Intelligence              │
└─────────────────────────────────────────────────────────────────┘
```

### OODA 闭环映射

```
感知 (Sense)      → Intelligence Agent + Graphiti
    │ 情报写入时序图谱，跨时间窗口关联事件
    ▼
理解 (Understand) → Intelligence Agent（Graphiti RAG 查询）
    │ 威胁等级评估 + 历史模式匹配
    ▼
决策 (Decide)     → Commander Agent（多选项 + OPA 校验）
    │ 打击方案排序 + 规则校验 + 人工确认（高危）
    ▼
行动 (Act)        → Operations Agent
    │ 命令下发 + 执行监控 + 结果回写 Graphiti
    ▼
感知 (Sense)      ← 闭环回到 Intelligence（接收执行反馈）
```

---

## 后果

### 变得更容易
- 多 Agent 协调开箱即用（Swarm 机制）
- Skill 生态可直接利用（40+ 内置 Skills + 现有 Skills 桥接）
- Permission 体系完整（OPA 可作为 OpenHarness Hook 接入）
- 工具开发标准化（Pydantic 输入模型 + JSON Schema 自描述）

### 变得更有挑战
- **两套 Skill 系统并存**：OpenHarness Skills（Markdown） vs 现有 Python Skills，需要桥接 Adapter
- **学习曲线**：OpenHarness 的 10 个子系统需要团队熟悉
- **运行时开销**：多 Agent + LLM 调用延迟叠加，需要异步 + 流式处理
- **框架依赖**：项目的核心能力部分依赖 OpenHarness 框架稳定性

### 需要决策的关键问题

1. ~~**Skill 体系合并策略**？统一到 OpenHarness Skill 格式（Markdown）还是保留 Python Skill（强类型）？~~ → **已由 ADR-004 决策：统一 Skill 双层并行策略**
2. **LLM 模型分配**？三个 Agent 用同一个模型还是分级（Commander 强推理 + Intelligence 快分析）？
3. **Graphiti 作为 OpenHarness Memory 的边界**？哪些状态走 Graphiti，哪些走 OpenHarness 内置 Memory？

---

## 集成实施计划（Phase 2）

### Week 1-2: 基础设施
- [ ] 安装 OpenHarness (`uv add openharness`)
- [ ] 配置 OpenHarness CLI 环境（模型、API）
- [ ] 实现 OpenHarness 原生扩展点适配（利用 engine/tools/plugins/hooks，见 ADR-005）
- [ ] 验证 OpenHarness Agent Loop 在项目中能跑通

### Week 3-4: 单 Agent 试点
- [ ] 将 `Intelligence Agent` 作为第一个 OpenHarness Agent 接入
- [ ] 复用现有 `skills/intelligence.py` 的 Skill 作为 Tool
- [ ] Graphiti 作为 Agent Memory 的底层存储实现
- [ ] 端到端测试：用户输入 → Intelligence Agent 分析 → Graphiti 写入

### Week 5-8: 多 Agent 协同
- [ ] 实现 `Commander Agent`（高权限，带 OPA Hook）
- [ ] 实现 `Operations Agent`（执行层，带结果回写）
- [ ] 接入 OpenHarness Swarm Coordinator，实现动态任务分解
- [ ] 实现 OODA 闭环：Act 结果自动触发 Sense

### Week 9-12: 生产化
- [ ] 流式输出 + 实时反馈 UI
- [ ] 多 Agent 状态可视化（谁在做什么）
- [ ] 回滚机制（Agent 执行失败时回退到人工介入）
- [ ] 压力测试 + 延迟优化

---

## 可逆性

- OpenHarness 作为独立进程运行，通过 HTTP API 与主系统交互
- 如需切换回自研编排，可将 OpenHarness 降级为"外部工具"而非核心引擎
- OpenHarness 原生扩展点（plugins/hooks）是关键的可拔插层，见 ADR-005

---

*起草日期：2026-04-11*
*状态：已接受（2026-04-13 评审通过，更新过时内容）*
