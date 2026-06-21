"""
联网搜索模块 - 提供统一的搜索接口

功能:
- 支持多种搜索后端（Tavily、SerpAPI、OH WebSearchTool、Mock）
- 自动降级处理
- 统一的搜索结果格式
- Mock 仅在明确配置时启用

降级链（按优先级）:
1. Tavily（需 API Key，英文强）
2. SerpAPI（需 API Key，Google 引擎）
3. OH WebSearchTool（免费，DuckDuckGo HTML + NetworkGuard 防 SSRF）
4. Mock（仅 SEARCH_ALLOW_MOCK=true 时启用）

使用方式:
```python
from .search_service import SearchService

search_service = SearchService()
results = await search_service.search("美伊战争", max_results=5)
```
"""

import asyncio
import logging
import os
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


class OHWebSearchProvider(BaseSearchProvider):
    """基于 OpenHarness WebSearchTool 的搜索提供者

    复用 OH 内置的 WebSearchTool，优势：
    - NetworkGuard 防 SSRF 攻击
    - httpx 异步 HTTP 客户端
    - 正则解析 DuckDuckGo HTML 结果
    - 零额外依赖
    """

    def __init__(self):
        self._tool = None
        self._available = None

    def _get_tool(self):
        """延迟加载 OH WebSearchTool"""
        if self._tool is not None:
            return self._tool
        try:
            from openharness.tools.web_search_tool import WebSearchTool
            self._tool = WebSearchTool()
            logger.info("OH WebSearchTool loaded successfully")
        except ImportError:
            logger.debug("OpenHarness WebSearchTool not available")
            self._tool = False  # 标记为不可用，避免重复导入
        return self._tool if self._tool is not False else None

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """使用 OH WebSearchTool 执行搜索"""
        tool = self._get_tool()
        if not tool:
            return []

        try:
            from openharness.tools.web_search_tool import WebSearchToolInput
            from openharness.tools.base import ToolExecutionContext

            arguments = WebSearchToolInput(
                query=query,
                max_results=min(max_results, 10),
            )
            context = ToolExecutionContext(
                tool_metadata={},
                permission_checker=None,
                hook_executor=None,
                ask_user_prompt=None,
            )

            result = await tool.execute(arguments, context)

            if result.is_error:
                logger.warning("OH WebSearchTool returned error: %s", result.output)
                return []

            # 解析 OH 的纯文本输出格式:
            # Search results for: {query}
            # 1. {title}
            #    URL: {url}
            #    {snippet}
            return self._parse_oh_output(result.output, query)

        except Exception as e:
            logger.error("OH WebSearchTool search failed: %s", e)
            return []

    def _parse_oh_output(self, output: str, query: str) -> List[SearchResult]:
        """解析 OH WebSearchTool 的纯文本输出为 SearchResult 列表"""
        results = []
        lines = output.strip().split("\n")
        i = 0

        # 跳过标题行 "Search results for: ..."
        if lines and lines[0].startswith("Search results"):
            i = 1

        current_title = ""
        current_url = ""
        current_snippet = ""

        while i < len(lines):
            line = lines[i].strip()

            # 匹配编号标题行 "1. Title"
            if line and line[0].isdigit() and ". " in line:
                # 保存前一个结果
                if current_title:
                    results.append(SearchResult(
                        title=current_title,
                        url=current_url,
                        content=current_snippet,
                        snippet=current_snippet,
                        date="",
                    ))

                # 解析新标题
                dot_pos = line.index(". ")
                current_title = line[dot_pos + 2:].strip()
                current_url = ""
                current_snippet = ""

            # 匹配 URL 行 "URL: ..."
            elif line.startswith("URL:"):
                current_url = line[4:].strip()

            # 匹配摘要行（非空、非标题、非 URL）
            elif line and not line[0].isdigit():
                current_snippet = line

            i += 1

        # 保存最后一个结果
        if current_title:
            results.append(SearchResult(
                title=current_title,
                url=current_url,
                content=current_snippet,
                snippet=current_snippet,
                date="",
            ))

        logger.info("OH WebSearchTool returned %d results for: %s", len(results), query)
        return results

    def is_available(self) -> bool:
        """检查 OH WebSearchTool 是否可用"""
        if self._available is not None:
            return self._available
        tool = self._get_tool()
        self._available = tool is not None
        return self._available


