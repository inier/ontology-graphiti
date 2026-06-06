"""
数据采集�?- 数据摄取与归纳模�?
实现 ADR-031 L2: Data Ingestion & Normalization

组件:
- NewsIngester: 联网检�?�?LLM 归纳 �?OntologyDocument
- ManualInputHandler: 表单/JSON/自然语言 �?OntologyDocument
- RandomEventGenerator: 涉事方行为模�?�?OntologyDocument（参�?NetLogo�?
- OntologyDocumentIO: 导入/导出 .odoc.json
- WebScraper: 网页内容抓取（免费方案，无需 API Key�?
"""

import json
import uuid
import random
import logging
import asyncio
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# 尝试导入网页抓取依赖
try:
    import requests
    from bs4 import BeautifulSoup
    WEB_SCRAPE_AVAILABLE = True
except ImportError:
    WEB_SCRAPE_AVAILABLE = False
    logging.warning("网页抓取依赖未安装，将使用 Mock 数据")

from ..schema.document import (
    OntologyDocument, OntologyEntity, OntologyRelation, OntologyEvent,
    OntologyAction, OntologyRule, OntologyConstraint, VersionRef,
    SourceInfo, DocumentMeta, TemporalInfo, SourceType, DocType,
    EntityType, ActionStatus, OntologyDocumentSchema, make_battle_event_document
)
from .document_io import OntologyDocumentIO

logger = logging.getLogger("data_ingestion")


# ─────────────────────────────────────────────────
# 联网检索采�?- NewsIngester
# ─────────────────────────────────────────────────

ONTOLOGY_EXTRACT_PROMPT = """
你是一位专业的情报分析师。请从以下新�?报道文本中提取结构化信息�?
输出符合 OntologyDocument 格式�?JSON（仅输出 JSON，不要任何解释）�?

【事件背景�?
{context}

【文本内容�?
{text}

【输出格式要求�?
{{
  "doc_id": "evt-{date}-xxxxx",
  "doc_type": "event",
  "source": {{"type": "news_ingest", "url": "{url}", "collected_at": "{timestamp}", "confidence": 0.8}},
  "meta": {{"title": "..", "description": "..", "tags": [..], "language": "zh", "classification": "SIM"}},
  "entities": [
    {{
      "entity_id": "unit-xxx-001",
      "entity_type": "Unit|Equipment|Location|Person|Organization",
      "name": "..",
      "name_en": "..",
      "basic_properties": {{"side": "red|blue|neutral", "location": "..", "status": ".."}},
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
      "location": "..",
      "participants": ["entity_id_1", "entity_id_2"],
      "description": "..",
      "outcome": {{}},
      "phase": ".."
    }}
  ],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": "新闻采集归纳"}}
}}

注意: 如果文本信息不足，合理推断并标注 confidence 较低值�?
"""


