"""Web 数据采集技能 - 提供联网搜索、网页爬取和浏览器自动化能力

包含三个核心 Skill:
- web_search: 搜索互联网获取信息
- web_crawl: 爬取指定网页内容（支持 JS 渲染降级）
- browser_automate: AI 驱动浏览器自动化采集（通过 MCP 调用 browser-use）
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging

from odap.tools.base import (
    BaseSkill,
    SkillInput,
    SkillOutput,
    SkillMetadata,
    get_registry,
)
from odap.tools import register_skill

logger = logging.getLogger(__name__)


# ============================================================
# 输入/输出模型（对应 data-model.md 第 4-9 节）
# ============================================================

class WebSearchInput(SkillInput):
    """Web 搜索输入"""
    query: str = Field(description="搜索关键词", min_length=1, max_length=500)
    max_results: int = Field(default=5, description="最大返回结果数", ge=1, le=20)
    search_depth: str = Field(default="basic", description="搜索深度: basic/advanced")


class WebCrawlInput(SkillInput):
    """Web 爬取输入"""
    url: str = Field(description="要爬取的网页 URL")
    output_format: str = Field(default="markdown", description="输出格式: markdown/fit_markdown/html/text")
    css_selector: Optional[str] = Field(default=None, description="内容提取 CSS 选择器")
    timeout: int = Field(default=30, description="超时时间（秒）", ge=5, le=120)


class SearchResultItem(BaseModel):
    """单条搜索结果（data-model.md 第 5 节）"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source_domain: str = ""
    published_date: str = ""


class WebSearchData(BaseModel):
    """搜索结果数据（data-model.md 第 4 节）"""
    query: str
    results: List[SearchResultItem] = Field(default_factory=list)
    total_count: int = 0
    engine_used: str = "unknown"
    source: str = "external"
    confidence: str = "medium"


class LinkItem(BaseModel):
    """页面链接（data-model.md 第 8 节）"""
    text: str = ""
    href: str = ""
    link_type: str = "external"


class PageMetadata(BaseModel):
    """页面元数据（data-model.md 第 9 节）"""
    title: str = ""
    description: str = ""
    author: str = ""
    published_date: str = ""
    language: str = ""


class WebCrawlData(BaseModel):
    """爬取结果数据（data-model.md 第 7 节）"""
    url: str
    title: str = ""
    content: str = ""
    links: List[LinkItem] = Field(default_factory=list)
    metadata: PageMetadata = Field(default_factory=PageMetadata)
    source: str = "external"
    confidence: str = "medium"
    is_complete: bool = True
    crawl_method: str = "requests_fallback"


