# Phase 1 — 安全基线修复详细 Spec

> **目标**：消除审计漏点 + 统一 PEP 编排 + OpenHarness↔OPA 打通 + 日志脱敏
> **优先级**：P0（安全基线，必须先于 Phase 2 完成）

---

## P1-01 / P1-02：OPA 决策审计全路径接入 + 审计失败可观测化

### 问题

当前 `opa_service.py` 存在 4 处审计漏点：

1. **`OPAManager.check_permission`（RBAC + 缓存路径）**（`opa_service.py:719`）：缓存命中时直接返回，不写审计；mock 模式下也不写审计。
2. **`ABACService.check_permission_abac`**（`opa_service.py:1124`）：完全未调用 `audit_opa_decision`。
3. **审计写入失败静默吞异常**：`_audit_policy_decision`（`opa_service.py:177`）和 `OPAClient._audit_decision`（`opa_service.py:469`）均用 `except Exception: pass`。
4. **`OPAClient.check_permission_abac`**（`opa_service.py:531`）：未调用 `_audit_decision`。

### 修复方案

#### 4.1 `OPAManager.check_permission` 补审计

```python
# opa_service.py:719 — 修改 check_permission
def check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
    request = {"user_role": user_role, "action": action, "resource": resource}
    cache_key = self._generate_cache_key({"user_roles": [user_role], **request})

    cached = self._get_from_cache(cache_key)
    if cached is not None:
        # FIX: 缓存命中也写审计（标记 cache_hit=True）
        self._audit_decision_with_cache(user_role, action, resource, cached.get("allow", False), cache_hit=True)
        return cached.get("allow", False)

    # ... 现有 OPA/mock 调用逻辑 ...

    self._add_to_cache(cache_key, {"allow": result})
    self._record_history(user_role, action, resource, result)
    # FIX: 非缓存路径写审计
    self._audit_decision_with_cache(user_role, action, resource, result, cache_hit=False)
    return result
```

新增辅助方法：

```python
def _audit_decision_with_cache(self, subject, action, resource, allowed, cache_hit=False):
    """统一审计入口，带缓存标记"""
    try:
        from odap.infra.security.unified_audit import audit_opa_decision
        audit_opa_decision(
            subject=subject,
            action=action,
            resource=resource.get("id", str(resource)) if isinstance(resource, dict) else str(resource),
            result="allow" if allowed else "deny",
            reason=f"cache_hit={cache_hit}",
            policy_version=self.get_bundle_version(),
        )
    except Exception as e:
        # FIX: 不再 pass，计数 + 告警
        from odap.infra.opa.metrics import increment_audit_failure
        increment_audit_failure(str(e))
```

#### 4.2 `ABACService.check_permission_abac` 补审计

```python
# opa_service.py:1124 — 在每个 return 前补审计
def check_permission_abac(self, subject, action, resource, env=None):
    # ... 现有逻辑 ...
    result = self._evaluate(...)  # 重构为先计算再统一审计
    self._audit_abac_decision(subject, action, resource, result)
    return result

def _audit_abac_decision(self, subject, action, resource, result):
    try:
        from odap.infra.security.unified_audit import audit_opa_decision
        audit_opa_decision(
            subject=subject.get("user_id", "unknown"),
            action=action.get("type", str(action)),
            resource=resource.get("type", str(resource)),
            result="allow" if result.get("allow") else "deny",
            reason=result.get("reason", ""),
            policy_version=self.opa_manager.get_bundle_version(),
        )
    except Exception as e:
        from odap.infra.opa.metrics import increment_audit_failure
        increment_audit_failure(str(e))
```

#### 4.3 `OPAClient.check_permission_abac` 补审计

```python
# opa_service.py:531 — 补 _audit_decision 调用
def check_permission_abac(self, user, action, resource, environment=None):
    try:
        response = httpx.post(...)
        result = response.json().get("result", {"allow": False})
        self._audit_decision(
            user.get("id", "unknown"), action, resource,
            result.get("allow", False), result.get("reason", "")
        )
        return result
    except Exception as e:
        self._audit_decision(user.get("id", "unknown"), action, resource, False, str(e))
        raise RuntimeError(f"ABAC 权限检查失败: {e}")
```

#### 4.4 消除 `except: pass` 静默吞异常

将所有 `_audit_policy_decision` / `_audit_decision` 中的 `except Exception: pass` 替换为：

```python
except Exception as e:
    from odap.infra.opa.metrics import increment_audit_failure
    increment_audit_failure(f"{type(e).__name__}: {e}")
```

