# 项目长期记忆 — 战场情报分析与打击决策系统

## 项目概述
- **项目路径**: `/Users/caec/workspace/ontology/graphiti`
- **系统定位**: 战场情报分析与打击决策系统，参考 Palantir AIP 架构
- **技术核心**: OpenHarness + Graphiti + Python Skill + OPA

## 关键技术来源（2026-04-11 更新）
- **OpenHarness**: HKUDS（香港大学数据科学实验室）开源项目
  - GitHub: https://github.com/HKUDS/OpenHarness
  - 协议: MIT

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

ADR 文档已独立化，存放在 `docs/adr/` 目录（共 43 条有效，ADR-001~047，含 4 条空洞编号），详见 `docs/adr/README.md`。
核心 ADR：ADR-001(OpenHarness), ADR-002(Graphiti), ADR-003(OPA), ADR-004(Skill), ADR-005(分层Agent), ADR-006(复用策略), ADR-045(G6+Leaflet), ADR-046(模块化单体), ADR-047(工具注册表P0分步)

### OpenHarness 复用矩阵（2026-04-11）

| 类别 | 组件 | 复用方式 |
|------|------|----------|
| **✅ 完全复用** | Agent Loop、Tool框架、Skill格式、Plugin系统、Provider管理 | 开箱即用 |
| **⚠️ 适配复用** | Memory (→Graphiti)、Permissions (→OPA)、Coordinator (→三Agent) | 桥接适配 |
| **🔴 独立扩展** | 战场本体、56领域Skills、时序推理、态势可视化 | 自研 |

### Graphiti 集成经验（2026-04-14）

- **ZhipuAIClient 需三层适配**：URL 智能拼接（去尾部 `/chat/completions`）+ 字段名映射（`_normalize_fields`）+ 缺失字段填充（`_fill_missing_fields`）
- **EpisodicNode 字段**：`content`（不是 `episode_body`），`name`，`uuid`，`created_at`
- **EntityEdge 字段**：`name`，`fact`，`uuid`，`source_node_uuid`，`target_node_uuid`
- **Graphiti.search()** 返回 `list[EntityEdge]`，不是 Episode
- **Embedder 配置**：需要从 chat base_url 推导 embedding base_url（SiliconFlow 模型 `Pro/BAAI/bge-m3`）
- **Neo4j 驱动内置指数退避重试**，必须用 `asyncio.wait_for(timeout=15)` 做快速失败

### 演进路线

| Phase | 时间 | 目标 | 状态 |
|-------|------|------|------|
| Phase 0 | 2-4周 | 基础设施搭建 | ✅ 已完成 |
| Phase 1-A | 1-2月 | 四大基础设施验证（Graphiti+Neo4j, OPA, Skill基类） | ✅ 已完成 |
| Phase 1-B | 1-2月 | 单 Agent 闭环（Intelligence Agent ReAct + RAG + 追踪） | ✅ 已完成 |
| Phase 2 | 2-3月 | 三 Agent 协同 OODA | ✅ 已完成 |
| Phase 3 | 3-6月 | 模拟器增强（Web 可视化 + 热写入 + 标准本体格式） | ✅ 已完成 |
| Phase 4 | 6-12月 | 生产化部署 | ⬜ |

## Phase 4 文档体系（2026-04-19 完成）

九步文档流程全部完成（Step 1-9），Phase 4 规划已就绪：

| Step | 产出 | 状态 |
|------|------|------|
| 1 | `docs/req-alpha.md` — 需求整合（26 FR + 29 NFR + 5 SI） | ✅ |
| 2 | 六层架构 + 专家角色识别 | ✅ |
| 3 | 18 模块划分 + ADR-007~010 | ✅ |
| 4 | 18 个 DESIGN.md + 索引更新 | ✅ |
| 5 | UI/DFX/测试设计文档 | ✅ |
| 6 | `docs/TASK_BREAKDOWN.md` v2.0 — 23 工作项 + 6 Sprint | ✅ |
| 7 | `docs/CHECKLIST.md` — 213 条验收项 | ✅ |
| 8 | `docs/COMPLETENESS_REPORT.md` — 100% 需求覆盖 | ✅ |
| 9 | `docs/ANOMALY_REPORT.md` — 39 条待确认项 | ✅ |

### 关键路径
WR-01→WR-03→WR-04→WR-05→WR-17→WR-18，预估 11.5 周

### 待人工确认的关键决策（ANOMALY_REPORT）
1. ~~**I-17** ReGraph vs G6~~ → ✅ ADR-045 已决策：G6
2. ~~**I-21** Phase 4 单体 vs 微服务~~ → ✅ ADR-046 已决策：模块化单体
3. **I-22** 审计日志存储 → ✅ ADR-042 已决策：SQLite + 文件哈希链锚点
4. **I-36** 🟡 M-11 工具注册表 P0/P1 优先级 → ✅ ADR-047 已决策：P0 分步实现
5. ~~ADR-039~044 待创建~~ → ✅ 已全部创建（2026-04-19）

## ANOMALY_REPORT 状态（2026-04-19 更新）

- **14 条亟需人工确认项 → 全部已关闭**
- 三大关键决策：ADR-045(G6+Leaflet)、ADR-046(模块化单体)、ADR-047(工具注册表P0分步)
- 代码清理已完成：biz/permission/ 删除、adapters/ 并入 infra/、web/legacy/ 归档、1~ 删除
- I-24（storage/非空）和 I-28（simulator_ui/不存在）为记录修正，非操作项
- Redis 和消息队列 Phase 4 不引入（YAGNI），Phase 5+ 再评估

## 重要文档
- `docs/ARCHITECTURE.md`（v3.2，2026-04-15）
- `docs/adr/README.md`（含优先级列，ADR-001~047，全部已创建）
- `docs/TASK_BREAKDOWN.md`（v2.0，2026-04-19，Phase 4 工作项拆分）
- `docs/CHECKLIST.md`（v1.0，213 条验收 Checklist）
- `docs/COMPLETENESS_REPORT.md`（v1.0，范围完整性确认）
- `docs/ANOMALY_REPORT.md`（v1.0，39 条不相关/待确认信息）
- `docs/AUDIT_REPORT.md`（全量文档审计报告）
- `docs/RESTRUCTURE_PLAN.md`（2026-04-15，项目目录重构方案）
- **需求文档三件套**：
  - `docs/req-alpha.md` — v1.0 原始技术研究（归档）
  - `docs/req-beta.md` — v1.1.0 早期需求规格（归档）
  - `docs/req-ok.md` — v2.0.0 需求定稿（⭐ 唯一权威来源）

## 核心文件
- `odap/infra/graphiti/`: Graphiti 客户端
- `odap/infra/opa/`: OPA 策略管理
- `odap/biz/swarm/`: Swarm 编排器
- `odap/biz/ontology/`: 本体管理引擎
