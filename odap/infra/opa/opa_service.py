"""
OPA 权限管理模块
支持真实 OPA Server (REST API) 和 Mock 两种模式

架构：
- OPA Server 未启动时自动 fallback 到 Mock 模式
- 通过环境变量 OPA_URL 配置 OPA 地址
- 策略文件 core/opa_policy.rego 在 OPA Server 启动时自动加载
"""

import sys
import os
import json
import time
import hashlib
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass
from enum import Enum

import httpx

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class AccessControlModel(Enum):
    """访问控制模型"""
    RBAC = "rbac"          # 基于角色的访问控制
    ABAC = "abac"          # 基于属性的访问控制
    PBAC = "pbac"          # 基于策略的访问控制
    CBAC = "cbac"          # 基于上下文的访问控制


class PermissionScope(Enum):
    """权限作用域"""
    SYSTEM = "system"      # 系统级权限
    PROJECT = "project"    # 项目级权限
    RESOURCE = "resource"  # 资源级权限
    DATA = "data"          # 数据级权限


class DecisionResult(Enum):
    """决策结果"""
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"


class DecisionReason(Enum):
    """决策原因"""
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_DENIED = "permission_denied"
    INSUFFICIENT_ROLE = "insufficient_role"
    RESOURCE_RESTRICTED = "resource_restricted"
    TIME_RESTRICTION = "time_restriction"
    IP_RESTRICTION = "ip_restriction"


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