`increment_audit_failure` 在 Phase 2 的 `metrics.py` 中实现；Phase 1 先用 logging.warning 替代 pass：

```python
except Exception as e:
    logger.warning(f"审计写入失败（不阻断业务）: {e}")
```

### 涉及文件

- `apps/api/odap/infra/opa/opa_service.py`（修改 4 处）

### 测试

- `tests/unit/test_opa_audit_coverage.py`（新建）：验证 RBAC/ABAC/mock/缓存 4 条路径均产生审计事件。

---

## P1-03 / P1-04 / P1-06：统一 PEP + OpenHarness OPA 守卫

### 问题

白皮书 §3 要求运行时执行流：**意图→白名单校验(PEP)→OPA评估→决策执行→异步采集告警**。

当前 OpenHarness `PermissionChecker`（`packages/openharness/.../permissions/checker.py`）与 ODAP `OPAManager` 是两套独立权限体系，未串联。

### 修复方案

#### 新建 `PolicyEnforcementPoint`（PEP）

文件：`apps/api/odap/infra/opa/pep.py`

```python
"""
策略执行点 (Policy Enforcement Point)

白皮书 §3 运行时执行流编排：
  意图 → 白名单校验 → OPA ABAC 评估 → 决策执行 → 审计

职责：
1. 工具白名单校验（不在白名单直接 BLOCKED，不进入 OPA）
2. 调用 OPAManager 进行 ABAC 评估
3. 串联 PreToolUse / PostToolUse Hook
4. 统一写审计（含 agent_id, trace_id, input_context, output_artifact）
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class EnforcementRequest:
    """PEP 执行请求"""
    agent_id: str
    tool_name: str
    action: str
    resource: Dict[str, Any]
    subject: Dict[str, Any]          # user_id, roles, clearance_level, workspace_id
    environment: Dict[str, Any]      # time, ip, session_duration
    input_context: Dict[str, Any]    # 工具调用输入参数
    trace_id: str = ""
    session_id: str = ""


@dataclass
class EnforcementResult:
    """PEP 执行结果"""
    allowed: bool
    reason: str
    stage: str                       # "whitelist" | "opa" | "executed"
    opa_decision: Optional[Dict] = None
    output_artifact: Optional[Dict] = None
    blocked_at: Optional[str] = None # "whitelist" | "opa" | None


class PolicyEnforcementPoint:
    """统一策略执行点"""

    def __init__(self, opa_manager, hook_registry=None, allowed_tools: List[str] = None):
        self.opa = opa_manager
        self.hooks = hook_registry
        self.allowed_tools = set(allowed_tools or [])

    def evaluate(self, req: EnforcementRequest) -> EnforcementResult:
        """执行白皮书 §3 完整流程"""
        # Stage 1: 白名单校验 (PEP)
        if req.tool_name not in self.allowed_tools:
            result = EnforcementResult(
                allowed=False,
                reason=f"Tool '{req.tool_name}' not in allow-list",
                stage="whitelist",
                blocked_at="whitelist",
            )
            self._audit(req, result)
            return result

        # Stage 2: PreToolUse Hook
        self._fire_hook("pre_tool_use", req)

        # Stage 3: OPA ABAC 评估
        opa_result = self.opa.check_permission_abac(
            user=req.subject,
            action=req.action,
            resource=req.resource,
            environment=req.environment,
        )
        if not opa_result.get("allow", False):
            result = EnforcementResult(
                allowed=False,
                reason=opa_result.get("reason", "OPA denied"),
                stage="opa",
                opa_decision=opa_result,
                blocked_at="opa",
            )
            self._audit(req, result)
            self._fire_hook("post_tool_use", req, result)
            return result

        # Stage 4: 决策执行（由调用方执行工具，PEP 仅返回 ALLOW）
        result = EnforcementResult(
            allowed=True,
            reason="Permission granted",
            stage="executed",
            opa_decision=opa_result,
        )
        self._audit(req, result)
        return result

    def record_execution(self, req: EnforcementRequest, output_artifact: Dict):
        """工具执行完成后记录 output_artifact（PostToolUse）"""
        self._fire_hook("post_tool_use", req, output_artifact=output_artifact)

    def _fire_hook(self, event: str, req: EnforcementRequest, result=None, output_artifact=None):
        """触发 Hook 事件"""
        if not self.hooks:
            return
        # 接入 odap.biz.integration.hook_system
        try:
            from odap.infra.events import HookRegistry, HookPhase, HookContext
            registry = HookRegistry.get_instance()
            ctx = HookContext(event_name=event)
            payload = {
                "agent_id": req.agent_id,
                "tool_name": req.tool_name,
                "action": req.action,
                "trace_id": req.trace_id,
                "result": result.__dict__ if result else None,
                "output_artifact": output_artifact,
            }
            ctx.set_data("payload", payload)
            for hook in registry.get_hooks(event, HookPhase.POST):
                hook.handler(ctx, payload)
        except Exception as e:
            logger.warning(f"Hook {event} 执行失败: {e}")

    def _audit(self, req: EnforcementRequest, result: EnforcementResult):
        """统一审计写入（含 agent_id, trace_id, input_context）"""
        try:
            from odap.infra.security.unified_audit import audit_opa_decision
            audit_opa_decision(
                subject=req.agent_id,
                action=f"{req.tool_name}:{req.action}",
                resource=req.resource.get("id", req.resource.get("type", "unknown")),
                result="allow" if result.allowed else "deny",
                reason=result.reason,
                policy_version=self.opa.get_bundle_version(),
            )
        except Exception as e:
            logger.warning(f"PEP 审计写入失败: {e}")
```

