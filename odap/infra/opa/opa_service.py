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
from typing import Optional, Dict, Any, List

import httpx

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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

        # 决定使用真实 OPA 还是 Mock
        if use_mock is not None:
            self.use_mock = use_mock
        else:
            if self.opa_client.health_check():
                self.use_mock = False
                print(f"OPA Server 已连接: {self.opa_client.opa_url}")
                self._auto_load_policy()
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

    def check_permission(self, user_role: str, action: str, resource: Dict) -> bool:
        """
        检查用户权限（自动选择真实 OPA 或 Mock）
        """
        if self.use_mock:
            result = self._mock_check_permission(user_role, action, resource)
        else:
            try:
                result = self.opa_client.check_permission(user_role, action, resource)
            except (ConnectionError, RuntimeError) as e:
                print(f"警告: OPA 异常 ({e})，临时 fallback 到 Mock")
                self.use_mock = True
                result = self._mock_check_permission(user_role, action, resource)

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
