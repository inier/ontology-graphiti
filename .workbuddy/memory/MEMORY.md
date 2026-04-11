# 项目长期记忆 — 战场情报分析与打击决策系统

## 项目概述
- **项目路径**: `/Users/caec/workspace/ontology/graphiti`
- **系统定位**: 战场情报分析与打击决策系统，基于 Palantir AIP 架构
- **技术核心**: OpenHarness + Graphiti + Python Skill + OPA

## 架构设计 v2.0（2026-04-11）

### 核心架构：四层组件

| 层次 | 组件 | 职责 |
|------|------|------|
| L1 | OpenHarness | Agent Loop + Swarm + Tool 调度 + Permission |
| L2 | Graphiti | 双时态知识图谱 + 时序推理 + RAG 增强 |
| L3 | Python Skills | 领域工具（情报/作战/分析/可视化） |
| L4 | OPA | 策略治理 + 权限校验 + Fail-Close |

### OpenHarness 核心子系统

- `engine/`: Agent Loop
- `tools/`: 43+ 内置工具
- `plugins/`: 扩展点
- `permissions/`: 权限检查（桥接 OPA）
- `hooks/`: 生命周期事件
- `mcp/`: 外部系统集成
- `memory/`: 记忆管理（桥接 Graphiti）
- `coordinator/`: Swarm 多 Agent

### 三 Agent 角色

| Agent | 定位 | LLM | 职责 |
|-------|------|-----|------|
| Commander | 决策中枢 | 强推理模型 | 最终拍板，OPA 校验 |
| Intelligence | 感知+理解 | 快分析模型 | Observe + Orient |
| Operations | 执行中心 | 规划模型 | Act + 回写 |

### 关键设计决策

- ADR-001: OpenHarness 作为 Agent 基础设施（已接受）
- ADR-002: Graphiti 作为双时态知识图谱（已接受）
- ADR-003: OPA 作为策略治理引擎（已接受）
- ADR-004: Skill 双层并行策略（已接受）
- ADR-005: 三 Agent 角色分工（已接受）

### 演进路线

| Phase | 时间 | 目标 |
|-------|------|------|
| Phase 0 | 2-4周 | 基础设施搭建 |
| Phase 1 | 1-2月 | 单 Agent 闭环（Intelligence） |
| Phase 2 | 2-3月 | 三 Agent 协同 OODA |
| Phase 3 | 3-6月 | 生产化部署 |
| Phase 4 | 6-12月 | 高级特性 |

## 重要文档
- `docs/ARCHITECTURE.md`（v2.0，2026-04-11，完全重写）

## 核心文件
- `core/openharness_bridge.py`: OpenHarness 桥接适配器
- `core/opa_client.py`: OPA 策略客户端
- `core/graphiti_client.py`: Graphiti 客户端
- `core/swarm_orchestrator.py`: Swarm 编排器
