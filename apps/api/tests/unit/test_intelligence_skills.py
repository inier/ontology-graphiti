"""
情报技能模块单元测试

测试 odap/tools/intelligence/intelligence.py 中的所有组件：
- RadarSearchSkill (BaseSkill 子类) execute 方法
- AnalyzeDomainSkill execute 方法
- search_radar 旧式接口
- analyze_domain 旧式接口

Mock 策略：GraphManager 需 mock。

AGENTS.md Rule 9: 新增模块必须同步新增测试文件。
"""

import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# TestRadarSearchSkill
# ---------------------------------------------------------------------------


class TestRadarSearchSkill:
    """测试 RadarSearchSkill (BaseSkill 子类)"""

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_execute_with_area(self, mock_manager):
        """带区域参数执行雷达搜索"""
        mock_manager.query_entities.return_value = [
            {
                "id": "weapon-1",
                "properties": {"type": "雷达", "name": "Radar Alpha"},
            },
            {
                "id": "weapon-2",
                "properties": {"type": "火炮", "name": "Artillery Beta"},
            },
        ]

        from odap.tools.intelligence.intelligence import RadarSearchSkill, RadarSearchInput

        skill = RadarSearchSkill()
        input_data = RadarSearchInput(area="B")
        result = skill.execute(input_data)

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["area"] == "B"
        assert result.data["radars"][0]["id"] == "weapon-1"
        mock_manager.query_entities.assert_called_once_with(
            entity_type="WeaponSystem", area="B"
        )

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_execute_without_area(self, mock_manager):
        """不带区域参数执行雷达搜索（全局搜索）"""
        mock_manager.query_entities.return_value = [
            {
                "id": "weapon-1",
                "properties": {"type": "雷达", "name": "Radar Alpha"},
            },
        ]

        from odap.tools.intelligence.intelligence import RadarSearchSkill, RadarSearchInput

        skill = RadarSearchSkill()
        input_data = RadarSearchInput()
        result = skill.execute(input_data)

        assert result.success is True
        assert result.data["count"] == 1
        assert result.data["area"] == "全局"

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_execute_no_radars(self, mock_manager):
        """搜索区域无雷达"""
        mock_manager.query_entities.return_value = [
            {
                "id": "weapon-2",
                "properties": {"type": "火炮", "name": "Artillery Beta"},
            },
        ]

        from odap.tools.intelligence.intelligence import RadarSearchSkill, RadarSearchInput

        skill = RadarSearchSkill()
        input_data = RadarSearchInput(area="C")
        result = skill.execute(input_data)

        assert result.success is True
        assert result.data["count"] == 0
        assert result.data["radars"] == []

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_metadata(self, mock_manager):
        """验证 RadarSearchSkill 元数据"""
        from odap.tools.intelligence.intelligence import RadarSearchSkill

        skill = RadarSearchSkill()
        assert skill.metadata.name == "search_radar"
        assert skill.metadata.category == "intelligence"
        assert skill.metadata.danger_level == "low"
        assert skill.metadata.requires_opa_check is False


# ---------------------------------------------------------------------------
# TestAnalyzeDomainSkill
# ---------------------------------------------------------------------------


class TestAnalyzeDomainSkill:
    """测试 AnalyzeDomainSkill (BaseSkill 子类)"""

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_execute_with_entities(self, mock_manager):
        """图谱有实体时生成动态推荐"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 10,
            "entity_types": {"WeaponSystem": 5, "Radar": 3, "Threat": 2},
        }

        from odap.tools.intelligence.intelligence import AnalyzeDomainSkill, SkillInput

        skill = AnalyzeDomainSkill()
        input_data = SkillInput()
        result = skill.execute(input_data)

        assert result.success is True
        assert result.data["total_entities"] == 10
        assert result.data["domain_status"] == "活跃"
        assert len(result.data["recommendations"]) > 0
        assert result.data["recommendations_source"] == "dynamic"

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_execute_empty_graph(self, mock_manager):
        """空图谱时推荐先摄入数据"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
        }

        from odap.tools.intelligence.intelligence import AnalyzeDomainSkill, SkillInput

        skill = AnalyzeDomainSkill()
        input_data = SkillInput()
        result = skill.execute(input_data)

        assert result.success is True
        assert result.data["total_entities"] == 0
        assert any("摄入数据" in r for r in result.data["recommendations"])

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_execute_no_special_entities(self, mock_manager):
        """无特殊实体类型时使用默认推荐"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 5,
            "entity_types": {"Location": 5},
        }

        from odap.tools.intelligence.intelligence import AnalyzeDomainSkill, SkillInput

        skill = AnalyzeDomainSkill()
        input_data = SkillInput()
        result = skill.execute(input_data)

        assert result.success is True
        assert any("暂无特别建议" in r for r in result.data["recommendations"])

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_metadata(self, mock_manager):
        """验证 AnalyzeDomainSkill 元数据"""
        from odap.tools.intelligence.intelligence import AnalyzeDomainSkill

        skill = AnalyzeDomainSkill()
        assert skill.metadata.name == "analyze_domain"
        assert skill.metadata.category == "intelligence"
        assert skill.metadata.danger_level == "low"


# ---------------------------------------------------------------------------
# TestLegacyFunctions
# ---------------------------------------------------------------------------


class TestLegacyFunctions:
    """测试旧式裸函数接口（向后兼容）"""

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_search_radar_returns_list(self, mock_manager):
        """search_radar 返回雷达列表"""
        mock_manager.query_entities.return_value = [
            {
                "id": "weapon-1",
                "properties": {"type": "雷达", "name": "Radar Alpha"},
            },
        ]

        from odap.tools.intelligence.intelligence import search_radar

        result = search_radar(area="B")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["id"] == "weapon-1"

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_search_radar_empty_result(self, mock_manager):
        """search_radar 无结果时返回空列表"""
        mock_manager.query_entities.return_value = []

        from odap.tools.intelligence.intelligence import search_radar

        result = search_radar(area="Z")

        assert isinstance(result, list)
        assert len(result) == 0

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_analyze_domain_returns_dict(self, mock_manager):
        """analyze_domain 返回态势分析字典"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 5,
            "entity_types": {"WeaponSystem": 5},
        }

        from odap.tools.intelligence.intelligence import analyze_domain

        result = analyze_domain()

        assert isinstance(result, dict)
        assert "total_entities" in result
        assert "recommendations" in result
        assert result["domain_status"] == "活跃"

    @patch("odap.tools.intelligence.intelligence.manager")
    def test_analyze_domain_empty_stats(self, mock_manager):
        """analyze_domain 空图谱时返回推荐"""
        mock_manager.get_graph_statistics.return_value = {
            "total_entities": 0,
            "entity_types": {},
        }

        from odap.tools.intelligence.intelligence import analyze_domain

        result = analyze_domain()

        assert isinstance(result, dict)
        assert result["total_entities"] == 0
