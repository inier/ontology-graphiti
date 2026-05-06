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

## 阅读路径

- **新成员**: ARCHITECTURE.md → ARCHITECTURE_FULL_CHAIN.md
- **开发者**: ARCHITECTURE_FULL_CHAIN_DEEP.md（按Phase查阅）
- **运维**: ARCHITECTURE_OPS.md
- **架构师**: ARCHITECTURE.md + ARCHITECTURE_EVOLVE.md
