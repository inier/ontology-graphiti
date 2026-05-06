# ADR-009: Markdown 编写 OPA 策略

> **来源**: `docs/ARCHITECTURE.md` 第 17 章

**状态**: 已接受 | **日期**: 2026-04-16

---

## 1. 上下文

需要用 Markdown 编写 OPA 策略，降低编写门槛。

---

## 2. 决策

构建**Markdown → Rego 转换工具**。

### 2.1 转换流程

```
Markdown 文档 → Parser → Rego 策略 → OPA 加载
```

### 2.2 Markdown 格式

```markdown
# 角色: commander

## 允许的操作
- 查询
- 攻击（需确认）

## 规则
如果 角色是 commander 且 操作是 attack
那么 允许
```

---

## 3. 后果

| 正面 | 负面 |
|------|------|
| ✅ 编写门槛低 | ❌ 转换层增加复杂性 |
| ✅ 易于 review | ❌ 高级特性受限 |
| ✅ 版本化管理 | |

---

## 4. 可逆性

**高**。可直接编写 Rego。

---

## 5. 相关文档

- [ADR-003: OPA 策略治理引擎](ADR-003_opa_策略治理引擎mvp_生产化.md)
