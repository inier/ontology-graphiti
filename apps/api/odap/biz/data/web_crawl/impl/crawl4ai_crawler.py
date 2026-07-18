"""Crawl4AI 爬取器 - 基于 Playwright 的 JS 渲染爬取

支持两种模式：
1. HTTP 模式（推荐）：通过 HTTP 调用独立 Crawl4AI 容器，避免异步桥接
2. 本地模式（降级）：直接在进程内调用 crawl4ai，使用异步桥接
"""

import logging
import os
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def _get_crawl4ai_url() -> str:
    """获取 Crawl4AI API 地址（优先在线配置，fallback 环境变量）"""
    try:
        from odap.infra.config_composer import get_config
        url = get_config("crawl.api_url", "")
        if url:
            return url
    except Exception:
        pass
    return os.environ.get("CRAWL4AI_API_URL", "http://graphiti-crawl4ai:8020")


class Crawl4AICrawler:
    """Crawl4AI 爬取器

    优先通过 HTTP 调用独立容器（避免异步桥接脆弱性）；
    容器不可用时降级为本地异步爬取。
    """

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._semaphore = None  # 在异步上下文中按需创建

    @staticmethod
    def is_available() -> bool:
        """检查 Crawl4AI 是否可用（HTTP 容器或本地包）"""
        # HTTP 容器模式
        if Crawl4AICrawler._is_http_available():
            return True
        # 本地包模式
        try:
            import crawl4ai  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def _is_http_available() -> bool:
        """检查 Crawl4AI HTTP 容器是否可用"""
        try:
            import httpx
            resp = httpx.get(f"{_get_crawl4ai_url()}/health", timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def crawl(self, url: str, output_format: str = "markdown",
              css_selector: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """同步爬取入口

        优先 HTTP 模式（无异步桥接），降级为本地异步模式。
        """
        # 优先：HTTP 模式（无异步桥接，简单可靠）
        result = self._crawl_via_http(url, output_format, css_selector, timeout)
        if result is not None:
            return result

        # 降级：本地异步模式
        logger.info("Crawl4AI HTTP container unavailable, falling back to local async mode")
        return self._crawl_local(url, output_format, css_selector, timeout)

    def _crawl_via_http(self, url: str, output_format: str,
                        css_selector: Optional[str], timeout: int) -> Optional[Dict[str, Any]]:
        """通过 HTTP 调用独立 Crawl4AI 容器

        Returns:
            爬取结果 dict，或 None（容器不可用时返回 None 以触发降级）
        """
        try:
            import httpx

            payload = {
                "url": url,
                "output_format": output_format,
                "css_selector": css_selector,
                "timeout": timeout,
            }
            # Crawl4AI HTTP API 端点（/crawl 或 /api/crawl）
            resp = httpx.post(
                f"{_get_crawl4ai_url()}/crawl",
                json=payload,
                timeout=timeout + 15,  # 额外 15s 网络缓冲
            )
            if resp.status_code != 200:
                logger.warning(f"Crawl4AI HTTP returned {resp.status_code}")
                return None

            data = resp.json()
            if data.get("status") == "error":
                return None

            return {
                "url": data.get("url", url),
                "title": data.get("title", ""),
                "content": data.get("content", ""),
                "links": data.get("links", []),
                "metadata": data.get("metadata", {}),
                "source": "external",
                "confidence": "medium",
                "crawl_method": "crawl4ai_http",
            }
        except Exception as e:
            logger.debug(f"Crawl4AI HTTP mode unavailable: {e}")
            return None

    def _crawl_local(self, url: str, output_format: str,
                     css_selector: Optional[str], timeout: int) -> Dict[str, Any]:
        """本地异步爬取（降级模式，需要 crawl4ai 包）"""
        try:
            import asyncio
            import concurrent.futures

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        return pool.submit(
                            asyncio.run,
                            self._async_crawl(url, output_format, css_selector, timeout)
                        ).result(timeout=timeout + 10)
                else:
                    return loop.run_until_complete(
                        self._async_crawl(url, output_format, css_selector, timeout)
                    )
            except RuntimeError:
                return asyncio.run(
                    self._async_crawl(url, output_format, css_selector, timeout)
                )
        except ImportError:
            raise ImportError(
                "crawl4ai not installed and HTTP container unavailable. "
                "Install with: pip install crawl4ai, or start the Crawl4AI container."
            )

    async def _async_crawl(self, url: str, output_format: str,
                           css_selector: Optional[str], timeout: int) -> Dict[str, Any]:
        """异步爬取实现（本地模式）"""
        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
        except ImportError:
            raise ImportError("crawl4ai not installed. Install with: pip install crawl4ai")

        browser_config = BrowserConfig(headless=True, browser_type="chromium")
        run_config = CrawlerRunConfig(
            css_selector=css_selector,
            word_count_threshold=10,
            excluded_tags=["nav", "footer", "aside", "header"],
            page_timeout=timeout * 1000,
        )

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

            content = result.markdown
            if output_format == "html":
                content = getattr(result, "cleaned_html", result.markdown)
            elif output_format == "fit_markdown":
                content = getattr(result, "fit_markdown", result.markdown)
            elif output_format == "text":
                content = result.markdown  # text 格式用 markdown 近似

            return {
                "url": result.url or url,
                "title": (result.metadata.get("title", "") if result.metadata else ""),
                "content": content or "",
                "links": self._extract_links(result.links) if result.links else [],
                "metadata": result.metadata or {},
                "source": "external",
                "confidence": "medium",
                "crawl_method": "crawl4ai",
            }

    @staticmethod
    def _extract_links(links_data: Any) -> List[Dict[str, str]]:
        """提取链接列表"""
        result = []
        if isinstance(links_data, dict):
            for link_type in ["external", "internal"]:
                for link in links_data.get(link_type, []):
                    if isinstance(link, dict):
                        result.append({
                            "text": link.get("text", ""),
                            "href": link.get("href", ""),
                            "link_type": link_type,
                        })
                    elif isinstance(link, str):
                        result.append({"text": "", "href": link, "link_type": link_type})
        return result
