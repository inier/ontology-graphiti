"""
OPA 权限管理模块
支持 ABAC 策略、策略热更新 Bundle、策略沙箱

功能：
- ABAC 策略模型（基于属性、角色、环境条件）
- 策略热更新 Bundle 机制
- 策略沙箱（What-If 权限模拟）
- 批量权限检查 + 缓存
"""

import sys
import os
import json
import time
import hashlib
import threading
import logging
from typing import Optional, Dict, Any, List, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

from odap.biz.platform.roles.api.schemas import PermissionScope

import httpx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============ SECURITY: OPA fail-close policy ============
# When OPA is unavailable, the default behavior is to DENY all permission
# requests (fail-close). This is required by:
#   - Architecture Constitution: P0-7 (OPA unavailable MUST fail-close)
#   - Security: fail-open is a P0 vulnerability (compromised OPA = full access)
#
# The `mock` mode is ONLY allowed when:
#   - ENV is non-production (dev/test/staging)
#   - OPA_MOCK_MODE=true is explicitly set
#
# Production deployments must reject mock mode at startup.

class OPAUnavailableError(RuntimeError):
    """Raised when the OPA server is unreachable or unhealthy.

    The default behavior is fail-close (deny). Callers should NOT catch this
    unless they have a deliberate fail-open reason (e.g., dev environment).
    """
    pass


def _is_production_env() -> bool:
    """Check whether the current process is running in production."""
    env = os.environ.get("ENV", os.environ.get("ENVIRONMENT", "")).lower()
    return env in ("production", "prod", "live")


def _resolve_opa_fail_mode() -> str:
    """
    Resolve the OPA fail mode at startup.

    Returns one of: "deny" (fail-close, default), "mock" (dev only).

    Rules:
      1. If OPA_FAIL_MODE is set explicitly, use it (and validate).
      2. In production, force "deny" — never allow "mock".
      3. In non-production, default to "deny" (secure-by-default).
    """
    explicit = os.environ.get("OPA_FAIL_MODE", "").lower()
    if explicit in ("deny", "mock"):
        if explicit == "mock" and _is_production_env():
            raise RuntimeError(
                "SECURITY: OPA_FAIL_MODE=mock is FORBIDDEN in production. "
                "Production must use fail-close (deny). Set ENV != production "
                "or remove OPA_FAIL_MODE."
            )
        return explicit
    return "deny"  # secure default


class AccessControlModel(str, Enum):
    RBAC = "rbac"
    ABAC = "abac"
    PBAC = "pbac"
    CBAC = "cbac"


