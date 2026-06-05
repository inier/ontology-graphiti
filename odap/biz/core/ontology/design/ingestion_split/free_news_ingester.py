"""
数据采集层 - 免费新闻摄入器
实现 ADR-031 L2: Data Ingestion & Normalization

FreeNewsIngester: 免费新闻摄入器（无需 API Key）
使用本地网页抓取 + 规则提取，而非 Tavily/SerpAPI
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .web_scraper import WebScraper
from ..schema.document import (
    OntologyDocument, OntologyEvent, VersionRef,
    SourceInfo, DocumentMeta, SourceType, DocType, make_battle_event_document,
)

logger = logging.getLogger("data_ingestion")


class FreeNewsIngester:
    """
    免费新闻摄入器（无需 API Key）

    使用本地网页抓取 + 规则提取，而非 Tavily/SerpAPI
    """

    def __init__(self, scraper: WebScraper = None, llm_client=None):
        self.scraper = scraper or WebScraper()
        self.llm = llm_client

    async def ingest(
        self,
        url: str,
        title_hint: str = "",
        event_context: str = "",
    ) -> List[OntologyDocument]:
        """
        从 URL 抓取新闻内容并转换为 OntologyDocument

        Args:
            url: 新闻页面 URL
            title_hint: 标题提示（可选，用于增强提取）
            event_context: 事件背景（可选）

        Returns:
            List[OntologyDocument]
        """
        logger.info(f"免费新闻摄入: {url}")

        try:
            # 抓取网页内容
            scrape_result = self.scraper.scrape(url)

            if scrape_result.get("status") != "success":
                logger.warning(f"网页抓取失败，使用 Mock: {scrape_result.get('error')}")
                return self._generate_mock_from_url(url, title_hint, event_context)

            # 构建 OntologyDocument
            doc = self._build_document(scrape_result, event_context)

            # 验证文档
            from odap.biz.core.ontology.design.schema.document import OntologyDocumentSchema
            result = OntologyDocumentSchema.validate(doc.to_dict())
            if result.is_valid:
                return [doc]
            else:
                logger.warning(f"文档验证失败: {result.errors}")
                return [doc]

        except Exception as e:
            logger.error(f"免费新闻摄入异常: {e}")
            return self._generate_mock_from_url(url, title_hint, event_context)

    def _build_document(self, scrape_result: Dict[str, Any], context: str) -> OntologyDocument:
        """从抓取结果构建 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        title = scrape_result.get("title", "网页内容")
        text = scrape_result.get("text", "")
        description = scrape_result.get("description", "")
        url = scrape_result.get("url", "")
        publish_date = scrape_result.get("publish_date")

        # 截取前 2000 字符作为描述
        desc = description or text[:500]

        doc = OntologyDocument(
            doc_id=f"web-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(
                type=SourceType.NEWS_INGEST.value,
                url=url,
                collected_at=now,
                confidence=0.75,
            ),
            meta=DocumentMeta(
                title=title,
                description=desc,
                tags=["网页抓取", "新闻"],
                language="zh",
            ),
            ontology_version=VersionRef(commit_message=f"网页抓取: {title[:30]}"),
        )

        # 如果有内容，添加一个通用事件
        if text:
            doc.events.append(OntologyEvent(
                event_type="report",
                timestamp=publish_date or now,
                location="未知",
                participants=[],
                description=text[:1000],
                outcome={},
                phase="initial",
            ))

        return doc

    def _generate_mock_from_url(self, url: str, title: str, context: str) -> List[OntologyDocument]:
        """从 URL 生成 Mock 文档"""
        doc = make_battle_event_document(
            title=title or f"网页内容: {url}",
            red_unit="红方部队",
            blue_unit="蓝方部队",
            location="未知区域",
            event_type="contact",
            source_type=SourceType.NEWS_INGEST.value,
        )
        doc.source.url = url
        doc.source.confidence = 0.5
        doc.meta.description = f"基于 URL '{url}' 生成的 Mock 数据（{context or '无背景'}）"
        logger.info(f"生成 Mock 网页文档: {doc.doc_id}")
        return [doc]