class TavilySearch(BaseSearchProvider):
    """Tavily API 搜索（需要 API Key）"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or self._get_api_key()
        self._available = None

    def _get_api_key(self) -> Optional[str]:
        """从配置组合引擎获取 API Key"""
        try:
            from odap.infra.config_composer import get_config
            return get_config("search.tavily_api_key", "")
        except Exception:
            return os.environ.get("TAVILY_API_KEY", "")

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

                    logger.info("Tavily 搜索返回 %d 条结果", len(results))
                    return results

        except Exception as e:
            logger.error("Tavily 搜索失败: %s", e)
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
        """从在线配置获取 API Key（fallback 环境变量）"""
        try:
            from odap.infra.config_composer import get_config
            val = get_config("search.serpapi_key", "")
            if val:
                return val
        except Exception:
            pass
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

                    logger.info("SerpAPI 搜索返回 %d 条结果", len(results))
                    return results

        except Exception as e:
            logger.error("SerpAPI 搜索失败: %s", e)
            return []

    def is_available(self) -> bool:
        """检查 API Key 是否配置"""
        return bool(self.api_key)


class MockSearch(BaseSearchProvider):
    """模拟搜索（仅在 SEARCH_ALLOW_MOCK=true 时启用）

    默认不启用。仅在测试或演示环境明确配置时才加入降级链。
    """

    async def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """返回模拟搜索结果"""
        results = []
        for i in range(min(max_results, 3)):
            results.append(SearchResult(
                title=f"模拟搜索结果 {i+1}: {query}",
                url=f"https://mock-search.local/result{i+1}",
                content=f"这是关于 '{query}' 的模拟搜索内容，用于测试和演示。",
                snippet=f"模拟摘要：{query} 相关内容..",
                date=""
            ))

        logger.info("Mock 搜索返回 %d 条结果", len(results))
        return results

    def is_available(self) -> bool:
        """仅在环境变量明确启用时可用"""
        return os.environ.get("SEARCH_ALLOW_MOCK", "").lower() in ("true", "1", "yes")

    def to_dict_list(self, results: List[SearchResult]) -> List[Dict[str, Any]]:
        """将搜索结果转为带 is_mock 标记的 dict 列表"""
        return [{**r.to_dict(), "is_mock": True} for r in results]


class SearchService:
    """
    统一的搜索服务

    自动按优先级尝试各搜索提供者：
    1. Tavily（如果配置了 API Key）
    2. SerpAPI（如果配置了 API Key）
    3. OH WebSearchTool（免费，DuckDuckGo HTML + NetworkGuard）
    4. Mock（仅 SEARCH_ALLOW_MOCK=true 时启用）

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
        self._providers.append(OHWebSearchProvider())
        # MockSearch 仅在明确配置时加入降级链
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
            if not provider.is_available():
                continue

            logger.info("使用搜索提供者: %s", provider.__class__.__name__)
            if isinstance(provider, MockSearch):
                logger.warning("所有真实搜索提供者不可用，降级使用 MockSearch 返回模拟数据")

            try:
                results = await provider.search(query, max_results)
                if results:
                    return results
            except Exception as e:
                logger.error("搜索提供者 %s 执行失败: %s", provider.__class__.__name__, e)
                continue

        logger.warning("所有搜索提供者都不可用")
        return []

    def search_sync(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """同步版本的搜索方法，供非异步上下文使用"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在异步上下文中，用 run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.search(query, max_results))
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(self.search(query, max_results))
        except RuntimeError:
            return asyncio.run(self.search(query, max_results))

    @property
    def providers(self) -> List[BaseSearchProvider]:
        """暴露 providers 列表（向后兼容）"""
        return self._providers

    def get_available_providers(self) -> List[str]:
        """获取所有可用的搜索提供者"""
        return [p.__class__.__name__ for p in self._providers if p.is_available()]