class DecisionResult(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"
    NOT_APPLICABLE = "not_applicable"


class DecisionReason(str, Enum):
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    INSUFFICIENT_ROLE = "insufficient_role"
    RESOURCE_RESTRICTED = "resource_restricted"
    TIME_RESTRICTION = "time_restriction"
    IP_RESTRICTION = "ip_restriction"
    POLICY_NOT_FOUND = "policy_not_found"


@dataclass
class PermissionRequest:
    """权限请求"""
    user_id: str
    user_roles: List[str]
    user_attributes: Dict[str, Any]
    action: str
    resource_type: str
    resource_id: str
    resource_attributes: Dict[str, Any]
    environment: Dict[str, Any]
    request_id: str
    timestamp: float


@dataclass
class PermissionDecision:
    """权限决策"""
    request: PermissionRequest
    result: DecisionResult
    reason: DecisionReason
    constraints: Dict[str, Any]
    decision_time: float
    decision_id: str
    policy_version: str


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    expires_at: Optional[float] = None


@dataclass
class PolicyBundle:
    """策略 Bundle"""
    version: str
    revision: str
    policies: Dict[str, str]
    metadata: Dict[str, Any]
    created_at: str
    checksum: str


@dataclass
class PolicySandboxResult:
    """策略沙箱执行结果"""
    success: bool
    allow: bool
    reason: str
    evaluated_policies: List[str]
    execution_time_ms: float
    errors: List[str] = field(default_factory=list)


class ABACPolicyEvaluator:
    """ABAC 策略评估器"""

    def __init__(self):
        self.policy_rules = self._init_policy_rules()

    def _init_policy_rules(self) -> Dict[str, Any]:
        """初始化 ABAC 策略规则"""
        return {
            "system_admin": {
                "permissions": ["*"],
                "restrictions": []
            },
            "commander": {
                "permissions": ["view_intelligence", "command_units", "authorize_attacks", "approve_missions"],
                "restrictions": ["cannot_attack_civilian_infrastructure"],
                "attributes": {
                    "clearance_level": "secret",
                    "max_attack_authority": "strategic"
                }
            },
            "pilot": {
                "permissions": ["view_intelligence", "request_support", "operate_weapons"],
                "restrictions": ["cannot_attack_civilian_infrastructure", "cannot_command"],
                "attributes": {
                    "clearance_level": "confidential",
                    "max_attack_authority": "tactical"
                }
            },
            "intelligence_analyst": {
                "permissions": ["view_intelligence", "analyze_data", "generate_reports"],
                "restrictions": ["cannot_command", "cannot_attack", "cannot_approve_missions"],
                "attributes": {
                    "clearance_level": "secret"
                }
            },
            "operator": {
                "permissions": ["view_situational_awareness", "operate_systems"],
                "restrictions": ["cannot_attack", "cannot_command", "cannot_approve_missions"],
                "attributes": {
                    "clearance_level": "confidential"
                }
            }
        }

    def evaluate(self, user: Dict, action: str, resource: Dict,
                 environment: Dict = None) -> Dict[str, Any]:
        user_roles = user.get("roles", [])
        user_attrs = user.get("attributes", {})
        resource_type = resource.get("type", "")
        resource_attrs = resource.get("attributes", {})

        if "system_admin" in user_roles:
            return {"allow": True, "reason": "System admin has all permissions", "evaluated_policies": ["system_admin"]}

        if not user_roles:
            return {"allow": False, "reason": "No role assigned", "evaluated_policies": []}

        evaluated = []
        for role in user_roles:
            if role not in self.policy_rules:
                continue

            policy = self.policy_rules[role]
            evaluated.append(role)

            if "*" in policy["permissions"] or action in policy["permissions"]:
                for restriction in policy.get("restrictions", []):
                    if restriction == "cannot_attack_civilian_infrastructure":
                        if resource_type == "CivilianInfrastructure" and action == "attack":
                            return {"allow": False, "reason": f"Restriction: {restriction}", "evaluated_policies": evaluated}
                    elif restriction == f"cannot_{action}":
                        return {"allow": False, "reason": f"Restriction: {restriction}", "evaluated_policies": evaluated}

        clearance_match = self._check_clearance(user_attrs, resource_attrs)
        if not clearance_match:
            return {"allow": False, "reason": "Insufficient clearance level", "evaluated_policies": evaluated}

        if environment:
            env_result = self._check_environment_constraints(environment, user_attrs)
            if not env_result["allowed"]:
                return env_result

        return {"allow": True, "reason": "Permission granted", "evaluated_policies": evaluated}

    def _check_clearance(self, user_attrs: Dict, resource_attrs: Dict) -> bool:
        user_level = user_attrs.get("clearance_level", "public")
        required_level = resource_attrs.get("required_clearance", "public")

        level_order = ["public", "confidential", "secret", "top_secret"]
        try:
            return level_order.index(user_level) >= level_order.index(required_level)
        except ValueError:
            return True

    def _check_environment_constraints(self, environment: Dict,
                                      user_attrs: Dict) -> Dict[str, Any]:
        time_of_day = environment.get("time_of_day")
        if time_of_day:
            if user_attrs.get("restricted_hours"):
                restricted = user_attrs["restricted_hours"]
                if restricted.get("start") and restricted.get("end"):
                    if time_of_day < restricted["start"] or time_of_day > restricted["end"]:
                        return {"allow": False, "reason": "Outside allowed working hours"}

        ip_restriction = environment.get("ip_restriction")
        if ip_restriction and user_attrs.get("allowed_ips"):
            if ip_restriction not in user_attrs["allowed_ips"]:
                return {"allow": False, "reason": "IP address not allowed"}

        return {"allow": True, "reason": "Environment constraints satisfied"}


class PolicyBundleManager:
    """策略 Bundle 管理器"""

    def __init__(self, bundle_dir: str = None):
        self.bundle_dir = bundle_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "bundles"
        )
        os.makedirs(self.bundle_dir, exist_ok=True)
        self.current_bundle: Optional[PolicyBundle] = None
        self.bundle_history: List[PolicyBundle] = []
        self._load_current_bundle()

    def _load_current_bundle(self):
        current_path = os.path.join(self.bundle_dir, "current_bundle.json")
        if os.path.exists(current_path):
            try:
                with open(current_path, "r") as f:
                    data = json.load(f)
                    self.current_bundle = PolicyBundle(**data)
            except Exception as e:
                logger.info(f'加载 Bundle 失败: {e}')

    def _save_bundle(self, bundle: PolicyBundle):
        bundle_path = os.path.join(self.bundle_dir, f"bundle_{bundle.version}.json")
        with open(bundle_path, "w") as f:
            json.dump({
                "version": bundle.version,
                "revision": bundle.revision,
                "policies": bundle.policies,
                "metadata": bundle.metadata,
                "created_at": bundle.created_at,
                "checksum": bundle.checksum
            }, f, indent=2, default=str)

        current_path = os.path.join(self.bundle_dir, "current_bundle.json")
        with open(current_path, "w") as f:
            json.dump({
                "version": bundle.version,
                "revision": bundle.revision,
                "policies": bundle.policies,
                "metadata": bundle.metadata,
                "created_at": bundle.created_at,
                "checksum": bundle.checksum
            }, f, indent=2, default=str)

    def create_bundle(self, policies: Dict[str, str], metadata: Dict[str, Any] = None) -> PolicyBundle:
        import uuid
        version = f"1.0.{int(time.time())}"
        revision = str(uuid.uuid4())[:8]

        policy_data = json.dumps(policies, sort_keys=True)
        checksum = hashlib.sha256(policy_data.encode()).hexdigest()

        bundle = PolicyBundle(
            version=version,
            revision=revision,
            policies=policies,
            metadata=metadata or {},
            created_at=datetime.now().isoformat(),
            checksum=checksum
        )

        self._save_bundle(bundle)
        self.bundle_history.append(bundle)
        self.current_bundle = bundle

        return bundle

    def hot_update_bundle(self, policies: Dict[str, str]) -> PolicyBundle:
        return self.create_bundle(policies, {"update_type": "hot_update"})

    def rollback_bundle(self) -> Optional[PolicyBundle]:
        if len(self.bundle_history) < 2:
            return None

        self.bundle_history.pop()
        previous = self.bundle_history[-1]
        self._save_bundle(previous)
        self.current_bundle = previous

        return previous

    def get_bundle(self) -> Optional[PolicyBundle]:
        return self.current_bundle

    def get_bundle_history(self) -> List[PolicyBundle]:
        return list(self.bundle_history)


