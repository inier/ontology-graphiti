# ODAP 文档体系关系图

> **版本**: 2.0.0 | **日期**: 2026-05-07 | **状态**: 正式 | **优先级**: P0
> **用途**: SDD 层次化文档体系的完整索引，提供快速导航
> **上游**: [文档管理规范](./DOCUMENT_MANAGEMENT.md) | **下游**: 所有层级文档

---

## 0. 快速索引

| 角色 | 推荐阅读路径 |
|------|-------------|
| 新成员 | [README.md](./README.md) → [需求定稿](00-requirements/req-ok.md) → [核心架构](02-architecture/ARCHITECTURE.md) |
| 前端开发 | [ADR-007](07-adr/ADR-007_前端采用_react_ant_design_技术栈.md) → [ADR-037](07-adr/ADR-037_frontend_mobile_first_i18n.md) → [ADR-045](07-adr/ADR-045_frontend_visualization_g6_leaflet.md) → [04-UI设计](04-ui/) → [web_frontend](03-modules/web_frontend/DESIGN.md) |
| 后端开发 | [核心架构](02-architecture/ARCHITECTURE.md) → [03-模块设计](03-modules/) → [07-ADR](07-adr/) → [08-任务分解](08-tasks/TASK_BREAKDOWN.md) |
| 架构师 | [需求定稿](00-requirements/req-ok.md) → [核心架构](02-architecture/ARCHITECTURE.md) → [07-ADR](07-adr/) → [09-检查清单](09-checklists/CHECKLIST_v2.md) |
| 产品经理 | [需求定稿](00-requirements/req-ok.md) → [产品设计](01-product-design/ODAP综合优化设计文档.md) → [09-检查清单](09-checklists/CHECKLIST_v2.md) |
| 文档维护者 | [文档管理规范](./DOCUMENT_MANAGEMENT.md) → 本文档 |

---

## 1. SDD 目录结构