class WebSearchSkill(BaseSkill):
    """使用搜索引擎搜索互联网信息"""

    metadata = SkillMetadata(
        name="web_search",
        description="搜索互联网获取信息。当用户提问涉及外部实时信息、最新动态、或内部图谱无法回答的问题时使用此工具。",
        category="web",
        danger_level="low",
        requires_opa_check=True,
        opa_action="data_collection:search",
        input_schema=WebSearchInput,
        version="1.0.0",
    )
    input_schema = WebSearchInput

    def execute(self, input_data: WebSearchInput) -> SkillOutput:
        try:
            results = self._do_search(input_data.query, input_data.max_results, input_data.search_depth)
            data = WebSearchData(
                query=input_data.query,
                results=results,
                total_count=len(results),
                engine_used=self._get_engine_name(),
                source="external",
                confidence="medium",
            )
            return SkillOutput(
                success=True,
                data=data.model_dump(),
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return SkillOutput(
                success=False,
                error=str(e),
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )

    def _do_search(self, query: str, max_results: int, search_depth: str) -> List[SearchResultItem]:
        """执行搜索，复用现有 SearchService 四级降级链"""
        try:
            from odap.biz.core.ontology.design.services.search_service import SearchService
            service = SearchService()
            # SearchService.search() 是 async 方法，使用 search_sync() 同步调用
            raw_results = service.search_sync(query, max_results=max_results)
            return self._normalize_results(raw_results)
        except ImportError:
            logger.warning("SearchService not available, using fallback")
            return self._fallback_search(query, max_results)

    def _normalize_results(self, raw_results: Any) -> List[SearchResultItem]:
        """将搜索结果标准化为统一格式"""
        if isinstance(raw_results, list):
            results = []
            for item in raw_results:
                if isinstance(item, dict):
                    results.append(SearchResultItem(
                        title=item.get("title", ""),
                        url=item.get("url", item.get("link", "")),
                        snippet=item.get("snippet", item.get("content", "")),
                        source_domain=self._extract_domain(item.get("url", item.get("link", ""))),
                        published_date=item.get("published_date", ""),
                    ))
                elif isinstance(item, str):
                    results.append(SearchResultItem(title=item))
            return results
        return []

    def _fallback_search(self, query: str, max_results: int) -> List[SearchResultItem]:
        """降级搜索：尝试 OH WebSearchTool"""
        try:
            from odap.biz.core.ontology.design.services.search_service import OHWebSearchProvider
            provider = OHWebSearchProvider()
            if provider.is_available():
                import asyncio
                raw = asyncio.run(provider.search(query, max_results=max_results))
                return self._normalize_results(raw)
        except Exception:
            pass
        return [SearchResultItem(title="搜索服务暂不可用", snippet=f"无法搜索: {query}")]

    def _get_engine_name(self) -> str:
        """获取当前使用的搜索引擎名称"""
        try:
            from odap.biz.core.ontology.design.services.search_service import SearchService
            service = SearchService()
            for provider in service.providers:
                if provider.is_available():
                    return provider.__class__.__name__
        except Exception:
            pass
        return "unknown"

    def _extract_domain(self, url: str) -> str:
        """从 URL 提取域名"""
        if not url:
            return ""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "")
        except Exception:
            return ""


class WebCrawlSkill(BaseSkill):
    """爬取指定 URL 的网页内容，支持 JS 渲染降级"""

    metadata = SkillMetadata(
        name="web_crawl",
        description="爬取指定网页内容，支持 JavaScript 渲染页面。当需要获取特定 URL 的详细内容时使用此工具。",
        category="web",
        danger_level="medium",
        requires_opa_check=True,
        opa_action="data_collection:crawl",
        input_schema=WebCrawlInput,
        version="1.0.0",
    )
    input_schema = WebCrawlInput

    def execute(self, input_data: WebCrawlInput) -> SkillOutput:
        try:
            result = self._crawl(input_data.url, input_data.output_format, input_data.css_selector, input_data.timeout)
            return SkillOutput(
                success=True,
                data=result,
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )
        except Exception as e:
            logger.error(f"Web crawl failed: {e}")
            return SkillOutput(
                success=False,
                error=str(e),
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )

    def _crawl(self, url: str, output_format: str, css_selector: Optional[str], timeout: int) -> Dict[str, Any]:
        """执行爬取，委托给 CrawlService（Crawl4AI 优先 → requests+BS4 降级）"""
        try:
            from odap.biz.data.web_crawl.services.crawl_service import CrawlService
            service = CrawlService()
            result = service.crawl_url(url, output_format, css_selector, timeout)
            if result.get("status") == "error":
                data = WebCrawlData(
                    url=url,
                    title="",
                    content=result.get("message", "Crawl failed"),
                    source="external",
                    confidence="low",
                    crawl_method="none",
                    is_complete=False,
                )
                return data.model_dump()
            # 将 service 返回的 dict 转换为 WebCrawlData
            raw_links = result.get("links", [])
            links = [LinkItem(**link) if isinstance(link, dict) else link for link in raw_links]
            raw_meta = result.get("metadata", {})
            metadata = PageMetadata(**raw_meta) if isinstance(raw_meta, dict) else PageMetadata()
            data = WebCrawlData(
                url=result.get("url", url),
                title=result.get("title", ""),
                content=result.get("content", ""),
                links=links,
                metadata=metadata,
                source=result.get("source", "external"),
                confidence=result.get("confidence", "medium"),
                is_complete=True,
                crawl_method=result.get("crawl_method", "requests_fallback"),
            )
            return data.model_dump()
        except Exception as e:
            logger.error(f"Crawl delegation failed: {e}")
            data = WebCrawlData(
                url=url,
                title="",
                content=f"爬取失败: {e}",
                source="external",
                confidence="low",
                crawl_method="none",
                is_complete=False,
            )
            return data.model_dump()


