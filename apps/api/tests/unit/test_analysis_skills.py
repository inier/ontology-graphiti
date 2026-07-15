"""
分析技能模块单元测试

测试 odap/tools/analysis/analysis.py 中的所有函数：
- analyze_entity_status: 按 entity_id / entity_type / 无参数查询
- analyze_battle_events: 带时间范围和不带时间范围
- analyze_force_comparison: 带区域和不带区域
- analyze_weapon_capabilities: 带武器类型和不带武器类型
- analyze_civilian_infrastructure: 民用基础设施分析
- get_domain_summary: 领域态势摘要

Mock 策略：GraphManager 和 load_simulation_data 均需 mock，
因为函数先尝试图谱查询，失败后降级到模拟数据。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# 公共 mock 数据
# ---------------------------------------------------------------------------

_MOCK_SIMULATION_DATA = {
    "locations": [
        {"id": "loc-1", "properties": {"name": "Alpha Base", "coordinates": [10, 20]}},
    ],
    "units": [
        {
            "id": "unit-1",
            "properties": {
                "name": "1st Brigade",
                "affiliation": "Blue Force",
                "strength": 100,
                "area": "A",
            },
        },
        {
            "id": "unit-2",
            "properties": {
                "name": "Red Battalion",
                "affiliation": "Red Force",
                "strength": 80,
                "area": "B",
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
                "range": 200,
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
                "range": 100,
                "power": 80,
                "status": "正常",
                "area": "A",
            },
        },
    ],
    "civilian_infrastructures": [
        {
            "id": "civ-1",
            "properties": {
                "name": "City Hospital",
                "type": "hospital",
                "area": "A",
                "protected": True,
            },
        },
        {
            "id": "civ-2",
            "properties": {
                "name": "Power Plant",
                "type": "power_plant",
                "area": "B",
                "protected": False,
            },
        },
    ],
    "events": [
        {
            "id": "evt-1",
            "timestamp": "2026-01-01T10:00:00",
            "properties": {"type": "radar_detection"},
        },
        {
            "id": "evt-2",
            "timestamp": "2026-01-02T12:00:00",
            "properties": {"type": "enemy_reinforcement"},
        },
    ],
}


# ---------------------------------------------------------------------------
# TestAnalyzeEntityStatus
# ---------------------------------------------------------------------------


class TestAnalyzeEntityStatus:
    """测试 analyze_entity_status 函数"""

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_entity_id_from_graph(self, mock_manager, mock_load):
        """通过 entity_id 从图谱成功获取实体"""
        mock_manager.get_entity.return_value = {
            "id": "unit-1",
            "properties": {"name": "1st Brigade"},
        }

        from odap.tools.analysis.analysis import analyze_entity_status

        result = analyze_entity_status(entity_id="unit-1")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["entity"]["id"] == "unit-1"
        mock_load.assert_not_called()

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_entity_id_fallback_simulation(self, mock_manager, mock_load):
        """图谱查询失败后降级到模拟数据，按 entity_id 查找"""
        mock_manager.get_entity.return_value = None
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_entity_status

        result = analyze_entity_status(entity_id="unit-1")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["entity"]["id"] == "unit-1"

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_entity_id_not_found(self, mock_manager, mock_load):
        """entity_id 在模拟数据中也不存在时返回错误"""
        mock_manager.get_entity.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_entity_status

        result = analyze_entity_status(entity_id="nonexistent")

        assert result["status"] == "error"
        assert "不存在" in result["message"]

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_entity_type_from_graph(self, mock_manager, mock_load):
        """通过 entity_type 从图谱成功获取实体列表"""
        mock_manager.query_entities.return_value = [
            {"id": "unit-1", "properties": {"name": "1st Brigade"}},
            {"id": "unit-2", "properties": {"name": "Red Battalion"}},
        ]

        from odap.tools.analysis.analysis import analyze_entity_status

        result = analyze_entity_status(entity_type="MilitaryUnit")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["count"] == 2

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_entity_type_fallback_simulation(self, mock_manager, mock_load):
        """图谱查询失败后降级到模拟数据，按 entity_type 查找"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_entity_status

        result = analyze_entity_status(entity_type="MilitaryUnit")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["count"] == 2

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_no_args_returns_error(self, mock_manager, mock_load):
        """不提供 entity_id 和 entity_type 时返回错误"""
        from odap.tools.analysis.analysis import analyze_entity_status

        result = analyze_entity_status()

        assert result["status"] == "error"
        assert "请提供" in result["message"]


