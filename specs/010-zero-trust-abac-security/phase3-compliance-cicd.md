# Phase 3 — 合规与 CI/CD 详细 Spec

> **目标**：审计保留期调优 + `opa test` CI 集成 + PostToolUse 记录 output_artifact
> **优先级**：P2
> **前置条件**：Phase 1 + Phase 2 完成

---

## P3-01：审计保留期调优

### 现状

`apps/api/odap/web/app.py:103-136` 中默认保留策略：

| 级别 | 当前保留期 | 白皮书要求 | 调整 |
|------|-----------|-----------|------|
| DEBUG | 7 天 (HARD_DELETE) | — | 不变 |
| INFO | 90 天 (ARCHIVE_TO_MINIO) | 1-2 年 | → 180 天 |
| WARN | 180 天 (ARCHIVE_TO_MINIO) | — | 不变 |
| ERROR | 365 天 (KEEP_FOREVER) | 1-2 年 | 不变 |
| CRITICAL | 365 天 (KEEP_FOREVER) | 1-2 年 | 不变 |
| 通配兜底 | 365 天 (ARCHIVE_TO_MINIO) | — | 不变 |

### 修改

`apps/api/odap/web/app.py` 第 111 行：

```python
# 调整前
RetentionPolicy(
    ws_id="*", classification="INFO",
    retention_days=90, action=RetentionAction.ARCHIVE_TO_MINIO,
    created_at=now,
),
# 调整后
RetentionPolicy(
    ws_id="*", classification="INFO",
    retention_days=180, action=RetentionAction.ARCHIVE_TO_MINIO,  # 90→180 天
    created_at=now,
),
```

---

## P3-02：`opa test` CI 集成

### 新建 `.github/workflows/opa-test.yml`

```yaml
# 白皮书 §6: CI/CD 集成 — opa test 集成至 CI 流水线，实现安全左移
name: OPA Policy Tests

on:
  push:
    paths:
      - 'apps/api/odap/infra/opa/policies/**'
      - 'apps/api/odap/infra/opa/**/*.rego'
      - '.github/workflows/opa-test.yml'
  pull_request:
    paths:
      - 'apps/api/odap/infra/opa/policies/**'
      - 'apps/api/odap/infra/opa/**/*.rego'

jobs:
  opa-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install OPA
        run: |
          curl -L -o opa https://openpolicyagent.org/downloads/v0.61.0/opa_linux_amd64_static
          chmod +x opa
          sudo mv opa /usr/local/bin/

      - name: Lint Rego policies (fmt check)
        run: |
          opa fmt --diff apps/api/odap/infra/opa/policies/
          # 如果有 diff，fmt 会返回非零退出码
          opa fmt --fail apps/api/odap/infra/opa/policies/

      - name: Run OPA tests
        run: |
          # 对每个策略包运行测试
          for rego in apps/api/odap/infra/opa/policies/*.rego; do
            echo "Testing: $rego"
            opa check "$rego"
          done

          # 如果有 *_test.rego 文件，运行 opa test
          if find apps/api/odap/infra/opa/policies/ -name '*_test.rego' | grep -q .; then
            opa test apps/api/odap/infra/opa/policies/ -v
          fi

      - name: Validate main policy
        run: |
          opa check apps/api/odap/infra/opa/opa_policy.rego
          opa check apps/api/odap/infra/opa/policies/abac_policy.rego
```

### 新增 Rego 测试文件

为关键策略补充 `_test.rego` 文件。示例 `apps/api/odap/infra/opa/policies/abac_policy_test.rego`：

```rego
package domain.abac

test_allow_system_admin {
    allow with input as {
        "subject": {"roles": ["system_admin"], "clearance_level": "public", "workspace_id": "ws1"},
        "action": {"type": "view", "category": "general"},
        "resource": {"type": "doc", "classification": "top_secret", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard"},
    }
}

test_deny_insufficient_clearance {
    deny with input as {
        "subject": {"roles": ["guest"], "clearance_level": "public", "workspace_id": "ws1"},
        "action": {"type": "view", "category": "general"},
        "resource": {"type": "doc", "classification": "secret", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard"},
    }
}

test_deny_workspace_isolation {
    deny with input as {
        "subject": {"roles": ["analyst"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "view", "category": "general"},
        "resource": {"type": "doc", "classification": "public", "workspace_id": "ws2"},
        "environment": {"isolation_level": "strict"},
    }
}

test_deny_high_privilege_short_session {
    deny with input as {
        "subject": {"roles": ["director"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "refund", "category": "financial"},
        "resource": {"type": "payment", "classification": "public", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard", "session_duration_seconds": 120},
    }
}

test_allow_high_privilege_long_session {
    allow with input as {
        "subject": {"roles": ["director"], "clearance_level": "secret", "workspace_id": "ws1"},
        "action": {"type": "refund", "category": "financial"},
        "resource": {"type": "payment", "classification": "public", "workspace_id": "ws1"},
        "environment": {"isolation_level": "standard", "session_duration_seconds": 600},
    }
}
```

---

## P3-03：PostToolUse 记录 output_artifact

### 问题

白皮书 §2.3 要求审计日志包含 `input_context` 与 `output_artifact`。当前 PEP（Phase 1）已记录 `input_context`，但 `output_artifact` 缺失。

### 修复

在 `PolicyEnforcementPoint` 中增加 `record_execution` 方法的审计写入（Phase 1 已预留骨架，Phase 3 补全审计）：

```python
# pep.py — record_execution 增强
def record_execution(self, req: EnforcementRequest, output_artifact: Dict):
    """工具执行完成后记录 output_artifact（PostToolUse）"""
    # 触发 Hook
    self._fire_hook("post_tool_use", req, output_artifact=output_artifact)

    # 写审计 — 补充 output_artifact
    try:
        from odap.infra.security.unified_audit import log_audit
        from odap.infra.security.audit_sanitizer import sanitize_audit_data

        safe_output = sanitize_audit_data(output_artifact)
        log_audit(
            action=f"tool_executed:{req.tool_name}",
            resource=req.resource.get("id", req.tool_name),
            user=req.agent_id,
            service="pep",
            details={
                "trace_id": req.trace_id,
                "input_context": sanitize_audit_data(req.input_context),
                "output_artifact": safe_output,
                "opa_decision": "allow",
            },
        )
    except Exception as e:
        logger.warning(f"PostToolUse 审计写入失败: {e}")
```

### 调用方接入

在 Agent 工具执行流程中，工具执行完成后调用：

```python
# 示例：Agent 工具执行后
result = tool.execute(**input_params)
pep.record_execution(req, output_artifact={"result": result, "duration_ms": elapsed})
```

---

## Phase 3 验收标准

- [ ] INFO 级审计保留 180 天（通过 `audit_retention_policies` 表验证）
- [ ] `opa test` 在 CI 中执行，Rego 策略格式检查失败阻断合并
- [ ] `abac_policy_test.rego` 5 个测试用例全部通过
- [ ] PostToolUse 审计事件含 `output_artifact` 字段（已脱敏）
- [ ] Phase 3 测试通过
