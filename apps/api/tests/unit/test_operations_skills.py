"""
执行技能模块单元测试

测试 odap/tools/operations/operations.py 中的所有函数：
- attack_target: 存在/不存在目标，允许/拒绝权限
- command_unit: 存在/不存在部队，允许/拒绝权限

Mock 策略：GraphManager 和 OPAManager 均需 mock。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# TestAttackTarget
# ---------------------------------------------------------------------------


class TestAttackTarget:
    """测试 attack_target 函数"""

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_existing_target_allowed(self, mock_manager, mock_opa):
        """目标存在且权限允许时攻击成功"""
        mock_manager.query_entities.return_value = [
            {
                "id": "target-1",
                "properties": {"name": "Enemy Radar"},
            },
        ]
        mock_opa.check_permission.return_value = True

        from odap.tools.operations.operations import attack_target

        result = attack_target("target-1", "commander")

        assert result["status"] == "success"
        assert "Enemy Radar" in result["message"]
        assert result["user_role"] == "commander"
        mock_opa.check_permission.assert_called_once_with(
            "commander", "attack",
            {"id": "target-1", "properties": {"name": "Enemy Radar"}},
        )

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_existing_target_denied(self, mock_manager, mock_opa):
        """目标存在但权限拒绝时返回 denied"""
        mock_manager.query_entities.return_value = [
            {
                "id": "target-1",
                "properties": {"name": "Enemy Radar"},
            },
        ]
        mock_opa.check_permission.return_value = False

        from odap.tools.operations.operations import attack_target

        result = attack_target("target-1", "analyst")

        assert result["status"] == "denied"
        assert "权限不足" in result["message"]

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_nonexistent_target(self, mock_manager, mock_opa):
        """目标不存在时返回 denied（fail-close 策略）"""
        mock_manager.query_entities.return_value = []

        from odap.tools.operations.operations import attack_target

        result = attack_target("nonexistent", "commander")

        assert result["status"] == "denied"
        assert "不存在" in result["message"]
        # 目标不存在时不应调用 OPA
        mock_opa.check_permission.assert_not_called()

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_multiple_entities_find_correct(self, mock_manager, mock_opa):
        """多个实体中正确找到目标"""
        mock_manager.query_entities.return_value = [
            {"id": "other-1", "properties": {"name": "Other"}},
            {"id": "target-1", "properties": {"name": "Enemy Radar"}},
        ]
        mock_opa.check_permission.return_value = True

        from odap.tools.operations.operations import attack_target

        result = attack_target("target-1", "commander")

        assert result["status"] == "success"
        assert result["target"]["id"] == "target-1"


# ---------------------------------------------------------------------------
# TestCommandUnit
# ---------------------------------------------------------------------------


class TestCommandUnit:
    """测试 command_unit 函数"""

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_existing_unit_allowed(self, mock_manager, mock_opa):
        """部队存在且权限允许时指挥成功"""
        mock_manager.query_entities.return_value = [
            {
                "id": "unit-1",
                "properties": {"name": "1st Brigade"},
            },
        ]
        mock_opa.check_permission.return_value = True

        from odap.tools.operations.operations import command_unit

        result = command_unit("unit-1", "前进", "commander")

        assert result["status"] == "success"
        assert "1st Brigade" in result["message"]
        assert result["command"] == "前进"
        assert result["user_role"] == "commander"

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_existing_unit_denied(self, mock_manager, mock_opa):
        """部队存在但权限拒绝时返回 denied"""
        mock_manager.query_entities.return_value = [
            {
                "id": "unit-1",
                "properties": {"name": "1st Brigade"},
            },
        ]
        mock_opa.check_permission.return_value = False

        from odap.tools.operations.operations import command_unit

        result = command_unit("unit-1", "前进", "analyst")

        assert result["status"] == "denied"
        assert "权限不足" in result["message"]

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_nonexistent_unit(self, mock_manager, mock_opa):
        """部队不存在时返回 denied"""
        mock_manager.query_entities.return_value = []

        from odap.tools.operations.operations import command_unit

        result = command_unit("nonexistent", "前进", "commander")

        assert result["status"] == "denied"
        assert "不存在" in result["message"]
        mock_opa.check_permission.assert_not_called()

    @patch("odap.tools.operations.operations.opa_manager")
    @patch("odap.tools.operations.operations.manager")
    def test_command_stored_in_result(self, mock_manager, mock_opa):
        """命令内容正确保存在结果中"""
        mock_manager.query_entities.return_value = [
            {"id": "unit-1", "properties": {"name": "1st Brigade"}},
        ]
        mock_opa.check_permission.return_value = True

        from odap.tools.operations.operations import command_unit

        result = command_unit("unit-1", "撤退", "commander")

        assert result["command"] == "撤退"
