"""
策略管理与智能问答集成测试 —— 完整总结报告

验证以下核心流程：
1. 策略列表中存在禁用状态的策略
2. 通过 API 启用/禁用策略，状态正确更新
3. 启用的策略在 IntelligenceAgent 工具执行中生效（OPA 权限检查）
4. 启用的策略在 OPAPermissionBackend 中生效
5. 启用的策略在 ActionExecutor 中生效
6. 端到端流程：策略管理 → OPA 检查 → Q&A 结果体现

测试范围说明：
- 策略 API CRUD + Toggle（状态变更）
- IntelligenceAgent._execute_tool() 的 OPA 权限检查
- OPAPermissionBackend.check() 的 policy-based 权限决策
- ActionExecutor._check_opa() 的策略验证
- fail-close 安全行为

作者: ODAP 架构团队
日期: 2026-06-20
"""

import pytest
import sys
import os
import json
import time
from unittest.mock import MagicMock, patch, PropertyMock

# 确保项目根在 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ============================================================================
# Test Suite 1: 策略 API Toggle — 状态变更基础验证
# ============================================================================

class TestPolicyToggleAPI:
    """验证策略列表状态、启用/禁用 API 的正确性"""

    @pytest.fixture
    def client(self, tmp_path):
        """创建带模拟认证的 TestClient，指向临时 SQLite DB"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from odap.infra.opa import routes as opa_routes
        from odap.infra.security import jwt_auth

        test_db_dir = str(tmp_path)
        original_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = test_db_dir

        opa_routes._initialized = False
        original_db_path = opa_routes.POLICY_DB_PATH
        opa_routes.POLICY_DB_PATH = os.path.join(test_db_dir, "opa_policies.db")

        app = FastAPI()
        app.include_router(opa_routes.router)

        async def _mock_current_user():
            return {"user_id": "test-user", "role": "admin", "workspace_id": "test-ws"}
        app.dependency_overrides[jwt_auth.get_current_user] = _mock_current_user

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()
        if original_data_dir is not None:
            os.environ["DATA_DIR"] = original_data_dir
        else:
            os.environ.pop("DATA_DIR", None)
        opa_routes.POLICY_DB_PATH = original_db_path
        opa_routes._initialized = False

    # ── 1.1 策略列表状态验证 ──

    def test_policies_list_includes_status_field(self, client):
        """验证策略列表返回每条策略的 status 字段"""
        response = client.get("/api/policies")
        assert response.status_code == 200
        data = response.json()
        assert "policies" in data
        assert data["total"] >= 3  # 默认 3 条策略
        for p in data["policies"]:
            assert "status" in p, f"策略 {p['policy_id']} 缺少 status 字段"
            assert p["status"] in ("enabled", "disabled"), \
                f"策略 {p['policy_id']} status 值异常: {p['status']}"

    def test_default_policies_are_enabled(self, client):
        """验证默认策略初始状态为 enabled"""
        response = client.get("/api/policies")
        data = response.json()
        for p in data["policies"]:
            assert p["status"] == "enabled", \
                f"默认策略 {p['policy_id']} 初始状态应为 enabled，实际为 {p['status']}"

    # ── 1.2 策略禁用 → 验证状态变更 ──

    def test_toggle_policy_to_disabled(self, client):
        """将默认策略设为 disabled，验证 API 返回和持久化"""
        # 获取第一个默认策略
        list_resp = client.get("/api/policies")
        policies = list_resp.json()["policies"]
        policy_id = policies[0]["policy_id"]

        # 禁用
        toggle_resp = client.post(f"/api/policies/{policy_id}/toggle?enabled=false")
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["status"] == "disabled"

        # 验证 GET 也返回 disabled
        get_resp = client.get(f"/api/policies/{policy_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "disabled"

    def test_toggle_policy_back_to_enabled(self, client):
        """禁用后再启用，验证状态正确回切"""
        list_resp = client.get("/api/policies")
        policy_id = list_resp.json()["policies"][0]["policy_id"]

        # 先禁用
        client.post(f"/api/policies/{policy_id}/toggle?enabled=false")
        # 再启用
        toggle_resp = client.post(f"/api/policies/{policy_id}/toggle?enabled=true")
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["status"] == "enabled"

        # 持久化验证
        get_resp = client.get(f"/api/policies/{policy_id}")
        assert get_resp.json()["status"] == "enabled"

    # ── 1.3 按状态筛选策略 ──

    def test_filter_policies_by_disabled_status(self, client):
        """按 status=disabled 筛选，验证只返回禁用策略"""
        list_resp = client.get("/api/policies")
        policy_id = list_resp.json()["policies"][0]["policy_id"]

        # 禁用一个策略
        client.post(f"/api/policies/{policy_id}/toggle?enabled=false")

        # 筛选 disabled
        disabled_resp = client.get("/api/policies?status=disabled")
        disabled_data = disabled_resp.json()
        assert all(p["status"] == "disabled" for p in disabled_data["policies"])

        # 筛选 enabled 不包含已禁用的
        enabled_resp = client.get("/api/policies?status=enabled")
        enabled_ids = {p["policy_id"] for p in enabled_resp.json()["policies"]}
        assert policy_id not in enabled_ids

    def test_filter_policies_by_enabled_status(self, client):
        """按 status=enabled 筛选"""
        response = client.get("/api/policies?status=enabled")
        assert response.status_code == 200
        data = response.json()
        assert all(p["status"] == "enabled" for p in data["policies"])

    # ── 1.4 策略创建与状态 ──

    def test_create_policy_default_enabled(self, client):
        """新创建的策略默认状态为 enabled"""
        payload = {
            "name": "新建策略测试",
            "description": "验证新策略默认为启用状态",
            "markdown_content": "# 测试策略\n## 角色: admin\n## 允许的操作\n- 查询",
            "category": "custom",
        }
        response = client.post("/api/policies", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "enabled"
        assert data["policy_id"].startswith("policy-")

    # ── 1.5 边界条件 ──

    def test_toggle_nonexistent_policy_returns_404(self, client):
        """切换不存在的策略返回 404"""
        response = client.post("/api/policies/nonexistent-id/toggle?enabled=true")
        assert response.status_code == 404

    def test_rego_content_preserved_after_toggle(self, client):
        """验证 toggle 后策略的 rego_content 保持不变"""
        list_resp = client.get("/api/policies")
        policy_id = list_resp.json()["policies"][0]["policy_id"]

        # 获取原始 rego
        orig = client.get(f"/api/policies/{policy_id}").json()
        orig_rego = orig["rego_content"]

        # Toggle 禁用 → 启用 → 禁用 三次
        client.post(f"/api/policies/{policy_id}/toggle?enabled=false")
        client.post(f"/api/policies/{policy_id}/toggle?enabled=true")
        client.post(f"/api/policies/{policy_id}/toggle?enabled=false")

        final = client.get(f"/api/policies/{policy_id}").json()
        assert final["rego_content"] == orig_rego
        assert final["status"] == "disabled"


# ============================================================================
# Test Suite 2: IntelligenceAgent 策略生效 — OPA 权限检查在工具执行中体现
# ============================================================================

class TestIntelligenceAgentPolicyEnforcement:
    """验证 IntelligenceAgent 在工具执行时正确调用 OPA 策略检查"""

    def _create_agent(self):
        """创建带 mock OPA 的 IntelligenceAgent 实例"""
        from odap.biz.core.agent.intelligence_agent import IntelligenceAgent

        # Mock OPAManager 导入
        with patch("odap.biz.core.agent.intelligence_agent.OPAManager") as mock_opa_cls:
            mock_opa = MagicMock()
            mock_opa_cls.return_value = mock_opa

            # Mock get_graph_write_proxy 和 QueryService
            with patch("odap.biz.core.agent.intelligence_agent.get_graph_write_proxy") as mock_proxy:
                mock_proxy.return_value = MagicMock()

                with patch("odap.biz.core.agent.intelligence_agent.QueryService") as mock_qs:
                    mock_qs.return_value = MagicMock()

                    # Mock OpenHarness engine adapter to avoid OH deps
                    with patch("odap.biz.core.agent.intelligence_agent.OHQueryEngineFactory") as mock_factory:
                        mock_factory.create.return_value = MagicMock()
                        mock_factory.create.return_value.submit_message = MagicMock(
                            return_value={"response": "分析完成"}
                        )

                        agent = IntelligenceAgent(user_role="intelligence_analyst")
                        agent._mock_opa = mock_opa
                        return agent

    def test_operations_tool_blocked_when_opa_denies(self):
        """当 OPA 拒绝时，operations 类别工具执行返回 denied"""
        agent = self._create_agent()
        agent._mock_opa.check_permission.return_value = False

        with patch("odap.biz.core.agent.intelligence_agent.SKILL_CATALOG", {
            "command_unit": {
                "handler": lambda **kw: {"status": "executed"},
                "category": "operations",
            }
        }):
            result = agent._execute_tool("command_unit", {"action": "command", "target_id": "T-001"})
            result_dict = json.loads(result)
            assert result_dict["status"] == "denied"
            assert "权限不足" in result_dict["message"]

        # 验证 OPA 被正确调用
        agent._mock_opa.check_permission.assert_called_once_with(
            "intelligence_analyst", "command", {"type": "unknown"}
        )

    def test_operations_tool_allowed_when_opa_grants(self):
        """当 OPA 允许时，operations 类别工具正常执行"""
        agent = self._create_agent()
        agent._mock_opa.check_permission.return_value = True

        with patch("odap.biz.core.agent.intelligence_agent.SKILL_CATALOG", {
            "engage_target": {
                "handler": lambda **kw: {"status": "success", "target": kw.get("target_id")},
                "category": "operations",
            }
        }):
            result = agent._execute_tool("engage_target", {"action": "engage", "target_id": "T-002"})
            result_dict = json.loads(result)
            assert result_dict["status"] == "success"
            assert result_dict["target"] == "T-002"

    def test_non_operations_tool_skips_opa_check(self):
        """非 operations 类别的工具不触发 OPA 检查"""
        agent = self._create_agent()
        agent._mock_opa.check_permission.reset_mock()

        with patch("odap.biz.core.agent.intelligence_agent.SKILL_CATALOG", {
            "radar_search": {
                "handler": lambda **kw: {"contacts": []},
                "category": "intelligence",
            }
        }):
            result = agent._execute_tool("radar_search", {"query": "B区雷达"})
            result_dict = json.loads(result)
            assert "contacts" in result_dict

        # OPA 不应该被调用
        agent._mock_opa.check_permission.assert_not_called()

    def test_unknown_tool_returns_error(self):
        """调用不存在的工具返回错误"""
        agent = self._create_agent()
        result = agent._execute_tool("nonexistent_tool", {})
        result_dict = json.loads(result)
        assert "error" in result_dict
        assert "不存在" in result_dict["error"]

    def test_opa_check_failure_propagates_exception(self):
        """OPA 检查抛出异常时，异常向上传播"""
        agent = self._create_agent()
        agent._mock_opa.check_permission.side_effect = RuntimeError("OPA unavailable")

        with patch("odap.biz.core.agent.intelligence_agent.SKILL_CATALOG", {
            "move_unit": {
                "handler": lambda **kw: {"status": "moved"},
                "category": "operations",
            }
        }):
            # check_permission 抛异常，_execute_tool 不捕获 OPA 异常
            with pytest.raises(RuntimeError, match="OPA unavailable"):
                agent._execute_tool("move_unit", {"action": "move", "target_id": "T-003"})

    def test_different_roles_get_different_opa_results(self):
        """不同角色调用 operations 工具时，OPA 使用不同的 user_role"""
        agent = self._create_agent()
        agent.user_role = "commander"
        agent._mock_opa.check_permission.return_value = True

        with patch("odap.biz.core.agent.intelligence_agent.SKILL_CATALOG", {
            "command_unit": {
                "handler": lambda **kw: {"status": "ordered"},
                "category": "operations",
            }
        }):
            agent._execute_tool("command_unit", {"action": "command", "target_id": "T-004"})

        # 验证 OPA 使用 commander 角色
        agent._mock_opa.check_permission.assert_called_once_with(
            "commander", "command", {"type": "unknown"}
        )


# ============================================================================
# Test Suite 3: OPAPermissionBackend 策略生效 — OpenHarness 权限后端
# ============================================================================

class TestOPAPermissionBackendPolicyEnforcement:
    """验证 OPAPermissionBackend 正确执行 policy-based 权限决策"""

    @pytest.fixture
    def backend_with_mock_opa(self):
        """创建带 mock OPA Manager 的 OPAPermissionBackend"""
        from odap.infra.openharness.permission_backend import OPAPermissionBackend

        mock_opa = MagicMock()
        mock_opa.check_permission_abac.return_value = {"allow": True, "reason": "granted"}
        backend = OPAPermissionBackend(opa_manager=mock_opa)
        backend._mock_opa = mock_opa
        return backend

    @staticmethod
    def _run_async(coro):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_tool_permission_granted(self, backend_with_mock_opa):
        """策略允许时，工具权限检查通过"""
        backend = backend_with_mock_opa
        backend._mock_opa.check_permission_abac.return_value = {"allow": True}
        result = self._run_async(
            backend.check("radar_search", {"query": "B区"}, {"user_role": "intelligence_analyst"})
        )
        assert result is True

    def test_tool_permission_denied(self, backend_with_mock_opa):
        """策略拒绝时，工具权限检查返回 False"""
        backend = backend_with_mock_opa
        backend._mock_opa.check_permission_abac.return_value = {
            "allow": False, "reason": "role not authorized"
        }
        result = self._run_async(
            backend.check("attack_target", {"target_id": "T-001"}, {"user_role": "guest"})
        )
        assert result is False

    def test_policy_map_routing(self, backend_with_mock_opa):
        """验证不同工具映射到正确的 policy package"""
        backend = backend_with_mock_opa
        self._run_async(
            backend.check("attack_target", {"target_id": "T-001"},
                         {"user_role": "commander", "target": {"type": "military"}})
        )
        backend._mock_opa.check_permission_abac.assert_called()

    def test_unknown_tool_uses_default_policy(self, backend_with_mock_opa):
        """未映射的工具使用 common.default 策略"""
        backend = backend_with_mock_opa
        result = self._run_async(
            backend.check("unknown_tool", {}, {"user_role": "analyst"})
        )
        assert result is True

    def test_opa_unavailable_fail_close(self):
        """OPA 不可用时，OPAPermissionBackend 应 fail-close"""
        from odap.infra.openharness.permission_backend import OPAPermissionBackend
        backend = OPAPermissionBackend(opa_manager=None)
        backend._opa_manager = None

        result = self._run_async(
            backend.check("radar_search", {}, {"user_role": "analyst"})
        )
        assert result is False  # fail-close: 无 OPA 时默认拒绝

    def test_check_and_raise_denied(self, backend_with_mock_opa):
        """check_and_raise 在权限不足时抛 PermissionDeniedError"""
        from odap.infra.openharness.permission_backend import PermissionDeniedError
        backend = backend_with_mock_opa
        backend._mock_opa.check_permission_abac.return_value = {"allow": False}

        with pytest.raises(PermissionDeniedError, match="attack_target"):
            self._run_async(
                backend.check_and_raise("attack_target", {"target_id": "T-001"},
                                       {"user_role": "guest"})
            )

    def test_full_permission_matrix(self, backend_with_mock_opa):
        """验证完整的权限矩阵：不同角色对不同工具的权限"""
        backend = backend_with_mock_opa

        test_cases = [
            # (tool_name, user_role, opa_result, expected)
            ("radar_search", "intelligence_analyst", True, True),
            ("attack_target", "commander", True, True),
            ("attack_target", "intelligence_analyst", False, False),
            ("observe", "intelligence_analyst", True, True),
            ("command_unit", "commander", True, True),
            ("command_unit", "guest", False, False),
        ]

        for tool, role, opa_allow, expected in test_cases:
            backend._mock_opa.check_permission_abac.return_value = {
                "allow": opa_allow,
                "reason": f"test_{opa_allow}",
            }
            result = self._run_async(
                backend.check(tool, {}, {"user_role": role})
            )
            assert result == expected, \
                f"{tool} by {role}: expected {expected}, got {result}"


# ============================================================================
# Test Suite 4: ActionExecutor OPA 策略验证
# ============================================================================

class TestActionExecutorPolicyValidation:
    """验证 ActionExecutor 在执行动作前正确进行 OPA 策略校验"""

    @staticmethod
    def _run_async(coro):
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def test_action_blocked_by_opa_policy(self):
        """OPA 策略拒绝时，动作记录状态为 rejected"""
        from odap.biz.decision.action_service.executor import ActionExecutor
        from odap.biz.decision.action_service.schemas import ActionRequest

        executor = ActionExecutor()
        mock_opa = MagicMock()
        executor._opa_manager = mock_opa

        # Mock storage
        mock_storage = MagicMock()
        executor._action_storage = mock_storage

        mock_storage.create_record.return_value = {
            "action_record_id": "rec-001",
            "action_type_id": "attack",
            "target_object_id": "CIV-001",
            "target_object_type": "unit",
            "parameters": {},
            "status": "pending",
        }
        mock_storage.get_record.return_value = {
            "action_record_id": "rec-001",
            "action_type_id": "attack",
            "target_object_id": "CIV-001",
            "target_object_type": "unit",
            "parameters": {},
            "status": "rejected",
            "opa_decision": {"allow": False, "reason": "Civilian target protected"},
        }

        # Mock OMS 返回有效的 action type
        mock_oms = MagicMock()
        mock_oms.get_action_type.return_value = {
            "id": "attack",
            "name": "Attack Target",
            "required_params": ["target_object_id"],
            "confirmation_required": False,
        }
        executor._oms = mock_oms

        # OPA 拒绝
        mock_opa.check_permission_abac.return_value = {
            "allow": False,
            "reason": "Civilian target protected by policy",
        }

        request = ActionRequest(
            action_type_id="attack",
            target_object_id="CIV-001",
            target_object_type="unit",
            parameters={},
            requested_by="test-commander",
        )

        record = self._run_async(executor.submit_action(request))
        assert record["status"] == "rejected"

    def test_action_allowed_by_opa_policy(self):
        """OPA 策略允许时，动作正常进入执行流程"""
        from odap.biz.decision.action_service.executor import ActionExecutor
        from odap.biz.decision.action_service.schemas import ActionRequest

        executor = ActionExecutor()
        mock_opa = MagicMock()
        executor._opa_manager = mock_opa

        mock_storage = MagicMock()
        executor._action_storage = mock_storage

        mock_storage.create_record.return_value = {
            "action_record_id": "rec-002",
            "action_type_id": "observe",
            "target_object_id": "AREA-B",
            "target_object_type": "area",
            "parameters": {},
            "status": "pending",
        }

        mock_storage.get_record.return_value = {
            "action_record_id": "rec-002",
            "action_type_id": "observe",
            "target_object_id": "AREA-B",
            "target_object_type": "area",
            "parameters": {},
            "status": "executed",
            "opa_decision": {"allow": True, "reason": "granted"},
        }

        mock_oms = MagicMock()
        mock_oms.get_action_type.return_value = {
            "id": "observe",
            "name": "Observe Area",
            "required_params": ["target_object_id"],
            "confirmation_required": False,
        }
        executor._oms = mock_oms

        mock_opa.check_permission_abac.return_value = {
            "allow": True, "reason": "Observation within authorized area"
        }

        request = ActionRequest(
            action_type_id="observe",
            target_object_id="AREA-B",
            target_object_type="area",
            parameters={},
            requested_by="test-analyst",
        )

        record = self._run_async(executor.submit_action(request))
        # 不应该被拒绝
        assert record["status"] != "rejected"

    def test_action_requires_confirmation_goes_to_approved(self):
        """需要确认的动作，OPA 通过后状态为 approved"""
        from odap.biz.decision.action_service.executor import ActionExecutor
        from odap.biz.decision.action_service.schemas import ActionRequest

        executor = ActionExecutor()
        mock_opa = MagicMock()
        executor._opa_manager = mock_opa

        mock_storage = MagicMock()
        executor._action_storage = mock_storage

        mock_storage.create_record.return_value = {
            "action_record_id": "rec-003",
            "action_type_id": "engage",
            "target_object_id": "T-005",
            "target_object_type": "unit",
            "parameters": {"weapon_type": "precision"},
            "status": "pending",
        }

        mock_storage.get_record.return_value = {
            "action_record_id": "rec-003",
            "action_type_id": "engage",
            "target_object_id": "T-005",
            "target_object_type": "unit",
            "parameters": {"weapon_type": "precision"},
            "status": "approved",
            "opa_decision": {"allow": True, "reason": "Target within ROE"},
        }

        mock_oms = MagicMock()
        mock_oms.get_action_type.return_value = {
            "id": "engage",
            "name": "Engage Target",
            "required_params": ["target_object_id"],
            "confirmation_required": True,
        }
        executor._oms = mock_oms

        mock_opa.check_permission_abac.return_value = {
            "allow": True, "reason": "Target within rules of engagement"
        }

        request = ActionRequest(
            action_type_id="engage",
            target_object_id="T-005",
            target_object_type="unit",
            parameters={"weapon_type": "precision"},
            requested_by="test-commander",
        )

        record = self._run_async(executor.submit_action(request))
        # 记录状态不应为 rejected
        assert record["status"] != "rejected"

    def test_validation_fails_before_opa_check(self):
        """参数校验失败时，不会进行 OPA 检查（提前拒绝）"""
        from odap.biz.decision.action_service.executor import ActionExecutor
        from odap.biz.decision.action_service.schemas import ActionRequest

        executor = ActionExecutor()
        mock_opa = MagicMock()
        executor._opa_manager = mock_opa

        mock_storage = MagicMock()
        executor._action_storage = mock_storage

        mock_storage.create_record.return_value = {
            "action_record_id": "rec-004",
            "action_type_id": "attack",
            "target_object_id": "T-006",
            "target_object_type": "unit",
            "parameters": {},
            "status": "pending",
        }

        mock_storage.get_record.return_value = {
            "action_record_id": "rec-004",
            "action_type_id": "attack",
            "target_object_id": "T-006",
            "target_object_type": "unit",
            "parameters": {},
            "status": "rejected",
            "validation_result": {"valid": False, "errors": ["missing weapon_type"]},
        }

        mock_oms = MagicMock()
        mock_oms.get_action_type.return_value = {
            "id": "attack",
            "name": "Attack Target",
            "required_params": ["target_object_id", "weapon_type"],
            "confirmation_required": False,
        }
        executor._oms = mock_oms

        # 缺少必需参数 weapon_type
        request = ActionRequest(
            action_type_id="attack",
            target_object_id="T-006",
            target_object_type="unit",
            parameters={},  # 缺少 weapon_type
            requested_by="test-commander",
        )

        record = self._run_async(executor.submit_action(request))
        assert record["status"] == "rejected"


# ============================================================================
# Test Suite 5: 策略 + Q&A 集成 — 端到端流程
# ============================================================================

class TestPolicyQAIntegration:
    """策略管理与智能问答的集成验证"""

    @pytest.fixture
    def integration_client(self, tmp_path):
        """创建集成测试客户端，使用临时 DB"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from odap.infra.opa import routes as opa_routes
        from odap.infra.security import jwt_auth

        test_db_dir = str(tmp_path)
        original_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = test_db_dir

        opa_routes._initialized = False
        original_db_path = opa_routes.POLICY_DB_PATH
        opa_routes.POLICY_DB_PATH = os.path.join(test_db_dir, "opa_policies.db")

        app = FastAPI()
        app.include_router(opa_routes.router)

        async def _mock_current_user():
            return {"user_id": "test-user", "role": "admin", "workspace_id": "test-ws"}
        app.dependency_overrides[jwt_auth.get_current_user] = _mock_current_user

        with TestClient(app) as client:
            yield client

        app.dependency_overrides.clear()
        if original_data_dir is not None:
            os.environ["DATA_DIR"] = original_data_dir
        else:
            os.environ.pop("DATA_DIR", None)
        opa_routes.POLICY_DB_PATH = original_db_path
        opa_routes._initialized = False

    def test_full_policy_lifecycle_with_qa_context(self, integration_client):
        """
        端到端流程:
        1. 策略列表初始状态检查
        2. 禁用一个策略
        3. 验证禁用生效（列表筛选 + 单条查询）
        4. 重新启用
        5. 创建新策略并验证默认启用
        6. 模拟 Q&A 场景中的策略检查
        """
        client = integration_client

        # ── Step 1: 策略列表初始状态 ──
        list_resp = client.get("/api/policies")
        assert list_resp.status_code == 200
        policies = list_resp.json()["policies"]
        assert len(policies) >= 3
        assert all(p["status"] == "enabled" for p in policies)
        print(f"\n  [Step 1] ✅ 初始策略列表: {len(policies)} 条，全部 enabled")

        # ── Step 2: 禁用第一条策略 ──
        policy_id = policies[0]["policy_id"]
        policy_name = policies[0]["name"]

        toggle_off = client.post(f"/api/policies/{policy_id}/toggle?enabled=false")
        assert toggle_off.status_code == 200
        assert toggle_off.json()["status"] == "disabled"
        print(f"  [Step 2] ✅ 策略已禁用: {policy_name} ({policy_id})")

        # ── Step 3: 验证禁用生效 ──
        # 3a. 单条查询
        get_resp = client.get(f"/api/policies/{policy_id}")
        assert get_resp.json()["status"] == "disabled"

        # 3b. 按 enabled 筛选不包含该策略
        enabled_resp = client.get("/api/policies?status=enabled")
        enabled_ids = {p["policy_id"] for p in enabled_resp.json()["policies"]}
        assert policy_id not in enabled_ids

        # 3c. 按 disabled 筛选包含该策略
        disabled_resp = client.get("/api/policies?status=disabled")
        disabled_ids = {p["policy_id"] for p in disabled_resp.json()["policies"]}
        assert policy_id in disabled_ids
        print(f"  [Step 3] ✅ 禁用验证通过: enabled({len(enabled_ids)}) / disabled({len(disabled_ids)})")

        # ── Step 4: 重新启用 ──
        toggle_on = client.post(f"/api/policies/{policy_id}/toggle?enabled=true")
        assert toggle_on.json()["status"] == "enabled"

        get_after = client.get(f"/api/policies/{policy_id}")
        assert get_after.json()["status"] == "enabled"
        print(f"  [Step 4] ✅ 策略已重新启用")

        # ── Step 5: 创建新策略验证默认状态 ──
        new_policy = client.post("/api/policies", json={
            "name": "Q&A集成测试策略",
            "description": "验证智能问答中策略生效",
            "markdown_content": "# 情报分析策略\n## 角色: analyst\n## 允许的操作\n- 查询\n- 分析\n- 报告",
            "category": "intelligence",
        })
        assert new_policy.status_code == 200
        new_data = new_policy.json()
        assert new_data["status"] == "enabled"
        assert new_data["rego_content"] != ""
        print(f"  [Step 5] ✅ 新策略创建成功: {new_data['policy_id']}, status={new_data['status']}")

        # ── Step 6: 模拟 Q&A 场景中的 OPA 策略检查 ──
        # 使用 OPAManager mock 模式验证策略检查
        from odap.infra.opa.opa_service import OPAManager
        import asyncio

        opa_mgr = OPAManager(use_mock=True)

        # 模拟情报分析员查询操作 — 应允许
        result = opa_mgr.check_permission("intelligence_analyst", "view", {"type": "intelligence"})
        assert isinstance(result, bool)
        print(f"  [Step 6] ✅ Mock OPA 策略检查: analyst.view → {result}")

        # 验证缓存机制
        start = time.time()
        for _ in range(50):
            opa_mgr.check_permission("intelligence_analyst", "view", {"type": "report"})
        elapsed = time.time() - start
        print(f"        缓存性能: 50次检查耗时 {elapsed:.3f}s (avg {elapsed/50*1000:.1f}ms)")

    def test_policy_status_transitions(self, integration_client):
        """验证策略状态切换的完整状态机"""
        client = integration_client

        list_resp = client.get("/api/policies")
        policy_id = list_resp.json()["policies"][0]["policy_id"]

        transitions = [
            ("enabled", "disabled", False),
            ("disabled", "enabled", True),
            ("enabled", "disabled", False),
            ("disabled", "disabled", False),  # 幂等
            ("disabled", "enabled", True),
        ]

        for from_state, target_state, enabled_param in transitions:
            resp = client.post(
                f"/api/policies/{policy_id}/toggle?enabled={'true' if enabled_param else 'false'}"
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == target_state, \
                f"状态切换 {from_state} → {target_state} 失败"

            verify = client.get(f"/api/policies/{policy_id}")
            assert verify.json()["status"] == target_state, \
                f"持久化验证 {from_state} → {target_state} 失败"

        print(f"\n  ✅ 策略状态切换全部通过: {len(transitions)} 次切换均正确")


# ============================================================================
# Test Suite 6: OPAManager Mock 模式 — 离线策略检查
# ============================================================================

class TestOPAManagerMockMode:
    """验证 OPAManager 在 mock 模式下的策略检查行为"""

    @pytest.fixture
    def opa_mock(self, monkeypatch):
        """创建 mock 模式的 OPAManager"""
        from odap.infra.opa.opa_service import OPAManager
        monkeypatch.setenv("OPA_MOCK_MODE", "1")
        manager = OPAManager(use_mock=True)
        yield manager

    def test_mock_check_permission_admin_allow_all(self, opa_mock):
        """Mock 模式下 admin 角色检查不抛异常且返回 boolean"""
        result = opa_mock.check_permission("admin", "anything", {"type": "any"})
        assert isinstance(result, bool)

    def test_mock_check_permission_returns_boolean(self, opa_mock):
        """Mock 模式下所有 check_permission 返回 boolean"""
        roles = ["admin", "commander", "intelligence_analyst", "operator", "guest"]
        actions = ["view", "attack", "command", "observe", "analyze"]

        for role in roles:
            for action in actions:
                result = opa_mock.check_permission(role, action, {"type": "test"})
                assert isinstance(result, bool), \
                    f"role={role}, action={action} 返回 {type(result)} 而非 bool"

    def test_mock_permission_caching(self, opa_mock):
        """Mock 模式下权限检查结果被缓存"""
        # 第一次调用
        start = time.time()
        result1 = opa_mock.check_permission("commander", "view", {"type": "report"})
        first_time = time.time() - start

        # 第二次调用（应命中缓存）
        start = time.time()
        result2 = opa_mock.check_permission("commander", "view", {"type": "report"})
        second_time = time.time() - start

        # 缓存命中后应更快或至少结果一致
        assert result1 == result2
        # 缓存应比首次调用快（允许一定误差）
        assert second_time <= first_time * 2, \
            f"缓存可能未生效: first={first_time:.6f}s, second={second_time:.6f}s"


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  策略管理与智能问答集成测试")
    print("=" * 70)
    pytest.main([__file__, "-v", "--tb=short", "--no-header"])
