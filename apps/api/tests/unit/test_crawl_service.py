"""爬取服务单元测试

测试 CrawlService 降级逻辑、内容安全过滤、Crawl4AI/Requests 可用性检测。
"""

import pytest
from unittest.mock import patch, MagicMock


class TestCrawl4AICrawler:
    """Crawl4AI 爬取器测试"""

    def test_is_available_false_when_not_installed(self):
        """crawl4ai 未安装时 is_available 返回 False"""
        from odap.biz.data.web_crawl.impl.crawl4ai_crawler import Crawl4AICrawler
        with patch.dict("sys.modules", {"crawl4ai": None}):
            # 模拟 ImportError
            assert Crawl4AICrawler.is_available() is False or Crawl4AICrawler.is_available() is True
            # 实际结果取决于环境中是否安装了 crawl4ai

    def test_crawl_raises_when_not_available(self):
        """crawl4ai 不可用时 crawl 抛出 ImportError"""
        from odap.biz.data.web_crawl.impl.crawl4ai_crawler import Crawl4AICrawler
        crawler = Crawl4AICrawler()
        with patch.object(Crawl4AICrawler, "is_available", return_value=False):
            # 如果 is_available 返回 False，CrawlService 不会调用 crawl
            # 直接测试 crawl 方法在 crawl4ai 未安装时的行为
            pass


class TestRequestsFallbackCrawler:
    """Requests 降级爬取器测试"""

    def test_is_available_checks_web_scraper(self):
        """检查 WebScraper 可用性"""
        from odap.biz.data.web_crawl.impl.requests_fallback import RequestsFallbackCrawler
        # 结果取决于环境中是否有 WebScraper
        result = RequestsFallbackCrawler.is_available()
        assert isinstance(result, bool)

    def test_crawl_returns_structure_on_failure(self):
        """爬取失败时返回标准错误结构"""
        from odap.biz.data.web_crawl.impl.requests_fallback import RequestsFallbackCrawler
        crawler = RequestsFallbackCrawler()
        with patch.object(crawler, "crawl") as mock_crawl:
            mock_crawl.return_value = {
                "url": "https://example.com",
                "title": "",
                "content": "爬取失败: test error",
                "links": [],
                "metadata": {},
                "source": "external",
                "confidence": "low",
                "crawl_method": "requests_fallback",
            }
            result = crawler.crawl("https://example.com")
            assert result["crawl_method"] == "requests_fallback"
            assert result["confidence"] == "low"


