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

from ..ingestion_split import (
    NewsIngester, ManualInputHandler, RandomEventGenerator,
    FreeNewsIngester, WebScraper
)
from ..schema.document import OntologyDocument
from ..storage import SQLiteIngestStorage
from .build_service import get_builder_service
from odap.biz.core.ontology.services.search_service import SearchService


logger = logging.getLogger("data_ingestion")


def get_local_time():
    """获取本地时间（带时区信息）"""
    return datetime.now(timezone.utc).astimezone()


@dataclass
class WebSearchResult:
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
    scenario_id: str = None
    workspace_id: str = "default"

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
            'created_by': self.created_by,
            'scenario_id': self.scenario_id,
            'workspace_id': self.workspace_id,
        }


class WebSearchService:

    def __init__(self, llm_client=None):
        self.llm = llm_client
        self._search_service = SearchService()
        self._news_ingester = NewsIngester(llm_client=llm_client)
        self._tavily_api_key = os.getenv("TAVILY_API_KEY", "")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        preferred_engine: Optional[str] = None,
        search_depth: str = "basic"
    ) -> WebSearchResult:
        results = await self._search_service.search(query, max_results)
        result_dicts = [r.to_dict() for r in results]
        providers = self._search_service.get_available_providers()
        engine_name = providers[0] if providers else 'none'
        return WebSearchResult(results=result_dicts, engine=engine_name, query=query)

    async def tavily_search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> WebSearchResult:
        from odap.biz.core.ontology.services.search_service import TavilySearch
        tavily = TavilySearch()
        if not tavily.is_available():
            raise ValueError("Tavily API Key 未配置，请设置 TAVILY_API_KEY 环境变量")
        results = await tavily.search(query, max_results)
        result_dicts = [r.to_dict() for r in results]
        return WebSearchResult(results=result_dicts, engine='tavily', query=query)

    def combine_sources(self, results: List[Dict[str, Any]]) -> str:
        return self._news_ingester._combine_sources(results)

    async def extract_with_llm(
        self,
        text: str,
        context: str,
        urls: List[str]
    ) -> List[Dict[str, Any]]:
        return await self._news_ingester._extract_with_llm(text, context, urls)

    def has_tavily_key(self) -> bool:
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
        
        # 保存构建历史
        if builds:
            import uuid
            for build in builds:
                entity_count = 0
                relation_count = 0
                event_count = 0
                if extracted_data:
                    entities_val = extracted_data.get('entities', 0)
                    relations_val = extracted_data.get('relations', 0)
                    events_val = extracted_data.get('events', 0)
                    entity_count = len(entities_val) if isinstance(entities_val, (list, tuple)) else (entities_val if isinstance(entities_val, (int, float)) else 0)
                    relation_count = len(relations_val) if isinstance(relations_val, (list, tuple)) else (relations_val if isinstance(relations_val, (int, float)) else 0)
                    event_count = len(events_val) if isinstance(events_val, (list, tuple)) else (events_val if isinstance(events_val, (int, float)) else 0)

                version_info = build.get('version_info') or {}
                status_val = build.get('status', 'completed')
                status_str = status_val.value if hasattr(status_val, 'value') else str(status_val)

                build_history = {
                    'id': str(uuid.uuid4()),
                    'ingest_id': record['id'],
                    'build_id': build.get('build_id'),
                    'version_id': version_info.get('version_id') if isinstance(version_info, dict) else None,
                    'document_id': build.get('document_id'),
                    'entity_count': entity_count,
                    'relation_count': relation_count,
                    'event_count': event_count,
                    'status': status_str,
                    'start_time': record['start_time'],
                    'end_time': record['end_time'],
                    'duration_seconds': record['duration_seconds']
                }
                self.storage.save_build_history(build_history)
        
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

    def update_original_content(self, record_id: str, content: str) -> None:
        """
        更新摄入记录的原始内容
        
        Args:
            record_id: 记录ID
            content: 新的原始内容
        """
        record = self.storage.get_ingest_record(record_id)
        if record:
            record['original_content'] = content
            self.storage.update_ingest_record(record_id, record)


