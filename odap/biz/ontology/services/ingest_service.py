"""数据摄入服务 - 重构版本

提供统一的数据摄入服务，支持多种摄入方式:
- URL网页抓取
- 新闻搜索 (多引擎: Tavily, DuckDuckGo, SerpAPI, 本地DDG)
- 手动录入
- JSON导入
- 自然语言输入
- 随机事件生成
"""

import uuid
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from ..ingestion import (
    NewsIngester, ManualInputHandler, RandomEventGenerator,
    FreeNewsIngester, WebScraper, OntologyDocument
)
from ..storage import SQLiteIngestStorage
from .build_service import get_builder_service


logger = logging.getLogger("data_ingestion")


def get_local_time():
    """获取本地时间（带时区信息）"""
    return datetime.now(timezone.utc).astimezone()


@dataclass
class SearchResult:
    """搜索结果封装"""
    results: List[Dict[str, Any]]
    engine: str
    query: str

    @property
    def is_empty(self) -> bool:
        return not self.results


@dataclass
class IngestRecordBuilder:
    """摄入记录构建器"""
    source: str
    source_details: Dict[str, Any] = field(default_factory=dict)
    original_content: str = ""
    record_count: int = 0
    created_by: str = "system"

    def build(self) -> Dict[str, Any]:
        """构建摄入记录基础结构"""
        return {
            'id': str(uuid.uuid4()),
            'source': self.source,
            'source_details': self.source_details,
            'original_content': self.original_content,
            'record_count': self.record_count,
            'status': 'processing',
            'start_time': get_local_time().isoformat(),
            'created_by': self.created_by
        }


