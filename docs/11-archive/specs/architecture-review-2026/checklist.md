---
id: odap.l11.specs-architecture-review-2026-checklist
status: archived
owner: archivist
version: ''
layer: L11
concern: archive
lifecycle: historical
superseded_by: ''
supersedes: []
last_verified: '2026-10-17'
citations: []
governance_reason: spec-kit 规格件已交付或已废弃，正文由对应 ADR/模块设计承接
governance_evidence: docs/11-archive/README.md 归档说明；spec-kit 流程产物（spec/tasks/checklist 三件套）
---

# Checklist - 架构文档全面审查与补全

## Phase 1: 需求文档分析

- [ ] Task 1.1: req-alpha.md 已读取，关键需求已提取
- [ ] Task 1.2: req-beta.md 已读取，关键需求已提取
- [ ] Task 1.3: 两个需求文档覆盖范围已对比

## Phase 2: 文档结构一致性检查

- [ ] Task 2.1: docs/modules/ 所有 DESIGN.md 完整性已检查
- [ ] Task 2.2: ADR 文档命名和引用一致性已检查
- [ ] Task 2.3: ADR 命名/引用问题已修复

## Phase 3: 领域术语清理

- [ ] Task 3.1: "战争|战场|battlefield" 残留已搜索
- [ ] Task 3.2: 已替换为"领域|domain"
- [ ] Task 3.3: 清理已完成验证

## Phase 4: 架构完整性验证

- [ ] Task 4.1: req-alpha 功能需求与 ARCHITECTURE.md 对比完成
- [ ] Task 4.2: req-beta 功能需求与 ARCHITECTURE.md 对比完成
- [ ] Task 4.3: 缺失模块文档已补全

## Phase 5: 代码与文档一致性

- [ ] Task 5.1: RESTRUCTURE_PLAN.md 与代码目录已检查
- [ ] Task 5.2: RESTRUCTURE_PLAN.md 旧引用已更新
- [ ] Task 5.3: 代码引用与文档一致性已验证

## 最终验证

- [ ] git status 显示所有更改已提交
- [ ] 无剩余的"战争/战场"术语
- [ ] 所有模块都有对应的 DESIGN.md
- [ ] 架构文档与需求文档一致
