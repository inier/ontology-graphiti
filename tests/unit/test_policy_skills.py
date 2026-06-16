"""
策略技能模块单元测试

测试 odap/tools/policy/policy.py 中的所有函数：
- simulate_policy_execution: 有效/无效角色，允许/拒绝操作
- check_permission: OPA 权限检查
- export_policy / import_policy: 策略导出导入（使用 tmp_path）
- list_policy_versions: 列出策略版本
- get_policy_history / clear_policy_history: 策略执行历史

Mock 策略：OPAManager 需 mock，ROLES 使用 patch。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 公共 mock ROLES
# ---------------------------------------------------------------------------

_MOCK_ROLES = {
    "commander": {
        "permissions": [
            "view_intelligence",
            "request_support",
            "command_units",
            "authorize_attacks",
            "approve_missions",
        ],
        "restrictions": [],
    },
    "analyst": {
        "permissions": ["view_intelligence", "analyze_data", "generate_reports"],
        "restrictions": ["cannot_attack", "cannot_command"],
    },
    "field_operator": {
        "permissions": ["view_intelligence", "request_support"],
        "restrictions": ["cannot_attack", "cannot_command"],
    },
}

_MOCK_DOMAIN_CONFIG = {"description": "test config", "factions": [], "regions": []}


# ---------------------------------------------------------------------------
# TestSimulatePolicyExecution
# ---------------------------------------------------------------------------


class TestSimulatePolicyExecution:
    """测试 simulate_policy_execution 函数"""

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_valid_role_allowed_action(self):
        """有效角色且权限允许时操作成功"""
        from odap.tools.policy.policy import simulate_policy_execution

        result = simulate_policy_execution("commander", "command_units")

        assert result["allowed"] is True
        assert result["role"] == "commander"
        assert "有权执行" in result["reason"]

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_valid_role_denied_by_permission(self):
        """有效角色但缺少必要权限时操作被拒"""
        from odap.tools.policy.policy import simulate_policy_execution

        result = simulate_policy_execution("analyst", "command_units")

        assert result["allowed"] is False
        assert "缺少必要权限" in result["reason"]

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_valid_role_denied_by_restriction(self):
        """有效角色但被限制时操作被拒"""
        from odap.tools.policy.policy import simulate_policy_execution

        result = simulate_policy_execution("analyst", "attack")

        assert result["allowed"] is False
        assert "限制" in result["reason"]

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_invalid_role(self):
        """无效角色时操作被拒"""
        from odap.tools.policy.policy import simulate_policy_execution

        result = simulate_policy_execution("hacker", "attack")

        assert result["allowed"] is False
        assert "不存在" in result["reason"]

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_civilian_infrastructure_restriction(self):
        """攻击民用设施被限制 - 使用有攻击权限但受民用设施限制的角色"""
        # 需要一个有 authorize_attacks 权限且有 cannot_attack_civilian_infrastructure 限制的角色
        custom_roles = {
            "restricted_commander": {
                "permissions": [
                    "view_intelligence",
                    "authorize_attacks",
                ],
                "restrictions": ["cannot_attack_civilian_infrastructure"],
            },
        }
        with patch("odap.tools.policy.policy.ROLES", custom_roles):
            from odap.tools.policy.policy import simulate_policy_execution

            result = simulate_policy_execution(
                "restricted_commander", "attack", target_type="CivilianInfrastructure"
            )

            assert result["allowed"] is False
            assert "民用设施" in result["reason"]

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_result_appended_to_history(self):
        """执行结果被追加到历史记录"""
        from odap.tools.policy.policy import simulate_policy_execution, _policy_history

        initial_len = len(_policy_history)
        simulate_policy_execution("commander", "command_units")

        assert len(_policy_history) == initial_len + 1


# ---------------------------------------------------------------------------
# TestCheckPermission
# ---------------------------------------------------------------------------


class TestCheckPermission:
    """测试 check_permission 函数"""

    @patch("odap.tools.policy.policy.opa_manager")
    def test_allowed(self, mock_opa):
        """OPA 允许时返回 allowed=True"""
        mock_opa.check_permission.return_value = True

        from odap.tools.policy.policy import check_permission

        result = check_permission("commander", "attack", "WeaponSystem")

        assert result["status"] == "success"
        assert result["allowed"] is True
        assert result["message"] == "允许执行"

    @patch("odap.tools.policy.policy.opa_manager")
    def test_denied(self, mock_opa):
        """OPA 拒绝时返回 allowed=False"""
        mock_opa.check_permission.return_value = False

        from odap.tools.policy.policy import check_permission

        result = check_permission("analyst", "attack", "WeaponSystem")

        assert result["status"] == "success"
        assert result["allowed"] is False
        assert result["message"] == "拒绝执行"

    @patch("odap.tools.policy.policy.opa_manager")
    def test_passes_resource_type(self, mock_opa):
        """正确传递 resource_type 给 OPA"""
        mock_opa.check_permission.return_value = True

        from odap.tools.policy.policy import check_permission

        check_permission("commander", "command", "MilitaryUnit")

        mock_opa.check_permission.assert_called_once_with(
            "commander", "command", {"type": "MilitaryUnit"}
        )


# ---------------------------------------------------------------------------
# TestExportImportPolicy
# ---------------------------------------------------------------------------


class TestExportImportPolicy:
    """测试 export_policy 和 import_policy 函数"""

    @patch("odap.tools.policy.policy.DOMAIN_CONFIG", _MOCK_DOMAIN_CONFIG)
    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_export_policy(self, tmp_path):
        """导出策略到文件"""
        # 临时覆盖 _policy_dir
        import odap.tools.policy.policy as policy_mod

        original_dir = policy_mod._policy_dir
        policy_mod._policy_dir = str(tmp_path)

        try:
            from odap.tools.policy.policy import export_policy

            result = export_policy("test_policy", version="1.0.0", description="test")

            assert result["status"] == "success"
            assert os.path.exists(result["file"])

            with open(result["file"], "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["policy_name"] == "test_policy"
            assert data["version"] == "1.0.0"
        finally:
            policy_mod._policy_dir = original_dir

    @patch("odap.tools.policy.policy.DOMAIN_CONFIG", _MOCK_DOMAIN_CONFIG)
    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_import_policy_valid_file(self, tmp_path):
        """导入有效策略文件"""
        import odap.tools.policy.policy as policy_mod

        original_dir = policy_mod._policy_dir
        policy_mod._policy_dir = str(tmp_path)

        try:
            # 先创建一个有效策略文件
            policy_file = str(tmp_path / "test_policy.json")
            with open(policy_file, "w", encoding="utf-8") as f:
                json.dump({"policy_name": "test", "version": "1.0"}, f)

            from odap.tools.policy.policy import import_policy

            result = import_policy(policy_file)

            assert result["status"] == "success"
            assert "导入成功" in result["message"]
        finally:
            policy_mod._policy_dir = original_dir

    def test_import_policy_nonexistent_file(self):
        """导入不存在的文件返回错误"""
        from odap.tools.policy.policy import import_policy

        result = import_policy("/nonexistent/path/policy.json")

        assert result["status"] == "error"
        assert "导入失败" in result["message"]

    def test_import_policy_invalid_json(self, tmp_path):
        """导入无效 JSON 文件返回错误"""
        bad_file = str(tmp_path / "bad_policy.json")
        with open(bad_file, "w") as f:
            f.write("{invalid json")

        from odap.tools.policy.policy import import_policy

        result = import_policy(bad_file)

        assert result["status"] == "error"
        assert "导入失败" in result["message"]


# ---------------------------------------------------------------------------
# TestListPolicyVersions
# ---------------------------------------------------------------------------


class TestListPolicyVersions:
    """测试 list_policy_versions 函数"""

    @patch("odap.tools.policy.policy.DOMAIN_CONFIG", _MOCK_DOMAIN_CONFIG)
    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_list_with_policies(self, tmp_path):
        """有策略文件时正确列出"""
        import odap.tools.policy.policy as policy_mod

        original_dir = policy_mod._policy_dir
        policy_mod._policy_dir = str(tmp_path)

        try:
            # 创建策略文件
            from odap.tools.policy.policy import export_policy

            export_policy("alpha", version="1.0.0")
            export_policy("beta", version="2.0.0")

            from odap.tools.policy.policy import list_policy_versions

            result = list_policy_versions()

            assert result["status"] == "success"
            assert len(result["policies"]) == 2
        finally:
            policy_mod._policy_dir = original_dir

    def test_list_empty_directory(self, tmp_path):
        """空目录时返回空列表"""
        import odap.tools.policy.policy as policy_mod

        original_dir = policy_mod._policy_dir
        policy_mod._policy_dir = str(tmp_path)

        try:
            from odap.tools.policy.policy import list_policy_versions

            result = list_policy_versions()

            assert result["status"] == "success"
            assert result["policies"] == []
        finally:
            policy_mod._policy_dir = original_dir


# ---------------------------------------------------------------------------
# TestPolicyHistory
# ---------------------------------------------------------------------------


class TestPolicyHistory:
    """测试 get_policy_history 和 clear_policy_history 函数"""

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_get_history(self):
        """获取策略执行历史"""
        from odap.tools.policy.policy import (
            get_policy_history,
            clear_policy_history,
            simulate_policy_execution,
        )

        clear_policy_history()
        simulate_policy_execution("commander", "command_units")

        result = get_policy_history()

        assert result["status"] == "success"
        assert result["total"] >= 1
        assert len(result["history"]) >= 1

    @patch("odap.tools.policy.policy.ROLES", _MOCK_ROLES)
    def test_clear_history(self):
        """清除策略执行历史"""
        from odap.tools.policy.policy import (
            get_policy_history,
            clear_policy_history,
            simulate_policy_execution,
        )

        simulate_policy_execution("commander", "command_units")
        clear_policy_history()

        result = get_policy_history()

        assert result["status"] == "success"
        assert result["total"] == 0
        assert result["history"] == []
