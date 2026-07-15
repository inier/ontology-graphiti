"""
数据采集层 - 网页内容抓取模块
实现 ADR-031 L2: Data Ingestion & Normalization

WebScraper: 网页内容抓取（免费方案，无需 API Key）
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import requests
    from bs4 import BeautifulSoup
    WEB_SCRAPE_AVAILABLE = True
except ImportError:
    WEB_SCRAPE_AVAILABLE = False
    logging.warning("网页抓取依赖未安装，将使用 Mock 数据")

logger = logging.getLogger("data_ingestion")


class WebScraper:
    """
    免费网页内容抓取器

    功能:
    - 直接抓取网页内容（HTML）
    - 提取标题、文本内容、链接
    - 支持新闻网站、博客、文档等

    优点:
    - 完全免费，无需 API Key
    - 轻量级实现，依赖少
    - 支持任意网页

    限制:
    - 无法获取 JavaScript 渲染的内容
    - 部分网站有反爬措施
    - 不支持需要登录的内容
    """

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    TIMEOUT = 15

    def __init__(self, headers: Dict[str, str] = None):
        self.headers = headers or self.DEFAULT_HEADERS.copy()

    def scrape(self, url: str) -> Dict[str, Any]:
        """
        抓取网页内容

        Args:
            url: 网页 URL

        Returns:
            Dict containing: url, title, text, links, description, publish_date
        """
        if not WEB_SCRAPE_AVAILABLE:
            logger.warning(f"网页抓取依赖未安装，使用 Mock 数据: {url}")
            return self._generate_mock_scrape(url)

        logger.info(f"开始抓取网页: {url}")

        try:
            response = requests.get(url, headers=self.headers, timeout=self.TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除脚本和样式元素
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()

            # 提取标题
            title = self._extract_title(soup)

            # 提取正文内容
            text = self._extract_text(soup)

            # 提取描述
            description = self._extract_description(soup)

            # 提取链接
            links = self._extract_links(soup, url)

            # 提取发布日期
            publish_date = self._extract_publish_date(soup)

            result = {
                "url": url,
                "title": title,
                "text": text,
                "description": description,
                "links": links,
                "publish_date": publish_date,
                "status": "success"
            }

            logger.info(f"成功抓取网页: {title}")
            return result

        except requests.exceptions.Timeout:
            logger.error(f"网页抓取超时: {url}")
            return {"url": url, "status": "error", "error": "请求超时"}
        except requests.exceptions.RequestException as e:
            logger.error(f"网页抓取失败: {url}, 错误: {e}")
            return {"url": url, "status": "error", "error": str(e)}
        except Exception as e:
            logger.error(f"网页抓取异常: {url}, 错误: {e}")
            return {"url": url, "status": "error", "error": str(e)}

    def _generate_mock_scrape(self, url: str) -> Dict[str, Any]:
        """生成 Mock 抓取结果"""
        return {
            "url": url,
            "title": f"Mock 网页标题 - {url.split('/')[-1]}",
            "text": "这是一个 Mock 网页内容。在实际环境中，这里会显示从网页抓取的真实内容。由于网页抓取依赖未安装，系统使用了 Mock 数据。\n\n在实际应用中，我们会从网页中提取标题、正文、描述等信息，并将其转换为本体文档。",
            "description": "这是一个 Mock 网页描述，模拟从网页抓取的内容。",
            "links": [
                {"url": url, "text": "原文链接"},
                {"url": "https://example.com", "text": "相关链接"}
            ],
            "publish_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "mock",
            "mock": True,
            "mock_reason": "dependencies_not_available"
        }

    def _extract_title(self, soup: Any) -> str:
        """提取网页标题"""
        # 优先从 meta 标签获取
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content", "").strip()

        # 次选 h1 标签
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        # 最后从 title 标签获取
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip()

        return "无标题"

    def _extract_text(self, soup: Any) -> str:
        """提取正文内容"""
        content_selectors = [
            "article",
            "[itemprop=articleBody]",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "main",
            "#content"
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text

        # 如果没有找到，返回 body 的文本
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)

    def _extract_description(self, soup: Any) -> str:
        """提取网页描述"""
        # 优先从 meta 标签获取
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc.get("content", "").strip()

        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            return meta_desc.get("content", "").strip()

        return ""

    def _extract_links(self, soup: Any, base_url: str) -> List[Dict[str, str]]:
        """提取网页链接"""
        links = []
        for a in soup.find_all("a", href=True)[:20]:
            href = a["href"]
            text = a.get_text().strip()

            # 过滤空链接和锚点
            if href and not href.startswith("#") and text:
                # 处理相对 URL
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(base_url, href)

                links.append({"url": href, "text": text})

        return links

    def _extract_publish_date(self, soup: Any) -> Optional[str]:
        """提取发布日期"""
        date_selectors = [
            {"itemprop": "datePublished"},
            {"property": "article:published_time"},
            {"name": "publish-date"},
            {"name": "date"},
            {"class": "publish-date"},
            {"class": "post-date"},
        ]

        for attrs in date_selectors:
            meta = soup.find("meta", attrs=attrs)
            if meta:
                date_str = meta.get("content", "") or meta.get("datetime", "")
                if date_str:
                    return date_str[:10] if len(date_str) >= 10 else date_str

        # 尝试从时间标签获取
        time_tag = soup.find("time")
        if time_tag:
            return time_tag.get("datetime", "")[:10] if time_tag.get("datetime") else None

        return None