#### OpenHarness OPA 守卫集成

文件：`apps/api/odap/biz/integration/openharness_agent/opa_guard.py`

```python
"""
OpenHarness 工具执行 OPA 守卫

白皮书 §2.1: OpenHarness Agent 内置 OPA 守卫，工具执行前调用 OPA。

将 OpenHarness 的 PermissionChecker 评估结果桥接到 ODAP OPA + PEP。
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class OpenHarnessOPAGuard:
    """OpenHarness 工具执行前的 OPA 守卫"""

    def __init__(self, pep=None):
        self.pep = pep  # PolicyEnforcementPoint

    def check_tool_execution(
        self,
        agent_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        subject: Dict[str, Any],
        environment: Dict[str, Any],
        trace_id: str = "",
    ) -> Dict[str, Any]:
        """
        工具执行前检查（替代直接调 PermissionChecker）

        流程: PEP 白名单 → OPA ABAC → 返回决策
        """
        if self.pep is None:
            logger.warning("PEP 未配置，fail-close 拒绝")
            return {"allowed": False, "reason": "PEP not configured (fail-close)"}

        from odap.infra.opa.pep import EnforcementRequest

        req = EnforcementRequest(
            agent_id=agent_id,
            tool_name=tool_name,
            action=tool_name,  # 工具名即 action
            resource={"type": "tool", "id": tool_name, "input": tool_input},
            subject=subject,
            environment=environment,
            input_context=tool_input,
            trace_id=trace_id,
        )

        result = self.pep.evaluate(req)
        return {
            "allowed": result.allowed,
            "reason": result.reason,
            "stage": result.stage,
            "blocked_at": result.blocked_at,
        }
```

#### `.env` 纳入敏感路径

文件：`packages/openharness/src/openharness/permissions/checker.py`

```python
# 在 SENSITIVE_PATH_PATTERNS 中追加：
SENSITIVE_PATH_PATTERNS: tuple[str, ...] = (
    # ... 现有模式 ...
    # 白皮书 §2.2: 禁止 Agent 读取 .env 环境变量文件
    "*/.env",
    "*/.env.*",        # .env.local, .env.production 等
    "*/.envrc",
)
```

#### PEP 路由注册

在 `apps/api/odap/infra/opa/routes.py` 或新建 `api/routes.py` 中增加：

```python
@router.post("/api/opa/pep/evaluate")
async def pep_evaluate(req: PEPRequest, user=Depends(get_current_user)):
    """PEP 统一评估入口"""
    from odap.infra.opa.pep import PolicyEnforcementPoint, EnforcementRequest
    pep = get_pep_instance()  # 全局单例
    result = pep.evaluate(EnforcementRequest(**req.dict()))
    return result.__dict__
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `apps/api/odap/infra/opa/pep.py` | 新建 |
| `apps/api/odap/biz/integration/openharness_agent/opa_guard.py` | 新建 |
| `packages/openharness/src/openharness/permissions/checker.py` | 修改（加 `.env`） |
| `apps/api/odap/infra/opa/__init__.py` | 导出 PEP |
| `apps/api/odap/web/app.py` | 注册 PEP 路由 |

### 测试

- `tests/unit/test_pep_whitelist.py`：白名单拦截不进入 OPA
- `tests/unit/test_pep_opa_eval.py`：OPA ALLOW/DENY 串联
- `tests/unit/test_opa_guard.py`：OpenHarness 守卫桥接
- `tests/unit/test_env_blocked.py`：`.env` 文件被拦截

---

## P1-05：审计日志脱敏

### 问题

白皮书 §5 要求：审计日志在写入前，必须对敏感凭证（API Key、密码）进行自动脱敏处理。

当前 `unified_audit.py` 的 `log_audit` 和 `audit_opa_decision` 直接写入 `details`/`context`，无脱敏。

### 修复方案

#### 新建 `AuditSanitizer`

文件：`apps/api/odap/infra/security/audit_sanitizer.py`

```python
"""
审计日志脱敏器

白皮书 §5: 日志脱敏 (Log Sanitization)
审计日志在写入前，对敏感凭证（API Key、密码、Token）自动脱敏。
"""

