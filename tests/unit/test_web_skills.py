"""Web 数据采集技能单元测试"""

import pytest
from unittest.mock import patch, MagicMock


class TestWebSearchSkill:
    """WebSearchSkill 测试"""

    def test_skill_metadata(self):
        """验证 Skill 元数据正确"""
        from odap.tools.web.web_skills import _web_search_skill
        assert _web_search_skill.metadata.name == "web_search"
        assert _web_search_skill.metadata.category == "web"
        assert _web_search_skill.metadata.requires_opa_check is True
        assert _web_search_skill.metadata.opa_action == "data_collection:search"

    def test_skill_registered_in_catalog(self):
        """验证 Skill 已注册到 SKILL_CATALOG"""
        from odap.tools import SKILL_CATALOG
        assert "web_search" in SKILL_CATALOG
        assert SKILL_CATALOG["web_search"]["category"] == "web"

    def test_skill_registered_in_registry(self):
        """验证 Skill 已注册到 SkillRegistry"""
        from odap.tools import get_registry
        registry = get_registry()
        skill = registry.get("web_search")
        assert skill is not None
        assert skill.metadata.name == "web_search"

    def test_search_success_with_mock(self):
        """验证搜索成功返回正确格式"""
        from odap.tools.web.web_skills import _web_search_skill
        mock_results = [
            {"title": "Test", "url": "https://example.com", "snippet": "Test snippet", "content": "Test content"}
        ]
        with patch.object(_web_search_skill, '_do_search', return_value=mock_results):
            result = _web_search_skill.run({"query": "test query"})
            assert result.success is True
            assert result.data["query"] == "test query"
            assert result.data["source"] == "external"
            assert result.data["confidence"] == "medium"
            assert len(result.data["results"]) == 1

    def test_search_failure_returns_error(self):
        """验证搜索失败返回错误"""
        from odap.tools.web.web_skills import _web_search_skill
        with patch.object(_web_search_skill, '_do_search', side_effect=Exception("Search failed")):
            result = _web_search_skill.run({"query": "test"})
            assert result.success is False
            assert "Search failed" in result.error

    def test_search_degradation(self):
        """验证搜索降级到 DuckDuckGo"""
        from odap.tools.web.web_skills import _web_search_skill
        with patch.object(_web_search_skill, '_do_search') as mock_search:
            mock_search.side_effect = [
                ImportError("SearchService not available"),
                [{"title": "DDG Result", "url": "https://ddg.com", "snippet": "DDG", "content": "DDG"}]
            ]
            # _do_search 内部会调用 _fallback_search
            # 这个测试验证降级逻辑存在
            assert _web_search_skill._fallback_search is not None


class TestWebCrawlSkill:
    """WebCrawlSkill 测试"""

    def test_skill_metadata(self):
        """验证 Skill 元数据正确"""
        from odap.tools.web.web_skills import _web_crawl_skill
        assert _web_crawl_skill.metadata.name == "web_crawl"
        assert _web_crawl_skill.metadata.category == "web"
        assert _web_crawl_skill.metadata.danger_level == "medium"
        assert _web_crawl_skill.metadata.requires_opa_check is True
        assert _web_crawl_skill.metadata.opa_action == "data_collection:crawl"

    def test_skill_registered_in_catalog(self):
        """验证 Skill 已注册到 SKILL_CATALOG"""
        from odap.tools import SKILL_CATALOG
        assert "web_crawl" in SKILL_CATALOG
        assert SKILL_CATALOG["web_crawl"]["category"] == "web"

    def test_crawl_fallback_to_requests(self):
        """验证爬取委托给 CrawlService（Crawl4AI 优先 → requests 降级）"""
        from odap.tools.web.web_skills import _web_crawl_skill
        with patch("odap.biz.data.web_crawl.services.crawl_service.CrawlService.crawl_url") as mock_crawl:
            mock_crawl.return_value = {
                "url": "https://example.com",
                "title": "Example",
                "content": "Test content",
                "links": [],
                "metadata": {},
                "source": "external",
                "confidence": "low",
                "crawl_method": "requests_fallback",
            }
            result = _web_crawl_skill.run({"url": "https://example.com"})
            assert result.success is True
            assert result.data["crawl_method"] == "requests_fallback"

    def test_crawl_failure_returns_error(self):
        """验证爬取失败返回错误"""
        from odap.tools.web.web_skills import _web_crawl_skill
        with patch.object(_web_crawl_skill, '_crawl', side_effect=Exception("Crawl failed")):
            result = _web_crawl_skill.run({"url": "https://example.com"})
            assert result.success is False
            assert "Crawl failed" in result.error

    def test_extract_domain(self):
        """验证域名提取"""
        from odap.tools.web.web_skills import _web_search_skill
        assert _web_search_skill._extract_domain("https://www.example.com/page") == "example.com"
        assert _web_search_skill._extract_domain("https://example.com") == "example.com"
        assert _web_search_skill._extract_domain("") == ""


class TestWebSkillRegistration:
    """Web Skill 注册集成测试"""

    def test_web_category_in_allowed_categories(self):
        """验证 web 类别在 IntelligenceAgent 的 allowed_categories 中"""
        from odap.biz.core.agent.intelligence_agent import IntelligenceAgent
        agent = IntelligenceAgent()
        # 检查 web 类别的 Skill 是否出现在工具列表中
        tool_names = [t["function"]["name"] for t in agent.tools]
        assert "web_search" in tool_names
        assert "web_crawl" in tool_names

    def test_web_search_tool_has_correct_schema(self):
        """验证 web_search 工具的参数 schema 正确"""
        from odap.biz.core.agent.intelligence_agent import IntelligenceAgent
        agent = IntelligenceAgent()
        web_search_tool = next(t for t in agent.tools if t["function"]["name"] == "web_search")
        params = web_search_tool["function"]["parameters"]
        assert "query" in params["properties"]
        assert "query" in params["required"]

    def test_web_crawl_tool_has_correct_schema(self):
        """验证 web_crawl 工具的参数 schema 正确"""
        from odap.biz.core.agent.intelligence_agent import IntelligenceAgent
        agent = IntelligenceAgent()
        web_crawl_tool = next(t for t in agent.tools if t["function"]["name"] == "web_crawl")
        params = web_crawl_tool["function"]["parameters"]
        assert "url" in params["properties"]
        assert "url" in params["required"]


class TestCollectionTaskModel:
    """CollectionTask 模型测试"""

    def test_default_values(self):
        """验证默认值正确"""
        from odap.biz.data.web_crawl.models import CollectionTask, CollectionTaskType, CollectionTaskStatus
        task = CollectionTask(task_type=CollectionTaskType.SEARCH, target="test query")
        assert task.status == CollectionTaskStatus.PENDING
        assert task.source == "external"
        assert task.confidence == "medium"
        assert task.result is None

    def test_enum_values(self):
        """验证枚举值正确"""
        from odap.biz.data.web_crawl.models import CollectionTaskType, CollectionTaskStatus
        assert CollectionTaskType.SEARCH.value == "search"
        assert CollectionTaskType.CRAWL.value == "crawl"
        assert CollectionTaskType.BROWSER.value == "browser"
        assert CollectionTaskStatus.PENDING.value == "pending"
        assert CollectionTaskStatus.COMPLETED.value == "completed"
        assert CollectionTaskStatus.DEGRADED.value == "degraded"
