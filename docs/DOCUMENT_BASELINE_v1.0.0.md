# 文档基线 v1.1.0

> **版本**: 1.1.0 | **日期**: 2026-05-07 | **状态**: 正式
> **用途**: 文档体系基线版本，后续变更以此为参照
> **基准日期**: 2026-05-03 | **最近更新**: 2026-05-07 (SDD重组)
> **基线范围**: 所有核心设计文档和架构决策

---

## 📊 基线概览

| 统计项 | 数量 | 说明 |
|--------|------|------|
| **文档总数** | ~130 | SDD层次化重组后 |
| **核心文档数** | 12 | ⭐ 已添加元数据的关键文档 |
| **ADR 文档数** | 54 | ADR-001 到 ADR-054 |
| **模块设计数** | 25 | 03-modules/*/DESIGN.md |
| **SDD 层次** | 12 | 00~11编号目录 |
| **特性规格数** | 8 | 11-archive/specs/ (已归档) |

---

## 📋 核心文档清单（已添加元数据）

| 文档路径 | 版本 | 状态 | 说明 |
|---------|------|------|------|
| docs/README.md | 3.0.0 | 正式 | SDD文档体系入口 |
| docs/00-requirements/req-ok.md | 2.0.0 | 正式 | 唯一需求真相来源 |
| docs/02-architecture/ARCHITECTURE.md | 4.0.1 | 正式 | 核心架构设计 |
| docs/09-checklists/CHECKLIST_v2.md | 2.0.0 | 正式 | 完整验收清单 |
| docs/DOCUMENT_RELATIONSHIP.md | 2.0.0 | 正式 | 文档关系完整索引 |
| docs/DOCUMENT_MANAGEMENT.md | 2.0.0 | 正式 | SDD防腐文档体系维护指南 |
| docs/00-requirements/README.md | 1.0.0 | 正式 | 需求文档索引 |
| docs/02-architecture/README.md | 2.0.0 | 正式 | 架构文档索引 |
| docs/07-adr/README.md | 1.0.0 | 正式 | ADR 索引 |
| docs/03-modules/README.md | 2.2.0 | 正式 | 模块设计索引 |
| **本文档** | **1.1.0** | **正式** | **文档基线记录** |

---

## 📁 文档分类统计（SDD重组后）

### 1. docs/ 目录（12层）

| 层级 | 目录 | 核心文档数 |
|------|------|:--------:|
| 原始需求 + 开发需求 | 00-requirements/ | 1 ⭐ |
| 产品设计 | 01-product-design/ | 2 |
| 架构设计 | 02-architecture/ | 14 |
| 模块设计 | 03-modules/ | 25 |
| UI设计 | 04-ui/ | 5 |
| 安全设计 | 05-security/ | 1 |
| DFX设计 | 06-dfx/ | 2 |
| ADR决策记录 | 07-adr/ | 54 |
| 任务分解 | 08-tasks/ | 1 |
| 检查清单 | 09-checklists/ | 1 |
| API规范 | 10-api/ | 2 |
| 归档 | 11-archive/ | ~30 |

---

## 🧩 模块设计清单（25个）

| 模块 | 路径 |
|------|------|
| Agent | 03-modules/agent/DESIGN.md |
| API Gateway | 03-modules/api_gateway/DESIGN.md |
| Audit Log | 03-modules/audit_log/DESIGN.md |
| Auth | 03-modules/auth/DESIGN.md |
| Decision Recommendation | 03-modules/decision_recommendation/DESIGN.md |
| Event Simulator | 03-modules/event_simulator/DESIGN.md |
| Graphiti Client | 03-modules/graphiti_client/DESIGN.md |
| Hook System | 03-modules/hook_system/DESIGN.md |
| Infra | 03-modules/infra/DESIGN.md |
| MCP Protocol | 03-modules/mcp_protocol/DESIGN.md |
| Ontology | 03-modules/ontology/DESIGN.md |
| Ontology Management Engine | 03-modules/ontology_management_engine/DESIGN.md |
| OPA Policy | 03-modules/opa_policy/DESIGN.md |
| OpenHarness Bridge | 03-modules/openharness_bridge/DESIGN.md |
| QA Engine | 03-modules/qa_engine/DESIGN.md |
| Session Memory | 03-modules/session_memory/DESIGN.md |
| Simulator | 03-modules/simulator/DESIGN.md |
| Skills | 03-modules/skills/DESIGN.md |
| Swarm Orchestrator | 03-modules/swarm_orchestrator/DESIGN.md |
| Test | 03-modules/test/DESIGN.md |
| Tool Registry | 03-modules/tool_registry/DESIGN.md |
| User Cognition Engine | 03-modules/user_cognition_engine/DESIGN.md |
| Visualization | 03-modules/visualization/DESIGN.md |
| Web Frontend | 03-modules/web_frontend/DESIGN.md |
| Workspace | 03-modules/workspace/DESIGN.md |

---

## 📌 SDD 重组说明（2026-05-07）

### 重组完成的工作

✅ 文档目录按SDD层次重新归集（00~11编号）  
✅ 删除3个冗余文件 + 2个残留空目录 + 1个空壳architecture/  
✅ modules/ → 03-modules/，adr/ → 07-adr/  
✅ 创建10个层级别README.md + 更新总索引  
✅ DOCUMENT_MANAGEMENT.md 升级为 SDD防腐文档体系维护指南（v2.0.0）  
✅ DOCUMENT_RELATIONSHIP.md 全部路径适配（v2.0.0）  
✅ ADR README 修复 DEEP引用 + 补充ADR-021条目  

### 基线状态标记

| 文档状态 | 说明 |
|---------|------|
| **已添加元数据** | 12个核心文档 |
| **路径已适配** | 所有根目录管理文档和层README |
| **已归档** | specs / legacy_code 等历史文档 |

---

## 🔄 后续工作建议

### 优先级 P0
1. 确保每次变更时同步更新下游文档（遵照防腐指南 §2.2）
2. 新增文档后更新对应层的 README.md
3. 月度检查所有相对路径是否有效

### 优先级 P1
1. 为 ADR 文档统一补充状态标记
2. 建立文档更新自动化检查脚本

---

## 📖 相关文档

- [文档管理规范](./DOCUMENT_MANAGEMENT.md) — SDD防腐文档体系维护指南
- [文档关系图](./DOCUMENT_RELATIONSHIP.md) — 完整索引
- [ADR 索引](./07-adr/README.md)
- [SDD 总入口](./README.md)
