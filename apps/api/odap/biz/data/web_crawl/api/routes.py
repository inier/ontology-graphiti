"""Web 爬取/搜索 API 路由

所有路由均需认证（Depends(get_current_user)），并通过 OPA 策略控制
域名访问权限（data_collection 包）。
"""

from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends

from odap.infra.security.jwt_auth import get_current_user
from odap.biz.data.web_crawl.api.schemas import (
    SearchRequest, SearchResponse, SearchResultItem,
    CrawlRequest, CrawlResponse, CrawlHealthResponse, LinkItem,
)
from odap.biz.data.web_crawl.services.search_service import SearchService
from odap.biz.data.web_crawl.services.crawl_service import CrawlService

router = APIRouter(prefix="/api/web", tags=["web-collection"])

_search_service = SearchService()
_crawl_service = CrawlService()


def _extract_domain(url: str) -> str:
    """从 URL 提取域名（去除 www. 前缀）"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except Exception:
        return ""


def _check_opa_permission(user: dict, action: str, target_domain: str = "") -> None:
    """检查 OPA data_collection 包权限，失败时抛出 403

    Args:
        user: JWT payload（含 role）
        action: 操作类型（search/crawl/browser）
        target_domain: 目标域名（crawl 操作需要）
    """
    from odap.infra.opa.opa_service import OPAManager

    opa_manager = OPAManager()
    opa_input = {
        "role": user.get("role", "guest"),
        "action": action,
    }
    if target_domain:
        opa_input["target_domain"] = target_domain

    allowed = opa_manager.check_package_permission("data_collection", opa_input)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"OPA policy denied {action} operation"
            + (f" for domain {target_domain}" if target_domain else ""),
        )


@router.post("/search", response_model=SearchResponse)
async def web_search(request: SearchRequest, user=Depends(get_current_user)):
    """搜索互联网获取信息

    需认证，并通过 OPA data_collection:search 策略校验。
    """
    try:
        _check_opa_permission(user, "search")
        result = _search_service.search(
            query=request.query,
            max_results=request.max_results,
            search_depth=request.search_depth,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Search failed"))
        return SearchResponse(
            query=result.get("query", request.query),
            results=[SearchResultItem(**r) for r in result.get("results", [])],
            total_count=result.get("total_count", 0),
            engine_used=result.get("engine_used", "unknown"),
            source=result.get("source", "external"),
            confidence=result.get("confidence", "medium"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl", response_model=CrawlResponse)
async def web_crawl(request: CrawlRequest, user=Depends(get_current_user)):
    """爬取指定 URL 的网页内容

    需认证，并通过 OPA data_collection:crawl 策略校验（含域名白名单）。
    """
    try:
        target_domain = _extract_domain(request.url)
        _check_opa_permission(user, "crawl", target_domain)
        result = _crawl_service.crawl_url(
            url=request.url,
            output_format=request.output_format,
            css_selector=request.css_selector,
            timeout=request.timeout,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message", "Crawl failed"))
        return CrawlResponse(
            url=result.get("url", request.url),
            title=result.get("title", ""),
            content=result.get("content", ""),
            links=[LinkItem(**link) for link in result.get("links", [])],
            metadata=result.get("metadata", {}),
            source=result.get("source", "external"),
            confidence=result.get("confidence", "medium"),
            is_complete=result.get("is_complete", True),
            crawl_method=result.get("crawl_method", "requests_fallback"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/crawl/health", response_model=CrawlHealthResponse)
async def crawl_health(user=Depends(get_current_user)):
    """检查爬取服务健康状态（需认证）"""
    try:
        result = _crawl_service.health_check()
        return CrawlHealthResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
