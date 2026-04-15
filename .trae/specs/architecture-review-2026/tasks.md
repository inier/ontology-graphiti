# Tasks - 架构文档全面审查与补全

## Phase 1: 需求文档分析

- [ ] Task 1.1: 读取 req-alpha.md 并提取关键需求
- [ ] Task 1.2: 读取 req-beta.md 并提取关键需求
- [ ] Task 1.3: 对比两个需求文档的覆盖范围

## Phase 2: 文档结构一致性检查

- [ ] Task 2.1: 检查 docs/modules/ 所有 DESIGN.md 完整性
- [ ] Task 2.2: 检查 ADR 文档命名和引用一致性
- [ ] Task 2.3: 修复发现的 ADR 命名/引用问题

## Phase 3: 领域术语清理

- [ ] Task 3.1: 全局搜索"战争|战场|battlefield"残留
- [ ] Task 3.2: 替换为"领域|domain"
- [ ] Task 3.3: 验证清理完成

## Phase 4: 架构完整性验证

- [ ] Task 4.1: 对比 req-alpha 功能需求与 ARCHITECTURE.md
- [ ] Task 4.2: 对比 req-beta 功能需求与 ARCHITECTURE.md
- [ ] Task 4.3: 识别并补全缺失的模块文档

## Phase 5: 代码与文档一致性

- [ ] Task 5.1: 检查 RESTRUCTURE_PLAN.md 与实际代码目录
- [ ] Task 5.2: 更新 RESTRUCTURE_PLAN.md 中的旧引用
- [ ] Task 5.3: 验证所有代码引用与文档一致

## Task Dependencies

- Phase 2 依赖 Phase 1 (需要需求上下文)
- Phase 3 可独立执行
- Phase 4 依赖 Phase 1 和 Phase 2
- Phase 5 依赖 Phase 2 和 Phase 4