```
docs/
│
├── README.md                             # ⭐ SDD 文档中心入口
├── DOCUMENT_MANAGEMENT.md                # ⭐ 防腐文档体系维护指南
├── DOCUMENT_BASELINE_v1.0.0.md           # 文档基线（首个可信版本）
├── DOCUMENT_RELATIONSHIP.md              # 本文档 — 完整索引
│
├── 00-requirements/                      # ⭐ 原始需求 + 开发需求
│   ├── req-ok.md                         # ⭐ 需求定稿（唯一权威来源）
│   ├── archive/                          # 早期技术研究归档
│   │   ├── req-alpha.md                  # v1.0 技术研究
│   │   └── req-beta.md                   # v1.1.0 早期需求
│   ├── backlog/                          # 待办事项
│   │   └── 待优化清单_2026-05-03.md
│   └── documents/                        # 补充前端文档
│
├── 01-product-design/                    # 产品设计
│   ├── ODAP综合优化设计文档.md            # ⭐ 综合优化设计
│   └── webui-enhancement-design.md       # WebUI增强设计
│
├── 02-architecture/                      # ⭐ 架构设计
│   ├── ARCHITECTURE.md                   # ⭐ 核心架构（v4.0，唯一权威）
│   ├── ARCHITECTURE_ANALYSIS_REPORT.md
│   ├── ARCHITECTURE_BIZ.md               # 业务架构
│   ├── ARCHITECTURE_EVOLVE.md            # 演进架构
│   ├── ARCHITECTURE_FULL_CHAIN.md        # 全链路概要
│   ├── ARCHITECTURE_FULL_CHAIN_DEEP.md   # ⭐ 全链路深入（v2.3）
│   ├── ARCHITECTURE_INFRA.md             # 基础设施架构
│   ├── ARCHITECTURE_OPS.md               # 运维架构
│   ├── ARCHITECTURE_TOOLS.md             # 工具链架构
│   ├── ARCHITECTURE_WEB.md               # Web架构
│   ├── DEEP_REVIEW_REPORT_20260505.md
│   ├── PHASE4_5_PLAN.md
│   ├── REVIEW_REPORT_20260505.md
│   └── reports/                          # 历史审查报告
│
├── 03-modules/                           # ⭐ 模块设计（25个模块）
│   ├── agent/DESIGN.md
│   ├── api_gateway/DESIGN.md
│   ├── audit_log/DESIGN.md
│   ├── auth/DESIGN.md
│   ├── decision_recommendation/DESIGN.md
│   ├── event_simulator/DESIGN.md
│   ├── graphiti_client/DESIGN.md
│   ├── hook_system/DESIGN.md
│   ├── infra/DESIGN.md
│   ├── mcp_protocol/DESIGN.md
│   ├── ontology/DESIGN.md
│   ├── ontology_management_engine/DESIGN.md
│   ├── opa_policy/DESIGN.md
│   ├── openharness_bridge/DESIGN.md
│   ├── qa_engine/DESIGN.md
│   ├── session_memory/DESIGN.md
│   ├── simulator/DESIGN.md
│   ├── skills/DESIGN.md
│   ├── swarm_orchestrator/DESIGN.md
│   ├── test/DESIGN.md
│   ├── tool_registry/DESIGN.md
│   ├── user_cognition_engine/DESIGN.md
│   ├── visualization/DESIGN.md
│   ├── web_frontend/DESIGN.md
│   ├── workspace/DESIGN.md
│   └── README.md                         # 模块索引
│
├── 04-ui/                                # UI设计
│   ├── UI_DESIGN.md                      # 完整UI设计稿
│   ├── COMPONENT_HIERARCHY.md            # 组件分级管理
│   ├── COMPONENT_SPEC.md                 # 组件规格
│   ├── MOBILE_FIRST_DESIGN.md            # 移动优先规范
│   └── ONTOLOGY_BUILD_UI.md              # 本体构建界面
│
├── 05-security/                          # 安全设计
│   └── SECURITY.md                       # 安全架构设计
│
├── 06-dfx/                               # DFX设计
│   ├── DFX_DESIGN.md                     # DFX综合设计
│   └── TEST_DESIGN.md                    # 测试架构设计
│
├── 07-adr/                               # 架构决策记录（54个ADR）
│   ├── ADR-001 ~ ADR-053                 # 所有ADR文档
│   └── README.md                         # ADR索引
│
├── 08-tasks/                             # 任务分解
│   └── TASK_BREAKDOWN.md                 # 任务拆分与Phase规划
│
├── 09-checklists/                        # 检查清单
│   └── CHECKLIST_v2.md                   # ⭐ 完整验收清单
│
├── 10-api/                               # API规范（契约层）
│   ├── API_SPEC.md
│   └── INGEST_API_SPEC.md
│
└── 11-archive/                           # 归档（历史依据）
    ├── legacy_code/
    └── specs/                            # 早期spec（8个特性规格）
```

---

## 2. SDD 层次体系图

```
┌───────────────────────────────────────────────────────────────────────┐
│                 00-requirements/  原始需求 + 开发需求                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │  req-alpha  │  │  req-beta   │  │  req-ok ⭐  │  │   待优化     │    │
│  │  技术研究   │  │  需求草稿   │  │  需求定稿   │  │   清单       │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│   01-product-design/     │    │   02-architecture/       │
│   产品设计                │    │   架构设计 ⭐             │
│   ODAP综合优化设计文档    │    │   ARCHITECTURE.md        │
└──────────────────────────┘    └──────────────────────────┘
                    │                               │
        ┌───────────┼───────────┬───────────┬───────┤
        ▼           ▼           ▼           ▼       ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│03-modules│ │  04-ui   │ │05-security│ │ 06-dfx   │ │  07-adr  │
│ 模块设计 │ │  UI设计   │ │  安全设计  │ │ DFX设计  │ │ 决策记录  │
│25个DESIGN│ │  5个文件  │ │ SECURITY  │ │DFX+TEST  │ │ 54个ADR  │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
        │                                               │
        └───────────────┬───────────────────────────────┘
                        ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    08-tasks/  →  09-checklists/                        │
│                    任务分解       检查清单验收                           │
└───────────────────────────────────────────────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│    10-api/       │    │   11-archive/    │
│    API规范       │    │    归档历史       │
└──────────────────┘    └──────────────────┘
```

---

## 3. 核心文档阅读路径

### 3.1 新成员入门路径

```
1. README.md                                  文档体系入口
2. 00-requirements/req-ok.md                  需求定稿
3. 02-architecture/ARCHITECTURE.md            核心架构文档
4. 09-checklists/CHECKLIST_v2.md              完整验收清单
```

