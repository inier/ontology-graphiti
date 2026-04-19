# ODAP 文档中心

欢迎来到 ODAP（Ontology-Driven Analysis Platform）文档中心！

> 基于 Graphiti + OPA + Skill 架构的智能决策系统，参考 Palantir AIP 架构设计

---

## 📚 目录

- [项目简介](#项目简介)
- [文档体系概览](#文档体系概览)
- [快速导航](#快速导航)
- [如何开始](#如何开始)
- [技术架构](#技术架构)

---

## 项目简介

ODAP 是一个面向知识驱动决策的分析平台，提供以下核心能力：

- **双时态知识图谱** - 基于 Graphiti 的知识管理系统
- **策略驱动治理** - 基于 OPA 的权限与策略引擎
- **技能体系** - 可扩展的 Skill 执行框架
- **多 Agent 协同** - Swarm 编排的智能决策系统
- **工作空间隔离** - 多租户场景支持
- **可视化与推演** - 态势感知与 What-if 分析

---

## 文档体系概览

ODAP 采用分层文档体系，从上到下依次为：

```
┌─────────────────────────────────────────┐
│           战略层（Business）             │
│  需求文档、架构规划、任务拆分、Checklist │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│         架构层（Architecture）           │
│        核心架构、ADR 决策记录            │
└─────────────────────────────────────────┘
                    │
         ┌──────────┼──────────┐
         ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ 决策层   │ │ 模块层   │ │ 设计层   │
│ (ADR)    │ │ (Design) │ │  (UI)    │
└──────────┘ └──────────┘ └──────────┘
         │          │          │
         └──────────┼──────────┘
                    ▼
┌─────────────────────────────────────────┐
│         实现层（Implementation）         │
│      前端代码、后端代码、技能定义         │
└─────────────────────────────────────────┘
```

---

## 快速导航

### 🏁 快速入门必读

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [DOCUMENT_RELATIONSHIP.md](./DOCUMENT_RELATIONSHIP.md) | 文档关系图，快速索引 | ⭐⭐⭐ |
| [req-ok.md](./req-ok.md) | 需求定稿，唯一权威来源 | ⭐⭐⭐ |
| [ARCHITECTURE_PLAN_v4.md](./ARCHITECTURE_PLAN_v4.md) | 架构规划 v4.0 | ⭐⭐⭐ |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 核心架构文档 | ⭐⭐⭐ |
| [CHECKLIST_v2.md](./CHECKLIST_v2.md) | 完整 Checklist v2 | ⭐⭐ |

### 📐 架构设计

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [adr/README.md](./adr/README.md) | ADR 索引 | ⭐⭐⭐ |
| [adr/ADR-001~047](./adr/) | 47 个架构决策记录 | ⭐⭐ |
| [modules/README.md](./modules/README.md) | 模块设计索引 | ⭐⭐ |

### 🎨 前端与 UI

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [ui/UI_DESIGN.md](./ui/UI_DESIGN.md) | UI 设计稿 | ⭐⭐⭐ |
| [ui/MOBILE_FIRST_DESIGN.md](./ui/MOBILE_FIRST_DESIGN.md) | 移动优先设计规范 | ⭐⭐ |
| [ui/COMPONENT_HIERARCHY.md](./ui/COMPONENT_HIERARCHY.md) | 组件分级体系 | ⭐⭐ |
| [modules/web_frontend/DESIGN.md](./modules/web_frontend/DESIGN.md) | 前端模块设计 | ⭐⭐ |

### 🔧 任务与开发

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [TASK_BREAKDOWN.md](./TASK_BREAKDOWN.md) | 任务拆分与开发计划 | ⭐⭐⭐ |
| [CHECKLIST_v2.md](./CHECKLIST_v2.md) | 开发 Checklist | ⭐⭐⭐ |
| [TEST_DESIGN.md](./TEST_DESIGN.md) | 测试设计 | ⭐⭐ |
| [DFX_DESIGN.md](./DFX_DESIGN.md) | DFX 设计 | ⭐⭐ |

---

## 如何开始

### 新成员加入

如果你是项目新成员，建议按以下顺序阅读：

1. **文档关系图** - [DOCUMENT_RELATIONSHIP.md](./DOCUMENT_RELATIONSHIP.md)
2. **需求定稿** - [req-ok.md](./req-ok.md)
3. **架构规划 v4.0** - [ARCHITECTURE_PLAN_v4.md](./ARCHITECTURE_PLAN_v4.md)
4. **核心架构** - [ARCHITECTURE.md](./ARCHITECTURE.md)
5. **完整 Checklist** - [CHECKLIST_v2.md](./CHECKLIST_v2.md)

### 前端开发

如果你是前端开发，建议阅读路径：

1. [ARCHITECTURE_PLAN_v4.md](./ARCHITECTURE_PLAN_v4.md) - 了解整体规划
2. [ARCHITECTURE.md](./ARCHITECTURE.md) - 第 11 章，前端界面架构
3. [adr/ADR-007](./adr/ADR-007_前端采用_react_ant_design_技术栈.md) - 技术选型
4. [adr/ADR-037](./adr/ADR-037_frontend_mobile_first_i18n.md) - 移动优先与国际化
5. [adr/ADR-045](./adr/ADR-045_frontend_visualization_g6_leaflet.md) - 可视化技术
6. [ui/UI_DESIGN.md](./ui/UI_DESIGN.md) - UI 设计稿
7. [modules/web_frontend/DESIGN.md](./modules/web_frontend/DESIGN.md) - 前端模块设计
8. [../frontend/](../frontend/) - 前端代码

### 后端开发

如果你是后端开发，建议阅读路径：

1. [ARCHITECTURE_PLAN_v4.md](./ARCHITECTURE_PLAN_v4.md) - 架构规划
2. [ARCHITECTURE.md](./ARCHITECTURE.md) - 核心架构（全文）
3. [TASK_BREAKDOWN.md](./TASK_BREAKDOWN.md) - 任务拆分
4. [modules/README.md](./modules/README.md) - 模块设计索引
5. [adr/ADR-038~047](./adr/) - 新增架构决策
6. [../odap/](../odap/) - 后端代码

### 架构师

如果你是架构师，建议阅读路径：

1. [req-ok.md](./req-ok.md) - 需求定稿
2. [ARCHITECTURE_PLAN_v4.md](./ARCHITECTURE_PLAN_v4.md) - 架构规划
3. [ARCHITECTURE.md](./ARCHITECTURE.md) - 核心架构（精读）
4. [adr/README.md](./adr/README.md) - ADR 索引
5. [CHECKLIST_v2.md](./CHECKLIST_v2.md) - 完整 Checklist

---

## 技术架构

### 核心组件

| 组件 | 技术 | 说明 |
|------|------|------|
| **知识图谱** | Graphiti + Neo4j | 双时态知识管理 |
| **策略引擎** | OPA | 权限与策略治理 |
| **技能体系** | 自定义 Skill 框架 | 可扩展技能执行 |
| **Agent 编排** | Swarm Orchestrator | 多 Agent 协同 |
| **前端** | React + Ant Design + TypeScript | 移动优先响应式设计 |
| **可视化** | G6 + Leaflet + ECharts | 图谱与态势可视化 |

### 七层架构

ODAP 采用七层架构设计（参考 Knora）：

1. **用户交互层** - 多角色界面（指挥官、管理员、通用对话）
2. **用户认知引擎层** - 意图识别、知识导航、解释引擎、角色视图
3. **Agent 编排层** - 三 Agent 协同、任务调度、消息路由
4. **核心引擎层** - Graphiti、Skill 注册、OPA 策略
5. **本体管理引擎层** - 数据审计、构建可视化、版本管理、验证
6. **工作空间隔离层** - 场景隔离、资源隔离、配置隔离
7. **基础设施与存储层** - Neo4j、PostgreSQL、Redis、MinIO

详细请参考：[ARCHITECTURE_PLAN_v4.md](./ARCHITECTURE_PLAN_v4.md)

---

## 版本信息

| 项目 | 当前版本 | 更新日期 |
|------|---------|---------|
| ODAP 平台 | v4.0 | 2026-04-19 |
| 文档体系 | v1.2.0 | 2026-04-19 |
| 核心架构 | v3.2 | - |

---

## 联系与反馈

如有问题或建议，请：
1. 查看 [ANOMALY_REPORT.md](./ANOMALY_REPORT.md) 异常报告
2. 查看 [AUDIT_REPORT.md](./AUDIT_REPORT.md) 审计报告
3. 或通过项目 Issue 反馈

---

**文档最后更新**: 2026-04-19
