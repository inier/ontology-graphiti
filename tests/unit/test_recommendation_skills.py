"""
推荐技能模块单元测试

测试 odap/tools/recommendation/recommendation.py 中的所有函数：
- recommend_strike_targets: 指挥官/非指挥官角色
- recommend_task_planning: 指挥官/分析师/其他角色
- recommend_force_deployment: 指挥官/非指挥官
- check_strike_risk: 不同目标归属的风险评估

Mock 策略：GraphManager 和 load_simulation_data 均需 mock。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 公共 mock 数据
# ---------------------------------------------------------------------------

_MOCK_SIMULATION_DATA = {
    "locations": [],
    "units": [
        {
            "id": "unit-blue",
            "properties": {
                "name": "Blue Brigade",
                "affiliation": "Blue Force",
                "strength": 100,
                "area": "A",
            },
        },
        {
            "id": "unit-red",
            "properties": {
                "name": "Red Battalion",
                "affiliation": "Red Force",
                "strength": 80,
                "area": "B",
            },
        },
        {
            "id": "unit-green",
            "properties": {
                "name": "Green Insurgents",
                "affiliation": "Green Insurgents",
                "strength": 50,
                "area": "C",
            },
        },
    ],
    "equipment": [
        {
            "id": "weapon-radar",
            "properties": {
                "name": "Enemy Radar",
                "type": "雷达",
                "affiliation": "Red Force",
                "status": "正常",
                "area": "B",
            },
        },
        {
            "id": "weapon-artillery",
            "properties": {
                "name": "Enemy Artillery",
                "type": "火炮",
                "affiliation": "Red Force",
                "status": "正常",
                "area": "B",
            },
        },
        {
            "id": "weapon-destroyed",
            "properties": {
                "name": "Destroyed Weapon",
                "type": "火炮",
                "affiliation": "Red Force",
                "status": "损毁",
                "area": "B",
            },
        },
    ],
    "civilian_infrastructures": [],
    "events": [
        {
            "id": "evt-1",
            "properties": {
                "type": "enemy_reinforcement",
                "timestamp": "2026-01-01T10:00:00",
            },
        },
        {
            "id": "evt-2",
            "properties": {
                "type": "radar_detection",
                "timestamp": "2026-01-02T12:00:00",
            },
        },
    ],
}


# ---------------------------------------------------------------------------
# TestRecommendStrikeTargets
# ---------------------------------------------------------------------------


class TestRecommendStrikeTargets:
    """测试 recommend_strike_targets 函数"""

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_commander_role_from_graph(self, mock_manager, mock_load):
        """指挥官角色从图谱获取打击目标"""
        mock_manager.query_entities.side_effect = [
            # WeaponSystem
            [
                {
                    "id": "weapon-radar",
                    "properties": {
                        "name": "Enemy Radar",
                        "type": "雷达",
                        "affiliation": "Red Force",
                        "status": "正常",
                        "area": "B",
                    },
                },
            ],
            # MilitaryUnit
            [
                {
                    "id": "unit-red",
                    "properties": {
                        "name": "Red Battalion",
                        "affiliation": "Red Force",
                        "area": "B",
                    },
                },
            ],
        ]

        from odap.tools.recommendation.recommendation import recommend_strike_targets

        result = recommend_strike_targets("commander")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["total"] > 0
        # 雷达应为高优先级
        radar_targets = [t for t in result["targets"] if t["type"] == "雷达"]
        assert len(radar_targets) > 0
        assert radar_targets[0]["priority"] == "high"

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_non_commander_denied(self, mock_manager, mock_load):
        """非指挥官角色被拒绝"""
        from odap.tools.recommendation.recommendation import recommend_strike_targets

        result = recommend_strike_targets("analyst")

        assert result["status"] == "denied"
        assert "指挥官" in result["message"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_commander_fallback_simulation(self, mock_manager, mock_load):
        """指挥官角色降级到模拟数据"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import recommend_strike_targets

        result = recommend_strike_targets("commander")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        # 损毁的武器不应出现
        destroyed = [t for t in result["targets"] if t["id"] == "weapon-destroyed"]
        assert len(destroyed) == 0

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_area_filter(self, mock_manager, mock_load):
        """按区域过滤打击目标"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import recommend_strike_targets

        result = recommend_strike_targets("commander", area="B")

        assert result["status"] == "success"
        for target in result["targets"]:
            assert target["area"] == "B"

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_target_type_filter(self, mock_manager, mock_load):
        """按目标类型过滤"""
        mock_manager.query_entities.side_effect = [
            [
                {
                    "id": "weapon-radar",
                    "properties": {
                        "name": "Enemy Radar",
                        "type": "雷达",
                        "affiliation": "Red Force",
                        "status": "正常",
                        "area": "B",
                    },
                },
                {
                    "id": "weapon-artillery",
                    "properties": {
                        "name": "Enemy Artillery",
                        "type": "火炮",
                        "affiliation": "Red Force",
                        "status": "正常",
                        "area": "B",
                    },
                },
            ],
            [],
        ]

        from odap.tools.recommendation.recommendation import recommend_strike_targets

        result = recommend_strike_targets("commander", target_type="雷达")

        assert result["status"] == "success"
        for target in result["targets"]:
            assert target["type"] == "雷达"


# ---------------------------------------------------------------------------
# TestRecommendTaskPlanning
# ---------------------------------------------------------------------------


class TestRecommendTaskPlanning:
    """测试 recommend_task_planning 函数"""

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_commander_role(self, mock_manager, mock_load):
        """指挥官角色获取任务规划推荐"""
        mock_manager.query_entities.return_value = [
            {
                "id": "evt-1",
                "properties": {
                    "type": "enemy_reinforcement",
                    "timestamp": "2026-01-01T10:00:00",
                },
            },
        ]

        from odap.tools.recommendation.recommendation import recommend_task_planning

        result = recommend_task_planning("commander")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert len(result["recommendations"]) > 0

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_analyst_role(self, mock_manager, mock_load):
        """分析师角色也能获取任务规划推荐"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import recommend_task_planning

        result = recommend_task_planning("intelligence_analyst")

        assert result["status"] == "success"

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_other_role_denied(self, mock_manager, mock_load):
        """其他角色被拒绝"""
        from odap.tools.recommendation.recommendation import recommend_task_planning

        result = recommend_task_planning("field_operator")

        assert result["status"] == "denied"
        assert "权限不足" in result["message"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_fallback_simulation(self, mock_manager, mock_load):
        """降级到模拟数据"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import recommend_task_planning

        result = recommend_task_planning("commander")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["recent_events_count"] > 0


# ---------------------------------------------------------------------------
# TestRecommendForceDeployment
# ---------------------------------------------------------------------------


class TestRecommendForceDeployment:
    """测试 recommend_force_deployment 函数"""

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_commander_from_graph(self, mock_manager, mock_load):
        """指挥官从图谱获取兵力部署推荐"""
        mock_manager.query_entities.side_effect = [
            # MilitaryUnit
            [
                {
                    "id": "unit-blue",
                    "properties": {"affiliation": "Blue Force", "area": "A"},
                },
                {
                    "id": "unit-red",
                    "properties": {"affiliation": "Red Force", "area": "A"},
                },
            ],
            # WeaponSystem
            [],
        ]

        from odap.tools.recommendation.recommendation import recommend_force_deployment

        result = recommend_force_deployment("commander", "A")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["deployment"]["area"] == "A"

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_non_commander_denied(self, mock_manager, mock_load):
        """非指挥官被拒绝"""
        from odap.tools.recommendation.recommendation import recommend_force_deployment

        result = recommend_force_deployment("analyst", "A")

        assert result["status"] == "denied"
        assert "指挥官" in result["message"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_fallback_blue_outnumbered(self, mock_manager, mock_load):
        """蓝方力量不足时建议增派"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import recommend_force_deployment

        result = recommend_force_deployment("commander", "B")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        # B区蓝方0个，红方1个
        assert result["deployment"]["current_blue_units"] == 0
        assert result["deployment"]["current_red_units"] == 1
        assert "增派" in result["deployment"]["recommendation"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_fallback_blue_sufficient(self, mock_manager, mock_load):
        """蓝方力量充足时建议维持或调离"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import recommend_force_deployment

        result = recommend_force_deployment("commander", "A")

        assert result["status"] == "success"
        # A区蓝方1个，红方0个
        assert result["deployment"]["current_blue_units"] == 1
        assert result["deployment"]["current_red_units"] == 0


# ---------------------------------------------------------------------------
# TestCheckStrikeRisk
# ---------------------------------------------------------------------------


class TestCheckStrikeRisk:
    """测试 check_strike_risk 函数"""

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_blue_force_critical_risk(self, mock_manager, mock_load):
        """友方目标为 critical 风险"""
        mock_manager.get_entity.return_value = {
            "id": "unit-blue",
            "properties": {
                "name": "Blue Brigade",
                "type": "军事单位",
                "affiliation": "Blue Force",
            },
        }

        from odap.tools.recommendation.recommendation import check_strike_risk

        result = check_strike_risk("unit-blue", "commander")

        assert result["status"] == "success"
        assert result["risk_level"] == "critical"
        assert "友方" in result["reason"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_civilian_high_risk(self, mock_manager, mock_load):
        """民用设施为 high 风险"""
        mock_manager.get_entity.return_value = {
            "id": "civ-1",
            "properties": {
                "name": "Hospital",
                "type": "医院",
                "affiliation": "CivilianInfrastructure",
            },
        }

        from odap.tools.recommendation.recommendation import check_strike_risk

        result = check_strike_risk("civ-1", "commander")

        assert result["status"] == "success"
        assert result["risk_level"] == "high"
        assert "民用" in result["reason"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_damaged_target_low_risk(self, mock_manager, mock_load):
        """受损目标为 low 风险"""
        mock_manager.get_entity.return_value = {
            "id": "weapon-1",
            "properties": {
                "name": "Damaged Radar",
                "type": "雷达",
                "affiliation": "Red Force",
                "status": "受损",
            },
        }

        from odap.tools.recommendation.recommendation import check_strike_risk

        result = check_strike_risk("weapon-1", "commander")

        assert result["status"] == "success"
        assert result["risk_level"] == "low"
        assert "受损" in result["reason"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_enemy_target_low_risk(self, mock_manager, mock_load):
        """敌方正常目标为 low 风险"""
        mock_manager.get_entity.return_value = {
            "id": "weapon-radar",
            "properties": {
                "name": "Enemy Radar",
                "type": "雷达",
                "affiliation": "Red Force",
                "status": "正常",
            },
        }

        from odap.tools.recommendation.recommendation import check_strike_risk

        result = check_strike_risk("weapon-radar", "commander")

        assert result["status"] == "success"
        assert result["risk_level"] == "low"
        assert "敌方" in result["reason"]

    @patch("odap.tools.recommendation.recommendation.load_simulation_data")
    @patch("odap.tools.recommendation.recommendation.manager")
    def test_target_not_found(self, mock_manager, mock_load):
        """目标不存在时返回错误"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.recommendation.recommendation import check_strike_risk

        result = check_strike_risk("nonexistent", "commander")

        assert result["status"] == "error"
        assert "不存在" in result["message"]