### 3.2 前端开发路径

```
1. 02-architecture/ARCHITECTURE.md §11         前端界面架构
2. 07-adr/ADR-007_前端技术栈.md                  技术选型
3. 07-adr/ADR-037_frontend_mobile_first_i18n.md  移动优先+国际化
4. 07-adr/ADR-045_frontend_visualization_g6_leaflet.md  可视化选型
5. 04-ui/UI_DESIGN.md                             UI设计稿
6. 04-ui/MOBILE_FIRST_DESIGN.md                   移动优先规范
7. 04-ui/COMPONENT_HIERARCHY.md                   组件分级管理
8. 03-modules/web_frontend/DESIGN.md              前端模块设计
```

### 3.3 后端开发路径

```
1. 02-architecture/ARCHITECTURE.md               核心架构文档
2. 08-tasks/TASK_BREAKDOWN.md                    任务拆分
3. 03-modules/*/DESIGN.md                        相关模块设计
4. 07-adr/                                       新增架构决策
```

### 3.4 架构师路径

```
1. 00-requirements/req-ok.md                    需求定稿
2. 02-architecture/ARCHITECTURE.md              核心架构（全文精读）
3. 07-adr/README.md                              ADR索引
4. 09-checklists/CHECKLIST_v2.md                 完整验收清单
```

---

## 4. 文档关系矩阵

| 上游 | 下游 | 关系 |
|------|------|:----:|
| `00-requirements/req-ok.md` | `02-architecture/ARCHITECTURE.md` | 需求→架构 |
| `02-architecture/ARCHITECTURE.md` | `08-tasks/TASK_BREAKDOWN.md` | 架构→任务 |
| `02-architecture/ARCHITECTURE.md` | `03-modules/*/DESIGN.md` | 架构→模块 |
| `02-architecture/ARCHITECTURE.md` | `04-ui/UI_DESIGN.md` | 架构→UI |
| `02-architecture/ARCHITECTURE.md` | `07-adr/*` | 架构→决策 |
| `07-adr/ADR-007` | `04-ui/UI_DESIGN.md` | 技术选型→UI |
| `07-adr/ADR-037` | `04-ui/MOBILE_FIRST_DESIGN.md` | 响应式→移动 |
| `07-adr/ADR-045` | `03-modules/web_frontend/DESIGN.md` | 可视化→前端 |
| `01-product-design/ODAP综合优化设计文档.md` | `02-architecture/ARCHITECTURE.md` | 产品→架构 |
| CHANGELOG | 最新变更跟踪 | — |

---

## 5. ADR 索引（按主题分类）

### 5.1 核心架构

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-001 | Agent 基础设施 OpenHarness + LangGraph | 已接受 |
| ADR-002 | Graphiti 作为双时态知识图谱 | 已接受 |
| ADR-005 | 分层 Agent 架构 | 已接受 |
| ADR-006 | OpenHarness 复用策略 | 已接受 |
| ADR-030 | Phase1 推迟引入 OpenHarness | 已接受 |
| ADR-038 | 本体管理引擎与用户认知引擎架构 | 已接受 |
| ADR-046 | 模块化单体部署 | 已接受 |

### 5.2 前端与 UI

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-007 | 前端采用 React + Ant Design | 已接受 |
| ADR-015 | 可扩展图表系统 | 已接受 |
| ADR-020 | 管理员控制台统一界面 | 已接受 |
| ADR-031 | Simulator Web 可视化 | 已接受 |
| ADR-037 | 前端移动优先、响应式+国际化 | 已接受 |
| ADR-045 | 前端可视化 G6+Leaflet | 已接受 |

### 5.3 安全与治理

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-003 | OPA 策略治理引擎 | 已接受 |
| ADR-008 | 审计日志完整记录 | 已接受 |
| ADR-009 | Markdown 编写 OPA 策略 | 已接受 |
| ADR-028 | OPA 统一权限校验 | 已接受 |
| ADR-042 | 审计日志存储查询 | 已接受 |

### 5.4 技能与扩展

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-004 | 统一 Skill 体系架构 | 已接受 |
| ADR-014 | 技能热插拔架构 | 已接受 |
| ADR-026 | MCP 协议集成 | 已接受 |
| ADR-027 | Hook 系统架构 | 已接受 |
| ADR-029 | 工具注册架构 | 已接受 |
| ADR-047 | 工具注册 P0 分阶段实现 | 已接受 |

