"""
TDD Phase 2-3: 三国 + 西游 Skills 单元测试

行为: B2-5~B2-8 (三国Skills), B3-5~B3-8 (西游Skills)

运行方式:
  /c/Miniconda3/python.exe -m pytest tests/unit/test_domain_skills.py -v --tb=short
"""

import pytest
import os
import sys
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ============================================================
# B2-5~B2-8: 三国演义 Skills
# ============================================================

class TestSanguoSkills:
    """验证三国演义 Skills 的函数签名和行为"""

    def test_sanguo_timeline_exists(self):
        """B2-5a: sanguo_timeline 函数存在且可调用"""
        from odap.tools.agent_tools.sanguo_skills import sanguo_timeline
        assert callable(sanguo_timeline)

        # 无存储时返回错误信息（不抛异常）
        result = sanguo_timeline(start_year=184, end_year=200)
        assert "status" in result
        assert result["status"] in ("success", "error")

    def test_sanguo_faction_analysis_exists(self):
        """B2-6a: sanguo_faction_analysis 函数存在且可调用"""
        from odap.tools.agent_tools.sanguo_skills import sanguo_faction_analysis
        assert callable(sanguo_faction_analysis)

        result = sanguo_faction_analysis()
        assert "status" in result

    def test_sanguo_character_query_exists(self):
        """B2-7a: sanguo_character_query 函数存在，参数正确"""
        from odap.tools.agent_tools.sanguo_skills import sanguo_character_query
        assert callable(sanguo_character_query)

        # 验证函数签名参数
        sig = inspect.signature(sanguo_character_query)
        params = list(sig.parameters.keys())
        assert "name" in params
        assert "faction" in params
        assert "role" in params

        result = sanguo_character_query(name="刘备")
        assert "status" in result

    def test_sanguo_event_query_exists(self):
        """B2-8a: sanguo_event_query 函数存在，参数正确"""
        from odap.tools.agent_tools.sanguo_skills import sanguo_event_query
        assert callable(sanguo_event_query)

        sig = inspect.signature(sanguo_event_query)
        params = list(sig.parameters.keys())
        assert "name" in params, f"缺少 name 参数，实际: {params}"
        assert "year" in params, f"缺少 year 参数，实际: {params}"
        assert "category" in params, f"缺少 category 参数，实际: {params}"

        result = sanguo_event_query(year=208)
        assert "status" in result

    def test_sanguo_skills_registered(self):
        """B2-5b~B2-8b: 三国4个skill已注册到注册表"""
        from odap.tools.base import get_registry
        registry = get_registry()

        expected = [
            "sanguo_timeline",
            "sanguo_faction_analysis",
            "sanguo_character_query",
            "sanguo_event_query",
        ]
        for name in expected:
            assert name in registry, f"Skill {name} 未注册到注册表"

    def test_sanguo_timeline_default_params(self):
        """B2-5c: sanguo_timeline 默认参数合理（184-280）"""
        from odap.tools.agent_tools.sanguo_skills import sanguo_timeline

        # 默认参数应该在三国时间范围内
        sig = inspect.signature(sanguo_timeline)
        assert sig.parameters["start_year"].default == 184
        assert sig.parameters["end_year"].default == 280


# ============================================================
# B3-5~B3-8: 西游记 Skills
# ============================================================