def _lookup_ontology_id(scenario_id: str) -> Optional[str]:
    """从场景ID查找绑定的本体ID"""
    if not scenario_id or scenario_id == "default":
        return None
    try:
        from odap.biz.platform.workspace.impl.workspace import WorkspaceManager
        ws_manager = WorkspaceManager()
        scenario = ws_manager.get_scenario(scenario_id)
        if scenario and hasattr(scenario, 'ontology_id'):
            return scenario.ontology_id
    except Exception:
        pass
    return None


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
        scenario_id: str,
        ontology_id: str = None
    ) -> Tuple[List[str], Dict[str, int], List[Dict[str, Any]]]:
        """
        处理文档列表

        Args:
            documents: 文档列表
            ingest_record: 摄入记录
            scenario_id: 场景ID
            ontology_id: 本体ID

        Returns:
            Tuple: (文档ID列表, 统计信息字典, 构建结果列表)
        """
        document_ids = []
        stats = {'entities': 0, 'relations': 0, 'events': 0}
        builds = []

        # 如果未指定 ontology_id，自动从场景查找
        if not ontology_id and scenario_id:
            ontology_id = _lookup_ontology_id(scenario_id)

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
                    create_new_version=True,
                    ontology_id=ontology_id
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

        if llm_client is None:
            llm_client = self._create_llm_client()
        self.llm_client = llm_client

        self.news_ingester = NewsIngester(llm_client=self.llm_client)
        self.manual_input_handler = ManualInputHandler(llm_client=self.llm_client)
        self.random_event_generator = RandomEventGenerator(llm_client=self.llm_client)
        self.web_scraper = WebScraper()
        self.free_news_ingester = FreeNewsIngester(
            scraper=self.web_scraper,
            llm_client=self.llm_client
        )
        self.builder_service = get_builder_service()

        self.web_search_service = WebSearchService(llm_client=self.llm_client)
        self.record_manager = IngestRecordManager(self.storage)
        self.document_processor = DocumentProcessor(self.storage, self.builder_service)

    @staticmethod
    def _create_llm_client():
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.info("未配置 OPENAI_API_KEY，LLM 提取功能不可用，将降级为规则提取")
            return None
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            api_base = os.getenv("OPENAI_API_BASE", "https://open.bigmodel.cn/api/paas/v4")
            model = os.getenv("OPENAI_MODEL", "glm-4-flash")
            config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.7)
            client = ZhipuAIClient(config=config)
            logger.info(f"LLM 客户端初始化成功: model={model}, base_url={api_base}")
            return client
        except Exception as e:
            logger.warning(f"LLM 客户端初始化失败: {e}，将降级为规则提取")
            return None

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
            record_count=0,
            scenario_id=scenario_id
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
            record_count=max_sources,
            scenario_id=scenario_id
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
            record_count=max_sources,
            scenario_id=scenario_id
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
            original_content = form_data.get('text', form_data.get('content', str(form_data)))
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
            created_by=form_data.get('author', 'system'),
            scenario_id=scenario_id
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
            record_count=1,
            scenario_id=scenario_id
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
            record_count=1,
            scenario_id=scenario_id
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
        scenario_id: str = None,
        generator_type: str = "military",
        workspace_id: str = "default"
    ) -> str:
        """生成随机事件 - 简化版本，调用真实的 pipeline"""
        from ..ingestion_split import RandomEventGeneratorFactory
        from .pipeline_service import get_pipeline_service

        # 使用工厂类创建对应类型的生成器
        generator = RandomEventGeneratorFactory.get_generator(generator_type, self.llm_client)
        generator_name = generator.get_generator_name()

        # 先生成 documents，获取真实内容
        documents = await generator.generate(
            parties, scenario_context, count, scenario_id
        )

        # 构建丰富的事件描述
        event_descriptions = []
        for doc in documents:
            if doc.events:
                for event in doc.events:
                    event_descriptions.append(event.description)
            elif doc.entities:
                entity_names = [e.name for e in doc.entities]
                event_descriptions.append(f"实体: {', '.join(entity_names)}")

        if event_descriptions:
            detailed_text = " | ".join(event_descriptions)
        else:
            detailed_text = f"随机生成 {count} 个{generator_name}事件，参与方: {parties}"

        # 创建摄入记录，保存真实的 original_content
        builder = IngestRecordBuilder(
            source='random',
            source_details={
                'parties': parties,
                'count': count,
                'generator_type': generator_type,
                'generator_name': generator_name
            },
            original_content=detailed_text,
            record_count=count,
            scenario_id=scenario_id,
            workspace_id=workspace_id
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            # 调用真实的 pipeline 处理，这样会自动记录所有日志
            pipeline_service = get_pipeline_service()
            context = await pipeline_service.run(
                ingest_id=record_id,
                scenario_id=scenario_id or "default",
                source="random",
                source_details={
                    "parties": parties,
                    "count": count,
                    "generator_type": generator_type,
                    "generator_name": generator_name,
                    "scenario_context": scenario_context,
                    "content": detailed_text
                },
                workspace_id=workspace_id
            )

            # 完成摄入记录
            docs_count = len(documents)
            stats = context.stage_results.get("ontology", {})

            entity_cnt = stats.get('entity_count', 0)
            relation_cnt = stats.get('relation_count', 0)
            event_cnt = stats.get('event_count', stats.get('events_count', 0))
            if isinstance(entity_cnt, (list, tuple)):
                entity_cnt = len(entity_cnt)
            if isinstance(relation_cnt, (list, tuple)):
                relation_cnt = len(relation_cnt)
            if isinstance(event_cnt, (list, tuple)):
                event_cnt = len(event_cnt)

            source_data = [{
                'url': '',
                'title': generator_name,
                'text': detailed_text,
                'description': f"生成的{count}个{generator_name}获取: 实体{entity_cnt}个, 关系{relation_cnt}个, 事件{event_cnt}个. 详情: {detailed_text[:200]}",
                'publish_date': get_local_time().isoformat()
            }]

            extracted_data = {
                'source_data': source_data,
                'document_ids': [context.document_id] if context.document_id else [],
                'document_count': docs_count,
                'generator_type': generator_type,
                'generator_name': generator_name,
                'entities': entity_cnt,
                'relations': relation_cnt,
                'events': event_cnt,
            }
            extracted_data['source_data'] = source_data

            self.record_manager.complete(ingest_record, docs_count, extracted_data, builds=None)
        except Exception as e:
            self.record_manager.fail(ingest_record, str(e))
            raise

        return record_id

    def get_random_generator_types(self) -> List[Dict[str, str]]:
        """获取所有可用的随机事件生成器类型"""
        from ..ingestion_split import RandomEventGeneratorFactory
        types = RandomEventGeneratorFactory.list_generator_types()
        return [
            {
                "type": t,
                "name": RandomEventGeneratorFactory.get_generator(t, None).get_generator_name(),
                "description": RandomEventGeneratorFactory.get_generator(t, None).get_generator_description()
            }
            for t in types
        ]

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

    def get_ingest_history(self, limit: int = 100, scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取摄入历史，可按场景ID过滤"""
        return self.storage.get_ingest_records(limit, scenario_id)

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

    def get_process_logs(self, ingest_id: str) -> List[Dict[str, Any]]:
        """获取摄入记录的处理日志"""
        return self.storage.get_process_logs(ingest_id)

    def get_build_history(self, ingest_id: str) -> Optional[Dict[str, Any]]:
        """获取摄入记录的构建历史"""
        return self.storage.get_build_history(ingest_id)

    def save_build_history(self, build_record: Dict[str, Any]) -> None:
        """保存构建历史记录"""
        self.storage.save_build_history(build_record)

    def list_all_versions(self) -> List[Dict[str, Any]]:
        """获取所有版本列表"""
        return self.storage.list_all_versions()

    def get_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取版本详情"""
        return self.storage.get_version(version_id)

    def get_version_documents(self, version_id: str) -> List[Dict[str, Any]]:
        version = self.storage.get_version(version_id)
        if not version:
            return []
        docs = []
        doc_snapshot = version.get("doc_snapshot")
        if doc_snapshot:
            if isinstance(doc_snapshot, str):
                import json
                try:
                    doc_snapshot = json.loads(doc_snapshot)
                except Exception:
                    doc_snapshot = None
            if isinstance(doc_snapshot, dict):
                docs.append(doc_snapshot)
            elif isinstance(doc_snapshot, list):
                docs.extend(doc_snapshot)
        doc_id = version.get("doc_id")
        if doc_id and not docs:
            doc = self.storage.get_ontology_document(doc_id)
            if doc:
                docs.append(doc.to_dict() if hasattr(doc, 'to_dict') else doc)
        ontology_id = version.get("ontology_id")
        if ontology_id and not docs:
            ont_docs = self.storage.list_ontology_documents(ontology_id, limit=100)
            for d in ont_docs:
                docs.append(d.to_dict() if hasattr(d, 'to_dict') else d)
        return docs

    def scan_data_conflicts(self) -> Dict[str, Any]:
        from ..impl.data_cleaner import DataCleaner
        cleaner = DataCleaner(storage=self.storage)
        return cleaner.scan()

    def repair_data_conflicts(self, dry_run: bool = True) -> Dict[str, Any]:
        from ..impl.data_cleaner import DataCleaner
        cleaner = DataCleaner(storage=self.storage)
        return cleaner.repair(dry_run=dry_run)


from odap.biz.core.ontology.schema.document import OntologyDocumentSchema

_ingest_service_instance = None

def get_ingest_service() -> IngestService:
    """获取摄入服务实例（单例）"""
    global _ingest_service_instance
    if _ingest_service_instance is None:
        _ingest_service_instance = IngestService()
    return _ingest_service_instance
