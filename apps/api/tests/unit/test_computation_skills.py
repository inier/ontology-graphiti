"""
计算推理技能模块单元测试

测试 odap/tools/computation/computation.py 中的所有函数：
- calculate_distance: 有效实体 / 不存在实体
- predict_outcome: 不同目标类型和状态
- analyze_threat_level: 带区域和不带区域
- calculate_strike_damage: 有效武器/目标 / 不存在的武器或目标

Mock 策略：GraphManager 和 load_simulation_data 均需 mock。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 公共 mock 数据
# ---------------------------------------------------------------------------

_MOCK_SIMULATION_DATA = {
    "locations": [
        {"id": "loc-1", "properties": {"coordinates": [10, 20]}},
        {"id": "loc-2", "properties": {"coordinates": [30, 40]}},
    ],
    "units": [
        {
            "id": "unit-1",
            "properties": {
                "name": "1st Brigade",
                "affiliation": "Blue Force",
                "strength": 100,
                "area": "A",
                "armor": 30,
            },
        },
        {
            "id": "unit-2",
            "properties": {
                "name": "Red Battalion",
                "affiliation": "Red Force",
                "strength": 80,
                "area": "B",
                "armor": 20,
            },
        },
    ],
    "equipment": [
        {
            "id": "weapon-1",
            "properties": {
                "name": "Radar Alpha",
                "type": "雷达",
                "affiliation": "Red Force",
                "power": 50,
                "status": "正常",
                "area": "B",
            },
        },
        {
            "id": "weapon-2",
            "properties": {
                "name": "Artillery Beta",
                "type": "火炮",
                "affiliation": "Blue Force",
                "power": 80,
                "status": "正常",
                "area": "A",
            },
        },
    ],
    "civilian_infrastructures": [],
    "events": [],
}


# ---------------------------------------------------------------------------
# TestCalculateDistance
# ---------------------------------------------------------------------------


class TestCalculateDistance:
    """测试 calculate_distance 函数"""

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_valid_entities_from_graph(self, mock_manager, mock_load):
        """从图谱获取两个有效实体并计算距离"""
        mock_manager.get_entity.side_effect = [
            {"id": "loc-1", "properties": {"coordinates": [0, 0]}},
            {"id": "loc-2", "properties": {"coordinates": [3, 4]}},
        ]

        from odap.tools.computation.computation import calculate_distance

        result = calculate_distance("loc-1", "loc-2")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["distance"] == 5.0
        assert result["unit"] == "km"

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_valid_entities_fallback_simulation(self, mock_manager, mock_load):
        """图谱失败后降级到模拟数据计算距离"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import calculate_distance

        result = calculate_distance("loc-1", "loc-2")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["distance"] > 0

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_nonexistent_entity(self, mock_manager, mock_load):
        """实体不存在时返回错误"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import calculate_distance

        result = calculate_distance("nonexistent-1", "nonexistent-2")

        assert result["status"] == "error"
        assert "不存在" in result["message"]


# ---------------------------------------------------------------------------
# TestPredictOutcome
# ---------------------------------------------------------------------------


class TestPredictOutcome:
    """测试 predict_outcome 函数"""

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_radar_target_from_graph(self, mock_manager, mock_load):
        """雷达目标有较高成功率"""
        mock_manager.get_entity.return_value = {
            "id": "weapon-1",
            "properties": {"type": "雷达", "status": "正常"},
        }

        from odap.tools.computation.computation import predict_outcome

        result = predict_outcome("missile", "weapon-1")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["predicted_success_rate"] == 0.85
        # 0.85 不小于 0.85，所以 risk_level 是 "low"
        assert result["risk_level"] == "low"

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_hospital_target_high_success(self, mock_manager, mock_load):
        """医院目标有最高成功率"""
        mock_manager.get_entity.return_value = {
            "id": "civ-1",
            "properties": {"type": "医院", "status": "正常"},
        }

        from odap.tools.computation.computation import predict_outcome

        result = predict_outcome("airstrike", "civ-1")

        assert result["status"] == "success"
        assert result["predicted_success_rate"] == 0.95

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_command_center_target(self, mock_manager, mock_load):
        """指挥中心目标成功率较低"""
        mock_manager.get_entity.return_value = {
            "id": "hq-1",
            "properties": {"type": "指挥中心", "status": "正常"},
        }

        from odap.tools.computation.computation import predict_outcome

        result = predict_outcome("missile", "hq-1")

        assert result["status"] == "success"
        assert result["predicted_success_rate"] == 0.6
        assert result["risk_level"] == "high"

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_damaged_target_increases_rate(self, mock_manager, mock_load):
        """受损目标增加成功率"""
        mock_manager.get_entity.return_value = {
            "id": "weapon-1",
            "properties": {"type": "雷达", "status": "受损"},
        }

        from odap.tools.computation.computation import predict_outcome

        result = predict_outcome("missile", "weapon-1")

        assert result["status"] == "success"
        # 受损加0.1: 0.85 + 0.1 = 0.95
        assert result["predicted_success_rate"] == 0.95

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_destroyed_target_zero_rate(self, mock_manager, mock_load):
        """已摧毁目标成功率为0"""
        mock_manager.get_entity.return_value = {
            "id": "weapon-1",
            "properties": {"type": "雷达", "status": "摧毁"},
        }

        from odap.tools.computation.computation import predict_outcome

        result = predict_outcome("missile", "weapon-1")

        assert result["status"] == "success"
        assert result["predicted_success_rate"] == 0.0

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_target_not_found_fallback(self, mock_manager, mock_load):
        """目标不存在时返回错误"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import predict_outcome

        result = predict_outcome("missile", "nonexistent")

        assert result["status"] == "error"
        assert "不存在" in result["message"]