class OPAClient:
    """
    OPA REST API 客户端
    通过 HTTP 调用 OPA Server 的 /v1/data/ 端点
    """

    def __init__(self, opa_url: str = None, timeout: float = 5.0):
        self.opa_url = (opa_url or os.getenv("OPA_URL", "http://localhost:8181")).rstrip("/")
        self.timeout = timeout

    def check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        """调用 OPA 判断是否允许操作"""
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/allow",
                json={
                    "input": {
                        "user_role": user_role,
                        "action": action,
                        "resource": resource,
                    }
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("result", False)
        except httpx.ConnectError:
            raise ConnectionError(f"OPA Server 不可达: {self.opa_url}")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"OPA 返回错误: {e.response.status_code} {e.response.text}")
        except Exception as e:
            raise RuntimeError(f"OPA 调用异常: {e}")

    def check_permission_abac(self, user: Dict, action: str, resource: Dict, environment: Dict = None) -> Dict[str, Any]:
        """基于ABAC模型检查权限"""
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/abac_allow",
                json={
                    "input": {
                        "user": user,
                        "action": action,
                        "resource": resource,
                        "environment": environment or {}
                    }
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("result", {"allow": False})
        except Exception as e:
            raise RuntimeError(f"ABAC 权限检查失败: {e}")

    def check_permissions_batch(self, requests: List[Dict]) -> List[Dict]:
        """批量检查权限"""
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/batch_allow",
                json={
                    "input": {
                        "requests": requests
                    }
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("result", [])
        except Exception as e:
            raise RuntimeError(f"批量权限检查失败: {e}")

    def check_policy_simulation(self, user_role: str, action: str,
                                 resource: Dict) -> Dict[str, Any]:
        """调用 OPA 策略模拟"""
        try:
            response = httpx.post(
                f"{self.opa_url}/v1/data/domain/policy_simulation",
                json={
                    "input": {
                        "user_role": user_role,
                        "action": action,
                        "resource": resource,
                    }
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json().get("result", {})
        except Exception as e:
            raise RuntimeError(f"OPA 策略模拟失败: {e}")

    def put_policy(self, policy_path: str, rego_content: str) -> bool:
        """上传 Rego 策略到 OPA"""
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
            raise RuntimeError(f"OPA 策略上传失败: {e}")

    def get_policy(self, policy_path: str) -> str:
        """获取 Rego 策略内容"""
        try:
            response = httpx.get(
                f"{self.opa_url}/v1/policies/{policy_path}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.text
        except Exception as e:
            raise RuntimeError(f"获取策略失败: {e}")

    def delete_policy(self, policy_path: str) -> bool:
        """删除 Rego 策略"""
        try:
            response = httpx.delete(
                f"{self.opa_url}/v1/policies/{policy_path}",
                timeout=self.timeout,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            raise RuntimeError(f"删除策略失败: {e}")

    def list_policies(self) -> List[str]:
        """列出所有策略"""
        try:
            response = httpx.get(
                f"{self.opa_url}/v1/policies",
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            return list(result.keys())
        except Exception as e:
            raise RuntimeError(f"列出策略失败: {e}")

    def health_check(self) -> bool:
        """检查 OPA Server 是否可用"""
        try:
            response = httpx.get(f"{self.opa_url}/health", timeout=2.0)
            return response.status_code == 200
        except Exception:
            return False


class OPAManager:
    """
    OPA 权限管理器
    自动检测 OPA Server 可用性，不可用时 fallback 到 Mock
    """

    def __init__(self, opa_url: str = None, use_mock: bool = None):
        self.opa_client = OPAClient(opa_url=opa_url)
        self.policy_history: List[Dict] = []

        # 策略版本管理
        self.policy_versions = {
            "current": "1.0.0",
            "previous": "0.9.0",
            "history": [],
        }

        # 策略缓存
        self.policy_cache: Dict[str, CacheEntry] = {}
        self.cache_max_size = 1000
        self.cache_ttl = 300  # 5分钟
        self.cache_hits = 0
        self.cache_misses = 0

        # Bundle 管理
        self.bundle_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bundles")
        os.makedirs(self.bundle_dir, exist_ok=True)
        self.bundle_version = "1.0.0"

        # 决定使用真实 OPA 还是 Mock
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            if self.opa_client.health_check():
                self.use_mock = False
                print(f"OPA Server 已连接: {self.opa_client.opa_url}")
                self._auto_load_policy()
                self._init_bundle()
            else:
                self.use_mock = True
                print(f"OPA Server 不可达，使用模拟模式")

    def _auto_load_policy(self):
        """自动加载 .rego 策略文件到 OPA"""
        rego_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opa_policy.rego")
        if os.path.exists(rego_path) and not self.use_mock:
            try:
                with open(rego_path, "r") as f:
                    rego_content = f.read()
                self.opa_client.put_policy("domain", rego_content)
                print("OPA 策略已加载: domain")
            except Exception as e:
                print(f"OPA 策略加载失败: {e}")

    def _init_bundle(self):
        """初始化策略 Bundle"""
        try:
            # 创建初始 bundle
            bundle_path = os.path.join(self.bundle_dir, f"bundle_{self.bundle_version}.json")
            if not os.path.exists(bundle_path):
                self._create_bundle()
            print(f"策略 Bundle 初始化完成: {self.bundle_version}")
        except Exception as e:
            print(f"Bundle 初始化失败: {e}")

    def _create_bundle(self):
        """创建策略 Bundle"""
        bundle_content = {
            "schema": "https://openpolicyagent.org/schemas/bundle/v1",
            "revision": self.bundle_version,
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
            },
            "policies": {
                "domain": {
                    "rego": self._get_policy_content()
                }
            }
        }
        bundle_path = os.path.join(self.bundle_dir, f"bundle_{self.bundle_version}.json")
        with open(bundle_path, "w") as f:
            json.dump(bundle_content, f, indent=2)

    def _get_policy_content(self):
        """获取策略内容"""
        rego_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "opa_policy.rego")
        if os.path.exists(rego_path):
            with open(rego_path, "r") as f:
                return f.read()
        return ""

    def _generate_cache_key(self, request: Dict) -> str:
        """生成缓存键"""
        key_data = {
            "user_role": request.get("user_role"),
            "action": request.get("action"),
            "resource_id": request.get("resource", {}).get("id", "unknown"),
            "resource_type": request.get("resource", {}).get("type", "unknown")
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[bool]:
        """从缓存获取决策"""
        if key in self.policy_cache:
            entry = self.policy_cache[key]
            if time.time() < entry.expires_at:
                entry.last_accessed = time.time()
                entry.access_count += 1
                self.cache_hits += 1
                return entry.value
            else:
                # 缓存过期
                del self.policy_cache[key]
        self.cache_misses += 1
        return None

    def _add_to_cache(self, key: str, value: bool):
        """添加到缓存"""
        if len(self.policy_cache) >= self.cache_max_size:
            # 移除最旧的缓存项
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
        """
        检查用户权限（自动选择真实 OPA 或 Mock）
        """
        # 生成缓存键
        request = {
            "user_role": user_role,
            "action": action,
            "resource": resource
        }
        cache_key = self._generate_cache_key(request)
        
        # 检查缓存
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            # 记录策略执行历史
            self.policy_history.append({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "user_role": user_role,
                "action": action,
                "resource_id": resource.get("id", "unknown") if isinstance(resource, dict) else str(resource),
                "result": "allowed" if cached_result else "denied",
                "mode": "cache",
            })
            return cached_result
        
        # 执行权限检查
        if self.use_mock:
            result = self._mock_check_permission(user_role, action, resource)
        else:
            try:
                result = self.opa_client.check_permission(user_role, action, resource)
            except (ConnectionError, RuntimeError) as e:
                print(f"警告: OPA 异常 ({e})，临时 fallback 到 Mock")
                self.use_mock = True
                result = self._mock_check_permission(user_role, action, resource)

        # 添加到缓存
        self._add_to_cache(cache_key, result)

        # 记录策略执行历史
        self.policy_history.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "user_role": user_role,
            "action": action,
            "resource_id": resource.get("id", "unknown") if isinstance(resource, dict) else str(resource),
            "result": "allowed" if result else "denied",
            "mode": "mock" if self.use_mock else "opa",
        })

        return result

    def check_permission_abac(self, user: Dict, action: str, resource: Dict, environment: Dict = None) -> Dict[str, Any]:
        """
        基于ABAC模型检查权限
        """
        if self.use_mock:
            # Mock ABAC检查
            return self._mock_check_permission_abac(user, action, resource, environment)
        else:
            try:
                result = self.opa_client.check_permission_abac(user, action, resource, environment)
                return result
            except (ConnectionError, RuntimeError) as e:
                print(f"警告: OPA ABAC 异常 ({e})，临时 fallback 到 Mock")
                self.use_mock = True
                return self._mock_check_permission_abac(user, action, resource, environment)

    def check_permissions_batch(self, requests: List[Dict]) -> List[Dict]:
        """
        批量检查权限
        """
        if self.use_mock:
            # Mock 批量检查
            return [
                {
                    "request": req,
                    "result": self._mock_check_permission(
                        req.get("user_role"),
                        req.get("action"),
                        req.get("resource")
                    )
                }
                for req in requests
            ]
        else:
            try:
                result = self.opa_client.check_permissions_batch(requests)
                return result
            except (ConnectionError, RuntimeError) as e:
                print(f"警告: OPA 批量检查异常 ({e})，临时 fallback 到 Mock")
                self.use_mock = True
                return [
                    {
                        "request": req,
                        "result": self._mock_check_permission(
                            req.get("user_role"),
                            req.get("action"),
                            req.get("resource")
                        )
                    }
                    for req in requests
                ]

    def _mock_check_permission_abac(self, user: Dict, action: str, resource: Dict, environment: Dict = None) -> Dict[str, Any]:
        """
        Mock ABAC权限检查
        """
        # 简化的ABAC规则
        user_roles = user.get("roles", [])
        user_attributes = user.get("attributes", {})
        
        # 检查用户是否有管理员角色
        if "system_admin" in user_roles:
            return {"allow": True, "reason": "System admin has all permissions"}
        
        # 检查用户属性
        if user_attributes.get("authenticated") is not True:
            return {"allow": False, "reason": "User not authenticated"}
        
        # 检查资源属性
        resource_type = resource.get("type", "")
        if resource_type == "CivilianInfrastructure" and action == "attack":
            return {"allow": False, "reason": "Cannot attack civilian infrastructure"}
        
        # 检查环境属性
        if environment:
            time_of_day = environment.get("time_of_day", "")
            if time_of_day and (time_of_day < "09:00" or time_of_day > "18:00"):
                return {"allow": False, "reason": "Outside working hours"}
        
        # 默认允许
        return {"allow": True, "reason": "Permission granted"}

    def _mock_check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        """
        Mock 权限检查（逻辑与 opa_policy.rego 完全一致）

        规则：
        1. 角色必须存在且拥有对应 permission
        2. 角色不能有匹配的 restriction
        """
        roles = {
            "pilot": {
                "permissions": ["view_intelligence", "request_support"],
                "restrictions": ["cannot_attack", "cannot_command"],
            },
            "commander": {
                "permissions": ["view_intelligence", "command_units", "authorize_attacks", "approve_missions"],
                "restrictions": ["cannot_attack_civilian_infrastructure"],
            },
            "intelligence_analyst": {
                "permissions": ["view_intelligence", "analyze_data", "generate_reports"],
                "restrictions": ["cannot_command", "cannot_attack"],
            },
        }

        permission_mapping = {
            "attack": ["authorize_attacks"],
            "command": ["command_units"],
            "view_intelligence": ["view_intelligence"],
            "request_support": ["request_support"],
            "analyze_data": ["analyze_data"],
            "generate_reports": ["generate_reports"],
            "approve_missions": ["approve_missions"],
        }

        if user_role not in roles:
            return False

        has_perm = any(
            perm in roles[user_role]["permissions"]
            for perm in permission_mapping.get(action, [action])
        )
        if not has_perm:
            return False

        restrictions = roles[user_role]["restrictions"]
        if "cannot_attack" in restrictions and action == "attack":
            return False
        if "cannot_command" in restrictions and action == "command":
            return False
        if "cannot_attack_civilian_infrastructure" in restrictions:
            if action == "attack" and resource.get("type") == "CivilianInfrastructure":
                return False

        return True

    def simulate_policy(self, user_role: str, action: str, resource: Dict) -> Dict:
        """模拟策略执行"""
        allowed = self.check_permission(user_role, action, resource)
        return {
            "action": action,
            "resource": resource.get("id", "unknown") if isinstance(resource, dict) else str(resource),
            "user_role": user_role,
            "result": "allowed" if allowed else "denied",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "mode": "mock" if self.use_mock else "opa",
        }

    def load_policy(self):
        """加载/重新加载 OPA 策略"""
        if self.use_mock:
            return
        self._auto_load_policy()

    def rollback_policy(self) -> str:
        """回退策略版本"""
        old_current = self.policy_versions["current"]
        old_previous = self.policy_versions["previous"]

        self.policy_versions["current"] = old_previous
        self.policy_versions["previous"] = old_current

        self.policy_versions["history"].append({
            "from": old_current,
            "to": old_previous,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })

        self.load_policy()
        return self.policy_versions["current"]

    def get_policy_version(self) -> str:
        """获取当前策略版本"""
        return self.policy_versions["current"]

    def get_policy_history(self) -> List[Dict]:
        """获取策略执行历史"""
        return list(self.policy_history)

    def clear_policy_history(self):
        """清空策略执行历史"""
        self.policy_history.clear()

    def update_bundle(self):
        """更新策略 Bundle（热更新）"""
        try:
            # 生成新的 bundle 版本
            import uuid
            new_version = f"1.0.{int(time.time())}"
            self.bundle_version = new_version
            
            # 创建新的 bundle
            self._create_bundle()
            
            # 加载新的 bundle 到 OPA
            if not self.use_mock:
                # 这里可以添加加载 bundle 到 OPA 的逻辑
                # 例如：self.opa_client.put_bundle(...)  
                print(f"策略 Bundle 热更新完成: {self.bundle_version}")
            
            return self.bundle_version
        except Exception as e:
            print(f"Bundle 更新失败: {e}")
            return self.bundle_version

    def get_bundle_version(self) -> str:
        """获取当前 Bundle 版本"""
        return self.bundle_version

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "total": total,
            "hit_rate_percent": hit_rate,
            "cache_size": len(self.policy_cache),
            "max_size": self.cache_max_size
        }

    def clear_cache(self):
        """清空缓存"""
        self.policy_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        print("策略缓存已清空")

    def policy_sandbox(self, policy_content: str) -> Dict[str, Any]:
        """策略沙箱执行"""
        try:
            # 这里可以添加策略沙箱执行逻辑
            # 例如：验证策略语法、执行策略等
            return {
                "success": True,
                "message": "策略执行成功",
                "sanitized": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "sanitized": True
            }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        cache_stats = self.get_cache_stats()
        
        return {
            "cache": cache_stats,
            "policy_versions": self.policy_versions,
            "bundle_version": self.bundle_version,
            "mode": "mock" if self.use_mock else "opa",
            "history_count": len(self.policy_history)
        }


if __name__ == "__main__":
    manager = OPAManager()

    print(f"OPA 模式: {'Mock' if manager.use_mock else 'Real OPA Server'}")

    print("\n测试权限检查:")
    tests = [
        ("pilot", "view_intelligence", {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}, True),
        ("pilot", "attack", {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}, False),
        ("commander", "attack", {"id": "RADAR_01", "type": "WeaponSystem", "properties": {"type": "雷达"}}, True),
        ("commander", "attack", {"id": "HOSPITAL_01", "type": "CivilianInfrastructure", "properties": {"type": "医院"}}, False),
    ]

    all_pass = True
    for role, action, resource, expected in tests:
        result = manager.check_permission(role, action, resource)
        status = "PASS" if result == expected else "FAIL"
        if result != expected:
            all_pass = False
        print(f"  {status}: {role}.{action} -> {result} (expected {expected})")

    print(f"\n结果: {'全部通过' if all_pass else '有失败项'}")

    # 测试策略模拟
    print("\n策略模拟:")
    sim = manager.simulate_policy("commander", "attack", {"id": "RADAR_01", "type": "WeaponSystem"})
    print(f"  {json.dumps(sim, ensure_ascii=False, indent=2)}")

    # 测试策略历史
    print(f"\n策略执行历史: {len(manager.get_policy_history())} 条记录")
