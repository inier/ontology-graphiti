# 架构文档全面审查与补全 - 规格文档

## Why
当前架构文档存在以下问题：
1. 文档命名与实际代码不一致（simulation_engine → mock_engine）
2. 领域特定术语（战争、战场）未完全清理
3. 多个模块缺少 DESIGN.md
4. ADR 引用不一致
5. RESTRUCTURE_PLAN.md 与实际目录结构不匹配
6. 架构文档与需求文档(req-alpha/req-beta)可能存在偏差

## What Changes

### Phase 1: 需求文档分析
- [ ] 读取 req-alpha.md 和 req-beta.md
- [ ] 提取关键功能需求和模块依赖

### Phase 2: 文档结构一致性检查
- [ ] 检查 docs/modules/ 下的 DESIGN.md 完整性
- [ ] 检查 ADR 文档命名和引用一致性
- [ ] 检查 ARCHITECTURE.md 与实际目录结构一致性

### Phase 3: 领域术语清理
- [ ] 确保所有"战争/战场"术语已替换为"领域"
- [ ] 检查代码注释和文档字符串

### Phase 4: 架构完整性验证
- [ ] 对比需求文档与架构设计
- [ ] 识别缺失的功能模块文档
- [ ] 验证模块间依赖关系

### Phase 5: 代码与文档一致性
- [ ] 检查 RESTRUCTURE_PLAN.md 与实际代码目录
- [ ] 确保 API 端点与实现一致

## Impact
- Affected specs: 所有架构相关文档
- Affected code: 可能需要同步更新的代码引用

## Requirements

### Requirement: 文档完整性
docs/modules/ 下每个模块必须有 DESIGN.md

### Requirement: 术语一致性
所有文档必须使用"领域"而非"战争/战场"

### Requirement: ADR 引用一致性
所有 ADR 文档必须有正确的命名和相互引用

### Requirement: 需求追溯性
req-alpha/req-beta 中的每个功能必须有对应的架构设计和实现