class TestXiyouSkills:
    """验证西游记 Skills 的函数签名和行为"""

    def test_xiyou_timeline_exists(self):
        """B3-5a: xiyou_timeline 函数存在且可调用"""
        from odap.tools.agent_tools.xiyou_skills import xiyou_timeline
        assert callable(xiyou_timeline)

        result = xiyou_timeline(trial_start=1, trial_end=10)
        assert "status" in result
        assert result["status"] in ("success", "error")

    def test_xiyou_character_query_exists(self):
        """B3-6a: xiyou_character_query 函数存在，支持种族过滤"""
        from odap.tools.agent_tools.xiyou_skills import xiyou_character_query
        assert callable(xiyou_character_query)

        sig = inspect.signature(xiyou_character_query)
        params = list(sig.parameters.keys())
        assert "race" in params, f"缺少 race 参数，实际: {params}"
        assert "faction" in params, f"缺少 faction 参数，实际: {params}"

        result = xiyou_character_query(race="神仙")
        assert "status" in result

    def test_xiyou_treasure_query_exists(self):
        """B3-7a: xiyou_treasure_query 函数存在，支持类型过滤"""
        from odap.tools.agent_tools.xiyou_skills import xiyou_treasure_query
        assert callable(xiyou_treasure_query)

        sig = inspect.signature(xiyou_treasure_query)
        params = list(sig.parameters.keys())
        assert "treasure_type" in params, f"缺少 treasure_type 参数，实际: {params}"
        assert "holder" in params, f"缺少 holder 参数，实际: {params}"

        result = xiyou_treasure_query(holder="孙悟空")
        assert "status" in result

    def test_xiyou_spell_query_exists(self):
        """B3-8a: xiyou_spell_query 函数存在，支持类型过滤"""
        from odap.tools.agent_tools.xiyou_skills import xiyou_spell_query
        assert callable(xiyou_spell_query)

        sig = inspect.signature(xiyou_spell_query)
        params = list(sig.parameters.keys())
        assert "spell_type" in params, f"缺少 spell_type 参数，实际: {params}"
        assert "master" in params, f"缺少 master 参数，实际: {params}"

        result = xiyou_spell_query(spell_type="变化")
        assert "status" in result

    def test_xiyou_skills_registered(self):
        """B3-5b~B3-8b: 西游4个skill已注册到注册表"""
        from odap.tools.base import get_registry
        registry = get_registry()

        expected = [
            "xiyou_timeline",
            "xiyou_character_query",
            "xiyou_treasure_query",
            "xiyou_spell_query",
        ]
        for name in expected:
            assert name in registry, f"Skill {name} 未注册到注册表"

    def test_xiyou_timeline_trial_range(self):
        """B3-5c: xiyou_timeline 默认参数合理（1-81难）"""
        from odap.tools.agent_tools.xiyou_skills import xiyou_timeline

        sig = inspect.signature(xiyou_timeline)
        assert sig.parameters["trial_start"].default == 1
        assert sig.parameters["trial_end"].default == 81

    def test_xiyou_skills_have_chinese_descriptions(self):
        """B3-5d: 西游skills的描述包含中文"""
        from odap.tools.base import get_registry
        registry = get_registry()

        xiyou_skill_names = [
            "xiyou_timeline", "xiyou_character_query",
            "xiyou_treasure_query", "xiyou_spell_query",
        ]
        for name in xiyou_skill_names:
            skill = registry.get(name)
            assert skill is not None, f"Skill {name} 不存在"
            desc = skill.metadata.description
            # 描述应包含中文
            has_chinese = any('\u4e00' <= c <= '\u9fff' for c in desc)
            assert has_chinese, f"Skill {name} 描述应包含中文: {desc}"


# ============================================================
# B2/B3 Cross: 技能包模块级别验证
# ============================================================

class TestSkillPackages:
    """验证技能包模块级别正确性"""

    def test_sanguo_skills_module_loads(self):
        """三国技能包模块可正常导入"""
        try:
            import odap.tools.agent_tools.sanguo_skills
            assert True
        except Exception as e:
            pytest.fail(f"三国技能包导入失败: {e}")

    def test_xiyou_skills_module_loads(self):
        """西游技能包模块可正常导入"""
        try:
            import odap.tools.agent_tools.xiyou_skills
            assert True
        except Exception as e:
            pytest.fail(f"西游技能包导入失败: {e}")

    def test_sanguo_registered_count(self):
        """三国至少注册4个skills"""
        from odap.tools.base import get_registry
        registry = get_registry()

        sanguo_skills = [s for s in registry.list_skills()
                         if s["name"].startswith("sanguo_")]
        assert len(sanguo_skills) >= 4, f"三国skills数量应>=4，实际: {len(sanguo_skills)}"

    def test_xiyou_registered_count(self):
        """西游至少注册4个skills"""
        from odap.tools.base import get_registry
        registry = get_registry()

        xiyou_skills = [s for s in registry.list_skills()
                        if s["name"].startswith("xiyou_")]
        assert len(xiyou_skills) >= 4, f"西游skills数量应>=4，实际: {len(xiyou_skills)}"
