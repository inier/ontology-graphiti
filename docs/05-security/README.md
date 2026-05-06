# 05-安全设计 (Security)

> **所属层次**: SDD 第7层 — 安全设计
> **上游**: [02-架构设计](../02-architecture) | **关联**: [07-ADR](../07-adr)

---

## 文档清单

| 文档 | 说明 |
|------|------|
| [SECURITY.md](SECURITY.md) | ⭐ 安全策略总纲：漏洞处理流程、安全机制配置 |

## 安全架构概览

- **身份认证**: SSO/OAuth2/本地认证 → JWT Token → 详见 [modules/auth](../03-modules/auth)
- **权限校验**: ABAC (OPA Rego) → fail-close策略 → 详见 [modules/opa_policy](../03-modules/opa_policy)
- **传输安全**: TLS 1.3 + HSTS + Cookie Secure
- **审计追踪**: 100%操作审计覆盖 → 详见 [modules/audit_log](../03-modules/audit_log)

## 相关ADR

- [ADR-003: OPA策略治理引擎](../07-adr/ADR-003_opa_策略治理引擎mvp_生产化.md)
- [ADR-028: 权限检查OPA集成](../07-adr/ADR-028_permission_checker_opa_integration.md)
