"""
联网搜索模块 - 提供统一的搜索接口

功能:
- 支持多种搜索后端（DuckDuckGo、Tavily、SerpAPI、模拟）
- 自动降级处理
- 统一的搜索结果格式

使用方式:
```python
from odap.biz.core.ontology.services.search_service import SearchService

search_service = SearchService()
results = await search_service.search("美伊战争", max_results=5)
```
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger("search_service")

@dataclass
class SearchResult:
    """标准化搜索结果"""
    title: str
    url: str
    content: str
    snippet: str
    date: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "snippet": self.snippet,
            "date": self.date,
        }


class BaseSearchProvider:
    """搜索提供者基类"""

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """执行搜索"""
        raise NotImplementedError

    def is_available(self) -> bool:
        """检查是否可用"""
        raise NotImplementedError


class DuckDuckGoSearch(BaseSearchProvider):
    """DuckDuckGo 搜索（免费方案）"""

    def __init__(self):
        self._available = None

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """使用 DuckDuckGo HTML 搜索"""
        try:
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse

            encoded_query = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            results = []
            for result in soup.select('.result')[:max_results]:
                title_elem = result.select_one('.result__title a')
                snippet_elem = result.select_one('.result__snippet')
                date_elem = result.select_one('.result__timestamp')

                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get('href', '')

                    if link.startswith('/l/?uddg='):
                        from urllib.parse import unquote
                        parsed = urllib.parse.urlparse(link)
                        link = unquote(parsed.query.split('uddg=')[-1] if 'uddg=' in link else '')

                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                    date_str = date_elem.get_text(strip=True) if date_elem else ''

                    results.append(SearchResult(
                        title=title,
                        url=link,
                        content=snippet,
                        snippet=snippet,
                        date=date_str
                    ))

            logger.info(f"DuckDuckGo 搜索返回 {len(results)} 条结果")
            return results

        except Exception as e:
            logger.error(f"DuckDuckGo 搜索失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查网络连接"""
        if self._available is not None:
            return self._available

        try:
            import requests
            response = requests.get(
                "https://html.duckduckgo.com",
                timeout=5
            )
            self._available = response.status_code == 200
        except Exception:
            self._available = False

        return self._available


class TavilySearch(BaseSearchProvider):
    """Tavily API 搜索（需要 API Key）"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._get_api_key()
        self._available = None

    def _get_api_key(self) -> Optional[str]:
        """从环境变量获取 API Key"""
        import os
        return os.getenv('TAVILY_API_KEY', '')

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """使用 Tavily API 搜索"""
        if not self.api_key:
            logger.warning("Tavily API Key 未配置")
            return []

        try:
            import aiohttp

            url = "https://api.tavily.com/search"
            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": max_results,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    results = []

                    for item in data.get("results", []):
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            content=item.get("content", ""),
                            snippet=item.get("snippet", item.get("content", "")),
                            date=""
                        ))

                    logger.info(f"Tavily 搜索返回 {len(results)} 条结果")
                    return results

        except Exception as e:
            logger.error(f"Tavily 搜索失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查 API Key 是否配置"""
        self._available = bool(self.api_key)
        return self._available


class SerpAPISearch(BaseSearchProvider):
    """SerpAPI 搜索（需要 API Key）"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._get_api_key()

    def _get_api_key(self) -> Optional[str]:
        """从环境变量获取 API Key"""
        import os
        return os.getenv('SERPAPI_KEY', '')

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """使用 SerpAPI 搜索"""
        if not self.api_key:
            logger.warning("SerpAPI Key 未配置")
            return []

        try:
            import aiohttp

            url = "https://serpapi.com/search"
            params = {
                "q": query,
                "api_key": self.api_key,
                "num": max_results,
                "engine": "google",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    data = await resp.json()
                    results = []

                    for item in data.get("organic_results", [])[:max_results]:
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            content=item.get("snippet", ""),
                            snippet=item.get("snippet", ""),
                            date=""
                        ))

                    logger.info(f"SerpAPI 搜索返回 {len(results)} 条结果")
                    return results

        except Exception as e:
            logger.error(f"SerpAPI 搜索失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查 API Key 是否配置"""
        return bool(self.api_key)


class MockSearch(BaseSearchProvider):
    """模拟搜索（用于测试或无 API 时）"""

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """返回模拟搜索结果"""
        results = []
        for i in range(min(max_results, 3)):
            results.append(SearchResult(
                title=f"模拟搜索结果 {i+1}: {query}",
                url=f"https://mock-search.local/result{i+1}",
                content=f"这是关于 '{query}' 的模拟搜索内容，用于测试和演示。",
                snippet=f"模拟摘要：{query} 相关内容...",
                date=""
            ))

        logger.info(f"Mock 搜索返回 {len(results)} 条结果")
        return results

    def is_available(self) -> bool:
        """始终可用"""
        return True


class SearchService:
    """
    统一的搜索服务

    自动按优先级尝试各搜索提供者：
    1. Tavily（如果配置了 API Key）
    2. SerpAPI（如果配置了 API Key）
    3. DuckDuckGo（免费，无需配置）
    4. Mock（降级方案）

    使用示例:
    ```python
    search_service = SearchService()
    results = await search_service.search("美伊战争局势", max_results=5)

    for result in results:
        print(f"{result.title}\\n{result.url}\\n{result.snippet}\\n")
    ```
    """

    def __init__(self):
        self._providers: List[BaseSearchProvider] = []
        self._init_providers()

    def _init_providers(self):
        """初始化搜索提供者"""
        self._providers.append(TavilySearch())
        self._providers.append(SerpAPISearch())
        self._providers.append(DuckDuckGoSearch())
        self._providers.append(MockSearch())

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        执行搜索，自动选择可用的提供者

        Args:
            query: 搜索关键词
            max_results: 最大结果数

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        for provider in self._providers:
            if provider.is_available():
                logger.info(f"使用搜索提供者: {provider.__class__.__name__}")
                results = await provider.search(query, max_results)
                if results:
                    return results

        logger.warning("所有搜索提供者都不可用")
        return []

    def get_available_providers(self) -> List[str]:
        """获取所有可用的搜索提供者"""
        return [p.__class__.__name__ for p in self._providers if p.is_available()]