# ============================================================
# 创建 Skill 实例
# ============================================================

_web_search_skill = WebSearchSkill()
_web_crawl_skill = WebCrawlSkill()


# ============================================================
# 旧式裸函数（向后兼容，委托给 BaseSkill）
# ============================================================

def web_search(query: str, max_results: int = 5, search_depth: str = "basic"):
    """搜索互联网获取信息"""
    result = _web_search_skill.run({"query": query, "max_results": max_results, "search_depth": search_depth})
    if result.success:
        return result.data
    return {"status": "error", "message": result.error}


def web_crawl(url: str, output_format: str = "markdown", css_selector: str = None, timeout: int = 30):
    """爬取指定网页内容"""
    result = _web_crawl_skill.run({"url": url, "output_format": output_format, "css_selector": css_selector, "timeout": timeout})
    if result.success:
        return result.data
    return {"status": "error", "message": result.error}


# ============================================================
# 双注册：SKILL_CATALOG + SkillRegistry
# ============================================================

register_skill(
    name="web_search",
    description="搜索互联网获取信息。当用户提问涉及外部实时信息、最新动态、或内部图谱无法回答的问题时使用此工具。",
    handler=web_search,
    category="web",
)

register_skill(
    name="web_crawl",
    description="爬取指定网页内容，支持 JavaScript 渲染页面。当需要获取特定 URL 的详细内容时使用此工具。",
    handler=web_crawl,
    category="web",
)

# 用 BaseSkill 实例覆盖 LegacySkillAdapter
get_registry().register(_web_search_skill)
get_registry().register(_web_crawl_skill)

logger.info("Web skills registered: web_search, web_crawl")


# ============================================================
# BrowserAutomateSkill - AI 驱动浏览器自动化
# ============================================================

class BrowserAutomateInput(SkillInput):
    """浏览器自动化任务输入"""
    task: str = Field(..., description="自然语言描述的浏览器任务")
    url: Optional[str] = Field(None, description="起始 URL")
    max_steps: int = Field(25, description="最大执行步数")
    timeout_seconds: int = Field(300, description="超时时间（秒），硬限制 5 分钟")


