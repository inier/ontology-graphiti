# 06-DFX设计 (Design for X)

> **所属层次**: SDD 第8层 — DFX设计
> **上游**: [02-架构设计](../02-architecture) | **关联**: [09-Checklists](../09-checklists)

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [DFX_DESIGN.md](DFX_DESIGN.md) | ⭐ DFX总纲：性能/安全/可靠性/可维护性/可用性/兼容性设计决策 |
| [TEST_DESIGN.md](TEST_DESIGN.md) | 测试策略：pytest+vitest+Playwright三层体系 |

## DFX维度

| 维度 | 目标 | 关键文档 |
|------|------|---------|
| **性能** | P95延迟 < 3s | [ARCHITECTURE_FULL_CHAIN_DEEP.md §5.12](../02-architecture/ARCHITECTURE_FULL_CHAIN_DEEP.md) |
| **安全** | RBAC+ABAC全覆盖 | [05-安全设计](../05-security) |
| **可靠性** | 可用性 99.9% | [ARCHITECTURE_OPS.md](../02-architecture/ARCHITECTURE_OPS.md) |
| **可维护性** | 测试覆盖率 > 80% | 本目录 TEST_DESIGN.md |
| **可用性** | Net Promoter Score > 60 | [04-UI设计](../04-ui) |
| **兼容性** | MCP协议集成 | [ADR-026](../07-adr/ADR-026_mcp_protocol_integration.md) |
