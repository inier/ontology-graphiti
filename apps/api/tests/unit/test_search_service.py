"""SearchService 单元测试"""

import asyncio
import os
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from odap.biz.core.ontology.design.services.search_service import (
    SearchService,
    SearchResult,
    MockSearch,
    OHWebSearchProvider,
    TavilySearch,
    SerpAPISearch,
    BaseSearchProvider,
)


def _run(coro):
    """辅助: 在事件循环中运行异步协程"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestSearchResult(unittest.TestCase):
    """SearchResult 数据类测试"""

    def test_to_dict(self):
        result = SearchResult(
            title="Test",
            url="https://example.com",
            content="Content here",
            snippet="Snippet here",
            date="2024-01-01",
        )
        d = result.to_dict()
        self.assertEqual(d["title"], "Test")
        self.assertEqual(d["url"], "https://example.com")
        self.assertEqual(d["content"], "Content here")
        self.assertEqual(d["snippet"], "Snippet here")
        self.assertEqual(d["date"], "2024-01-01")

    def test_default_date(self):
        result = SearchResult(title="T", url="U", content="C", snippet="S")
        self.assertEqual(result.date, "")

    def test_to_dict_keys(self):
        result = SearchResult(title="T", url="U", content="C", snippet="S")
        d = result.to_dict()
        expected_keys = {"title", "url", "content", "snippet", "date"}
        self.assertEqual(set(d.keys()), expected_keys)


class TestMockSearch(unittest.TestCase):
    """MockSearch 搜索提供者测试"""

    def test_not_available_by_default(self):
        """MockSearch 默认不可用（需 SEARCH_ALLOW_MOCK=true）"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEARCH_ALLOW_MOCK", None)
            provider = MockSearch()
            self.assertFalse(provider.is_available())

    def test_available_when_configured(self):
        """配置 SEARCH_ALLOW_MOCK=true 后可用"""
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            provider = MockSearch()
            self.assertTrue(provider.is_available())

    def test_search_returns_results(self):
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            provider = MockSearch()
            results = _run(provider.search("测试查询"))
            self.assertEqual(len(results), 3)

    def test_search_max_results(self):
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            provider = MockSearch()
            results = _run(provider.search("测试", max_results=1))
            self.assertEqual(len(results), 1)

    def test_search_result_format(self):
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            provider = MockSearch()
            results = _run(provider.search("测试"))
            for r in results:
                self.assertIsInstance(r, SearchResult)
                self.assertIn("测试", r.title)
                self.assertTrue(r.url.startswith("https://"))

    def test_to_dict_list_marks_mock(self):
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            provider = MockSearch()
            results = _run(provider.search("测试"))
            dict_list = provider.to_dict_list(results)
            for d in dict_list:
                self.assertTrue(d.get("is_mock"))


class TestOHWebSearchProvider(unittest.TestCase):
    """OHWebSearchProvider 搜索提供者测试"""

    def test_not_available_when_oh_missing(self):
        """OH 不可用时 is_available 返回 False"""
        provider = OHWebSearchProvider()
        provider._tool = False  # 模拟 OH 导入失败
        provider._available = False  # 同时重置缓存
        self.assertFalse(provider.is_available())

    def test_available_when_oh_present(self):
        """OH 可用时 is_available 返回 True"""
        provider = OHWebSearchProvider()
        provider._tool = MagicMock()  # 模拟 OH WebSearchTool 加载成功
        provider._available = True
        self.assertTrue(provider.is_available())

    def test_search_returns_empty_when_oh_missing(self):
        provider = OHWebSearchProvider()
        provider._tool = False
        results = _run(provider.search("test"))
        self.assertEqual(results, [])

    def test_parse_oh_output(self):
        """测试解析 OH WebSearchTool 的纯文本输出"""
        provider = OHWebSearchProvider()
        oh_output = """Search results for: test query
1. First Result
   URL: https://example.com/1
   This is the first snippet
2. Second Result
   URL: https://example.com/2
   This is the second snippet"""
        results = provider._parse_oh_output(oh_output, "test query")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "First Result")
        self.assertEqual(results[0].url, "https://example.com/1")
        self.assertEqual(results[0].snippet, "This is the first snippet")
        self.assertEqual(results[1].title, "Second Result")


