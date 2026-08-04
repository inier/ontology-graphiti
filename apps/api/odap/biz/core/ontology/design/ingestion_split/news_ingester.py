"""
数据采集层 - 联网检索采集模块
实现 ADR-031 L2: Data Ingestion & Normalization
实现 ADR-074 §1.3: 摄入纯采集化（删除 LLM 抽取，产出 pending 态文档）

NewsIngester: 联网检索 → 汇总文本 → pending 态 OntologyDocument
  - 只负责数据采集和文本汇总，不做 LLM 结构化抽取
  - 产出的 OntologyDocument 六字段为空，transformation_status="pending"
  - 下游由 Hyper-Extract (he feed) 消费 pending 态文档进行结构化抽取
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from odap.infra.config_composer import get_config

from ..schema.document import (
    OntologyDocument, DocType,
    SourceType, SourceInfo, DocumentMeta, VersionRef,
)

logger = logging.getLogger("data_ingestion")


class NewsIngester:
    """
    联网检索采集器（纯采集，ADR-074 §1.3）

    检索链路:
    本地 DuckDuckGo API (首选) → Tavily API → SerpAPI → DuckDuckGo HTML 解析 (降级)

    产出: pending 态 OntologyDocument（entities/relations/events 等六字段为空），
    下游由 Hyper-Extract 消费进行结构化抽取。
    """

    def __init__(self, llm_client=None, search_api_key: str = None, tavily_api_key: str = None):
        """
        初始化采集器。

        Args:
            llm_client: 已废弃（ADR-074 §1.3），保留参数仅为向后兼容，不再使用。
            search_api_key: SerpAPI Key
            tavily_api_key: Tavily API Key
        """
        if llm_client is not None:
            logger.warning(
                "NewsIngester.llm_client 已废弃（ADR-074 §1.3），"
                "摄入层不再做 LLM 抽取，请改用 Hyper-Extract。"
            )
        self._search_api_key = search_api_key or get_config("search.serpapi_key", "")
        self._tavily_api_key = tavily_api_key or get_config("search.tavily_api_key", "")
        self._ddg_api_url = get_config("search.ddg_api_url", "")

    async def ingest(
        self,
        query: str,
        event_context: str = "",
        max_sources: int = 5,
        workspace_id: str = "default",
        ontology_id: Optional[str] = None,
    ) -> List[OntologyDocument]:
        """
        联网检索 → 汇总文本 → pending 态 OntologyDocument

        纯采集模式（ADR-074 §1.3）：不做 LLM 抽取，产出 pending 态文档，
        六字段（entities/relations/events/actions/rules/constraints）为空，
        transformation_status="pending"，由下游 HE 消费。

        Iter 2.2 (ADR-074 §2.2): 当 ontology_id 提供时，采集完成后自动将
        汇总文本投递到 HE KA 队列（三级优先级 normal），实现采集 → 队列 →
        HE 引擎的自动衔接。投递失败仅记录日志，不影响采集产出。

        Args:
            query: 检索关键词（如 "B区遭遇战 2026"）
            event_context: 事件背景描述（记录到 meta.description 辅助下游 HE 理解）
            max_sources: 最大检索来源数
            workspace_id: 工作空间ID（用于 HE kb 分区，默认 "default"）
            ontology_id: 目标本体ID。提供时触发自动队列投递；None 时不投递
                （向后兼容，不破坏现有调用方）。

        Returns:
            List[OntologyDocument]: pending 态文档列表（六字段为空）
        """
        logger.info(f"开始联网检索（纯采集模式）: {query}")

        try:
            # 步骤1: 联网检索
            search_results = await self._search(query, max_sources)

            if not search_results:
                logger.warning("检索结果为空，产出空 pending 态文档")
                docs = [self._build_pending_doc(query, event_context, "", [], workspace_id=workspace_id)]
            else:
                # 步骤2: 汇总文本
                combined_text = self._combine_sources(search_results)
                urls = [r.get("url", "") for r in search_results[:3]]

                # 步骤3: 构建 pending 态文档（不做 LLM 抽取）
                doc = self._build_pending_doc(
                    query, event_context, combined_text, urls,
                    workspace_id=workspace_id,
                )
                logger.info(
                    f"采集完成，产出 pending 态文档: {doc.doc_id} "
                    f"(transformation_status=pending, 文本长度={len(combined_text)}, "
                    f"raw_data_ref={doc.raw_data_ref})"
                )
                docs = [doc]

            # 步骤4 (Iter 2.2): 自动投递到 HE KA 队列
            if ontology_id:
                self._dispatch_to_queue(docs, workspace_id, ontology_id)

            # 步骤5 (Iter 3.2): #1 数据采集审计 — 写入 Graphiti (零 LLM)
            self._audit_ingestion(docs, workspace_id, query, search_results)

            return docs

        except Exception as e:
            logger.error(f"联网检索失败: {e}，产出空 pending 态文档")
            return [self._build_pending_doc(query, event_context, "", [], workspace_id=workspace_id)]

    def _audit_ingestion(
        self,
        docs: List[OntologyDocument],
        workspace_id: str,
        query: str,
        search_results: List[Dict[str, Any]],
    ) -> None:
        """Iter 3.2: #1 数据采集审计 — 写入 Graphiti (零 LLM, EpisodicNode.save)。

        记录何时从哪个数据源采集了什么，支持事实演化追溯。
        审计失败仅记录日志，不影响采集产出。
        """
        try:
            from odap.infra.security.graphiti_audit_writer import get_graphiti_audit_writer
            writer = get_graphiti_audit_writer()
            primary_url = ""
            if search_results:
                primary_url = search_results[0].get("url", "")
            for doc in docs:
                writer.log_ingestion_audit(
                    workspace_id=workspace_id,
                    doc_id=doc.doc_id,
                    source_type=doc.source.type,
                    source_url=primary_url,
                    raw_data_ref=doc.raw_data_ref or "",
                    query=query,
                    text_length=len(doc.meta.description or ""),
                )
        except Exception as exc:
            logger.warning("数据采集审计失败（不影响采集产出）: %s", exc)

    def _dispatch_to_queue(
        self,
        docs: List[OntologyDocument],
        workspace_id: str,
        ontology_id: str,
    ) -> None:
        """Iter 2.2: 将采集产出投递到 HE KA 队列。

        从 pending 态文档的 meta.description 中提取汇总文本，投递到
        ``odap_queue.feed_he_kb`` 任务（默认 normal 优先级）。

        投递失败仅记录日志，不影响采集产出（容错降级）。
        """
        try:
            from odap.infra.queue import dispatch_ingestion_to_queue

            for doc in docs:
                text = doc.meta.description or ""
                if not text:
                    logger.warning(
                        "跳过队列投递: 文档 %s 的 meta.description 为空",
                        doc.doc_id,
                    )
                    continue

                result = dispatch_ingestion_to_queue(
                    workspace_id=workspace_id,
                    ontology_id=ontology_id,
                    text=text,
                    source_doc_id=doc.doc_id,
                    priority="normal",
                )
                logger.info(
                    "队列投递: doc=%s mode=%s queue=%s status=%s task_id=%s",
                    doc.doc_id,
                    result.mode,
                    result.queue,
                    result.status,
                    result.task_id,
                )
        except Exception as exc:
            logger.warning(
                "队列投递失败（不影响采集产出）: %s",
                exc,
            )

    def _build_pending_doc(
        self,
        query: str,
        event_context: str,
        combined_text: str,
        urls: List[str],
        workspace_id: str = "default",
    ) -> OntologyDocument:
        """构建 pending 态 OntologyDocument（ADR-074 §1.3 + §2.1）。

        六字段为空，transformation_status="pending"，
        汇总文本存到 meta.description 供下游 HE 消费。

        Iter 3.1 (ADR-074 §2.1): 原始文本上传 MinIO 持久化，
        OntologyDocument 记录 raw_data_ref 支持原文回溯。
        """
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")
        doc_id = f"evt-{date_str}-{uuid.uuid4().hex[:6]}"
        primary_url = urls[0] if urls else ""

        # Iter 3.1: 上传原始文本到 MinIO（或本地降级）
        raw_data_ref = None
        if combined_text:
            raw_data_ref = self._upload_raw_data(
                workspace_id=workspace_id,
                doc_id=doc_id,
                text=combined_text,
                source_type="news_ingest",
            )

        # 将汇总文本截断到合理长度，作为 meta.description
        # 下游 HE 可通过 meta.description 获取采集的原文汇总
        # 完整原文通过 raw_data_ref 回溯
        description = combined_text[:2000] if combined_text else (
            f"[采集失败] 查询词: {query}，背景: {event_context or '无'}"
        )

        return OntologyDocument(
            doc_id=doc_id,
            doc_type=DocType.EVENT.value,
            source=SourceInfo(
                type=SourceType.NEWS_INGEST.value,
                url=primary_url,
                collected_at=now,
                confidence=0.8,
            ),
            meta=DocumentMeta(
                title=f"新闻采集: {query}",
                description=description,
                tags=["news_ingest", "pending"],
                language="zh",
                classification="SIM",
            ),
            # 六字段为空 — 下游 HE 负责结构化抽取
            entities=[],
            relations=[],
            events=[],
            actions=[],
            rules=[],
            constraints=[],
            ontology_version=VersionRef(
                commit_message=f"新闻采集（待 HE 抽取）: {query}",
            ),
            # pending 态 — 标识待下游 HE 消费
            transformation_status="pending",
            # Iter 3.1: 原始数据引用（MinIO 或本地降级地址）
            raw_data_ref=raw_data_ref,
        )

    def _upload_raw_data(
        self,
        workspace_id: str,
        doc_id: str,
        text: str,
        source_type: str = "news_ingest",
    ) -> Optional[str]:
        """Iter 3.1: 上传原始文本到 MinIO，返回 raw_data_ref。

        失败时降级到本地磁盘，保证 raw_data_ref 始终可用。
        """
        try:
            from odap.infra.storage.raw_data_storage import get_raw_data_storage
            storage = get_raw_data_storage()
            result = storage.upload_raw(
                workspace_id=workspace_id,
                doc_id=doc_id,
                text=text,
                source_type=source_type,
            )
            if result.get("status") == "success":
                ref = result.get("raw_data_ref")
                logger.info(
                    "原始数据已持久化: doc=%s ref=%s mode=%s",
                    doc_id, ref, result.get("storage_mode"),
                )
                return ref
            else:
                logger.warning("原始数据上传失败: %s", result.get("message"))
                return None
        except Exception as exc:
            logger.warning("原始数据上传异常（不影响采集）: %s", exc)
            return None

    async def _search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """执行联网检索（本地 DuckDuckGo API → Tavily → SerpAPI → DuckDuckGo HTML → 空结果）"""
        # 本地 DuckDuckGo API（首选）
        if self._ddg_api_url:
            try:
                return await self._search_ddg_local(query, max_results)
            except Exception as e:
                logger.warning(f"本地 DuckDuckGo API 检索失败: {e}")

        # Tavily
        if self._tavily_api_key:
            try:
                return await self._search_tavily(query, max_results)
            except Exception as e:
                logger.warning(f"Tavily 检索失败: {e}")

        # SerpAPI
        if self._search_api_key:
            try:
                return await self._search_serpapi(query, max_results)
            except Exception as e:
                logger.warning(f"SerpAPI 检索失败: {e}")

        # DuckDuckGo HTML 解析（免费方案）
        try:
            ddg_results = await self._search_duckduckgo(query, max_results)
            if ddg_results:
                return ddg_results
        except Exception as e:
            logger.warning(f"DuckDuckGo 检索失败: {e}")

        # 所有检索源均失败，返回空列表（调用方产出空 pending 态文档）
        logger.info("所有检索源均无结果")
        return []

    async def _search_ddg_local(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """本地 DuckDuckGo API 检索"""
        import aiohttp
        import urllib.parse

        encoded_query = urllib.parse.quote(query)
        url = f"{self._ddg_api_url}/search?q={encoded_query}&max_results={max_results}"

        logger.info(f"使用本地 DuckDuckGo API: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                results = []
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "content": item.get("content", item.get("snippet", "")),
                        "snippet": item.get("snippet", item.get("content", "")),
                        "date": item.get("date", ""),
                    })
                logger.info(f"本地 DuckDuckGo API 返回 {len(results)} 条结果")
                return results

    async def _search_tavily(self, query: str, max_results: int, search_depth: str = "basic") -> List[Dict[str, Any]]:
        """Tavily API 检索"""
        import aiohttp
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": self._tavily_api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                return data.get("results", [])

    async def _search_duckduckgo(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """DuckDuckGo HTML 解析检索（免费方案，无需 API Key）"""
        try:
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse
            import time
        except ImportError:
            logger.warning("DuckDuckGo 搜索需要 requests 和 bs4 依赖")
            return []

        domains = [
            "https://html.duckduckgo.com/html/?q=",
            "https://duckduckgo.com/html/?q=",
            "https://start.duckduckgo.com/html/?q=",
        ]

        encoded_query = urllib.parse.quote(query)

        for domain in domains:
            url = f"{domain}{encoded_query}"

            try:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }

                logger.info(f"尝试 DuckDuckGo 搜索: {url}")
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')

                results = []
                selectors = ['.result', '.web-result', '[data-testid="result"]', '.search-result']

                elements = []
                for selector in selectors:
                    found = soup.select(selector)
                    if found:
                        logger.info(f"使用选择器 '{selector}' 找到 {len(found)} 个结果")
                        elements = found
                        break

                for result in elements[:max_results]:
                    title_elem = (result.select_one('.result__title a') or
                                 result.select_one('a[href]') or
                                 result.find('a', href=True))
                    snippet_elem = (result.select_one('.result__snippet') or
                                   result.select_one('p') or
                                   result.select_one('.description'))

                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        link = title_elem.get('href', '')

                        if link.startswith('/l/?uddg='):
                            from urllib.parse import unquote
                            parsed = urllib.parse.urlparse(link)
                            link = unquote(parsed.query.split('uddg=')[-1] if 'uddg=' in link else '')

                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''

                        results.append({
                            "title": title,
                            "url": link,
                            "content": snippet,
                            "snippet": snippet,
                            "date": "",
                        })

                if results:
                    logger.info(f"DuckDuckGo 搜索返回 {len(results)} 条结果")
                    return results

            except requests.exceptions.Timeout:
                logger.warning(f"DuckDuckGo 域名 {domain} 请求超时")
                continue
            except requests.exceptions.ConnectionError:
                logger.warning(f"DuckDuckGo 域名 {domain} 连接失败")
                continue
            except requests.exceptions.RequestException as e:
                logger.warning(f"DuckDuckGo 域名 {domain} 请求失败: {e}")
                continue

            time.sleep(1)

        logger.warning("所有 DuckDuckGo 域名都无法访问")
        return []

    async def _search_serpapi(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """SerpAPI 搜索（备选方案，需要 API Key）"""
        import aiohttp

        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": self._search_api_key,
            "num": max_results,
            "engine": "google",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                results = []
                for item in data.get("organic_results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("link", ""),
                        "content": item.get("snippet", ""),
                        "snippet": item.get("snippet", ""),
                    })
                return results

    def _combine_sources(self, results: List[Dict[str, Any]]) -> str:
        """汇总多源文本"""
        parts = []
        for i, r in enumerate(results[:5], 1):
            title = r.get("title", "")
            content = r.get("content", r.get("snippet", ""))
            url = r.get("url", "")
            parts.append(f"[来源{i}] {title}\nURL: {url}\n{content[:1000]}")
        return "\n\n---\n\n".join(parts)