class PolicySandbox:
    """策略沙箱"""

    def __init__(self):
        self.evaluator = ABACPolicyEvaluator()

    def simulate(self, policy_content: str, user: Dict, action: str,
                 resource: Dict, environment: Dict = None) -> PolicySandboxResult:
        start_time = time.time()
        errors = []

        try:
            allow = self.evaluator.evaluate(user, action, resource, environment)
            execution_time = (time.time() - start_time) * 1000

            return PolicySandboxResult(
                success=True,
                allow=allow.get("allow", False),
                reason=allow.get("reason", ""),
                evaluated_policies=allow.get("evaluated_policies", []),
                execution_time_ms=execution_time
            )
        except Exception as e:
            logger.warning("silent except caught in {exc} (line 391)", exc_info=True)
            execution_time = (time.time() - start_time) * 1000
            errors.append(str(e))
            return PolicySandboxResult(
                success=False,
                allow=False,
                reason="Sandbox execution failed",
                evaluated_policies=[],
                execution_time_ms=execution_time,
                errors=errors
            )

    def what_if(self, user: Dict, actions: List[str],
                resources: List[Dict]) -> Dict[str, Any]:
        results = {}
        for action in actions:
            action_results = []
            for resource in resources:
                result = self.evaluator.evaluate(user, action, resource)
                action_results.append({
                    "action": action,
                    "resource": resource.get("id", "unknown"),
                    "resource_type": resource.get("type", "unknown"),
                    "allow": result.get("allow"),
                    "reason": result.get("reason")
                })
            results[action] = action_results

        return {
            "user_id": user.get("id", "unknown"),
            "total_actions_tested": len(actions) * len(resources),
            "results": results
        }


