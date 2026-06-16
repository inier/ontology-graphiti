"""Web 数据采集技能 - 提供联网搜索、网页爬取和浏览器自动化能力

包含三个核心 Skill:
- web_search: 搜索互联网获取信息
- web_crawl: 爬取指定网页内容（支持 JS 渲染降级）
- browser_automate: AI 驱动浏览器自动化采集（通过 MCP 调用 browser-use）
"""

from typing import Optional, List, Dict, Any
from pydantic import Field
from datetime import datetime
import uuid
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
# 输入/输出模型
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


class SearchResultItem(dict):
    """单条搜索结果"""
    pass


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
            return SkillOutput(
                success=True,
                data={
                    "query": input_data.query,
                    "results": results,
                    "total_count": len(results),
                    "engine_used": self._get_engine_name(),
                    "source": "external",
                    "confidence": "medium",
                },
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

    def _do_search(self, query: str, max_results: int, search_depth: str) -> List[Dict[str, Any]]:
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

    def _normalize_results(self, raw_results: Any) -> List[Dict[str, Any]]:
        """将搜索结果标准化为统一格式"""
        if isinstance(raw_results, list):
            results = []
            for item in raw_results:
                if isinstance(item, dict):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", item.get("link", "")),
                        "snippet": item.get("snippet", item.get("content", "")),
                        "source_domain": self._extract_domain(item.get("url", item.get("link", ""))),
                        "published_date": item.get("published_date", ""),
                    })
                elif isinstance(item, str):
                    results.append({"title": item, "url": "", "snippet": "", "source_domain": "", "published_date": ""})
            return results
        return []

    def _fallback_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
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
        return [{"title": "搜索服务暂不可用", "url": "", "snippet": f"无法搜索: {query}", "source_domain": "", "published_date": ""}]

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
                return {"url": url, "title": "", "content": result.get("message", "Crawl failed"),
                        "links": [], "metadata": {}, "source": "external", "confidence": "low",
                        "crawl_method": "none", "is_complete": False}
            result["is_complete"] = True
            return result
        except Exception as e:
            logger.error(f"Crawl delegation failed: {e}")
            return {"url": url, "title": "", "content": f"爬取失败: {e}",
                    "links": [], "metadata": {}, "source": "external", "confidence": "low",
                    "crawl_method": "none", "is_complete": False}


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
        """执行浏览器自动化任务，通过 MCP 调用 browser-use Server"""
        try:
            import httpx
            import os

            mcp_url = os.environ.get(
                "BROWSER_MCP_URL",
                "http://graphiti-browser-use:8030",
            )

            payload = {
                "task": input_data.task,
                "max_steps": input_data.max_steps,
                "timeout_seconds": min(input_data.timeout_seconds, 300),  # 硬限制 5 分钟
            }
            if input_data.url:
                payload["url"] = input_data.url

            # 同步调用 MCP Server（带超时）
            timeout = input_data.timeout_seconds + 30  # 额外 30s 网络缓冲
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    f"{mcp_url}/tools/browse_task/execute",
                    json=payload,
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
