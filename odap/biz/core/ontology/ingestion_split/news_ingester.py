"""
数据采集层 - 联网检索采集模块
实现 ADR-031 L2: Data Ingestion & Normalization

NewsIngester: 联网检索 → LLM 归纳 → OntologyDocument
"""

import json
import uuid
import logging
import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.schema.document import (
    OntologyDocument, OntologyDocumentSchema, SourceType, DocType,
    make_battle_event_document,
)

logger = logging.getLogger("data_ingestion")


ONTOLOGY_EXTRACT_PROMPT = """
你是一位专业的情报分析师。请从以下新闻/报道文本中提取结构化信息，
输出符合 OntologyDocument 格式的 JSON（仅输出 JSON，不要任何解释）。

【事件背景】
{context}

【文本内容】
{text}

【输出格式要求】
{{
  "doc_id": "evt-{date}-xxxxx",
  "doc_type": "event",
  "source": {{"type": "news_ingest", "url": "{url}", "collected_at": "{timestamp}", "confidence": 0.8}},
  "meta": {{"title": "...", "description": "...", "tags": [...], "language": "zh", "classification": "SIM"}},
  "entities": [
    {{
      "entity_id": "unit-xxx-001",
      "entity_type": "Unit|Equipment|Location|Person|Organization",
      "name": "...",
      "name_en": "...",
      "basic_properties": {{"side": "red|blue|neutral", "location": "...", "status": "..."}},
      "statistical_properties": {{"combat_power": 0.0-1.0, "morale": 0.0-1.0}},
      "capabilities": {{}},
      "constraints": []
    }}
  ],
  "relations": [
    {{
      "relation_id": "rel-xxx",
      "relation_type": "engaged_with|commands|supported_by|deployed_at|reinforces",
      "source_entity": "entity_id",
      "target_entity": "entity_id",
      "properties": {{}},
      "temporal": {{"start_time": "{timestamp}", "is_current": true}}
    }}
  ],
  "events": [
    {{
      "event_id": "evt-xxx",
      "event_type": "contact|attack|retreat|reinforce|patrol|cease_fire",
      "timestamp": "{timestamp}",
      "location": "...",
      "participants": ["entity_id_1", "entity_id_2"],
      "description": "...",
      "outcome": {{}},
      "phase": "..."
    }}
  ],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": "新闻采集归纳"}}
}}

注意: 如果文本信息不足，合理推断并标注 confidence 较低值。
"""


class NewsIngester:
    """
    联网检索并归纳为 OntologyDocument

    检索链路:
    本地 DuckDuckGo API (首选) → Tavily API → SerpAPI → DuckDuckGo HTML 解析 (降级) → Mock (无API时)
    """

    def __init__(self, llm_client=None, search_api_key: str = None, tavily_api_key: str = None):
        self.llm = llm_client
        self._search_api_key = search_api_key or os.getenv('SERPAPI_KEY', '')
        self._tavily_api_key = tavily_api_key or os.getenv('TAVILY_API_KEY', '')
        self._ddg_api_url = os.getenv('DDG_API_URL', '')
        self._use_mock = (llm_client is None)

    async def ingest(
        self,
        query: str,
        event_context: str = "",
        max_sources: int = 5,
    ) -> List[OntologyDocument]:
        """
        联网检索 + LLM 归纳 → OntologyDocument 列表

        Args:
            query: 检索关键词（如 "B区遭遇战 2026"）
            event_context: 事件背景描述（辅助 LLM 理解）
            max_sources: 最大检索来源数

        Returns:
            List[OntologyDocument]: 验证通过的文档列表
        """
        logger.info(f"开始联网检索: {query}")

        if self._use_mock:
            logger.warning("未配置 LLM/Search API，使用 Mock 数据")
            return self._generate_mock_news_docs(query, event_context)

        try:
            # 步骤1: 联网检索
            search_results = await self._search(query, max_sources)
            if not search_results:
                logger.warning("检索结果为空，使用 Mock")
                return self._generate_mock_news_docs(query, event_context)

            # 步骤2: 汇总文本
            combined_text = self._combine_sources(search_results)
            urls = [r.get("url", "") for r in search_results[:3]]

            # 步骤3: LLM 结构化抽取
            raw_docs = await self._extract_with_llm(combined_text, event_context, urls)

            # 步骤4: 验证
            validated = []
            for doc_data in raw_docs:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    validated.append(OntologyDocument.from_dict(doc_data))
                else:
                    logger.warning(f"文档验证失败: {result.errors}")

            logger.info(f"成功归纳 {len(validated)} 个文档")
            return validated

        except Exception as e:
            logger.error(f"联网检索失败: {e}，使用 Mock")
            return self._generate_mock_news_docs(query, event_context)

    async def _search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """执行联网检索（本地 DuckDuckGo API → Tavily → SerpAPI → DuckDuckGo HTML → Mock）"""
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

        # 降级 Mock
        logger.info("使用 Mock 检索结果")
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

    async def _extract_with_llm(
        self, text: str, context: str, urls: List[str]
    ) -> List[Dict[str, Any]]:
        """使用 LLM 将文本抽取为 OntologyDocument JSON"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")
        url_str = urls[0] if urls else ""

        prompt = ONTOLOGY_EXTRACT_PROMPT.format(
            context=context or "领域事件分析",
            text=text,
            date=date_str,
            url=url_str,
            timestamp=now,
        )

        try:
            if hasattr(self.llm, 'complete'):
                response = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'chat'):
                response = await self.llm.chat([{"role": "user", "content": prompt}])
            else:
                return []

            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"LLM 抽取失败: {e}")
            return []

    def _parse_json_response(self, response: str) -> List[Dict[str, Any]]:
        """解析 LLM 响应中的 JSON"""
        text = response.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            elif isinstance(parsed, dict):
                return [parsed]
        except Exception:
            pass
        return []

    def _generate_mock_news_docs(self, query: str, context: str) -> List[OntologyDocument]:
        """生成 Mock 新闻文档（无 API 时的降级）"""
        doc = make_battle_event_document(
            title=f"新闻采集: {query}",
            red_unit="红方部队",
            blue_unit="蓝方部队",
            location="交战区域",
            event_type="contact",
            source_type=SourceType.NEWS_INGEST.value,
        )
        doc.source.url = f"https://mock-news.local/search?q={query}"
        doc.source.confidence = 0.6
        doc.meta.description = f"基于检索词 '{query}' 生成的 Mock 数据（{context or '无背景'}）"
        logger.info(f"生成 Mock 新闻文档: {doc.doc_id}")
        return [doc]
