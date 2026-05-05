# 架构文档目录

> **版本**: 1.2.0 | **日期**: 2026-05-03 | **状态**: 正式
> **用途**: 架构文档统一管理目录
> **上游文档**: DOCUMENT_BASELINE_v1.0.0.md, DOCUMENT_MANAGEMENT.md

---

## 目录结构

```
docs/architecture/
├── README.md                              # 本文件 - 架构文档索引
├── ARCHITECTURE.md                      # ⭐ 核心架构设计文档（v4.0，唯一权威）
└── reports/                            # 架构文档归档
    ├── AUDIT_REPORT.md                  # 全量文档审计报告（归档）
    ├── ARCHITECTURE_REVIEW_20260423.md  # 架构一致性审查报告（归档）
    ├── COMPLETENESS_REPORT.md           # 范围完整性确认报告（归档）
    ├── ANOMALY_REPORT.md                # 异常信息枚举报告（归档）
    └── TEST_REPORT.md                   # 重构测试报告（归档）
```

---

## 文档说明

### 1. 核心架构文档

| 文档 | 版本 | 状态 | 定位 | 说明 |
|------|------|------|------|------|
| **ARCHITECTURE.md** | 4.0.1 | 🟢 正式 | ⭐ **唯一权威架构文档** | **开发实现的权威参考**，包含 Phase 4-5 演进规划、技术实现文档、Checklist、异常确认 |

### 2. 归档文档（reports/）

| 文档 | 状态 | 说明 |
|------|------|------|
| AUDIT_REPORT.md | 📦 归档 | 全量文档审计报告 |
| ARCHITECTURE_REVIEW_20260423.md | 📦 归档 | 架构一致性审查报告 |
| COMPLETENESS_REPORT.md | 📦 归档 | 范围完整性确认报告 |
| ANOMALY_REPORT.md | 📦 归档 | 异常信息枚举报告 |
| TEST_REPORT.md | 📦 归档 | 重构测试报告 |

---

## 文档演进历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-13 | - | AUDIT_REPORT 审计 |
| 2026-04-15 | 1.0 | RESTRUCTURE_PLAN 初版 |
| 2026-04-18 | 1.0 | TEST_REPORT 重构测试 |
| 2026-04-19 | 2.0 | COMPLETENESS_REPORT 完整性确认 |
| 2026-04-23 | 1.5 | ARCHITECTURE_REVIEW 架构审查 |
| 2026-04-23 | - | ANOMALY_REPORT 异常枚举 |
| 2026-05-03 | 4.0.0 | ARCHITECTURE.md 整合完成（v3.2 + 附录E），版本升级 |
| 2026-05-03 | 4.0.1 | ARCHITECTURE.md 补充完整（新增核心分层设计、技术实现文档、Checklist、异常信息确认） |

---

## 版本说明

**ARCHITECTURE.md v4.0.1 = v3.2（现有架构）+ 附录E（完整的 Phase 4-5 演进规划）**

- 附录E 包含：
  - E.1-E.5：用户认知引擎、本体管理引擎详细设计、Phase 4-5 工作项、专家团队组织、术语映射
  - E.6：核心分层设计（7层架构职责详析）
  - E.7：技术实现文档（UI设计规范、DFX设计、测试设计）
  - E.8：Checklist 梳理（需求覆盖、架构设计）
  - E.9：异常信息确认（7项已确认）
  - E.10：文档依赖关系
- 整合来源：ARCHITECTURE_PLAN v4.0_归档.md + CHECKLIST_v2.md

---

## 使用指南

### 开发时优先阅读

**ARCHITECTURE.md** - 唯一权威架构文档

### 查阅历史报告

如需了解架构审查历史，可查看 `reports/` 目录下的归档文档。

### 架构变更流程

1. 更新 `ARCHITECTURE.md`
2. 如需新增审查报告，在 `reports/` 目录创建新文件
3. 更新本文档的演进历史

---

## 文档关系

```
requirements/req-ok.md（唯一需求来源）
    ↓
ARCHITECTURE.md ⭐（v4.0，唯一权威架构文档）← modules/*/DESIGN.md（模块设计）
    ↓
reports/*（归档的历史文档和审查报告）
```

---

## 相关文档

- [文档管理规范](../DOCUMENT_MANAGEMENT.md)
- [文档基线](../DOCUMENT_BASELINE_v1.0.0.md)
- [需求文档](../requirements/README.md)
- [ADR 索引](../adr/README.md)
- [模块设计索引](../modules/README.md)