import re
import copy
from typing import Any, Dict, List, Optional

# 敏感字段名模式（大小写不敏感）
SENSITIVE_KEY_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|"
               r"auth[_-]?token|bearer|credential|private[_-]?key|client[_-]?secret)"),
]

# 敏感值模式（直接匹配值内容）
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),           # OpenAI API Key
    re.compile(r"(?i)AKIA[A-Z0-9]{16}"),              # AWS Access Key
    re.compile(r"(?i)gh[pousr]_[A-Za-z0-9]{36,}"),    # GitHub Token
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9\-\._~+/]+=*"),  # Bearer Token
]

REDACTED = "***REDACTED***"


def sanitize_value(value: Any, depth: int = 0) -> Any:
    """递归脱敏任意值"""
    if depth > 10:  # 防止无限递归
        return REDACTED
    if isinstance(value, dict):
        return {k: _sanitize_key_value(k, v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_value(v, depth + 1) for v in value]
    if isinstance(value, str):
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                return REDACTED
    return value


def _sanitize_key_value(key: str, value: Any, depth: int) -> Any:
    """键名匹配则脱敏，否则递归处理值"""
    for pattern in SENSITIVE_KEY_PATTERNS:
        if pattern.search(str(key)):
            return REDACTED
    return sanitize_value(value, depth)


def sanitize_audit_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏审计数据的顶层入口"""
    sanitized = copy.deepcopy(data)
    return sanitize_value(sanitized)
```

#### 接入 `unified_audit.py`

在 `log_audit`（`unified_audit.py:341`）和 `audit_opa_decision`（`unified_audit.py:420`）中，写入前调用 sanitizer：

```python
# unified_audit.py — log_audit 修改
def log_audit(action, resource=None, user=None, service="system",
              details=None, result_status="success", ...):
    # ... 现有逻辑 ...

    # FIX: 写入前脱敏
    from odap.infra.security.audit_sanitizer import sanitize_audit_data
    safe_details = sanitize_audit_data(details or {})
    safe_context = sanitize_audit_data(context or {})

    event = AuditEvent(
        # ...
        resource={..., "attributes": safe_details},
        context=safe_context,
        # ...
    )
```

```python
# unified_audit.py — audit_opa_decision 修改
def audit_opa_decision(subject, action, resource, result, reason="", ...):
    # FIX: 脱敏 reason 和 context 中可能包含的敏感信息
    from odap.infra.security.audit_sanitizer import sanitize_audit_data
    safe_context = sanitize_audit_data({
        "subject": subject, "action": action, "resource": resource,
        "result": result, "reason": reason, ...
    })
    # ... 使用 safe_context 构造 AuditEvent ...
```

### 涉及文件

| 文件 | 操作 |
|------|------|
| `apps/api/odap/infra/security/audit_sanitizer.py` | 新建 |
| `apps/api/odap/infra/security/unified_audit.py` | 修改（接入 sanitizer） |

### 测试

- `tests/unit/test_audit_sanitizer.py`：
  - `{"api_key": "sk-abc123..."}` → `{"api_key": "***REDACTED***"}`
  - `{"password": "secret123"}` → `{"password": "***REDACTED***"}`
  - 嵌套字典递归脱敏
  - 非敏感字段保持不变
  - `log_audit` 写入后 SQLite 中 details 已脱敏

---

## Phase 1 依赖关系

```
P1-05 (脱敏)  ──────────────┐
                             ▼
P1-01/02 (审计补全) ──▶ unified_audit.py 已接入 sanitizer
                             │
P1-03 (PEP) ─────────────────┤
                             ▼
P1-04/06 (OpenHarness 守卫) ──▶ 依赖 PEP
```

建议实施顺序：P1-05 → P1-01/02 → P1-03 → P1-04/06