### 5.5 运行时引擎

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-023 | 多工作空间隔离 | 已接受 |
| ADR-024 | 本体驱动分析核心架构 | 已接受 |
| ADR-039 | QA 引擎架构 | 已接受 |
| ADR-040 | API 网关统一入口 | 已接受 |
| ADR-041 | 工作空间资源隔离 | 已接受 |
| ADR-043 | Agent 路由器语义路由 | 已接受 |
| ADR-044 | 测试策略与框架 | 已接受 |

### 5.6 Phase 5 选型

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-052 | 智能问答 WebUI 选型 | 提议 |
| ADR-053 | Skill 可视化管理选型 | 提议 |

---

## 6. 模块设计索引

| 模块 | 路径 | 架构层 |
|------|------|--------|
| Agent | `03-modules/agent/DESIGN.md` | L3 |
| API Gateway | `03-modules/api_gateway/DESIGN.md` | L5 |
| Audit Log | `03-modules/audit_log/DESIGN.md` | L1 |
| Auth | `03-modules/auth/DESIGN.md` | L1 |
| Decision Recommendation | `03-modules/decision_recommendation/DESIGN.md` | L4 |
| Event Simulator | `03-modules/event_simulator/DESIGN.md` | L2 |
| Graphiti Client | `03-modules/graphiti_client/DESIGN.md` | L1 |
| Hook System | `03-modules/hook_system/DESIGN.md` | L1 |
| Infra | `03-modules/infra/DESIGN.md` | L1 |
| MCP Protocol | `03-modules/mcp_protocol/DESIGN.md` | L1 |
| Ontology | `03-modules/ontology/DESIGN.md` | L1 |
| Ontology Mgmt Engine | `03-modules/ontology_management_engine/DESIGN.md` | L1 |
| OPA Policy | `03-modules/opa_policy/DESIGN.md` | L1 |
| QA Engine | `03-modules/qa_engine/DESIGN.md` | L4 |
| Session Memory | `03-modules/session_memory/DESIGN.md` | L1 |
| Simulator | `03-modules/simulator/DESIGN.md` | L4 |
| Skills | `03-modules/skills/DESIGN.md` | L2 |
| Swarm Orchestrator | `03-modules/swarm_orchestrator/DESIGN.md` | L3 |
| Test | `03-modules/test/DESIGN.md` | — |
| Tool Registry | `03-modules/tool_registry/DESIGN.md` | L2 |
| Visualization | `03-modules/visualization/DESIGN.md` | L4 |
| Web Frontend | `03-modules/web_frontend/DESIGN.md` | L6 |
| Workspace | `03-modules/workspace/DESIGN.md` | L1 |

---

## 7. 文档更新规则

| 变更场景 | 必须同步更新 |
|----------|:------------|
| 需求变更 | `00-requirements/req-ok.md` → `02-architecture/ARCHITECTURE.md` → `08-tasks/TASK_BREAKDOWN.md` |
| 架构调整 | `02-architecture/ARCHITECTURE.md` → `07-adr/*` → `03-modules/*/DESIGN.md` |
| UI 变更 | `04-ui/UI_DESIGN.md` → `04-ui/MOBILE_FIRST_DESIGN.md` |
| 新增 ADR | `ADR-xxx.md` → `07-adr/README.md` → 本文档 |
| 模块设计变更 | `03-modules/*/DESIGN.md` → `02-architecture/ARCHITECTURE.md` |
| 文档体系变更 | `DOCUMENT_MANAGEMENT.md` → 本文档 |
| 文档归档 | 移至 `11-archive/` → 更新本文档 |

---

## 8. 相关文档链接

- [SDD 总入口](./README.md)
- [防腐维护指南](./DOCUMENT_MANAGEMENT.md)
- [文档基线 v1.0.0](./DOCUMENT_BASELINE_v1.0.0.md)
- [需求定稿](./00-requirements/req-ok.md)
- [核心架构](./02-architecture/ARCHITECTURE.md)
- [全链路深入](./02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md)
- [ADR 索引](./07-adr/README.md)
- [验收清单](./09-checklists/CHECKLIST_v2.md)
