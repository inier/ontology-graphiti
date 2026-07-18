"""爬取服务编排层

Crawl4AI 优先 → requests+BS4 降级
"""

from typing import Dict, Any
import logging

from odap.biz.data.web_crawl.impl.crawl4ai_crawler import Crawl4AICrawler
from odap.biz.data.web_crawl.impl.requests_fallback import RequestsFallbackCrawler
from odap.biz.data.web_crawl.impl.content_sanitizer import mark_external_content

logger = logging.getLogger(__name__)


class CrawlService:
    """爬取服务 - Crawl4AI 优先，requests 降级"""

    def __init__(self):
        self._crawl4ai = Crawl4AICrawler()
        self._fallback = RequestsFallbackCrawler()

    def crawl_url(self, url: str, output_format: str = "markdown",
                  css_selector: str = None, timeout: int = 30) -> Dict[str, Any]:
        """爬取指定 URL

        优先使用 Crawl4AI（支持 JS 渲染），不可用时降级到 requests+BS4。
        所有爬取结果经过安全过滤（移除 script/iframe，标记来源和可信度）。
        """
        # 1. 尝试 Crawl4AI
        if self._crawl4ai.is_available():
            try:
                result = self._crawl4ai.crawl(url, output_format, css_selector, timeout)
                if result.get("content"):
                    return mark_external_content(result, "crawl4ai")
                logger.warning(f"Crawl4AI returned empty content for {url}, trying fallback")
            except Exception as e:
                logger.warning(f"Crawl4AI failed for {url}: {e}, falling back to requests")
        else:
            logger.info("Crawl4AI not available, using requests fallback")

        # 2. 降级到 requests+BS4
        if self._fallback.is_available():
            result = self._fallback.crawl(url, output_format, css_selector, timeout)
            return mark_external_content(result, "requests_fallback")

        # 3. 两者都不可用
        return {
            "status": "error",
            "message": "No crawl backend available (Crawl4AI and requests fallback both unavailable)",
            "url": url,
        }

    def health_check(self) -> Dict[str, Any]:
        """检查爬取服务健康状态"""
        crawl4ai_available = self._crawl4ai.is_available()
        fallback_available = self._fallback.is_available()

        return {
            "crawl4ai_available": crawl4ai_available,
            "fallback_available": fallback_available,
            "active_browsers": 0,
            "max_concurrent": 3,
            "status": "healthy" if (crawl4ai_available or fallback_available) else "unhealthy",
        }
