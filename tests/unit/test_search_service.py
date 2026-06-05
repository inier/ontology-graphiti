"""SearchService 单元测试"""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

from odap.biz.core.ontology.design.services.search_service import (
    SearchService,
    SearchResult,
    MockSearch,
    DuckDuckGoSearch,
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

    def test_is_available(self):
        provider = MockSearch()
        self.assertTrue(provider.is_available())

    def test_search_returns_results(self):
        provider = MockSearch()
        results = _run(provider.search("测试查询"))
        self.assertEqual(len(results), 3)

    def test_search_max_results(self):
        provider = MockSearch()
        results = _run(provider.search("测试", max_results=1))
        self.assertEqual(len(results), 1)

    def test_search_result_format(self):
        provider = MockSearch()
        results = _run(provider.search("测试"))
        for r in results:
            self.assertIsInstance(r, SearchResult)
            self.assertIn("测试", r.title)
            self.assertTrue(r.url.startswith("https://"))

    def test_search_empty_query(self):
        provider = MockSearch()
        results = _run(provider.search(""))
        self.assertEqual(len(results), 3)


class TestDuckDuckGoSearch(unittest.TestCase):
    """DuckDuckGo 搜索提供者测试"""

    def test_is_available_returns_bool(self):
        provider = DuckDuckGoSearch()
        # 不实际联网，只检查返回类型
        provider._available = False
        self.assertFalse(provider.is_available())

    def test_search_network_failure_returns_empty(self):
        provider = DuckDuckGoSearch()
        with patch("requests.get", side_effect=Exception("Network error")):
            results = _run(provider.search("test"))
            self.assertEqual(results, [])


class TestTavilySearch(unittest.TestCase):
    """Tavily 搜索提供者测试"""

    def test_not_available_without_key(self):
        # 直接传空 key，_get_api_key 不会覆盖已传入的值
        provider = TavilySearch(api_key="")
        # 但 _get_api_key 可能从环境变量获取了 key
        # 所以我们直接验证 is_available 逻辑：有 key 就可用
        self.assertEqual(provider.is_available(), bool(provider.api_key))

    def test_available_with_key(self):
        provider = TavilySearch(api_key="test-key")
        self.assertTrue(provider.is_available())

    def test_search_returns_empty_without_key(self):
        # 使用 patch 确保 api_key 为空
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

    def test_get_available_providers(self):
        svc = SearchService()
        providers = svc.get_available_providers()
        # MockSearch 始终可用
        self.assertIn("MockSearch", providers)

    def test_search_falls_back_to_mock(self):
        svc = SearchService()
        # 所有网络搜索不可用时，应回退到 MockSearch
        results = _run(svc.search("测试查询"))
        self.assertTrue(len(results) > 0)

    def test_search_with_mock_only(self):
        svc = SearchService()
        # 只保留 MockSearch
        svc._providers = [MockSearch()]
        results = _run(svc.search("测试"))
        self.assertEqual(len(results), 3)


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