class BrowserAutomateSkill(BaseSkill):
    """AI 驱动浏览器自动化采集 Skill

    通过 MCP 协议调用 browser-use MCP Server，
    执行复杂浏览器交互采集任务（如登录后采集）。
    """

    metadata = SkillMetadata(
        name="browser_automate",
        description="AI 驱动浏览器自动化采集。当需要执行复杂浏览器交互（如登录、多步操作、动态页面交互）时使用此工具。",
        category="web",
        danger_level="high",
        requires_opa_check=True,
        opa_action="data_collection:browser",
        input_schema=BrowserAutomateInput,
        version="1.0.0",
    )
    input_schema = BrowserAutomateInput

    def execute(self, input_data: BrowserAutomateInput) -> SkillOutput:
        """执行浏览器自动化任务，通过 MCP 协议层调用 browser-use Server

        优先通过 MCPService（MCPServerManagerV2）调用，享受连接池/重试/健康检查；
        若 MCPService 不可用则降级为直接 httpx 调用。
        """
        arguments = {
            "task": input_data.task,
            "max_steps": input_data.max_steps,
            "timeout_seconds": min(input_data.timeout_seconds, 300),  # 硬限制 5 分钟
        }
        if input_data.url:
            arguments["url"] = input_data.url

        # 优先：通过 MCPService（MCPServerManagerV2）调用
        result = self._call_via_mcp_service(arguments, input_data.timeout_seconds)
        if result is not None:
            return result

        # 降级：直接 httpx 调用（MCPService 不可用时）
        return self._call_via_httpx(arguments, input_data)

    def _call_via_mcp_service(self, arguments: Dict[str, Any], timeout_seconds: int):
        """通过 MCPService.call_tool 调用 browser-use MCP Server

        Returns:
            SkillOutput（仅成功时）或 None（失败/不可用时返回 None 以触发 httpx 降级）
        """
        try:
            import asyncio
            from odap.biz.integration.mcp_adapter.services.mcp_service import MCPService

            mcp_service = MCPService()

            # 确保内置 server 已注册
            try:
                mcp_service.register_builtin_servers()
            except Exception:
                pass  # 已注册或注册失败不阻塞，call_tool 会返回错误

            # Skill.execute 在同步上下文中，可安全使用 asyncio.run()
            result = asyncio.run(
                mcp_service.call_tool("browser-use", "browse_task", arguments)
            )

            if result.get("success"):
                data = result.get("data", {})
                # MCPService 返回的 data 可能嵌套在 "data" 字段中
                if isinstance(data, dict) and "data" in data and "success" in data:
                    inner = data["data"]
                    return SkillOutput(
                        success=data.get("success", False),
                        data=inner.get("data", inner) if isinstance(inner, dict) else inner,
                        execution_time_ms=result.get("execution_time_ms", 0),
                        skill_name=self.metadata.name,
                        request_id="",
                    )
                return SkillOutput(
                    success=True,
                    data=data,
                    execution_time_ms=result.get("execution_time_ms", 0),
                    skill_name=self.metadata.name,
                    request_id="",
                )
            else:
                # MCPService 调用失败（如 Server not found），降级到 httpx
                logger.debug(f"MCPService call failed ({result.get('error')}), falling back to httpx")
                return None
        except ImportError:
            logger.debug("MCPService not available, falling back to httpx")
            return None
        except Exception as e:
            logger.warning(f"MCPService call failed, falling back to httpx: {e}")
            return None

    def _call_via_httpx(self, arguments: Dict[str, Any], input_data: BrowserAutomateInput) -> SkillOutput:
        """降级方案：直接通过 httpx 调用 browser-use MCP Server"""
        try:
            import httpx
            import os

            mcp_url = os.environ.get("BROWSER_MCP_URL", "")
            if not mcp_url:
                try:
                    from odap.infra.config_composer import get_config
                    mcp_url = get_config("mcp.browser_mcp_url", "")
                except Exception:
                    pass
            if not mcp_url:
                mcp_url = "http://graphiti-browser-use:8030"

            # 同步调用 MCP Server（带超时）
            timeout = input_data.timeout_seconds + 30  # 额外 30s 网络缓冲
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    f"{mcp_url}/tools/browse_task/execute",
                    json=arguments,
                )
                resp.raise_for_status()
                result = resp.json()

            if result.get("success"):
                return SkillOutput(
                    success=True,
                    data=result.get("data", {}),
                    execution_time_ms=result.get("execution_time_ms", 0),
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id,
                )
            else:
                return SkillOutput(
                    success=False,
                    error=result.get("error", "Unknown browser automation error"),
                    execution_time_ms=result.get("execution_time_ms", 0),
                    skill_name=self.metadata.name,
                    request_id=input_data.request_id,
                )

        except httpx.TimeoutException:
            return SkillOutput(
                success=False,
                error=f"Browser automation timed out after {input_data.timeout_seconds}s",
                execution_time_ms=input_data.timeout_seconds * 1000,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )
        except httpx.ConnectError:
            return SkillOutput(
                success=False,
                error="Browser-use MCP Server unavailable. Ensure the browser-use container is running.",
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )
        except Exception as e:
            logger.error(f"Browser automation failed: {e}")
            return SkillOutput(
                success=False,
                error=str(e),
                execution_time_ms=0,
                skill_name=self.metadata.name,
                request_id=input_data.request_id,
            )


_browser_automate_skill = BrowserAutomateSkill()


def browser_automate(task: str, url: str = None, max_steps: int = 25, timeout_seconds: int = 300):
    """AI 驱动浏览器自动化采集"""
    result = _browser_automate_skill.run({
        "task": task, "url": url, "max_steps": max_steps, "timeout_seconds": timeout_seconds,
    })
    if result.success:
        return result.data
    return {"status": "error", "message": result.error}


register_skill(
    name="browser_automate",
    description="AI 驱动浏览器自动化采集。执行复杂浏览器交互（如登录后采集、多步操作）。仅 admin 角色可用。",
    handler=browser_automate,
    category="web",
)

get_registry().register(_browser_automate_skill)

logger.info("Web skills registered: web_search, web_crawl, browser_automate")