class WebSearchService:
    """
    统一的联网检索服务

    支持多种搜索引擎，按优先级尝试:
    1. Tavily API (需要配置 TAVILY_API_KEY)
    2. 本地 DuckDuckGo API (需要配置 DDG_API_URL)
    3. SerpAPI (需要配置 SERPAPI_KEY)
    4. DuckDuckGo HTML 解析 (免费，无需配置)
    """

    ENGINES = ['tavily', 'ddg_local', 'serpapi', 'ddg_html']

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._tavily_api_key = os.getenv("TAVILY_API_KEY", "")
        self._ddg_api_url = os.getenv("DDG_API_URL", "")
        self._serpapi_key = os.getenv("SERPAPI_KEY", "")
        self._news_ingester = NewsIngester(llm_client=llm_client)

    async def search(
        self,
        query: str,
        max_results: int = 5,
        preferred_engine: Optional[str] = None,
        search_depth: str = "basic"
    ) -> SearchResult:
        """
        执行联网检索

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            preferred_engine: 优先使用的引擎 (tavily/ddg_local/serpapi/ddg_html)
            search_depth: 搜索深度 (basic/advanced)

        Returns:
            SearchResult: 搜索结果封装
        """
        engines = [preferred_engine] if preferred_engine else self.ENGINES

        for engine in engines:
            if engine == 'tavily' and self._tavily_api_key:
                try:
                    results = await self._search_tavily(query, max_results, search_depth)
                    if results:
                        return SearchResult(results=results, engine='tavily', query=query)
                except Exception as e:
                    logger.warning(f"Tavily 搜索失败: {e}")

            elif engine == 'ddg_local' and self._ddg_api_url:
                try:
                    results = await self._search_ddg_local(query, max_results)
                    if results:
                        return SearchResult(results=results, engine='ddg_local', query=query)
                except Exception as e:
                    logger.warning(f"本地 DuckDuckGo API 搜索失败: {e}")

            elif engine == 'serpapi' and self._serpapi_key:
                try:
                    results = await self._search_serpapi(query, max_results)
                    if results:
                        return SearchResult(results=results, engine='serpapi', query=query)
                except Exception as e:
                    logger.warning(f"SerpAPI 搜索失败: {e}")

            elif engine == 'ddg_html':
                try:
                    results = await self._news_ingester._search_duckduckgo(query, max_results)
                    if results:
                        return SearchResult(results=results, engine='ddg_html', query=query)
                except Exception as e:
                    logger.warning(f"DuckDuckGo HTML 搜索失败: {e}")

        return SearchResult(results=[], engine='none', query=query)

    async def tavily_search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> SearchResult:
        """
        专门使用 Tavily API 进行搜索

        Args:
            query: 搜索关键词
            max_results: 最大结果数
            search_depth: 搜索深度 (basic/advanced)

        Returns:
            SearchResult: 搜索结果封装
        """
        if not self._tavily_api_key:
            raise ValueError("Tavily API Key 未配置，请设置 TAVILY_API_KEY 环境变量")

        results = await self._search_tavily(query, max_results, search_depth)
        return SearchResult(results=results, engine='tavily', query=query)

    async def _search_tavily(self, query: str, max_results: int, search_depth: str) -> List[Dict[str, Any]]:
        """Tavily API 检索"""
        return await self._news_ingester._search_tavily(query, max_results, search_depth)

    async def _search_ddg_local(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """本地 DuckDuckGo API 检索"""
        return await self._news_ingester._search_ddg_local(query, max_results)

    async def _search_serpapi(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """SerpAPI 检索"""
        return await self._news_ingester._search_serpapi(query, max_results)

    def combine_sources(self, results: List[Dict[str, Any]]) -> str:
        """汇总多源文本"""
        return self._news_ingester._combine_sources(results)

    async def extract_with_llm(
        self,
        text: str,
        context: str,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        """使用 LLM 抽取结构化信息"""
        return await self._news_ingester._extract_with_llm(text, context, urls)

    def has_tavily_key(self) -> bool:
        """检查是否配置了 Tavily API Key"""
        return bool(self._tavily_api_key and self._tavily_api_key != "your_tavily_api_key_here")


class IngestRecordManager:
    """
    摄入记录管理器

    负责摄入记录的创建、更新、完成、失败等生命周期管理
    """

    def __init__(self, storage: SQLiteIngestStorage):
        self.storage = storage

    def create(self, builder: IngestRecordBuilder) -> Tuple[str, Dict[str, Any]]:
        """
        创建摄入记录

        Args:
            builder: 摄入记录构建器

        Returns:
            Tuple[str, Dict]: (记录ID, 记录对象)
        """
        record = builder.build()
        self.storage.save_ingest_record(record)
        return record['id'], record

    def complete(
        self,
        record: Dict[str, Any],
        processed_count: int,
        extracted_data: Optional[Dict[str, Any]] = None,
        builds: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        完成摄入记录

        Args:
            record: 摄入记录
            processed_count: 已处理数量
            extracted_data: 提取的数据
            builds: 构建结果列表
        """
        record['status'] = 'completed'
        record['processed_count'] = processed_count
        record['end_time'] = get_local_time().isoformat()
        record['duration_seconds'] = (
            get_local_time() - datetime.fromisoformat(record['start_time'])
        ).total_seconds()

        if extracted_data:
            record['extracted_data'] = extracted_data
        if builds:
            record['builds'] = builds

        self.storage.update_ingest_record(record['id'], record)

    def fail(
        self,
        record: Dict[str, Any],
        error: Exception
    ) -> None:
        """
        标记摄入记录为失败

        Args:
            record: 摄入记录
            error: 异常对象
        """
        record['status'] = 'failed'
        record['errors'] = [{'message': str(error)}]
        record['end_time'] = get_local_time().isoformat()
        record['duration_seconds'] = (
            get_local_time() - datetime.fromisoformat(record['start_time'])
        ).total_seconds()

        self.storage.update_ingest_record(record['id'], record)


class DocumentProcessor:
    """
    文档处理器

    负责文档的保存、本体构建和统计
    """

    def __init__(self, storage: SQLiteIngestStorage, builder_service):
        self.storage = storage
        self.builder_service = builder_service

    async def process(
        self,
        documents: List[OntologyDocument],
        ingest_record: Dict[str, Any],
        scenario_id: str
    ) -> Tuple[List[str], Dict[str, int], List[Dict[str, Any]]]:
        """
        处理文档列表

        Args:
            documents: 文档列表
            ingest_record: 摄入记录
            scenario_id: 场景ID

        Returns:
            Tuple: (文档ID列表, 统计信息字典, 构建结果列表)
        """
        document_ids = []
        stats = {'entities': 0, 'relations': 0, 'events': 0}
        builds = []

        for doc in documents:
            document_ids.append(doc.doc_id)
            stats['entities'] += len(doc.entities)
            stats['relations'] += len(doc.relations)
            stats['events'] += len(doc.events)

            self.storage.save_ontology_document(doc)

            try:
                build_result = await self.builder_service.build_ontology(
                    document=doc,
                    scenario_id=scenario_id or "default",
                    workspace_id="default",
                    create_new_version=True
                )

                if 'build_id' in build_result:
                    builds.append({
                        'build_id': build_result['build_id'],
                        'document_id': doc.doc_id,
                        'status': build_result.get('status'),
                        'version_info': build_result.get('version_info')
                    })
            except Exception as e:
                logger.error(f"本体构建失败: {e}")

        return document_ids, stats, builds


class IngestService:
    """数据摄入服务 - 重构版本"""

    def __init__(self, llm_client=None):
        self.storage = SQLiteIngestStorage()
        self.llm_client = llm_client

        self.news_ingester = NewsIngester(llm_client=llm_client)
        self.manual_input_handler = ManualInputHandler(llm_client=llm_client)
        self.random_event_generator = RandomEventGenerator(llm_client=llm_client)
        self.web_scraper = WebScraper()
        self.free_news_ingester = FreeNewsIngester(
            scraper=self.web_scraper,
            llm_client=llm_client
        )
        self.builder_service = get_builder_service()

        self.web_search_service = WebSearchService(llm_client=llm_client)
        self.record_manager = IngestRecordManager(self.storage)
        self.document_processor = DocumentProcessor(self.storage, self.builder_service)

    async def ingest_from_url(
        self,
        url: str,
        event_context: str = "",
        scenario_id: str = None
    ) -> str:
        """从URL摄入数据（免费网页抓取方案）"""
        url = url.strip()

        builder = IngestRecordBuilder(
            source='url',
            source_details={'url': url, 'context': event_context},
            record_count=0
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            documents = await self.free_news_ingester.ingest(url, event_context=event_context)
            document_ids = [doc.doc_id for doc in documents]

            scrape_result = None
            if hasattr(self.free_news_ingester, 'scraper'):
                scrape_result = self.free_news_ingester.scraper.scrape(url)
                if scrape_result.get('status') == 'success':
                    ingest_record['original_content'] = scrape_result.get('text', '')
                else:
                    ingest_record['original_content'] = f"网页抓取失败: {scrape_result.get('error', '未知错误')}"

            source_data = self._build_source_data_from_scrape(scrape_result, documents, url)
            _, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default"
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': document_ids,
                'document_count': len(documents),
                **stats
            }

            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    async def ingest_from_news(
        self,
        query: str,
        event_context: str = "",
        max_sources: int = 5,
        scenario_id: str = None
    ) -> str:
        """从新闻搜索摄入数据（自动选择可用引擎）"""
        builder = IngestRecordBuilder(
            source='news',
            source_details={'query': query, 'max_sources': max_sources},
            original_content=query,
            record_count=max_sources
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            search_result = await self.web_search_service.search(query, max_sources)
            search_results = search_result.results

            if search_results:
                combined_text = self.web_search_service.combine_sources(search_results)
                ingest_record['original_content'] = combined_text
            else:
                combined_text = ""
                logger.warning(f"新闻搜索未返回结果，使用查询词作为原始内容: {query}")

            urls = [r.get("url", "") for r in search_results[:3]] if search_results else []
            raw_docs = await self.web_search_service.extract_with_llm(
                combined_text, event_context, urls
            )

            documents = []
            for doc_data in raw_docs:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    documents.append(OntologyDocument.from_dict(doc_data))

            source_data = self._build_source_data_from_search(search_results, documents)
            _, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default"
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id for doc in documents],
                'document_count': len(documents),
                'search_engine': search_result.engine,
                **stats
            }

            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    async def ingest_from_tavily(
        self,
        query: str,
        event_context: str = "",
        max_sources: int = 5,
        search_depth: str = "basic",
        scenario_id: str = None
    ) -> str:
        """使用 Tavily API 摄入数据"""
        builder = IngestRecordBuilder(
            source='tavily',
            source_details={
                'query': query,
                'search_depth': search_depth,
                'max_sources': max_sources
            },
            original_content=query,
            record_count=max_sources
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            search_result = await self.web_search_service.tavily_search(query, max_sources, search_depth)
            search_results = search_result.results

            if not search_results:
                raise RuntimeError("Tavily 搜索未返回结果")

            combined_text = self.web_search_service.combine_sources(search_results)
            urls = [r.get("url", "") for r in search_results[:3]]
            raw_docs = await self.web_search_service.extract_with_llm(
                combined_text, event_context, urls
            )

            documents = []
            for doc_data in raw_docs:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    documents.append(OntologyDocument.from_dict(doc_data))

            source_data = self._build_source_data_from_search(search_results, documents)
            _, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default"
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id for doc in documents],
                'document_count': len(documents),
                'search_engine': 'tavily',
                **stats
            }

            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    async def ingest_from_manual(
        self,
        form_data: Any,
        scenario_id: str = None
    ) -> str:
        """从手动输入摄入数据"""
        form_data_keys = []
        original_content = ""

        if isinstance(form_data, dict):
            form_data_keys = list(form_data.keys())
            original_content = str(form_data)
        elif isinstance(form_data, str):
            form_data = {"text": form_data}
            form_data_keys = ["text"]
            original_content = form_data["text"]
        else:
            form_data = {"data": str(form_data)}
            form_data_keys = ["data"]
            original_content = form_data["data"]

        builder = IngestRecordBuilder(
            source='manual',
            source_details={'form_data_keys': form_data_keys},
            original_content=original_content,
            record_count=1,
            created_by=form_data.get('author', 'system')
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            doc = await self.manual_input_handler.from_form(form_data, scenario_id)

            source_data = [{
                'url': '',
                'title': doc.meta.title or '手动输入',
                'text': original_content,
                'description': doc.meta.description or '',
                'publish_date': doc.source.collected_at or ''
            }]

            _, stats, builds = await self.document_processor.process(
                [doc], ingest_record, scenario_id or "default"
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id],
                'document_count': 1,
                **stats
            }

            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    async def ingest_from_json(
        self,
        raw_json: str,
        scenario_id: str = None
    ) -> str:
        """从 JSON 摄入数据"""
        builder = IngestRecordBuilder(
            source='json',
            source_details={'json_length': len(raw_json)},
            original_content=raw_json,
            record_count=1
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            doc = await self.manual_input_handler.from_json(raw_json, scenario_id)

            source_data = [{
                'url': '',
                'title': doc.meta.title or 'JSON输入',
                'text': raw_json,
                'description': doc.meta.description or '',
                'publish_date': doc.source.collected_at or ''
            }]

            _, stats, builds = await self.document_processor.process(
                [doc], ingest_record, scenario_id or "default"
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id],
                'document_count': 1,
                **stats
            }

            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    async def ingest_from_natural_language(
        self,
        text: str,
        scenario_id: str = None
    ) -> str:
        """从自然语言摄入数据"""
        builder = IngestRecordBuilder(
            source='natural_language',
            source_details={'text_length': len(text)},
            original_content=text,
            record_count=1
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            doc = await self.manual_input_handler.from_natural_language(text, scenario_id)

            source_data = [{
                'url': '',
                'title': doc.meta.title or '自然语言输入',
                'text': text,
                'description': doc.meta.description or '',
                'publish_date': doc.source.collected_at or ''
            }]

            _, stats, builds = await self.document_processor.process(
                [doc], ingest_record, scenario_id or "default"
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id],
                'document_count': 1,
                **stats
            }

            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    async def generate_random_events(
        self,
        parties: List[str],
        scenario_context: dict = None,
        count: int = 1,
        scenario_id: str = None
    ) -> str:
        """生成随机事件"""
        builder = IngestRecordBuilder(
            source='random',
            source_details={'parties': parties, 'count': count},
            original_content=f"随机生成 {count} 个事件，参与方: {parties}",
            record_count=count
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            documents = await self.random_event_generator.generate(
                parties, scenario_context, count, scenario_id
            )

            document_ids, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default"
            )

            source_data = [{
                'url': '',
                'title': '随机事件生成',
                'text': f"随机生成 {count} 个事件，参与方: {parties}",
                'description': f"生成了 {count} 个随机事件，包含 {stats['entities']} 个实体，{stats['relations']} 个关系，{stats['events']} 个事件",
                'publish_date': get_local_time().isoformat()
            }]

            extracted_data = {
                'source_data': source_data,
                'document_ids': document_ids,
                'document_count': len(documents),
                **stats
            }

            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as e:
            self.record_manager.fail(ingest_record, e)

        return record_id

    def _build_source_data_from_scrape(
        self,
        scrape_result: Optional[Dict],
        documents: List[OntologyDocument],
        url: str
    ) -> List[Dict[str, Any]]:
        """从抓取结果构建源数据"""
        source_data = []

        if scrape_result and scrape_result.get('status') == 'success':
            source_data.append({
                'url': scrape_result.get('url', ''),
                'title': scrape_result.get('title', ''),
                'text': scrape_result.get('text', ''),
                'description': scrape_result.get('description', ''),
                'publish_date': scrape_result.get('publish_date', '')
            })
        elif documents:
            for doc in documents:
                source_data.append({
                    'url': url,
                    'title': doc.meta.title or '网页内容',
                    'text': doc.meta.description or '',
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or ''
                })
        else:
            source_data.append({
                'url': url,
                'title': '网页内容',
                'text': '',
                'description': '',
                'publish_date': ''
            })

        return source_data

    def _build_source_data_from_search(
        self,
        search_results: List[Dict[str, Any]],
        documents: List[OntologyDocument]
    ) -> List[Dict[str, Any]]:
        """从搜索结果构建源数据"""
        source_data = []

        if search_results:
            for result in search_results:
                source_data.append({
                    'url': result.get('url', ''),
                    'title': result.get('title', ''),
                    'text': result.get('content', result.get('snippet', '')),
                    'description': result.get('snippet', ''),
                    'publish_date': result.get('date', '')
                })
        elif documents:
            for doc in documents:
                source_data.append({
                    'url': doc.source.url or '',
                    'title': doc.meta.title or '新闻内容',
                    'text': doc.meta.description or '',
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or ''
                })
        else:
            source_data.append({
                'url': '',
                'title': '新闻内容',
                'text': '',
                'description': '',
                'publish_date': ''
            })

        return source_data

    def get_ingest_status(self, ingest_id: str) -> Dict[str, Any]:
        """获取摄入状态"""
        return self.storage.get_ingest_record(ingest_id)

    def get_ingest_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取摄入历史"""
        return self.storage.get_ingest_records(limit)

    def get_ontology_documents(
        self,
        scenario_id: Optional[str] = None,
        limit: int = 100
    ) -> List[OntologyDocument]:
        """获取本体文档"""
        return self.storage.list_ontology_documents(scenario_id, limit)

    def get_ontology_document(self, doc_id: str) -> Optional[OntologyDocument]:
        """获取本体文档详情"""
        return self.storage.get_ontology_document(doc_id)


from odap.biz.ontology.schema.document import OntologyDocumentSchema

_ingest_service_instance = None

def get_ingest_service() -> IngestService:
    """获取摄入服务实例（单例）"""
    global _ingest_service_instance
    if _ingest_service_instance is None:
        _ingest_service_instance = IngestService()
    return _ingest_service_instance