class OPAClient:
    """
    OPA REST API 客户端
    """

    def __init__(self, opa_url: str = None, timeout: float = 5.0):
        self.opa_url = (opa_url or os.getenv("OPA_URL", "http://localhost:8181")).rstrip("/")
        self.timeout = timeout

    def check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/allow",
                json={"input": {"user_role": user_role, "action": action, "resource": resource}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("result", False)
        except Exception as e:
            raise RuntimeError(f"OPA 调用失败: {e}")

    def check_permission_abac(self, user: Dict, action: str,
                             resource: Dict, environment: Dict = None) -> Dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/abac_allow",
                json={"input": {"user": user, "action": action, "resource": resource,
                              "environment": environment or {}}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("result", {"allow": False})
        except Exception as e:
            raise RuntimeError(f"ABAC 权限检查失败: {e}")

    def check_permissions_batch(self, requests: List[Dict]) -> List[Dict]:
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/batch_allow",
                json={"input": {"requests": requests}},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("result", [])
        except Exception as e:
            raise RuntimeError(f"批量权限检查失败: {e}")

    def put_policy(self, policy_path: str, rego_content: str) -> bool:
        try:
            response = httpx.put(
                f"{self.opa_url}/v1/policies/{policy_path}",
                content=rego_content,
                headers={"Content-Type": "text/plain"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            raise RuntimeError(f"策略上传失败: {e}")

    def delete_policy(self, policy_path: str) -> bool:
        try:
            response = httpx.delete(
                f"{self.opa_url}/v1/policies/{policy_path}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            raise RuntimeError(f"删除策略失败: {e}")

    def health_check(self) -> bool:
        try:
            response = httpx.get(f"{self.opa_url}/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            logger.warning("silent except caught in {exc} (line 501)", exc_info=True)
            return False


OPAManagerV2 = None


class OPAManager:
    """
    OPA 权限管理器

    功能：
    - ABAC 策略评估
    - 策略热更新 Bundle
    - 策略沙箱
    - 批量权限检查 + 缓存
    """

    def __init__(self, opa_url: str = None, use_mock: bool = None):
        self.opa_client = OPAClient(opa_url=opa_url)

        self.abac_evaluator = ABACPolicyEvaluator()
        self.bundle_manager = PolicyBundleManager()
        self.policy_sandbox = PolicySandbox()

        self.policy_cache: Dict[str, CacheEntry] = {}
        self.cache_max_size = 1000
        self.cache_ttl = 300
        self.cache_hits = 0
        self.cache_misses = 0

        self.policy_history: List[Dict] = []
        self.policy_versions = {"current": "1.0.0", "previous": "0.9.0", "history": []}

        # SECURITY: Resolve the fail mode at startup. Default is "deny" (fail-close).
        # P0-7: OPA unavailable MUST fail-close.
        self._fail_mode = _resolve_opa_fail_mode()

        # Legacy OPA_MOCK_MODE env var still respected (transitional).
        # In production, OPA_FAIL_MODE=mock is rejected at startup by
        # _resolve_opa_fail_mode(), so this is safe.
        env_mock = os.environ.get("OPA_MOCK_MODE", "").lower()
        legacy_use_mock = False
        if env_mock in ("true", "1", "yes"):
            if self._fail_mode == "deny" and _is_production_env():
                # Defense-in-depth: even if OPA_FAIL_MODE is unset, the legacy
                # var cannot enable mock in production.
                raise RuntimeError(
                    "SECURITY: OPA_MOCK_MODE=true is FORBIDDEN in production. "
                    "Unset OPA_MOCK_MODE or set ENV != production."
                )
            legacy_use_mock = True

        # When use_mock is explicitly passed (e.g. in tests), honor it; but if
        # the fail mode is "deny", require explicit opt-in to mock.
        self.use_mock = False
        if use_mock is True:
            self.use_mock = True
            if self._fail_mode == "deny" and not legacy_use_mock:
                logger.warning(
                    "OPA Mock mode enabled at construction. "
                    "This is INTENDED for tests/dev only."
                )
        elif use_mock is None and legacy_use_mock:
            self.use_mock = True

        if self.use_mock:
            logger.warning("OPA Mock mode enabled - permission checks use static rules")
        else:
            # P0-7 fix: do NOT silently fall back to mock on health-check failure.
            # Instead, mark the manager as OPA-unavailable. Permission checks
            # will then fail-close (return deny) based on _fail_mode.
            if not self.opa_client.health_check():
                self._opa_unavailable = True
                logger.error(
                    "OPA server unavailable at startup. "
                    "All permission checks will fail-close (deny) "
                    "until OPA is reachable again. "
                    "Set OPA_FAIL_MODE=mock only in non-production if needed."
                )
            else:
                self._opa_unavailable = False
                logger.info(f"OPA Server connected: {self.opa_client.opa_url}")
                self._auto_load_policy()

    def _auto_load_policy(self):
        rego_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opa_policy.rego")
        if os.path.exists(rego_path) and not self.use_mock:
            try:
                with open(rego_path, "r") as f:
                    rego_content = f.read()
                self.opa_client.put_policy("domain", rego_content)
                logger.info('OPA 策略已加载: domain')
            except Exception as e:
                logger.info(f'OPA 策略加载失败: {e}')

    def _generate_cache_key(self, request: Dict) -> str:
        key_data = {
            "user_id": request.get("user_id"),
            "user_roles": tuple(sorted(request.get("user_roles", []))),
            "action": request.get("action"),
            "resource_id": request.get("resource", {}).get("id", "unknown"),
            "resource_type": request.get("resource", {}).get("type", "unknown")
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        if key in self.policy_cache:
            entry = self.policy_cache[key]
            if time.time() < entry.expires_at:
                entry.last_accessed = time.time()
                entry.access_count += 1
                self.cache_hits += 1
                return entry.value
            else:
                del self.policy_cache[key]
        self.cache_misses += 1
        return None

    def _add_to_cache(self, key: str, value: Dict):
        if len(self.policy_cache) >= self.cache_max_size:
            oldest_key = min(self.policy_cache, key=lambda k: self.policy_cache[k].created_at)
            del self.policy_cache[oldest_key]

        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            last_accessed=time.time(),
            expires_at=time.time() + self.cache_ttl
        )
        self.policy_cache[key] = entry

    def check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        request = {"user_role": user_role, "action": action, "resource": resource}
        cache_key = self._generate_cache_key({"user_roles": [user_role], **request})

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached.get("allow", False)

        if self.use_mock:
            logger.debug("Using mock OPA for permission check")
            result = self._mock_check_permission(user_role, action, resource)
        else:
            try:
                result = self.opa_client.check_permission(user_role, action, resource)
            except Exception as e:
                # P0-7 fix: FAIL-CLOSE on OPA errors. Default is deny.
                # Only fall back to mock if the operator explicitly opted in
                # via OPA_FAIL_MODE=mock in a non-production environment.
                if self._fail_mode == "mock":
                    logger.warning(
                        f"OPA 异常: {e}，fallback 到 Mock (fail_mode=mock, dev/test only)"
                    )
                    result = self._mock_check_permission(user_role, action, resource)
                else:
                    logger.error(
                        f"OPA 不可用: {e}. 拒绝 {user_role} 对 {resource} 的 {action} 权限 (fail-close)."
                    )
                    result = False  # FAIL-CLOSE

        self._add_to_cache(cache_key, {"allow": result})
        self._record_history(user_role, action, resource, result)
        return result

    def check_permission_abac(self, user: Dict, action: str, resource: Dict,
                             environment: Dict = None) -> Dict[str, Any]:
        request = {"user": user, "action": action, "resource": resource}
        cache_key = self._generate_cache_key({
            "user_id": user.get("id"),
            "user_roles": user.get("roles", []),
            **request
        })

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        if self.use_mock:
            result = self.abac_evaluator.evaluate(user, action, resource, environment)
        else:
            try:
                result = self.opa_client.check_permission_abac(user, action, resource, environment)
            except Exception as e:
                # P0-7 fix: FAIL-CLOSE on OPA errors.
                if self._fail_mode == "mock":
                    logger.warning(
                        f"OPA ABAC 异常: {e}，fallback 到本地评估 (fail_mode=mock, dev/test only)"
                    )
                    result = self.abac_evaluator.evaluate(user, action, resource, environment)
                else:
                    logger.error(
                        f"OPA ABAC 不可用: {e}. 拒绝用户 {user.get('id')} 对 {resource} 的 {action} 权限 (fail-close)."
                    )
                    result = {
                        "allow": False,
                        "reason": "OPA unavailable, fail-close",
                        "error": str(e),
                    }

        self._add_to_cache(cache_key, result)
        self._record_history(user.get("id", "unknown"), action, resource, result.get("allow"))
        return result

    def check_permissions_batch(self, requests: List[Dict]) -> List[Dict]:
        results = []
        for req in requests:
            if "user_role" in req:
                result = self.check_permission(
                    req["user_role"], req["action"], req["resource"]
                )
                results.append({"request": req, "result": result})
            elif "user" in req:
                result = self.check_permission_abac(
                    req["user"], req["action"], req["resource"], req.get("environment")
                )
                results.append({"request": req, "result": result})
        return results

    def _mock_check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        logger.warning(f"OPA mock mode: checking permission for role={user_role}, action={action}, resource={resource}")
        roles = {
            "pilot": {"permissions": ["view_intelligence", "request_support"], "restrictions": ["cannot_attack", "cannot_command"]},
            "commander": {"permissions": ["view_intelligence", "command_units", "authorize_attacks"], "restrictions": ["cannot_attack_civilian_infrastructure"]},
            "intelligence_analyst": {"permissions": ["view_intelligence", "analyze_data", "generate_reports"], "restrictions": ["cannot_command", "cannot_attack"]},
        }

        if user_role not in roles:
            return False

        policy = roles[user_role]
        if action not in policy["permissions"]:
            return False

        for restriction in policy.get("restrictions", []):
            if restriction == "cannot_attack" and action == "attack":
                return False
            if restriction == "cannot_attack_civilian_infrastructure" and action == "attack" and resource.get("type") == "CivilianInfrastructure":
                return False

        return True

    def _record_history(self, user_id: str, action: str, resource: Dict, result: bool):
        self.policy_history.append({
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "resource_id": resource.get("id", "unknown"),
            "result": "allowed" if result else "denied"
        })

    def simulate_policy(self, user_role: str, action: str, resource: Dict) -> Dict:
        allowed = self.check_permission(user_role, action, resource)
        return {
            "action": action,
            "resource": resource.get("id", "unknown"),
            "user_role": user_role,
            "result": "allowed" if allowed else "denied",
            "timestamp": datetime.now().isoformat()
        }

    def what_if_analysis(self, user: Dict, actions: List[str],
                        resources: List[Dict]) -> Dict[str, Any]:
        return self.policy_sandbox.what_if(user, actions, resources)

    def policy_sandbox_simulate(self, policy_content: str, user: Dict, action: str,
                               resource: Dict, environment: Dict = None) -> PolicySandboxResult:
        return self.policy_sandbox.simulate(policy_content, user, action, resource, environment)

    def hot_update_bundle(self, policies: Dict[str, str]) -> PolicyBundle:
        bundle = self.bundle_manager.hot_update_bundle(policies)
        self.policy_versions["previous"] = self.policy_versions["current"]
        self.policy_versions["current"] = bundle.version
        return bundle

    def rollback_bundle(self) -> Optional[PolicyBundle]:
        bundle = self.bundle_manager.rollback_bundle()
        if bundle:
            self.policy_versions["previous"] = self.policy_versions["current"]
            self.policy_versions["current"] = bundle.version
        return bundle

    def get_bundle_version(self) -> str:
        return self.policy_versions["current"]

    def get_policy_history(self) -> List[Dict]:
        return list(self.policy_history)

    def get_cache_stats(self) -> Dict[str, Any]:
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "total": total,
            "hit_rate_percent": hit_rate,
            "cache_size": len(self.policy_cache)
        }

    def clear_cache(self):
        self.policy_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0

    def load_policy(self, policy_id: str = None, rego_content: str = None) -> bool:
        try:
            if self.use_mock:
                return True
            if policy_id and rego_content:
                result = self.opa_client.put_policy(policy_id, rego_content)
                self.clear_cache()
                return result
            self._auto_load_policy()
            return True
        except Exception:
            logger.warning("silent except caught in {exc} (line 816)", exc_info=True)
            return False

    def delete_policy(self, policy_id: str) -> bool:
        try:
            if self.use_mock:
                return True
            result = self.opa_client.delete_policy(policy_id)
            self.clear_cache()
            return result
        except Exception:
            logger.warning("silent except caught in {exc} (line 826)", exc_info=True)
            return False

    def get_performance_metrics(self) -> Dict[str, Any]:
        return {
            "cache": self.get_cache_stats(),
            "policy_versions": self.policy_versions,
            "bundle_version": self.bundle_manager.get_bundle().version if self.bundle_manager.get_bundle() else None,
            "mode": "mock" if self.use_mock else "opa",
            "history_count": len(self.policy_history)
        }


OPAManagerV2 = OPAManager


class MarkdownPolicyService:

    def __init__(self, opa_manager: OPAManager = None):
        self.opa_manager = opa_manager or OPAManager()
        self._compiler = None
        self._version_storage = None

    @property
    def compiler(self):
        if self._compiler is None:
            from odap.infra.opa.markdown_compiler import MarkdownCompiler
            self._compiler = MarkdownCompiler()
        return self._compiler

    @property
    def version_storage(self):
        if self._version_storage is None:
            from odap.infra.opa.policy_version_storage import SQLitePolicyVersionStorage
            self._version_storage = SQLitePolicyVersionStorage()
        return self._version_storage

    def compile_markdown_policy(self, markdown_text: str) -> Dict[str, Any]:
        result = self.compiler.compile(markdown_text)
        if not result.success:
            return {
                "status": "error",
                "message": "编译失败",
                "errors": result.errors,
            }
        return {
            "status": "success",
            "rego_text": result.rego_text,
            "rules": result.rules,
        }

    def _notify_policy_load_failed(self, policy_id: str, errors: list):
        """策略编译/加载失败时通知管理员：发布 hook 事件 + 写入审计日志"""
        error_detail = "; ".join(str(e) for e in errors) if errors else "Unknown compilation error"

        # 1. 通过 Hook 系统发布 policy.load_failed 事件
        try:
            from odap.infra.events import HookRegistry, HookPhase, HookContext
            hook_registry = HookRegistry.get_instance()
            context = HookContext(event_name="policy.load_failed")
            payload = {
                "policy_id": policy_id,
                "errors": errors,
                "error_detail": error_detail,
                "timestamp": datetime.now().isoformat(),
            }
            context.set_data("payload", payload)
            hooks = hook_registry.get_hooks("policy.load_failed", HookPhase.POST)
            for hook in hooks:
                try:
                    hook.handler(context, payload)
                except Exception as e:
                    logger.warning(f"Policy load failed hook {hook.name} 执行失败: {e}")
        except Exception as e:
            logger.warning(f"发布 policy.load_failed hook 事件失败: {e}")

        # 2. 通过 WebSocket event bus 推送给连接的管理员客户端
        try:
            import asyncio
            from odap.web.ws.event_bus import get_event_bus
            bus = get_event_bus()
            event_data = {
                "policy_id": policy_id,
                "errors": errors,
                "error_detail": error_detail,
                "timestamp": datetime.now().isoformat(),
            }
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(bus.emit("policy:load_failed", event_data))
                else:
                    loop.run_until_complete(bus.emit("policy:load_failed", event_data))
            except RuntimeError:
                asyncio.run(bus.emit("policy:load_failed", event_data))
        except Exception as e:
            logger.warning(f"WebSocket 通知策略加载失败事件失败: {e}")

        # 3. 写入审计日志（WARNING 级别）
        try:
            from odap.infra.security.unified_audit import log_audit
            log_audit(
                action="policy.load_failed",
                resource=policy_id,
                user="system",
                service="opa",
                details={"errors": errors, "error_detail": error_detail},
            )
        except Exception as e:
            logger.warning(f"审计日志记录策略加载失败事件失败: {e}")

        logger.warning(f"策略加载失败通知已发送: policy_id={policy_id}, errors={error_detail}")

    def hot_update_markdown_policy(self, policy_id: str, markdown_text: str, user_role: str = "") -> Dict[str, Any]:
        compile_result = self.compiler.compile(markdown_text)
        if not compile_result.success:
            # 策略编译失败：发布 hook 事件 + 审计日志通知管理员
            self._notify_policy_load_failed(policy_id, compile_result.errors)
            errors = compile_result.errors
            if user_role != "admin":
                errors = ["编译失败，请联系管理员查看详情"]
            return {
                "status": "error",
                "message": "编译失败，旧策略保持运行",
                "errors": errors,
            }

        current_version = self.version_storage.get_latest_version(policy_id)
        current_version_num = 0
        if current_version:
            current_version_num = current_version.get("version", 0)

        new_version = current_version_num + 1

        self.version_storage.save_version(
            policy_id=policy_id,
            rego_text=compile_result.rego_text,
            markdown_text=markdown_text,
            version=new_version,
        )

        load_result = self.opa_manager.load_policy(
            policy_id=policy_id,
            rego_content=compile_result.rego_text,
        )

        if not load_result:
            return {
                "status": "error",
                "message": "策略加载到OPA失败，旧策略保持运行",
            }

        self.opa_manager.clear_cache()

        return {
            "status": "success",
            "policy_id": policy_id,
            "version": new_version,
            "rego_text": compile_result.rego_text,
        }


class ABACService:

    CLEARANCE_ORDER = {
        "public": 1,
        "confidential": 2,
        "secret": 3,
        "top_secret": 4,
    }

    def __init__(self, opa_manager: OPAManager = None):
        self.opa_manager = opa_manager or OPAManager()

    def check_permission_abac(
        self,
        subject: Dict[str, Any],
        action: Dict[str, Any],
        resource: Dict[str, Any],
        env: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        user_id = subject.get("user_id", "")
        roles = subject.get("roles", [])
        clearance_level = subject.get("clearance_level", "public")

        action_type = action.get("type", "")
        action_category = action.get("category", "general")

        resource_type = resource.get("type", "")
        classification = resource.get("classification", "public")
        workspace_id = resource.get("workspace_id", "")

        environment = env or {}
        time_info = environment.get("time", "")
        ip = environment.get("ip", "")
        isolation_level = environment.get("isolation_level", "standard")

        if "system_admin" in roles:
            return {
                "allow": True,
                "reason": "System admin has all permissions",
                "policy_version": self.opa_manager.get_bundle_version(),
            }

        clearance_sufficient = self._check_clearance(clearance_level, classification)
        if not clearance_sufficient:
            return {
                "allow": False,
                "reason": "Insufficient clearance level",
                "policy_version": self.opa_manager.get_bundle_version(),
            }

        workspace_ok = self._check_workspace(subject, workspace_id, isolation_level)
        if not workspace_ok:
            return {
                "allow": False,
                "reason": "Workspace isolation violation",
                "policy_version": self.opa_manager.get_bundle_version(),
            }

        action_ok = self._check_action_permission(roles, action_type, action_category)
        if not action_ok:
            return {
                "allow": False,
                "reason": "Action not permitted for assigned roles",
                "policy_version": self.opa_manager.get_bundle_version(),
            }

        if environment:
            env_ok = self._check_environment(environment, subject)
            if not env_ok["allowed"]:
                return {
                    "allow": False,
                    "reason": env_ok["reason"],
                    "policy_version": self.opa_manager.get_bundle_version(),
                }

        return {
            "allow": True,
            "reason": "Permission granted",
            "policy_version": self.opa_manager.get_bundle_version(),
        }

    def _check_clearance(self, user_level: str, required_level: str) -> bool:
        user_order = self.CLEARANCE_ORDER.get(user_level, 0)
        required_order = self.CLEARANCE_ORDER.get(required_level, 0)
        return user_order >= required_order

    def _check_workspace(self, subject: Dict, resource_workspace: str, isolation_level: str) -> bool:
        if isolation_level == "strict":
            subject_ws = subject.get("workspace_id", "")
            if subject_ws and resource_workspace and subject_ws != resource_workspace:
                return False
        return True

    def _check_action_permission(self, roles: List[str], action_type: str, action_category: str) -> bool:
        role_permissions = {
            "commander": ["view", "create", "update", "delete", "approve", "command_units", "authorize_attacks"],
            "analyst": ["view", "analyze_data", "generate_reports", "view_intelligence"],
            "operator": ["view", "perform", "observe"],
            "observer": ["view"],
            "auditor": ["view", "export"],
            "admin": ["*"],
            "team_leader": ["view", "create", "update", "approve"],
            "member": ["view", "create", "update"],
            "project_owner": ["view", "create", "update", "delete", "approve"],
            "guest": ["view"],
        }

        for role in roles:
            perms = role_permissions.get(role, [])
            if "*" in perms or action_type in perms:
                return True

        return False

    def _check_environment(self, env: Dict, subject: Dict) -> Dict[str, Any]:
        time_of_day = env.get("time_of_day")
        if time_of_day:
            restricted_hours = subject.get("restricted_hours")
            if restricted_hours:
                start = restricted_hours.get("start")
                end = restricted_hours.get("end")
                if start and end:
                    if time_of_day < start or time_of_day > end:
                        return {"allowed": False, "reason": "Outside allowed working hours"}

        ip_restriction = env.get("ip_restriction")
        if ip_restriction:
            allowed_ips = subject.get("allowed_ips", [])
            if allowed_ips and ip_restriction not in allowed_ips:
                return {"allowed": False, "reason": "IP address not allowed"}

        return {"allowed": True, "reason": "Environment constraints satisfied"}


OPAManagerV2 = OPAManager


if __name__ == "__main__":
    manager = OPAManager()

    logger.info(f"OPA 模式: {('Mock' if manager.use_mock else 'Real OPA Server')}")
    logger.info(f'Bundle 版本: {manager.get_bundle_version()}')

    logger.info('\n测试 ABAC 权限检查:')
    tests = [
        ({"id": "user1", "roles": ["commander"], "attributes": {"clearance_level": "secret"}},
         "attack", {"id": "RADAR_01", "type": "WeaponSystem"}, True),
        ({"id": "user2", "roles": ["pilot"], "attributes": {"clearance_level": "confidential"}},
         "view_intelligence", {"id": "RADAR_01", "type": "WeaponSystem"}, True),
        ({"id": "user3", "roles": ["commander"], "attributes": {"clearance_level": "secret"}},
         "attack", {"id": "HOSPITAL_01", "type": "CivilianInfrastructure"}, False),
    ]

    for user, action, resource, expected in tests:
        result = manager.check_permission_abac(user, action, resource)
        status = "PASS" if result.get("allow") == expected else "FAIL"
        logger.info(f"  {status}: {user['id']}.{action} -> {result.get('allow')} (expected {expected})")

    logger.info('\nWhat-If 分析:')
    what_if = manager.what_if_analysis(
        {"id": "commander1", "roles": ["commander"], "attributes": {"clearance_level": "secret"}},
        ["attack", "view_intelligence"],
        [{"id": "RADAR_01", "type": "WeaponSystem"}, {"id": "HOSPITAL_01", "type": "CivilianInfrastructure"}]
    )
    logger.info(f"  测试了 {what_if['total_actions_tested']} 个操作组合")

    logger.info('\n缓存统计:', manager.get_cache_stats())