# ---------------------------------------------------------------------------
# TestAnalyzeThreatLevel
# ---------------------------------------------------------------------------


class TestAnalyzeThreatLevel:
    """测试 analyze_threat_level 函数"""

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_without_area_from_graph(self, mock_manager, mock_load):
        """不带区域参数从图谱获取威胁等级"""
        mock_manager.query_entities.side_effect = [
            # MilitaryUnit
            [
                {
                    "id": "unit-2",
                    "properties": {
                        "affiliation": "Red Force",
                        "strength": 80,
                        "name": "Red Battalion",
                    },
                },
            ],
            # WeaponSystem
            [
                {
                    "id": "weapon-1",
                    "properties": {
                        "affiliation": "Red Force",
                        "power": 50,
                        "name": "Radar Alpha",
                    },
                },
            ],
        ]

        from odap.tools.computation.computation import analyze_threat_level

        result = analyze_threat_level()

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["threat_level"] in ("low", "medium", "high", "critical")
        assert result["threat_score"] > 0

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_with_area_fallback_simulation(self, mock_manager, mock_load):
        """带区域参数降级到模拟数据"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import analyze_threat_level

        result = analyze_threat_level(area="B")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["area"] == "B"

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_no_area_defaults_to_all(self, mock_manager, mock_load):
        """不带区域时默认为全部区域"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import analyze_threat_level

        result = analyze_threat_level()

        assert result["area"] == "全部区域"


# ---------------------------------------------------------------------------
# TestCalculateStrikeDamage
# ---------------------------------------------------------------------------


class TestCalculateStrikeDamage:
    """测试 calculate_strike_damage 函数"""

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_valid_weapon_and_target_from_graph(self, mock_manager, mock_load):
        """从图谱获取有效武器和目标计算毁伤"""
        mock_manager.get_entity.side_effect = [
            {"id": "weapon-2", "properties": {"name": "Artillery", "power": 80}},
            {"id": "unit-2", "properties": {"name": "Red Battalion", "armor": 20}},
        ]

        from odap.tools.computation.computation import calculate_strike_damage

        result = calculate_strike_damage("weapon-2", "unit-2")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["damage_percent"] > 0
        assert result["damage_level"] in ("轻微", "中等", "严重", "摧毁")

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_valid_weapon_and_target_fallback(self, mock_manager, mock_load):
        """降级到模拟数据计算毁伤"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import calculate_strike_damage

        result = calculate_strike_damage("weapon-2", "unit-1")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["damage_percent"] > 0

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_nonexistent_weapon(self, mock_manager, mock_load):
        """武器不存在时返回错误"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import calculate_strike_damage

        result = calculate_strike_damage("nonexistent-weapon", "unit-1")

        assert result["status"] == "error"
        assert "不存在" in result["message"]

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_nonexistent_target(self, mock_manager, mock_load):
        """目标不存在时返回错误"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.computation.computation import calculate_strike_damage

        result = calculate_strike_damage("weapon-1", "nonexistent-target")

        assert result["status"] == "error"
        assert "不存在" in result["message"]

    @patch("odap.tools.computation.computation.load_simulation_data")
    @patch("odap.tools.computation.computation.manager")
    def test_damage_level_light(self, mock_manager, mock_load):
        """低伤害等级（damage_percent < 30）"""
        mock_manager.get_entity.side_effect = [
            {"id": "w-low", "properties": {"name": "Weak Weapon", "power": 20}},
            {"id": "t-heavy", "properties": {"name": "Heavy Target", "armor": 50}},
        ]

        from odap.tools.computation.computation import calculate_strike_damage

        result = calculate_strike_damage("w-low", "t-heavy")

        assert result["status"] == "success"
        # power=20, armor=50: damage = 20*0.8 - 50*0.3 = 16-15 = 1, percent = 1%
        assert result["damage_level"] == "轻微"
