"""Requests 降级爬取器 - 基于 requests 的静态页面爬取

优先使用 BeautifulSoup4（如果可用），否则使用纯正则提取。
确保降级方案始终可用（仅依赖 requests）。
"""

import logging
import re
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)


def _extract_title_regex(html: str) -> str:
    """从 HTML 中提取 title"""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


def _extract_text_regex(html: str) -> str:
    """从 HTML 中提取纯文本（移除标签）"""
    # 移除 script/style
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    # 移除所有 HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 清理空白
    text = re.sub(r"\s+", " ", text).strip()
    return text[:50000]  # 限制长度


def _extract_links_regex(html: str, base_url: str = "") -> List[Dict[str, str]]:
    """从 HTML 中提取链接"""
    links = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
        href = m.group(1).strip()
        text = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if href and not href.startswith(("#", "javascript:", "mailto:")):
            if base_url and not href.startswith(("http://", "https://")):
                href = urljoin(base_url, href)
            links.append({"text": text[:200], "href": href, "link_type": "external"})
    return links[:200]  # 限制数量


class RequestsFallbackCrawler:
    """Requests 降级爬取器

    使用 requests 爬取静态 HTML 页面。
    优先使用 BeautifulSoup4（如果可用），否则使用纯正则提取。
    无法处理 JS 渲染内容，作为 Crawl4AI 不可用时的降级方案。
    """

    @staticmethod
    def is_available() -> bool:
        """检查降级爬取器是否可用（仅需 requests）"""
        try:
            import requests  # noqa: F401
            return True
        except ImportError:
            return False

    def crawl(self, url: str, output_format: str = "markdown",
              css_selector: Optional[str] = None, timeout: int = 30) -> Dict[str, Any]:
        """爬取静态 HTML 页面"""
        try:
            import requests as req
            resp = req.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (compatible; ODAP-Crawler/1.0)"
            })
            resp.raise_for_status()
            html = resp.text

            # 尝试使用 BeautifulSoup4
            try:
                from bs4 import BeautifulSoup
                return self._crawl_with_bs4(html, url, css_selector)
            except ImportError:
                return self._crawl_with_regex(html, url)

        except Exception as e:
            logger.error(f"Requests fallback crawl failed for {url}: {e}")
            return {
                "url": url,
                "title": "",
                "content": f"爬取失败: {e}",
                "links": [],
                "metadata": {},
                "source": "external",
                "confidence": "low",
                "crawl_method": "requests_fallback",
            }

    def _crawl_with_bs4(self, html: str, url: str, css_selector: Optional[str]) -> Dict[str, Any]:
        """使用 BeautifulSoup4 解析"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        text = soup.get_text(separator="\n", strip=True)
        links = [{"text": a.get_text(strip=True)[:200], "href": a.get("href", ""), "link_type": "external"}
                 for a in soup.find_all("a", href=True)]

        if css_selector:
            selected = soup.select(css_selector)
            if selected:
                text = "\n".join(el.get_text(strip=True) for el in selected)

        return {
            "url": url,
            "title": title,
            "content": text[:50000],
            "links": links[:200],
            "metadata": {},
            "source": "external",
            "confidence": "low",
            "crawl_method": "requests_fallback",
        }

    def _crawl_with_regex(self, html: str, url: str) -> Dict[str, Any]:
        """使用正则表达式解析（无 bs4 依赖）"""
        title = _extract_title_regex(html)
        text = _extract_text_regex(html)
        links = _extract_links_regex(html, url)

        return {
            "url": url,
            "title": title,
            "content": text,
            "links": links,
            "metadata": {},
            "source": "external",
            "confidence": "low",
            "crawl_method": "requests_fallback",
        }
