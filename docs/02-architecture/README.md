# 02-架构设计 (Architecture)

> **所属层次**: SDD 第4层 — 架构设计
> **上游**: [01-产品设计](../01-product-design) | **下游**: [03-模块设计](../03-modules)

---

## 文档清单

| 文档 | 版本 | 定位 | 说明 |
|------|:----:|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 4.0.1 | ⭐ **唯一权威架构** | 四层架构定义、Phase 4-5演进、Checklist、异常确认 |
| [ARCHITECTURE_FULL_CHAIN.md](ARCHITECTURE_FULL_CHAIN.md) | 1.0.0 | 全链路架构概述 | 5-Phase数据流：摄入→构建→问答→执行→反馈 |
| [ARCHITECTURE_FULL_CHAIN_DEEP.md](ARCHITECTURE_FULL_CHAIN_DEEP.md) | 2.3.0 | 全链路深入实现 | Python/TypeScript/DB Schema完整代码 |
| [ARCHITECTURE_BIZ.md](ARCHITECTURE_BIZ.md) | — | 业务架构 | L3-L4业务层详细设计 |
| [ARCHITECTURE_INFRA.md](ARCHITECTURE_INFRA.md) | — | 基础设施架构 | L1基础设施：Neo4j/OPA/图数据库 |
| [ARCHITECTURE_TOOLS.md](ARCHITECTURE_TOOLS.md) | — | 领域工具架构 | L2领域工具层 |
| [ARCHITECTURE_WEB.md](ARCHITECTURE_WEB.md) | — | Web层架构 | L5-L6接口层/交互层 |
| [ARCHITECTURE_EVOLVE.md](ARCHITECTURE_EVOLVE.md) | — | 演进架构 | 架构演进路径与决策 |
| [ARCHITECTURE_OPS.md](ARCHITECTURE_OPS.md) | 1.0.0 | 运维架构 | 监控/日志/备份/部署拓扑 |

## 补充文档

| 文档 | 说明 |
|------|------|
| [PHASE4_5_PLAN.md](PHASE4_5_PLAN.md) | Phase 4-5开发规划（工作项/组织/术语） |
| [ARCHITECTURE_ANALYSIS_REPORT.md](ARCHITECTURE_ANALYSIS_REPORT.md) | 架构分析报告 |
| [DEEP_REVIEW_REPORT_20260505.md](DEEP_REVIEW_REPORT_20260505.md) | 深层设计审查报告 |
| [REVIEW_REPORT_20260505.md](REVIEW_REPORT_20260505.md) | 架构审查报告 |
| [reports/](reports/) | 历史审查报告归档 |

## 子系统专项架构 (subsystems/)

针对特定子系统的深度架构设计，均为总体架构（ARCHITECTURE.md）的延伸。

| 文档 | 定位 | 说明 |
|------|------|------|
| [AI_ASSISTANT_UNIFIED.md](subsystems/AI_ASSISTANT_UNIFIED.md) | AI 助手统一架构 | 双本体模型、知识库接入、前端组件化、服务分层设计 |
| [AI_ASSISTANT_STANDALONE.md](subsystems/AI_ASSISTANT_STANDALONE.md) | AI 助手独立组件化 | Host-Plugin 架构 + OHMO 接入 + AGUI 协议统一通信 |
| [AI_ASSISTANT_PLATFORM_ONTOLOGY.md](subsystems/AI_ASSISTANT_PLATFORM_ONTOLOGY.md) | 平台功能本体建模 | FunctionalModule/Page/Operation 等实体类型定义 |
| [AI_ASSISTANT_OPERATIONS_MANUAL_SCHEMA.md](subsystems/AI_ASSISTANT_OPERATIONS_MANUAL_SCHEMA.md) | 操作手册知识库 Schema | Markdown 格式规范、结构化 JSON Schema、入库 Pipeline |
| [ONTOLOGY_SUBSYSTEM_BOUNDARY.md](subsystems/ONTOLOGY_SUBSYSTEM_BOUNDARY.md) | 本体子系统隔离架构 | design/application 两层边界规则、契约层访问、统一查询服务 |

## 阅读路径

- **新成员**: ARCHITECTURE.md → ARCHITECTURE_FULL_CHAIN.md
- **开发者**: ARCHITECTURE_FULL_CHAIN_DEEP.md（按Phase查阅）
- **运维**: ARCHITECTURE_OPS.md
- **架构师**: ARCHITECTURE.md + ARCHITECTURE_EVOLVE.md + subsystems/*（按子系统查阅）
