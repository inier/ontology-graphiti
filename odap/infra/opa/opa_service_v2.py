"""
OPA 权限管理模块 v2
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
from typing import Optional, Dict, Any, List, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

import httpx

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AccessControlModel(Enum):
    """访问控制模型"""
    RBAC = "rbac"
    ABAC = "abac"
    PBAC = "pbac"
    CBAC = "cbac"


class PermissionScope(Enum):
    """权限作用域"""
    SYSTEM = "system"
    PROJECT = "project"
    RESOURCE = "resource"
    DATA = "data"


class DecisionResult(Enum):
    """决策结果"""
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"
    NOT_APPLICABLE = "not_applicable"


class DecisionReason(Enum):
    """决策原因"""
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
        """
        ABAC 策略评估

        Args:
            user: 用户属性（包含 roles, attributes 等）
            action: 操作类型
            resource: 资源属性
            environment: 环境属性（时间、IP 等）

        Returns:
            决策结果
        """
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
        """检查用户权限级别是否满足资源要求"""
        user_level = user_attrs.get("clearance_level", "public")
        required_level = resource_attrs.get("required_clearance", "public")

        level_order = ["public", "confidential", "secret", "top_secret"]
        try:
            return level_order.index(user_level) >= level_order.index(required_level)
        except ValueError:
            return True

    def _check_environment_constraints(self, environment: Dict,
                                      user_attrs: Dict) -> Dict[str, Any]:
        """检查环境约束"""
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
            os.path.dirname(os.path.abspath(__file__)), "bundles_v2"
        )
        os.makedirs(self.bundle_dir, exist_ok=True)
        self.current_bundle: Optional[PolicyBundle] = None
        self.bundle_history: List[PolicyBundle] = []
        self._load_current_bundle()

    def _load_current_bundle(self):
        """加载当前 Bundle"""
        current_path = os.path.join(self.bundle_dir, "current_bundle.json")
        if os.path.exists(current_path):
            try:
                with open(current_path, "r") as f:
                    data = json.load(f)
                    self.current_bundle = PolicyBundle(**data)
            except Exception as e:
                print(f"加载 Bundle 失败: {e}")

    def _save_bundle(self, bundle: PolicyBundle):
        """保存 Bundle"""
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
        """创建新 Bundle"""
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
        """热更新 Bundle"""
        return self.create_bundle(policies, {"update_type": "hot_update"})

    def rollback_bundle(self) -> Optional[PolicyBundle]:
        """回滚到上一个 Bundle"""
        if len(self.bundle_history) < 2:
            return None

        self.bundle_history.pop()
        previous = self.bundle_history[-1]
        self._save_bundle(previous)
        self.current_bundle = previous

        return previous

    def get_bundle(self) -> Optional[PolicyBundle]:
        """获取当前 Bundle"""
        return self.current_bundle

    def get_bundle_history(self) -> List[PolicyBundle]:
        """获取 Bundle 历史"""
        return list(self.bundle_history)


class PolicySandbox:
    """策略沙箱"""

    def __init__(self):
        self.evaluator = ABACPolicyEvaluator()

    def simulate(self, policy_content: str, user: Dict, action: str,
                 resource: Dict, environment: Dict = None) -> PolicySandboxResult:
        """
        模拟策略执行

        Args:
            policy_content: Rego 策略内容
            user: 用户属性
            action: 操作类型
            resource: 资源属性
            environment: 环境属性

        Returns:
            沙箱执行结果
        """
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
        """
        What-If 分析：模拟多个操作的结果

        Args:
            user: 用户属性
            actions: 操作列表
            resources: 资源列表

        Returns:
            What-If 分析结果
        """
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


class OPAClientV2:
    """
    OPA REST API 客户端 v2
    """

    def __init__(self, opa_url: str = None, timeout: float = 5.0):
        self.opa_url = (opa_url or os.getenv("OPA_URL", "http://localhost:8181")).rstrip("/")
        self.timeout = timeout

    def check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        """调用 OPA 判断权限"""
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
        """ABAC 权限检查"""
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
        """批量权限检查"""
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
        """上传 Rego 策略"""
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

    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = httpx.get(f"{self.opa_url}/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False


class OPAManagerV2:
    """
    OPA 权限管理器 v2

    功能：
    - ABAC 策略评估
    - 策略热更新 Bundle
    - 策略沙箱
    - 批量权限检查 + 缓存
    """

    def __init__(self, opa_url: str = None, use_mock: bool = None):
        self.opa_client = OPAClientV2(opa_url=opa_url)

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

        self.use_mock = True
        if use_mock is not None:
            self.use_mock = use_mock
        elif self.opa_client.health_check():
            self.use_mock = False
            print(f"OPA Server 已连接: {self.opa_client.opa_url}")
            self._auto_load_policy()

    def _generate_cache_key(self, request: Dict) -> str:
        """生成缓存键"""
        key_data = {
            "user_id": request.get("user_id"),
            "user_roles": tuple(sorted(request.get("user_roles", []))),
            "action": request.get("action"),
            "resource_id": request.get("resource", {}).get("id", "unknown"),
            "resource_type": request.get("resource", {}).get("type", "unknown")
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """从缓存获取"""
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
        """添加到缓存"""
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
        """检查权限"""
        request = {"user_role": user_role, "action": action, "resource": resource}
        cache_key = self._generate_cache_key({"user_roles": [user_role], **request})

        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached.get("allow", False)

        if self.use_mock:
            result = self._mock_check_permission(user_role, action, resource)
        else:
            try:
                result = self.opa_client.check_permission(user_role, action, resource)
            except Exception as e:
                print(f"OPA 异常: {e}，fallback 到 Mock")
                result = self._mock_check_permission(user_role, action, resource)

        self._add_to_cache(cache_key, {"allow": result})
        self._record_history(user_role, action, resource, result)
        return result

    def check_permission_abac(self, user: Dict, action: str, resource: Dict,
                             environment: Dict = None) -> Dict[str, Any]:
        """ABAC 权限检查"""
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
                print(f"OPA ABAC 异常: {e}，fallback 到本地评估")
                result = self.abac_evaluator.evaluate(user, action, resource, environment)

        self._add_to_cache(cache_key, result)
        self._record_history(user.get("id", "unknown"), action, resource, result.get("allow"))
        return result

    def check_permissions_batch(self, requests: List[Dict]) -> List[Dict]:
        """批量权限检查"""
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
        """Mock 权限检查"""
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
        """记录历史"""
        self.policy_history.append({
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "resource_id": resource.get("id", "unknown"),
            "result": "allowed" if result else "denied"
        })

    def simulate_policy(self, user_role: str, action: str, resource: Dict) -> Dict:
        """策略模拟"""
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
        """What-If 分析"""
        return self.policy_sandbox.what_if(user, actions, resources)

    def policy_sandbox_simulate(self, policy_content: str, user: Dict, action: str,
                               resource: Dict, environment: Dict = None) -> PolicySandboxResult:
        """策略沙箱模拟"""
        return self.policy_sandbox.simulate(policy_content, user, action, resource, environment)

    def hot_update_bundle(self, policies: Dict[str, str]) -> PolicyBundle:
        """热更新 Bundle"""
        bundle = self.bundle_manager.hot_update_bundle(policies)
        self.policy_versions["previous"] = self.policy_versions["current"]
        self.policy_versions["current"] = bundle.version
        return bundle

    def rollback_bundle(self) -> Optional[PolicyBundle]:
        """回滚 Bundle"""
        bundle = self.bundle_manager.rollback_bundle()
        if bundle:
            self.policy_versions["previous"] = self.policy_versions["current"]
            self.policy_versions["current"] = bundle.version
        return bundle

    def get_bundle_version(self) -> str:
        """获取当前 Bundle 版本"""
        return self.policy_versions["current"]

    def get_policy_history(self) -> List[Dict]:
        """获取策略执行历史"""
        return list(self.policy_history)

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
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
        """清空缓存"""
        self.policy_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0

    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        return {
            "cache": self.get_cache_stats(),
            "policy_versions": self.policy_versions,
            "bundle_version": self.bundle_manager.get_bundle().version if self.bundle_manager.get_bundle() else None,
            "mode": "mock" if self.use_mock else "opa",
            "history_count": len(self.policy_history)
        }


if __name__ == "__main__":
    manager = OPAManagerV2()

    print(f"OPA 模式: {'Mock' if manager.use_mock else 'Real OPA Server'}")
    print(f"Bundle 版本: {manager.get_bundle_version()}")

    print("\n测试 ABAC 权限检查:")
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
        print(f"  {status}: {user['id']}.{action} -> {result.get('allow')} (expected {expected})")

    print("\nWhat-If 分析:")
    what_if = manager.what_if_analysis(
        {"id": "commander1", "roles": ["commander"], "attributes": {"clearance_level": "secret"}},
        ["attack", "view_intelligence"],
        [{"id": "RADAR_01", "type": "WeaponSystem"}, {"id": "HOSPITAL_01", "type": "CivilianInfrastructure"}]
    )
    print(f"  测试了 {what_if['total_actions_tested']} 个操作组合")

    print("\n缓存统计:", manager.get_cache_stats())