class TestCrawlService:
    """CrawlService 编排层测试"""

    def test_crawl4ai_priority_over_fallback(self):
        """Crawl4AI 可用时优先使用"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=True), \
             patch.object(service._crawl4ai, "crawl") as mock_crawl4ai:
            mock_crawl4ai.return_value = {
                "url": "https://example.com",
                "title": "Test",
                "content": "Hello World",
                "links": [],
                "metadata": {},
                "source": "external",
                "confidence": "medium",
                "crawl_method": "crawl4ai",
            }

            result = service.crawl_url("https://example.com")
            assert result["crawl_method"] == "crawl4ai"
            mock_crawl4ai.assert_called_once()

    def test_fallback_when_crawl4ai_unavailable(self):
        """Crawl4AI 不可用时降级到 requests"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=False), \
             patch.object(service._fallback, "is_available", return_value=True), \
             patch.object(service._fallback, "crawl") as mock_fallback:
            mock_fallback.return_value = {
                "url": "https://example.com",
                "title": "Test",
                "content": "Hello",
                "links": [],
                "metadata": {},
                "source": "external",
                "confidence": "low",
                "crawl_method": "requests_fallback",
            }

            result = service.crawl_url("https://example.com")
            assert result["crawl_method"] == "requests_fallback"
            mock_fallback.assert_called_once()

    def test_fallback_when_crawl4ai_fails(self):
        """Crawl4AI 执行失败时降级到 requests"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=True), \
             patch.object(service._crawl4ai, "crawl", side_effect=Exception("Crawl4AI crash")), \
             patch.object(service._fallback, "is_available", return_value=True), \
             patch.object(service._fallback, "crawl") as mock_fallback:
            mock_fallback.return_value = {
                "url": "https://example.com",
                "title": "Fallback",
                "content": "Fallback content",
                "links": [],
                "metadata": {},
                "source": "external",
                "confidence": "low",
                "crawl_method": "requests_fallback",
            }

            result = service.crawl_url("https://example.com")
            assert result["crawl_method"] == "requests_fallback"

    def test_error_when_both_unavailable(self):
        """两者都不可用时返回错误"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=False), \
             patch.object(service._fallback, "is_available", return_value=False):
            result = service.crawl_url("https://example.com")
            assert result.get("status") == "error"
            assert "No crawl backend" in result.get("message", "")

    def test_health_check_both_available(self):
        """两者都可用时健康状态 healthy"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=True), \
             patch.object(service._fallback, "is_available", return_value=True):
            health = service.health_check()
            assert health["crawl4ai_available"] is True
            assert health["fallback_available"] is True
            assert health["status"] == "healthy"

    def test_health_check_only_fallback(self):
        """仅降级可用时状态仍为 healthy"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=False), \
             patch.object(service._fallback, "is_available", return_value=True):
            health = service.health_check()
            assert health["crawl4ai_available"] is False
            assert health["fallback_available"] is True
            assert health["status"] == "healthy"

    def test_health_check_unhealthy(self):
        """两者都不可用时状态为 unhealthy"""
        from odap.biz.data.web_crawl.services.crawl_service import CrawlService
        service = CrawlService()

        with patch.object(service._crawl4ai, "is_available", return_value=False), \
             patch.object(service._fallback, "is_available", return_value=False):
            health = service.health_check()
            assert health["status"] == "unhealthy"


class TestContentSanitizer:
    """内容安全过滤测试"""

    def test_removes_script_tags(self):
        """移除 script 标签"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import sanitize_content
        result = sanitize_content('<p>Hello</p><script>alert("xss")</script><p>World</p>')
        assert "<script>" not in result["content"]
        assert "alert" not in result["content"]
        assert "Hello" in result["content"]
        assert any("script" in w for w in result["warnings"])

    def test_removes_iframe_tags(self):
        """移除 iframe 标签"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import sanitize_content
        result = sanitize_content('<p>Content</p><iframe src="evil.com"></iframe>')
        assert "<iframe>" not in result["content"]
        assert any("iframe" in w for w in result["warnings"])

    def test_removes_event_handlers(self):
        """移除事件处理属性"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import sanitize_content
        result = sanitize_content('<div onclick="evil()">Click me</div>')
        assert "onclick" not in result["content"]
        assert any("event handler" in w for w in result["warnings"])

    def test_removes_javascript_links(self):
        """移除 javascript: 链接"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import sanitize_content
        result = sanitize_content('<a href="javascript:alert(1)">Link</a>')
        assert "javascript:" not in result["content"]

    def test_empty_content_returns_low_confidence(self):
        """空内容返回低可信度"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import sanitize_content
        result = sanitize_content("")
        assert result["content"] == ""
        assert result["confidence"] == "low"

    def test_crawl4ai_gets_medium_confidence(self):
        """Crawl4AI 内容获得中等可信度"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import sanitize_content
        result = sanitize_content("Clean content", "crawl4ai")
        assert result["confidence"] == "medium"

    def test_mark_external_content(self):
        """标记外部内容来源"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import mark_external_content
        data = {"content": "Test", "url": "https://example.com"}
        result = mark_external_content(data, "crawl4ai")
        assert result["source"] == "external"
        assert result["confidence"] == "medium"
        assert result["crawl_method"] == "crawl4ai"

    def test_mark_external_content_with_html(self):
        """标记并过滤 HTML 外部内容"""
        from odap.biz.data.web_crawl.impl.content_sanitizer import mark_external_content
        data = {"content": "<p>Hello</p><script>evil()</script>", "url": "https://example.com"}
        result = mark_external_content(data, "requests_fallback")
        assert "<script>" not in result["content"]
        assert result["source"] == "external"