# ---------------------------------------------------------------------------
# TestAnalyzeBattleEvents
# ---------------------------------------------------------------------------


class TestAnalyzeBattleEvents:
    """测试 analyze_battle_events 函数"""

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_without_time_range_from_graph(self, mock_manager, mock_load):
        """不带时间范围从图谱获取事件"""
        mock_manager.query_entities.return_value = [
            {"id": "evt-1", "type": "skirmish"},
            {"id": "evt-2", "type": "skirmish"},
        ]

        from odap.tools.analysis.analysis import analyze_battle_events

        result = analyze_battle_events()

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["total_events"] == 2

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_time_range_from_graph(self, mock_manager, mock_load):
        """带时间范围从图谱获取事件"""
        mock_manager.query_temporal.return_value = [
            {"id": "evt-1", "type": "raid"},
        ]

        from odap.tools.analysis.analysis import analyze_battle_events

        result = analyze_battle_events(time_range="2026-01-01")

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        mock_manager.query_temporal.assert_called_once_with(valid_time="2026-01-01")

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_fallback_simulation_without_time_range(self, mock_manager, mock_load):
        """图谱失败后降级到模拟数据，不带时间范围"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_battle_events

        result = analyze_battle_events()

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["total_events"] == 2

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_fallback_simulation_with_time_range(self, mock_manager, mock_load):
        """图谱失败后降级到模拟数据，带时间范围过滤"""
        mock_manager.query_temporal.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_battle_events

        result = analyze_battle_events(time_range="2026-01-02")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        # 只有 evt-2 的 timestamp >= "2026-01-02"
        assert result["total_events"] == 1


# ---------------------------------------------------------------------------
# TestAnalyzeForceComparison
# ---------------------------------------------------------------------------


class TestAnalyzeForceComparison:
    """测试 analyze_force_comparison 函数"""

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_without_area_from_graph(self, mock_manager, mock_load):
        """不带区域参数从图谱获取力量对比"""
        mock_manager.query_entities.side_effect = [
            # 第一次调用: MilitaryUnit
            [
                {
                    "id": "unit-1",
                    "properties": {"affiliation": "Blue Force", "strength": 100},
                },
                {
                    "id": "unit-2",
                    "properties": {"affiliation": "Red Force", "strength": 80},
                },
            ],
            # 第二次调用: WeaponSystem
            [
                {
                    "id": "weapon-1",
                    "properties": {"affiliation": "Red Force", "power": 50},
                },
            ],
        ]

        from odap.tools.analysis.analysis import analyze_force_comparison

        result = analyze_force_comparison()

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert "force_comparison" in result
        assert result["dominant_force"] is not None

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_area_fallback_simulation(self, mock_manager, mock_load):
        """带区域参数降级到模拟数据"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_force_comparison

        result = analyze_force_comparison(area="A")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["area"] == "A"

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_no_area_defaults_to_all(self, mock_manager, mock_load):
        """不带区域时默认为全部区域"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_force_comparison

        result = analyze_force_comparison()

        assert result["area"] == "全部区域"


# ---------------------------------------------------------------------------
# TestAnalyzeWeaponCapabilities
# ---------------------------------------------------------------------------


class TestAnalyzeWeaponCapabilities:
    """测试 analyze_weapon_capabilities 函数"""

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_without_weapon_type_from_graph(self, mock_manager, mock_load):
        """不带武器类型从图谱获取武器能力"""
        mock_manager.query_entities.return_value = [
            {
                "id": "weapon-1",
                "properties": {
                    "name": "Radar Alpha",
                    "type": "雷达",
                    "affiliation": "Red Force",
                    "range": 200,
                    "power": 50,
                    "status": "正常",
                },
            },
        ]

        from odap.tools.analysis.analysis import analyze_weapon_capabilities

        result = analyze_weapon_capabilities()

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["total_weapons"] == 1
        assert result["most_powerful"] is not None

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_with_weapon_type_fallback_simulation(self, mock_manager, mock_load):
        """带武器类型过滤降级到模拟数据"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_weapon_capabilities

        result = analyze_weapon_capabilities(weapon_type="雷达")

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        # 模拟数据中只有1个雷达
        assert result["total_weapons"] == 1

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_sorted_by_power(self, mock_manager, mock_load):
        """武器能力按 power 降序排列"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_weapon_capabilities

        result = analyze_weapon_capabilities()

        capabilities = result["capabilities"]
        for i in range(len(capabilities) - 1):
            assert capabilities[i]["power"] >= capabilities[i + 1]["power"]


# ---------------------------------------------------------------------------
# TestAnalyzeCivilianInfrastructure
# ---------------------------------------------------------------------------


class TestAnalyzeCivilianInfrastructure:
    """测试 analyze_civilian_infrastructure 函数"""

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_from_graph(self, mock_manager, mock_load):
        """从图谱获取民用基础设施"""
        mock_manager.query_entities.return_value = [
            {
                "id": "civ-1",
                "properties": {"type": "hospital", "area": "A", "protected": True},
            },
            {
                "id": "civ-2",
                "properties": {"type": "power_plant", "area": "B", "protected": False},
            },
        ]

        from odap.tools.analysis.analysis import analyze_civilian_infrastructure

        result = analyze_civilian_infrastructure()

        assert result["status"] == "success"
        assert result["data_source"] == "graph"
        assert result["total"] == 2
        assert result["protected_count"] == 1

    @patch("odap.tools.analysis.analysis.load_simulation_data")
    @patch("odap.tools.analysis.analysis.manager")
    def test_fallback_simulation(self, mock_manager, mock_load):
        """图谱失败后降级到模拟数据"""
        mock_manager.query_entities.side_effect = Exception("graph error")
        mock_load.return_value = _MOCK_SIMULATION_DATA

        from odap.tools.analysis.analysis import analyze_civilian_infrastructure

        result = analyze_civilian_infrastructure()

        assert result["status"] == "success"
        assert result["data_source"] == "simulation"
        assert result["total"] == 2
        assert "by_type" in result
        assert "by_area" in result
        assert result["protected_count"] == 1
        assert "civ-1" in result["protected_ids"]


# ---------------------------------------------------------------------------
# TestGetDomainSummary
# ---------------------------------------------------------------------------


class TestGetDomainSummary:
    """测试 get_domain_summary 函数"""

    @patch("odap.tools.analysis.analysis.manager")
    def test_returns_summary(self, mock_manager):
        """返回领域态势摘要"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 42,
            "entity_types": {"MilitaryUnit": 10, "WeaponSystem": 5},
            "mode": "networkx",
        }

        from odap.tools.analysis.analysis import get_domain_summary

        result = get_domain_summary()

        assert result["status"] == "success"
        assert result["total_entities"] == 42
        assert result["entity_types"]["MilitaryUnit"] == 10
        assert result["graph_mode"] == "networkx"
        assert len(result["recommendations"]) == 3

    @patch("odap.tools.analysis.analysis.manager")
    def test_empty_graph(self, mock_manager):
        """空图谱时仍返回成功"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
            "mode": "unknown",
        }

        from odap.tools.analysis.analysis import get_domain_summary

        result = get_domain_summary()

        assert result["status"] == "success"
        assert result["total_entities"] == 0