class NewsIngester:
    """
    联网检索并归纳�?OntologyDocument

    检索链�?
    本地 DuckDuckGo API (首�? �?Tavily API �?SerpAPI �?DuckDuckGo HTML 解析 (降级) �?Mock (无API�?
    """

    def __init__(self, llm_client=None, search_api_key: str = None, tavily_api_key: str = None):
        self.llm = llm_client
        # 优先使用传入的参数，其次从环境变量读�?
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
        联网检�?+ LLM 归纳 �?OntologyDocument 列表

        Args:
            query: 检索关键词（如 "B区遭遇战 2026"�?
            event_context: 事件背景描述（辅�?LLM 理解�?
            max_sources: 最大检索来源数

        Returns:
            List[OntologyDocument]: 验证通过的文档列�?
        """
        logger.info(f"开始联网检�? {query}")

        if self._use_mock:
            logger.warning("未配�?LLM/Search API，使用 Mock 数据")
            return self._generate_mock_news_docs(query, event_context)

        try:
            # 步骤1: 联网检�?
            search_results = await self._search(query, max_sources)
            if not search_results:
                logger.warning("检索结果为空，使用 Mock")
                return self._generate_mock_news_docs(query, event_context)

            # 步骤2: 汇总文�?
            combined_text = self._combine_sources(search_results)
            urls = [r.get("url", "") for r in search_results[:3]]

            # 步骤3: LLM 结构化抽�?
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
        """执行联网检索（本地 DuckDuckGo API / Tavily / SerpAPI / DuckDuckGo HTML / Mock）""
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
        logger.info("使用 Mock 检索结�?)
        return []

    async def _search_ddg_local(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """本地 DuckDuckGo API 检�?""
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
                logger.info(f"本地 DuckDuckGo API 返回 {len(results)} 条结�?)
                return results

    async def _search_tavily(self, query: str, max_results: int, search_depth: str = "basic") -> List[Dict[str, Any]]:
        """Tavily API 检�?""
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
        """DuckDuckGo HTML 解析检索（免费方案，无需 API Key�?

        通过抓取 DuckDuckGo HTML 搜索结果页面，解析出搜索结果
        """
        if not WEB_SCRAPE_AVAILABLE:
            logger.warning("DuckDuckGo 搜索需�?requests �?bs4 依赖")
            return []

        try:
            import urllib.parse
            import time
            
            # 尝试多个 DuckDuckGo 域名
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
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    }

                    logger.info(f"尝试 DuckDuckGo 搜索: {url}")
                    response = requests.get(url, headers=headers, timeout=10)
                    response.raise_for_status()

                    soup = BeautifulSoup(response.text, 'html.parser')

                    results = []
                    # 尝试多个可能的结果选择�?
                    selectors = [
                        '.result',
                        '.web-result',
                        '[data-testid="result"]',
                        '.search-result',
                    ]
                    
                    elements = []
                    for selector in selectors:
                        found = soup.select(selector)
                        if found:
                            logger.info(f"使用选择�?'{selector}' 找到 {len(found)} 个结�?)
                            elements = found
                            break
                    
                    for result in elements[:max_results]:
                        # 获取标题和链�?
                        title_elem = (result.select_one('.result__title a') or 
                                     result.select_one('a[href]') or 
                                     result.find('a', href=True))
                        snippet_elem = (result.select_one('.result__snippet') or 
                                       result.select_one('p') or 
                                       result.select_one('.description'))

                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            link = title_elem.get('href', '')

                            # 清理 DuckDuckGo 的跳转链�?
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
                        logger.info(f"DuckDuckGo 搜索返回 {len(results)} 条结�?)
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
                
                # 稍微延迟后尝试下一个域�?
                time.sleep(1)

            logger.warning("所�?DuckDuckGo 域名都无法访�?)
            return []

        except Exception as e:
            logger.error(f"DuckDuckGo 搜索失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []

    async def _search_serpapi(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """SerpAPI 搜索（备选方案，需�?API Key�?""
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
        """汇总多源文�?""
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
        # 提取 JSON �?
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
        """生成 Mock 新闻文档（无 API 时的降级�?""
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
        doc.meta.description = f"基于检索词 '{query}' 生成�?Mock 数据（{context or '无背�?}�?
        logger.info(f"生成 Mock 新闻文档: {doc.doc_id}")
        return [doc]

    async def from_json(self, raw_json: str, scenario_id: str = None) -> OntologyDocument:
        """验证并解�?JSON 字符�?""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}")

        # Schema 验证
        result = OntologyDocumentSchema.validate(data)
        if not result.is_valid:
            raise ValueError(f"Schema 验证失败: {'; '.join(result.errors)}")

        doc = OntologyDocument.from_dict(data)
        if scenario_id:
            doc.scenario_id = scenario_id
        doc.source.type = SourceType.MANUAL.value

        return doc

    async def from_natural_language(self, text: str, scenario_id: str = None) -> OntologyDocument:
        """
        自然语言 �?OntologyDocument（使�?LLM 转换�?
        如果没有 LLM，生成基础文档
        """
        if self.llm is None:
            # �?LLM：生成最简 event 文档
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=SourceInfo(type=SourceType.MANUAL.value, collected_at=now),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )
            doc.events.append(OntologyEvent(
                event_type="generic",
                timestamp=now,
                description=text[:500],
            ))
            doc.ontology_version.commit_message = f"自然语言输入: {text[:50]}"
            return doc

        # 使用 LLM 转换
        prompt = f"""将以下自然语言描述转换�?OntologyDocument JSON 格式（只输出 JSON�?

{text}

参考格�?
{{
  "doc_id": "manual-xxxxx",
  "doc_type": "event",
  "source": {{"type": "manual", "collected_at": "{datetime.now(timezone.utc).isoformat()}", "confidence": 0.95}},
  "meta": {{"title": "..", "description": "..", "tags": []}},
  "entities": [..],
  "relations": [..],
  "events": [..],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": ".."}}
}}"""

        try:
            if hasattr(self.llm, 'complete'):
                response = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'chat'):
                response = await self.llm.chat([{"role": "user", "content": prompt}])
            else:
                response = ""

            # 提取 JSON
            text_resp = response.strip()
            if "```json" in text_resp:
                text_resp = text_resp.split("```json")[1].split("```")[0].strip()
            elif "```" in text_resp:
                text_resp = text_resp.split("```")[1].split("```")[0].strip()

            data = json.loads(text_resp)
            doc = OntologyDocument.from_dict(data)
            if scenario_id:
                doc.scenario_id = scenario_id
            return doc
        except Exception as e:
            logger.error(f"LLM 转换失败: {e}，降级到基础文档")
            return await self.from_natural_language.__wrapped__(self, text, scenario_id) if hasattr(
                self.from_natural_language, '__wrapped__') else OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=SourceInfo(type=SourceType.MANUAL.value),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )


# ─────────────────────────────────────────────────
# 手动输入处理 - ManualInputHandler
# ─────────────────────────────────────────────────

class ManualInputHandler:
    """
    处理用户手动输入的动态信�?

    输入模式:
    1. 结构�?dict（来�?Web 表单�?
    2. 自由 JSON 字符串（直接粘贴�?
    3. 自然语言（LLM 转换，可选）
    """

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def from_form(self, form_data: dict, scenario_id: str = None) -> OntologyDocument:
        """从表�?dict 构建 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()

        doc = OntologyDocument(
            doc_id=form_data.get("doc_id") or f"manual-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}",
            doc_type=form_data.get("doc_type", DocType.EVENT.value),
            source=SourceInfo(
                type=SourceType.MANUAL.value,
                collected_at=now,
                confidence=1.0,
                author=form_data.get("author"),
            ),
            meta=DocumentMeta(
                title=form_data.get("title", "手动输入事件"),
                description=form_data.get("description", ""),
                tags=form_data.get("tags", []),
            ),
            scenario_id=scenario_id or form_data.get("scenario_id"),
        )

        # 解析实体
        for e_data in form_data.get("entities", []):
            doc.entities.append(OntologyEntity(**{
                k: v for k, v in e_data.items()
                if k in OntologyEntity.__dataclass_fields__
            }))

        # 解析关系
        for r_data in form_data.get("relations", []):
            temporal_data = r_data.pop("temporal", {})
            rel = OntologyRelation(**{
                k: v for k, v in r_data.items()
                if k in OntologyRelation.__dataclass_fields__ and k != "temporal"
            })
            if temporal_data:
                rel.temporal = TemporalInfo(**temporal_data)
            doc.relations.append(rel)

        # 解析事件
        for e_data in form_data.get("events", []):
            doc.events.append(OntologyEvent(**{
                k: v for k, v in e_data.items()
                if k in OntologyEvent.__dataclass_fields__
            }))

        # 版本
        doc.ontology_version.commit_message = f"手动输入: {doc.meta.title}"

        # 验证
        result = OntologyDocumentSchema.validate(doc)
        if not result.is_valid:
            raise ValueError(f"表单数据验证失败: {'; '.join(result.errors)}")

        return doc

    async def from_json(self, raw_json: str, scenario_id: str = None) -> OntologyDocument:
        """验证并解�?JSON 字符�?""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON 格式错误: {e}")

        # Schema 验证
        result = OntologyDocumentSchema.validate(data)
        if not result.is_valid:
            raise ValueError(f"Schema 验证失败: {'; '.join(result.errors)}")

        doc = OntologyDocument.from_dict(data)
        if scenario_id:
            doc.scenario_id = scenario_id
        doc.source.type = SourceType.MANUAL.value

        return doc

    async def from_natural_language(self, text: str, scenario_id: str = None) -> OntologyDocument:
        """
        自然语言�?OntologyDocument（使�?LLM 转换�?
        如果没有 LLM，生成基础文档
        """
        if self.llm is None:
            # �?LLM：生成最简 event 文档
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=SourceInfo(type=SourceType.MANUAL.value, collected_at=now),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )
            doc.events.append(OntologyEvent(
                event_type="generic",
                timestamp=now,
                description=text[:500],
            ))
            doc.ontology_version.commit_message = f"自然语言输入: {text[:50]}"
            return doc

        # 使用 LLM 转换
        prompt = f"""将以下自然语言描述转换�?OntologyDocument JSON 格式（只输出 JSON�?

{text}

参考格�?
{{
  "doc_id": "manual-xxxxx",
  "doc_type": "event",
  "source": {{"type": "manual", "collected_at": "{datetime.now(timezone.utc).isoformat()}", "confidence": 0.95}},
  "meta": {{"title": "..", "description": "..", "tags": []}},
  "entities": [..],
  "relations": [..],
  "events": [..],
  "actions": [],
  "rules": [],
  "constraints": [],
  "ontology_version": {{"version_id": "", "parent_version": null, "commit_message": ".."}}
}}"""

        try:
            if hasattr(self.llm, 'complete'):
                response = await self.llm.complete(prompt)
            elif hasattr(self.llm, 'chat'):
                response = await self.llm.chat([{"role": "user", "content": prompt}])
            else:
                response = ""

            # 提取 JSON
            text_resp = response.strip()
            if "```json" in text_resp:
                text_resp = text_resp.split("```json")[1].split("```")[0].strip()
            elif "```" in text_resp:
                text_resp = text_resp.split("```")[1].split("```")[0].strip()

            data = json.loads(text_resp)
            doc = OntologyDocument.from_dict(data)
            if scenario_id:
                doc.scenario_id = scenario_id
            return doc
        except Exception as e:
            logger.error(f"LLM 转换失败: {e}，降级到基础文档")
            now = datetime.now(timezone.utc).isoformat()
            doc = OntologyDocument(
                doc_type=DocType.EVENT.value,
                source=SourceInfo(type=SourceType.MANUAL.value, collected_at=now),
                meta=DocumentMeta(title="自然语言输入", description=text[:500]),
                scenario_id=scenario_id,
            )
            doc.events.append(OntologyEvent(
                event_type="generic",
                timestamp=now,
                description=text[:500],
            ))
            doc.ontology_version.commit_message = f"自然语言输入: {text[:50]}"
            return doc


# ─────────────────────────────────────────────────
# 随机事件生成�?- RandomEventGenerator
# 参�?NetLogo 多智能体行为概率模型
# ─────────────────────────────────────────────────

# ─────────────────────────────────────────────────
# 随机事件生成�?- 抽象基类
# ─────────────────────────────────────────────────

class BaseRandomGenerator(ABC):
    """随机事件生成器抽象基�?""

    @abstractmethod
    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """
        生成随机事件

        Args:
            parties: 参与方列表（可选，军事类使用）
            scenario_context: 场景上下�?
            count: 生成数量
            scenario_id: 场景ID

        Returns:
            List[OntologyDocument]: 生成的事件文档列�?
        """
        pass

    @abstractmethod
    def get_generator_name(self) -> str:
        """获取生成器名�?""
        pass

    @abstractmethod
    def get_generator_description(self) -> str:
        """获取生成器描�?""
        pass


class RandomEventGenerator(BaseRandomGenerator):
    """
    按涉事方和事件模板自动随机生成动态信�?
    参�?NetLogo 多智能体随机行为模型:
    - 每个涉事方有行为概率表（patrol/attack/retreat/reinforce�?
    - 基于当前状态（morale/supply/combat_power）权重调�?
    - 事件输出符合 OntologyDocument 格式
    """

    # 生成器类型标�?
    GENERATOR_TYPE = "military"
    GENERATOR_NAME = "军事战争事件生成�?
    GENERATOR_DESCRIPTION = "生成军事战争场景下的各种事件，包括进攻、巡逻、增援、撤退、侦察等行动"

    def get_generator_name(self) -> str:
        """获取生成器名�?""
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        """获取生成器描�?""
        return self.GENERATOR_DESCRIPTION

    # 涉事方行为概率表（参�?NetLogo�?
    PARTY_BEHAVIOR_PROFILES = {
        "red": {
            "attack": 0.40,
            "patrol": 0.25,
            "reinforce": 0.20,
            "retreat": 0.10,
            "recon": 0.05,
        },
        "blue": {
            "attack": 0.30,
            "patrol": 0.30,
            "reinforce": 0.25,
            "retreat": 0.10,
            "recon": 0.05,
        },
        "neutral": {
            "patrol": 0.55,
            "evacuate": 0.25,
            "report": 0.15,
            "cease_fire": 0.05,
        },
    }

    # 单位名称�?- 扩展版本
    UNIT_NAMES = {
        "red": [
            "红方装甲�?, "红方机步�?, "红方炮兵�?, "红方特战�?, "红方工兵�?, "红方防空�?,
            "红方摩步�?, "红方陆航�?, "红方电子对抗�?, "红方后勤保障�?, "红方侦察�?, "红方装甲�?,
            "红方空降�?, "红方装甲�?8�?, "红方合成�?, "红方信息化作战单�?,
        ],
        "blue": [
            "蓝方机步�?, "蓝方装甲�?, "蓝方炮兵�?, "蓝方海军陆战�?, "蓝方工兵�?, "蓝方防空�?,
            "蓝方特种作战�?, "蓝方空中突击�?, "蓝方装甲骑兵�?, "蓝方后勤支援�?, "蓝方电子战营", "蓝方炮兵�?,
            "蓝方机械化步兵师", "蓝方快速反应部�?, "蓝方两栖作战�?, "蓝方空中支援联队",
        ],
        "neutral": [
            "第三方观察团", "中立方协调员", "平民撤离�?, "联合国维和部�?, "人道主义救援组织",
            "国际红十字会代表", "当地平民志愿�?, "记者团",
        ],
    }

    # 扩展的地点库 - 包含更多类型的地�?
    LOCATIONS = [
        # 战术地点
        "A区北部高�?, "B区遭遇地�?, "C区渡�?, "D区城�?,
        "E区山地走�?, "F区海岸线", "G区平�?, "H区丛�?,
        "K区桥梁枢�?, "L区铁路交叉点", "M区机�?, "N区港口设�?,
        "O区山区要�?, "P区沙漠地�?, "Q区沼泽地�?, "R区城市郊�?,
        # 特定地点
        "108高地", "203号阵�?, "莲花湖地�?, "青河渡口", "龙山山口",
        "虎头山阵�?, "白云机场", "红星�?, "友谊�?, "中央平原",
    ]

    # 装备�?- 新增
    EQUIPMENT_TYPES = [
        "99A式主战坦�?, "96A式主战坦�?, "15式轻型坦�?,
        "04A式步战车", "86A式步战车", "08式步战车",
        "PLZ-05自行榴弹�?, "PLZ-07自行榴弹�?, "122毫米牵引�?,
        "AH-64阿帕�?, "Mi-28浩劫", "�?10武装直升�?,
        "东风-11弹道导弹", "东风-15战术导弹", "红旗-9防空系统",
        "翼龙无人�?, "彩虹无人�?, "侦察无人�?,
        "99式自行高�?, "04式弹炮合一系统", "09式轮式步战车",
    ]

    # 天气条件 - 新增
    WEATHER_CONDITIONS = [
        "晴朗", "多云", "阴天", "小雨", "中雨", "大雨",
        "大雾", "小雪", "中雪", "大风", "沙尘�?, "夜间",
    ]

    # 时间�?- 新增
    TIME_PERIODS = [
        "凌晨", "拂晓", "上午", "中午", "下午", "傍晚", "黄昏", "夜间", "深夜",
    ]

    # 地形类型 - 新增
    TERRAIN_TYPES = [
        "山地", "丘陵", "平原", "丛林", "沙漠", "沼泽", "城市", "海岸", "高原", "草原",
    ]

    # 事件类型对应关系
    ACTION_TO_EVENT = {
        "attack": "contact",
        "patrol": "patrol",
        "reinforce": "reinforce",
        "retreat": "retreat",
        "recon": "recon",
        "evacuate": "evacuate",
        "report": "report",
        "cease_fire": "cease_fire",
    }

    # 行动描述模板 - 新增，更丰富的描�?
    ACTION_DESCRIPTIONS = {
        "attack": [
            "对{opponent}发起突然袭击�?,
            "在{location}地区与{eqp}协同进攻{opponent}�?,
            "使用无人机侦察后，对{opponent}发动精确打击�?,
            "在{terrain}地形对{opponent}实施包围进攻�?,
        ],
        "patrol": [
            "在{location}附近进行例行巡逻，",
            "对{terrain}地带进行搜索排查�?,
            "在{eqp}掩护下对{location}实施巡逻，",
            "针对可疑目标进行定点巡逻，",
        ],
        "reinforce": [
            "增派{eqp}前往{location}支援�?,
            "从后方调集预备队增援{location}�?,
            "空中投送{eqp}至{location}�?,
            "通过公路机动向{location}输送增援力量，",
        ],
        "retreat": [
            "因战略调整主动撤离{location}�?,
            "在{eqp}掩护下有序撤退�?,
            "受恶劣天气{weather}影响暂时后撤�?,
            "完成阻击任务后主动撤出{location}�?,
        ],
        "recon": [
            "派遣侦察分队前往{location}搜集情报�?,
            "使用无人机对{terrain}地带实施抵近侦察�?,
            "化装侦察员潜入{location}获取情报�?,
            "电子侦察{location}区域的敌方通讯�?,
        ],
        "evacuate": [
            "组织平民从{location}安全撤离�?,
            "在{weather}条件下紧急疏散当地居民，",
            "开辟安全走廊协助民众撤离危险区域，",
            "医疗队前往{location}执行撤离任务�?,
        ],
        "report": [
            "向上级汇报{location}区域态势�?,
            "观察员报告{terrain}地带的最新情况，",
            "情报部门汇总并上报{location}侦察结果�?,
            "多方信息汇总后形成态势报告�?,
        ],
        "cease_fire": [
            "根据停火协议在{location}停止军事行动�?,
            "双方协商后在{terrain}地带实现停火�?,
            "联合国调停后在{location}实施停火�?,
            "暂时在{location}地区实行临时停火�?,
        ],
    }

    # 结果描述 - 新增
    OUTCOME_DESCRIPTIONS = {
        "attack": [
            "摧毁敌方{count}个目�?,
            "造成敌方重大伤亡",
            "成功突破敌方防线",
            "占领关键阵地",
            "击退敌方进攻",
        ],
        "patrol": [
            "未发现异常情�?,
            "发现可疑目标并标�?,
            "确认区域安全",
            "搜集到有价值情�?,
            "排除{count}处安全隐�?,
        ],
        "reinforce": [
            "有效增强了防御力�?,
            "及时补充了作战人�?,
            "提升了整体战斗力",
            "巩固了防�?,
            "扭转了不利局�?,
        ],
        "retreat": [
            "成功保存了有生力�?,
            "避免了更大损�?,
            "撤至安全区域",
            "完成战略转移",
            "重新部署完毕",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
        use_llm_for_description: bool = False,
    ) -> List[OntologyDocument]:
        """
        按涉事方生成随机事件

        Args:
            parties: 参与方列表（�?["red", "blue"]�?
            scenario_context: 当前场景状态（影响行为概率权重�?
            count: 生成事件数量
            scenario_id: 归属场景
            use_llm_for_description: 是否�?LLM 生成丰富描述

        Returns:
            List[OntologyDocument]
        """
        context = scenario_context or {}
        docs = []
        
        # 如果没有提供 parties，使用默认�?
        if not parties:
            parties = ["red", "blue"]

        for _ in range(count):
            # 随机选择涉事�?
            party = random.choice(parties)
            behavior_profile = self.PARTY_BEHAVIOR_PROFILES.get(party, self.PARTY_BEHAVIOR_PROFILES["red"])

            # 根据场景状态调整权�?
            adjusted_profile = self._adjust_weights(behavior_profile, context, party)

            # 随机选择行为
            action_type = self._weighted_choice(adjusted_profile)

            # 生成对手（仅进攻/撤退时有对手�?
            opponent = None
            if action_type in ["attack", "retreat", "reinforce"]:
                other_parties = [p for p in parties if p != party]
                if other_parties:
                    opponent = random.choice(other_parties)

            doc = await self._build_document(
                actor_party=party,
                action_type=action_type,
                opponent_party=opponent,
                context=context,
                scenario_id=scenario_id,
                use_llm=use_llm_for_description,
            )
            docs.append(doc)

        logger.info(f"随机生成 {len(docs)} 个事件（涉事�? {parties}�?)
        return docs

    def _adjust_weights(self, profile: dict, context: dict, party: str) -> dict:
        """根据场景状态动态调整行为权�?""
        adjusted = dict(profile)
        morale = context.get(f"{party}_morale", 0.7)
        supply = context.get(f"{party}_supply", 0.7)
        combat_power = context.get(f"{party}_combat_power", 0.7)

        # 士气�?�?增加撤退概率
        if morale < 0.4 and "retreat" in adjusted:
            adjusted["retreat"] = adjusted.get("retreat", 0) * 2
        # 供给不足 �?减少攻击概率
        if supply < 0.3 and "attack" in adjusted:
            adjusted["attack"] = adjusted.get("attack", 0) * 0.5
        # 战力�?�?增加进攻概率
        if combat_power > 0.8 and "attack" in adjusted:
            adjusted["attack"] = adjusted.get("attack", 0) * 1.5

        # 归一�?
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}
        return adjusted

    def _weighted_choice(self, weights: dict) -> str:
        """加权随机选择"""
        keys = list(weights.keys())
        values = list(weights.values())
        return random.choices(keys, weights=values, k=1)[0]

    async def _build_document(
        self,
        actor_party: str,
        action_type: str,
        opponent_party: Optional[str],
        context: dict,
        scenario_id: str,
        use_llm: bool,
    ) -> OntologyDocument:
        """构建随机事件 OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")
        location = random.choice(self.LOCATIONS)
        weather = random.choice(self.WEATHER_CONDITIONS)
        time_period = random.choice(self.TIME_PERIODS)
        terrain = random.choice(self.TERRAIN_TYPES)
        equipment = random.choice(self.EQUIPMENT_TYPES)

        actor_names = self.UNIT_NAMES.get(actor_party, ["未知部队"])
        actor_name = random.choice(actor_names)
        actor_id = f"unit-{actor_party}-{uuid.uuid4().hex[:6]}"

        # 随机生成单位属�?
        unit_types = ["armor", "infantry", "artillery", "recon", "mechanized", "airborne", "armored"]
        combat_power = round(random.uniform(0.4, 0.95), 2)
        morale = round(random.uniform(0.5, 0.95), 2)
        supply_level = round(random.uniform(0.3, 0.90), 2)

        entities = [
            OntologyEntity(
                entity_id=actor_id,
                entity_type=EntityType.UNIT.value,
                name=actor_name,
                name_en=actor_name,
                basic_properties={
                    "side": actor_party,
                    "location": location,
                    "status": "active",
                    "unit_type": random.choice(unit_types),
                    "equipment": equipment,
                    "time_period": time_period,
                    "weather": weather,
                },
                statistical_properties={
                    "combat_power": combat_power,
                    "morale": morale,
                    "supply_level": supply_level,
                    "casualty_rate": round(random.uniform(0.0, 0.15), 3),
                },
            )
        ]

        relations = []
        events = []
        actions = []

        event_type = self.ACTION_TO_EVENT.get(action_type, "generic")

        # 生成丰富的描�?
        description_template = random.choice(self.ACTION_DESCRIPTIONS.get(action_type, ["执行{action_type}任务"]))
        outcome_template = random.choice(self.OUTCOME_DESCRIPTIONS.get(action_type, ["任务完成"]))
        target_count = random.randint(1, 5)

        if opponent_party:
            opp_names = self.UNIT_NAMES.get(opponent_party, ["未知部队"])
            opp_name = random.choice(opp_names)
            opp_id = f"unit-{opponent_party}-{uuid.uuid4().hex[:6]}"

            entities.append(OntologyEntity(
                entity_id=opp_id,
                entity_type=EntityType.UNIT.value,
                name=opp_name,
                name_en=opp_name,
                basic_properties={
                    "side": opponent_party,
                    "location": location,
                    "status": "active",
                },
                statistical_properties={
                    "combat_power": round(random.uniform(0.4, 0.90), 2),
                    "morale": round(random.uniform(0.5, 0.90), 2),
                    "supply_level": round(random.uniform(0.4, 0.90), 2),
                },
            ))

            rel_type_map = {
                "attack": "engaged_with",
                "reinforce": "reinforces",
                "retreat": "retreats_from",
            }
            relations.append(OntologyRelation(
                relation_type=rel_type_map.get(action_type, "related_to"),
                source_entity=actor_id,
                target_entity=opp_id,
                temporal=TemporalInfo(start_time=now, is_current=True),
            ))

            # 使用模板生成描述
            description = description_template.format(
                opponent=opp_name,
                location=location,
                eqp=equipment,
                terrain=terrain,
                weather=weather
            ) + outcome_template.format(count=target_count)

            events.append(OntologyEvent(
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[actor_id, opp_id],
                description=description,
                outcome={
                    "terrain_control": random.choice(["contested", "held", "lost"]),
                    "weather": weather,
                    "time_period": time_period,
                    "terrain": terrain,
                    "target_count": target_count,
                },
                phase=random.choice(["initial", "main", "final"]),
            ))
            actions.append(OntologyAction(
                action_type=action_type,
                actor=actor_id,
                target=opp_id,
                timestamp=now,
                parameters={
                    "mode": random.choice(["aggressive", "cautious", "defensive"]),
                    "equipment": equipment,
                    "weather": weather,
                },
                status=ActionStatus.EXECUTED.value,
            ))
        else:
            # 使用模板生成描述
            description = description_template.format(
                opponent="",
                location=location,
                eqp=equipment,
                terrain=terrain,
                weather=weather
            ) + outcome_template.format(count=target_count)

            events.append(OntologyEvent(
                event_type=event_type,
                timestamp=now,
                location=location,
                participants=[actor_id],
                description=description,
                outcome={
                    "weather": weather,
                    "time_period": time_period,
                    "terrain": terrain,
                },
                phase="active",
            ))

        title = f"[随机] {actor_name} - {action_type} ({time_period})"
        if use_llm and self.llm:
            description = await self._enrich_description(description)

        doc = OntologyDocument(
            doc_id=f"rand-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=[actor_party, action_type, location, terrain, weather],
            ),
            entities=entities,
            relations=relations,
            events=events,
            actions=actions,
            ontology_version=VersionRef(commit_message=f"随机生成: {actor_name} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc

    async def _enrich_description(self, basic_desc: str) -> str:
        """使用 LLM 丰富事件描述"""
        try:
            prompt = f"请将以下军事事件描述扩展�?-2句更生动的叙述（保持事实）：{basic_desc}"
            if hasattr(self.llm, 'complete'):
                return await self.llm.complete(prompt)
        except Exception:
            pass
        return basic_desc


# ─────────────────────────────────────────────────
# 商业事件生成�?
# ─────────────────────────────────────────────────

class BusinessEventGenerator(BaseRandomGenerator):
    """商业事件生成�?- 生成商业场景下的各种事件"""

    GENERATOR_TYPE = "business"
    GENERATOR_NAME = "商业事件生成�?
    GENERATOR_DESCRIPTION = "生成商业场景下的各种事件，包括投资、并购、产品发布、市场变化等"

    # 商业事件类型
    BUSINESS_ACTIONS = [
        "investment", "acquisition", "merger", "product_launch",
        "market_expansion", "restructuring", "ipo", "partnership",
        "regulatory_change", "market_volatility", "partnership_dissolution",
        "market_entry", "market_exit"
    ]

    # 公司�?
    COMPANIES = {
        "tech": [
            "科技创新集团", "数字先锋公司", "智能科技股份", "网络创新企业",
            "数据智能公司", "云端科技集团", "人工智能实验�?, "软件巨头科技",
        ],
        "finance": [
            "华夏银行", "全球投资集团", "财富管理公司", "证券金融公司",
            "保险集团", "资产管理公司", "信托投资公司", "私募股权基金",
        ],
        "retail": [
            "零售巨头集团", "连锁超市股份", "电商平台公司", "购物中心集团",
            "品牌运营公司", "供应链管理企�?, "物流配送公�?, "跨境贸易集团",
        ],
        "manufacturing": [
            "重工业集�?, "装备制造公�?, "汽车制造企�?, "电子产业集团",
            "新能源公�?, "新材料科技", "化工产业股份", "精密制造企�?,
        ],
    }

    # 地点�?
    LOCATIONS = [
        "北京CBD", "上海陆家�?, "深圳南山", "杭州西湖",
        "广州天河", "成都高新�?, "武汉光谷", "西安高新�?,
        "南京河西", "苏州工业�?, "天津滨海", "重庆两江",
    ]

    # 事件描述模板
    EVENT_TEMPLATES = {
        "investment": [
            "{company}获得{amount}投资，用于{purpose}",
            "{company}完成{amount}融资，由{investor}领投",
            "{investor}向{company}投资{amount}",
        ],
        "acquisition": [
            "{company}收购{target}，交易金额{amount}",
            "{company}完成对{target}的收购，进军{industry}行业",
            "{target}被{company}以{amount}收购",
        ],
        "merger": [
            "{company}与{partner}合并，组建{new_company}",
            "{company}和{partner}宣布合并，市值达{amount}",
        ],
        "product_launch": [
            "{company}发布新产品{product}，定位{position}",
            "{company}推出{purpose}产品{product}",
            "{company}的新产品{product}正式上市",
        ],
        "market_expansion": [
            "{company}宣布进入{region}市场",
            "{company}在{region}开设首家门�?,
            "{company}完成{region}市场的战略布局",
        ],
        "restructuring": [
            "{company}宣布重大战略重组",
            "{company}进行业务调整，聚焦{focus}",
            "{company}优化组织架构，提升效�?,
        ],
        "ipo": [
            "{company}在{stock_market}上市，发行价{price}",
            "{company}IPO申请获批，即将登陆{stock_market}",
            "{company}成功上市，融资{amount}",
        ],
        "partnership": [
            "{company}与{partner}建立战略合作",
            "{company}和{partner}签署合作协议",
            "{company}与{partner}联合开发{product}",
        ],
        "partnership_dissolution": [
            "{company}与{partner}终止合作",
            "{company}和{partner}宣布解除合作关系",
            "{company}与{partner}的战略合作到�?,
        ],
        "market_entry": [
            "{company}正式进入{industry}行业",
            "{company}在{location}成立新公司，布局{industry}",
            "{company}宣布进入{region}市场",
        ],
        "market_exit": [
            "{company}退出{region}市场",
            "{company}宣布战略收缩，退出{industry}业务",
            "{company}决定剥离{industry}板块",
        ],
        "regulatory_change": [
            "{industry}行业迎来新政策，{company}积极响应",
            "{region}出台{industry}监管新规",
            "监管变化影响{industry}，{company}调整策略",
        ],
        "market_volatility": [
            "{stock_market}波动，{company}股价{change}",
            "市场不确定性增加，{company}调整投资策略",
            "{stock_market}指数{change}，{industry}板块承压",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def get_generator_name(self) -> str:
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        return self.GENERATOR_DESCRIPTION

    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """生成商业事件"""
        docs = []
        for _ in range(count):
            doc = await self._build_document(scenario_context, scenario_id)
            docs.append(doc)
        return docs

    async def _build_document(self, context: dict, scenario_id: str) -> OntologyDocument:
        """构建商业事件文档"""
        import random
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        action_type = random.choice(self.BUSINESS_ACTIONS)
        sector = random.choice(list(self.COMPANIES.keys()))
        company = random.choice(self.COMPANIES[sector])
        location = random.choice(self.LOCATIONS)

        company_id = f"company-{uuid.uuid4().hex[:6]}"

        # 随机生成金额
        amounts = ["1亿元", "5亿元", "10亿元", "50亿元", "100亿元", "500亿元"]
        amount = random.choice(amounts)

        # 随机生成其他相关公司
        other_sectors = [s for s in self.COMPANIES.keys() if s != sector]
        if other_sectors:
            target_sector = random.choice(other_sectors)
        else:
            target_sector = sector
        target = random.choice(self.COMPANIES[target_sector])
        partner = random.choice(self.COMPANIES[random.choice(list(self.COMPANIES.keys()))])

        investor = random.choice(self.COMPANIES[random.choice(list(self.COMPANIES.keys()))])

        # 生成产品
        products = ["智能平台", "解决方案", "创新产品", "生态系�?, "服务平台"]
        product = random.choice(products)

        purposes = ["技术研�?, "市场拓展", "产品创新", "团队建设", "产业升级"]
        purpose = random.choice(purposes)

        positions = ["高端市场", "中端市场", "大众市场", "细分市场"]
        position = random.choice(positions)

        focuses = ["核心业务", "技术创�?, "数字化转�?, "绿色发展"]
        focus = random.choice(focuses)

        regions = ["华东地区", "华南地区", "华北地区", "西部地区", "海外市场"]
        region = random.choice(regions)

        industries = ["科技", "金融", "制�?, "零售", "医疗"]
        industry = random.choice(industries)

        stock_markets = ["上交所", "深交所", "港交所", "纽交所", "纳斯达克"]
        stock_market = random.choice(stock_markets)

        prices = ["10�?, "20�?, "50�?, "100�?, "200�?]
        price = random.choice(prices)

        changes = ["大幅上涨5%", "上涨3%", "小幅上涨1%", "下跌2%", "大幅下跌5%", "波动加剧"]
        change = random.choice(changes)

        new_companies = ["创新集团", "联合企业", "控股公司", "产业集团"]
        new_company = random.choice(new_companies)

        # 获取模板
        template = random.choice(self.EVENT_TEMPLATES.get(action_type, ["{company}完成{action_type}"]))
        description = template.format(
            company=company,
            target=target,
            partner=partner,
            investor=investor,
            amount=amount,
            product=product,
            purpose=purpose,
            position=position,
            region=region,
            industry=industry,
            stock_market=stock_market,
            price=price,
            change=change,
            new_company=new_company,
            focus=focus,
            location=location
        )

        title = f"[商业] {company} - {action_type}"

        doc = OntologyDocument(
            doc_id=f"biz-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=[sector, action_type, location],
            ),
            entities=[
                OntologyEntity(
                    entity_id=company_id,
                    entity_type="Company",
                    name=company,
                    basic_properties={
                        "sector": sector,
                        "location": location,
                    },
                ),
            ],
            events=[
                OntologyEvent(
                    event_type=action_type,
                    timestamp=now,
                    location=location,
                    participants=[company_id],
                    description=description,
                    outcome={"amount": amount, "status": "announced"},
                ),
            ],
            ontology_version=VersionRef(commit_message=f"商业事件: {company} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc


# ─────────────────────────────────────────────────
# 科技事件生成�?
# ─────────────────────────────────────────────────

class TechEventGenerator(BaseRandomGenerator):
    """科技事件生成�?- 生成科技领域的事�?""

    GENERATOR_TYPE = "tech"
    GENERATOR_NAME = "科技事件生成�?
    GENERATOR_DESCRIPTION = "生成科技领域的事件，包括技术突破、产品发布、融资、学术成果等"

    TECH_ACTIONS = [
        "breakthrough", "product_launch", "research", "patent",
        "launch", "collaboration", "award", "funding",
        "expansion", "launch_failure", "data_breach", "partnership"
    ]

    TECH_COMPANIES = [
        "未来科技", "智能创新", "量子实验�?, "生物科技公司",
        "新能源技�?, "量子计算中心", "AI研究�?, "机器人公�?,
        "元宇宙科技", "区块链实验室", "云计算中�?, "大数据公�?,
        "5G创新中心", "芯片设计公司", "自动驾驶研究�?, "无人机技术公�?,
    ]

    RESEARCH_AREAS = [
        "人工智能", "量子计算", "生物医药", "新能�?, "材料科学",
        "航空航天", "深海探测", "脑科�?, "基因编辑", "机器�?,
    ]

    LOCATIONS = [
        "北京中关�?, "上海张江", "深圳南山", "杭州云栖",
        "武汉光谷", "成都天府", "西安高新", "苏州工业�?,
    ]

    EVENT_TEMPLATES = {
        "breakthrough": [
            "{company}在{area}领域取得重大突破",
            "{company}宣布{area}研究获得突破性进�?,
            "{area}领域传来好消息，{company}实现技术跨�?,
        ],
        "product_launch": [
            "{company}发布新一代{product}",
            "{company}的{product}正式亮相",
            "{company}推出革命性产品{product}",
        ],
        "research": [
            "{company}启动{area}研究计划",
            "{company}与高校合作开展{area}研究",
            "{company}在{area}领域发表重要论文",
        ],
        "patent": [
            "{company}获得{area}技术专�?,
            "{company}申请的新专利获批",
            "{company}在{area}领域专利布局加�?,
        ],
        "award": [
            "{company}荣获{award}奖项",
            "{company}的{product}获得国际认可",
            "{company}团队因{area}研究获奖",
        ],
        "funding": [
            "{company}完成{amount}融资",
            "{company}获得{amount}投资",
            "{company}估值达{amount}",
        ],
        "expansion": [
            "{company}成立海外研发中心",
            "{company}在{location}建立研究基地",
            "{company}业务扩展至{area}",
        ],
        "partnership": [
            "{company}与{partner}建立战略合作",
            "{company}与{partner}联合开发{product}",
            "{company}与科研机构合作研究{area}",
        ],
        # 补充缺失的模�?
        "launch": [
            "{company}推出全新{product}",
            "{company}在{location}发布{product}",
            "{company}的新产品{product}正式上线",
        ],
        "collaboration": [
            "{company}与{partner}开展深度合�?,
            "{company}联合{partner}共同研发{product}",
            "{company}与{partner}在{area}领域达成合作",
        ],
        "launch_failure": [
            "{company}的{product}遭遇挫折",
            "{company}发布的{product}面临技术挑�?,
            "{company}在{product}研发中遇到问�?,
        ],
        "data_breach": [
            "{company}发生数据安全事件",
            "{company}加强数据安全措施",
            "{company}在{area}领域完善数据保护",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def get_generator_name(self) -> str:
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        return self.GENERATOR_DESCRIPTION

    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """生成科技事件"""
        docs = []
        for _ in range(count):
            doc = await self._build_document(scenario_context, scenario_id)
            docs.append(doc)
        return docs

    async def _build_document(self, context: dict, scenario_id: str) -> OntologyDocument:
        """构建科技事件文档"""
        import random
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        action_type = random.choice(self.TECH_ACTIONS)
        company = random.choice(self.TECH_COMPANIES)
        location = random.choice(self.LOCATIONS)
        area = random.choice(self.RESEARCH_AREAS)

        company_id = f"tech-{uuid.uuid4().hex[:6]}"

        amounts = ["1000万元", "5000万元", "1亿元", "5亿元", "10亿元", "20亿元"]
        amount = random.choice(amounts)

        partners = ["清华大学", "北京大学", "中科�?, "华为", "阿里达摩�?, "腾讯AI Lab"]
        partner = random.choice(partners)

        products = ["智能平台", "AI芯片", "量子计算�?, "机器�?, "无人�?, "操作系统"]
        product = random.choice(products)

        awards = ["科技进步一等奖", "最佳创新奖", "国际设计大奖", "技术突破奖"]
        award = random.choice(awards)

        template = random.choice(self.EVENT_TEMPLATES.get(action_type, ["{company}完成{action_type}"]))
        description = template.format(
            company=company,
            partner=partner,
            amount=amount,
            area=area,
            product=product,
            award=award,
            location=location,
        )

        title = f"[科技] {company} - {action_type}"

        doc = OntologyDocument(
            doc_id=f"tech-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=["科技", action_type, area],
            ),
            entities=[
                OntologyEntity(
                    entity_id=company_id,
                    entity_type="TechCompany",
                    name=company,
                    basic_properties={
                        "sector": "technology",
                        "location": location,
                        "research_area": area,
                    },
                ),
            ],
            events=[
                OntologyEvent(
                    event_type=action_type,
                    timestamp=now,
                    location=location,
                    participants=[company_id],
                    description=description,
                    outcome={"research_area": area, "status": "announced"},
                ),
            ],
            ontology_version=VersionRef(commit_message=f"科技事件: {company} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc


# ─────────────────────────────────────────────────
# 医疗健康事件生成�?
# ─────────────────────────────────────────────────

class HealthEventGenerator(BaseRandomGenerator):
    """医疗健康事件生成�?- 生成医疗健康领域的事�?""

    GENERATOR_TYPE = "healthcare"
    GENERATOR_NAME = "医疗健康事件生成�?
    GENERATOR_DESCRIPTION = "生成医疗健康领域的事件，包括新药研发、临床试验、医疗突破等"

    HEALTH_ACTIONS = [
        "drug_approval", "clinical_trial", "breakthrough", "research",
        "device_approval", "outbreak", "vaccination", "treatment",
        "partnership", "funding", "merger", "recall"
    ]

    MEDICAL_INSTITUTIONS = [
        "仁和医院", "第一人民医院", "中心医院", "医药研究�?,
        "生物制药公司", "医疗器械集团", "基因科技公司", "疫苗研发中心",
        "中医研究�?, "专科医院集团", "体检中心", "康复医院",
    ]

    LOCATIONS = [
        "北京协和医院", "上海华山医院", "广州中山医院", "成都华西医院",
        "武汉同济医院", "南京鼓楼医院", "西安西京医院", "杭州浙一医院",
    ]

    DISEASES = [
        "癌症", "糖尿�?, "心血管疾�?, "阿尔茨海默症", "帕金森症",
        "艾滋�?, "流感", "新冠肺炎", "肝炎", "肺炎",
    ]

    DRUGS = [
        "创新靶向�?, "新型疫苗", "生物制剂", "基因疗法",
        "免疫治疗药物", "中药新药", "医疗器械", "诊断试剂",
    ]

    EVENT_TEMPLATES = {
        "drug_approval": [
            "{institution}的{drug}获得药监局批准上市",
            "{institution}研发的新药{drug}获批",
            "{drug}正式上市，用于治疗{disease}",
        ],
        "clinical_trial": [
            "{institution}启动{drug}临床试验",
            "{institution}开展{disease}新疗法临床试�?,
            "{drug}的III期临床试验取得积极结�?,
        ],
        "breakthrough": [
            "{institution}在{disease}治疗领域取得突破",
            "{institution}的{drug}显示显著疗效",
            "研究人员发现治疗{disease}的新方法",
        ],
        "research": [
            "{institution}开展{disease}研究",
            "{institution}发表{disease}研究论文",
            "{institution}在{research}领域取得进展",
        ],
        "device_approval": [
            "{institution}的医疗器械获�?,
            "{institution}研发的新设备上市",
            "新型{therapy}设备获得认证",
        ],
        "outbreak": [
            "{location}爆发{disease}疫情",
            "{disease}疫情在{location}扩散",
            "{institution}报告{disease}病例增加",
        ],
        "vaccination": [
            "{institution}开展新疫苗接种工作",
            "{location}启动大规模疫苗接�?,
            "{drug}疫苗接种率达�?,
        ],
        "treatment": [
            "{institution}采用新疗法治疗{disease}",
            "{institution}成功实施{technique}手术",
            "新型{therapy}疗法在{disease}治疗中应�?,
        ],
        "partnership": [
            "{institution}与{partner}合作研发新药",
            "{institution}与科研机构合作研究{disease}",
            "{institution}与{partner}建立医疗联盟",
        ],
        "funding": [
            "{institution}获得{amount}医疗研发资金",
            "{institution}的{research}项目获批资助",
            "{drug}研发项目融资{amount}",
        ],
        "merger": [
            "{institution}与{partner}合并",
            "医疗行业并购案：{institution}收购{partner}",
            "{institution}与{partner}达成战略合作",
        ],
        "recall": [
            "{institution}召回{drug}",
            "{institution}发布医疗器械召回公告",
            "{drug}因安全问题被召回",
        ],
    }

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def get_generator_name(self) -> str:
        return self.GENERATOR_NAME

    def get_generator_description(self) -> str:
        return self.GENERATOR_DESCRIPTION

    async def generate(
        self,
        parties: List[str] = None,
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None,
    ) -> List[OntologyDocument]:
        """生成医疗健康事件"""
        docs = []
        for _ in range(count):
            doc = await self._build_document(scenario_context, scenario_id)
            docs.append(doc)
        return docs

    async def _build_document(self, context: dict, scenario_id: str) -> OntologyDocument:
        """构建医疗健康事件文档"""
        import random
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        action_type = random.choice(self.HEALTH_ACTIONS)
        institution = random.choice(self.MEDICAL_INSTITUTIONS)
        location = random.choice(self.LOCATIONS)
        disease = random.choice(self.DISEASES)
        drug = random.choice(self.DRUGS)

        institution_id = f"medical-{uuid.uuid4().hex[:6]}"

        amounts = ["1000万元", "5000万元", "1亿元", "5亿元", "10亿元"]
        amount = random.choice(amounts)

        partners = ["医学�?, "研究所", "制药公司", "医疗器械�?, "疾控中心"]
        partner = random.choice(partners)

        techniques = ["机器�?, "微创", "介入", "定向", "无创"]
        technique = random.choice(techniques)

        therapies = ["免疫治疗", "基因治疗", "细胞治疗", "靶向治疗"]
        therapy = random.choice(therapies)

        researches = ["新药研发", "临床试验", "精准医疗", "医疗器械"]
        research = random.choice(researches)

        template = random.choice(self.EVENT_TEMPLATES.get(action_type, ["{institution}完成{action_type}"]))
        description = template.format(
            institution=institution,
            partner=partner,
            amount=amount,
            disease=disease,
            drug=drug,
            location=location,
            technique=technique,
            therapy=therapy,
            research=research,
        )

        title = f"[医疗] {institution} - {action_type}"

        doc = OntologyDocument(
            doc_id=f"health-{date_str}-{uuid.uuid4().hex[:6]}",
            doc_type=DocType.EVENT.value,
            source=SourceInfo(type=SourceType.RANDOM_GEN.value, collected_at=now, confidence=0.85),
            meta=DocumentMeta(
                title=title,
                description=description,
                tags=["医疗", action_type, disease],
            ),
            entities=[
                OntologyEntity(
                    entity_id=institution_id,
                    entity_type="MedicalInstitution",
                    name=institution,
                    basic_properties={
                        "type": "hospital" if "医院" in institution else "research",
                        "location": location,
                    },
                ),
            ],
            events=[
                OntologyEvent(
                    event_type=action_type,
                    timestamp=now,
                    location=location,
                    participants=[institution_id],
                    description=description,
                    outcome={"disease": disease, "status": "announced"},
                ),
            ],
            ontology_version=VersionRef(commit_message=f"医疗事件: {institution} {action_type}"),
            scenario_id=scenario_id,
        )
        return doc


# ─────────────────────────────────────────────────
# 随机事件生成器工�?
# ─────────────────────────────────────────────────

class RandomEventGeneratorFactory:
    """随机事件生成器工�?""

    _generators = {
        "military": RandomEventGenerator,
        "business": BusinessEventGenerator,
        "tech": TechEventGenerator,
        "healthcare": HealthEventGenerator,
    }

    _descriptions = {
        "military": "军事战争事件生成�?- 生成进攻、巡逻、增援、撤退等军事行�?,
        "business": "商业事件生成�?- 生成投资、并购、产品发布等商业事件",
        "tech": "科技事件生成�?- 生成技术突破、产品发布等科技事件",
        "healthcare": "医疗健康事件生成�?- 生成新药研发、临床试验等医疗事件",
    }

    @classmethod
    def get_generator(cls, generator_type: str, llm_client=None) -> BaseRandomGenerator:
        """获取指定类型的生成器"""
        generator_class = cls._generators.get(generator_type)
        if not generator_class:
            raise ValueError(f"未知的生成器类型: {generator_type}")
        return generator_class(llm_client=llm_client)

    @classmethod
    def get_available_generators(cls) -> dict:
        """获取所有可用的生成器及其描�?""
        return {
            gen_type: {
                "class": gen_class,
                "description": cls._descriptions.get(gen_type, ""),
            }
            for gen_type, gen_class in cls._generators.items()
        }

    @classmethod
    def list_generator_types(cls) -> list:
        """列出所有可用的生成器类�?""
        return list(cls._generators.keys())


# 网页内容抓取 - WebScraper（免费方案，无需 API Key�?
# ─────────────────────────────────────────────────

class WebScraper:
    """
    免费网页内容抓取�?

    功能:
    - 直接抓取网页内容（HTML�?
    - 提取标题、文本内容、链�?
    - 支持新闻网站、博客、文档等

    优点:
    - 完全免费，无需 API Key
    - 轻量级实现，依赖�?
    - 支持任意网页

    限制:
    - 无法获取 JavaScript 渲染的内�?
    - 部分网站有反爬措�?
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

        logger.info(f"开始抓取网�? {url}")

        try:
            response = requests.get(url, headers=self.headers, timeout=self.TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除脚本和样式元�?
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
            "text": "这是一�?Mock 网页内容。在实际环境中，这里会显示从网页抓取的真实内容。由于网页抓取依赖未安装，系统使用了 Mock 数据。\n\n在实际应用中，我们会从网页中提取标题、正文、描述等信息，并将其转换为本体文档�?,
            "description": "这是一�?Mock 网页描述，模拟从网页抓取的内容�?,
            "links": [
                {"url": url, "text": "原文链接"},
                {"url": "https://example.com", "text": "相关链接"}
            ],
            "publish_date": datetime.now().strftime("%Y-%m-%d"),
            "status": "success",
            "mock": True
        }

    def _extract_title(self, soup: Any) -> str:
        """提取网页标题"""
        # 优先�?meta 标签获取
        og_title = soup.find("meta", property="og:title")
        if og_title:
            return og_title.get("content", "").strip()

        # 次�?h1 标签
        h1 = soup.find("h1")
        if h1:
            return h1.get_text().strip()

        # 最后从 title 标签获取
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text().strip()

        return "无标�?

    def _extract_text(self, soup: Any) -> str:
        """提取正文内容"""
        # 尝试常见的内容容�?
        contentSelectors = [
            "article",
            "[itemprop=articleBody]",
            ".article-content",
            ".post-content",
            ".entry-content",
            ".content",
            "main",
            "#content"
        ]

        for selector in contentSelectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text

        # 如果没有找到，返�?body 的文�?
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)

    def _extract_description(self, soup: Any) -> str:
        """提取网页描述"""
        # 优先�?meta 标签获取
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
        # 尝试多种方式查找发布日期
        dateSelectors = [
            {"itemprop": "datePublished"},
            {"property": "article:published_time"},
            {"name": "publish-date"},
            {"name": "date"},
            {"class": "publish-date"},
            {"class": "post-date"},
        ]

        for attrs in dateSelectors:
            meta = soup.find("meta", attrs=attrs)
            if meta:
                date_str = meta.get("content", "") or meta.get("datetime", "")
                if date_str:
                    return date_str[:10] if len(date_str) >= 10 else date_str

        # 尝试从时间标签获�?
        time_tag = soup.find("time")
        if time_tag:
            return time_tag.get("datetime", "")[:10] if time_tag.get("datetime") else None

        return None


# ─────────────────────────────────────────────────
# 网页内容抓取集成�?NewsIngester
# ─────────────────────────────────────────────────

class FreeNewsIngester:
    """
    免费新闻摄入器（无需 API Key�?

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
        �?URL 抓取新闻内容并转换为 OntologyDocument

        Args:
            url: 新闻页面 URL
            title_hint: 标题提示（可选，用于增强提取�?
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
        """从抓取结果构�?OntologyDocument"""
        now = datetime.now(timezone.utc).isoformat()
        date_str = datetime.now().strftime("%Y%m%d")

        title = scrape_result.get("title", "网页内容")
        text = scrape_result.get("text", "")
        description = scrape_result.get("description", "")
        url = scrape_result.get("url", "")
        publish_date = scrape_result.get("publish_date")

        # 截取�?2000 字符作为描述
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
        """�?URL 生成 Mock 文档"""
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
        doc.meta.description = f"基于 URL '{url}' 生成�?Mock 数据（{context or '无背�?}�?
        logger.info(f"生成 Mock 网页文档: {doc.doc_id}")
        return [doc]
