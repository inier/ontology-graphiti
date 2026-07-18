"""Web 爬取 API Schema 定义"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(description="搜索关键词", min_length=1, max_length=500)
    max_results: int = Field(default=5, description="最大返回结果数", ge=1, le=20)
    search_depth: str = Field(default="basic", description="搜索深度: basic/advanced")


class SearchResultItem(BaseModel):
    """单条搜索结果"""
    title: str = ""
    url: str = ""
    snippet: str = ""
    source_domain: str = ""
    published_date: str = ""


class SearchResponse(BaseModel):
    """搜索响应"""
    query: str
    results: List[SearchResultItem] = Field(default_factory=list)
    total_count: int = 0
    engine_used: str = "unknown"
    source: str = "external"
    confidence: str = "medium"


class CrawlRequest(BaseModel):
    """爬取请求"""
    url: str = Field(description="要爬取的网页 URL")
    output_format: str = Field(default="markdown", description="输出格式: markdown/fit_markdown/html/text")
    css_selector: Optional[str] = Field(default=None, description="内容提取 CSS 选择器")
    timeout: int = Field(default=30, description="超时时间（秒）", ge=5, le=120)


class LinkItem(BaseModel):
    """页面链接"""
    text: str = ""
    href: str = ""
    link_type: str = "external"


class CrawlResponse(BaseModel):
    """爬取响应"""
    url: str
    title: str = ""
    content: str = ""
    links: List[LinkItem] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: str = "external"
    confidence: str = "medium"
    is_complete: bool = True
    crawl_method: str = "requests_fallback"


class CrawlHealthResponse(BaseModel):
    """爬取服务健康状态"""
    crawl4ai_available: bool = False
    fallback_available: bool = True
    active_browsers: int = 0
    max_concurrent: int = 3