class TestTavilySearch(unittest.TestCase):
    """Tavily 搜索提供者测试"""

    def test_not_available_without_key(self):
        provider = TavilySearch(api_key="")
        self.assertEqual(provider.is_available(), bool(provider.api_key))

    def test_available_with_key(self):
        provider = TavilySearch(api_key="test-key")
        self.assertTrue(provider.is_available())

    def test_search_returns_empty_without_key(self):
        provider = TavilySearch(api_key="")
        provider.api_key = ""
        provider._available = False
        results = _run(provider.search("test"))
        self.assertEqual(results, [])


class TestSerpAPISearch(unittest.TestCase):
    """SerpAPI 搜索提供者测试"""

    def test_not_available_without_key(self):
        provider = SerpAPISearch(api_key="")
        self.assertFalse(provider.is_available())

    def test_available_with_key(self):
        provider = SerpAPISearch(api_key="test-key")
        self.assertTrue(provider.is_available())

    def test_search_returns_empty_without_key(self):
        provider = SerpAPISearch(api_key="")
        results = _run(provider.search("test"))
        self.assertEqual(results, [])


class TestSearchService(unittest.TestCase):
    """SearchService 统一搜索服务测试"""

    def test_init_creates_providers(self):
        svc = SearchService()
        self.assertTrue(len(svc._providers) > 0)

    def test_provider_types(self):
        """验证降级链包含正确的 Provider 类型"""
        svc = SearchService()
        provider_types = [type(p).__name__ for p in svc._providers]
        self.assertIn("TavilySearch", provider_types)
        self.assertIn("SerpAPISearch", provider_types)
        self.assertIn("OHWebSearchProvider", provider_types)
        self.assertIn("MockSearch", provider_types)

    def test_mock_not_available_by_default(self):
        """默认情况下 MockSearch 不在可用 Provider 中"""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SEARCH_ALLOW_MOCK", None)
            svc = SearchService()
            available = svc.get_available_providers()
            self.assertNotIn("MockSearch", available)

    def test_search_returns_empty_when_no_provider_available(self):
        """所有 Provider 不可用时返回空列表"""
        svc = SearchService()
        # 模拟所有 Provider 不可用
        for p in svc._providers:
            p.is_available = lambda: False
        results = _run(svc.search("测试查询"))
        self.assertEqual(results, [])

    def test_search_with_mock_enabled(self):
        """启用 Mock 时搜索应返回结果"""
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            svc = SearchService()
            # 禁用其他 Provider，只保留 Mock
            svc._providers = [MockSearch()]
            results = _run(svc.search("测试"))
            self.assertEqual(len(results), 3)

    def test_search_sync(self):
        """search_sync 方法应正常工作"""
        with patch.dict(os.environ, {"SEARCH_ALLOW_MOCK": "true"}):
            svc = SearchService()
            svc._providers = [MockSearch()]
            results = svc.search_sync("测试")
            self.assertEqual(len(results), 3)

    def test_providers_property(self):
        """providers 属性应暴露内部列表"""
        svc = SearchService()
        self.assertIsInstance(svc.providers, list)
        self.assertTrue(len(svc.providers) > 0)


class TestBaseSearchProvider(unittest.TestCase):
    """BaseSearchProvider 基类测试"""

    def test_search_not_implemented(self):
        provider = BaseSearchProvider()
        with self.assertRaises(NotImplementedError):
            _run(provider.search("test"))

    def test_is_available_not_implemented(self):
        provider = BaseSearchProvider()
        with self.assertRaises(NotImplementedError):
            provider.is_available()


if __name__ == "__main__":
    unittest.main()
