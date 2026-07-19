"""统一摄入服务 — 合并文件处理与数据采集

合并来源:
  - design/ingestion/services/ingest_service.py — 文件处理 (PDF/Word/OCR/CSV/JSON batch import)
  - design/services/ingest_service.py — 数据采集 (URL/News/Tavily/Manual/JSON/NL/RandomEvent/DatabaseSchema)

所有 import 使用函数级导入，避免循环依赖。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("unified_ingestion")


# ==============================================================================
# 辅助函数
# ==============================================================================

def _get_local_time():
    """获取本地时间（带时区信息）"""
    return datetime.now(timezone.utc).astimezone()


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
    except Exception as exc:
        logger.debug("Module import fallback: %s", exc)
    return None


# ==============================================================================
# 支持类
# ==============================================================================

@dataclass
class _WebSearchResult:
    results: List[Dict[str, Any]]
    engine: str
    query: str

    @property
    def is_empty(self) -> bool:
        return not self.results


@dataclass
class _IngestRecordBuilder:
    """摄入记录构建器"""
    source: str
    source_details: Dict[str, Any] = field(default_factory=dict)
    original_content: str = ""
    record_count: int = 0
    created_by: str = "system"
    scenario_id: str = None
    workspace_id: str = "default"

    def build(self) -> Dict[str, Any]:
        return {
            'id': str(uuid.uuid4()),
            'source': self.source,
            'source_details': self.source_details,
            'original_content': self.original_content,
            'record_count': self.record_count,
            'status': 'processing',
            'start_time': _get_local_time().isoformat(),
            'created_by': self.created_by,
            'scenario_id': self.scenario_id,
            'workspace_id': self.workspace_id,
        }


class _WebSearchService:
    """Web 搜索服务封装"""

    def __init__(self, llm_client=None):
        self.llm = llm_client
        from odap.biz.core.ontology.design.ingestion_split.news_ingester import NewsIngester
        from odap.biz.core.ontology.design.services.search_service import SearchService
        from odap.infra.config_composer import get_config
        self._search_service = SearchService()
        self._news_ingester = NewsIngester(llm_client=llm_client)
        self._tavily_api_key = get_config("search.tavily_api_key", "")

    async def search(
        self, query: str, max_results: int = 5,
        preferred_engine: Optional[str] = None, search_depth: str = "basic"
    ) -> _WebSearchResult:
        results = await self._search_service.search(query, max_results)
        result_dicts = [r.to_dict() for r in results]
        providers = self._search_service.get_available_providers()
        engine_name = providers[0] if providers else 'none'
        return _WebSearchResult(results=result_dicts, engine=engine_name, query=query)

    async def tavily_search(
        self, query: str, max_results: int = 5, search_depth: str = "basic"
    ) -> _WebSearchResult:
        from odap.biz.core.ontology.design.services.search_service import TavilySearch
        tavily = TavilySearch()
        if not tavily.is_available():
            raise ValueError("Tavily API Key 未配置，请设置 TAVILY_API_KEY 环境变量")
        results = await tavily.search(query, max_results)
        result_dicts = [r.to_dict() for r in results]
        return _WebSearchResult(results=result_dicts, engine='tavily', query=query)

    def combine_sources(self, results: List[Dict[str, Any]]) -> str:
        return self._news_ingester._combine_sources(results)

    async def extract_with_llm(
        self, text: str, context: str, urls: List[str]
    ) -> List[Dict[str, Any]]:
        return await self._news_ingester._extract_with_llm(text, context, urls)

    def has_tavily_key(self) -> bool:
        return bool(self._tavily_api_key and self._tavily_api_key != "your_tavily_api_key_here")


class _IngestRecordManager:
    """摄入记录管理器 — 负责摄入记录的创建、更新、完成、失败等生命周期管理"""

    def __init__(self, storage):
        self.storage = storage

    def create(self, builder: _IngestRecordBuilder) -> Tuple[str, Dict[str, Any]]:
        record = builder.build()
        self.storage.save_ingest_record(record)
        return record['id'], record

    def complete(
        self, record: Dict[str, Any], processed_count: int,
        extracted_data: Optional[Dict[str, Any]] = None,
        builds: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        record['status'] = 'completed'
        record['processed_count'] = processed_count
        record['end_time'] = _get_local_time().isoformat()
        record['duration_seconds'] = (
            _get_local_time() - datetime.fromisoformat(record['start_time'])
        ).total_seconds()

        if extracted_data:
            record['extracted_data'] = extracted_data

        if builds:
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
                    'duration_seconds': record['duration_seconds'],
                }
                self.storage.save_build_history(build_history)

        self.storage.update_ingest_record(record['id'], record)

    def fail(self, record: Dict[str, Any], error: Exception) -> None:
        record['status'] = 'failed'
        record['errors'] = [{'message': str(error)}]
        record['end_time'] = _get_local_time().isoformat()
        record['duration_seconds'] = (
            _get_local_time() - datetime.fromisoformat(record['start_time'])
        ).total_seconds()
        self.storage.update_ingest_record(record['id'], record)

    def update_original_content(self, record_id: str, content: str) -> None:
        record = self.storage.get_ingest_record(record_id)
        if record:
            record['original_content'] = content
            self.storage.update_ingest_record(record_id, record)


class _DocumentProcessor:
    """文档处理器 — 负责文档的保存、本体构建和统计"""

    def __init__(self, storage, builder_service):
        self.storage = storage
        self.builder_service = builder_service

    async def process(
        self, documents, ingest_record: Dict[str, Any],
        scenario_id: str, ontology_id: str = None
    ) -> Tuple[List[str], Dict[str, int], List[Dict[str, Any]]]:
        document_ids = []
        stats = {'entities': 0, 'relations': 0, 'events': 0}
        builds = []

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
                    ontology_id=ontology_id,
                )
                if 'build_id' in build_result:
                    builds.append({
                        'build_id': build_result['build_id'],
                        'document_id': doc.doc_id,
                        'status': build_result.get('status'),
                        'version_info': build_result.get('version_info'),
                    })
            except Exception as exc:
                logger.error("本体构建失败: %s", exc)

        return document_ids, stats, builds


# ==============================================================================
# 主服务类
# ==============================================================================

class UnifiedIngestionService:
    """统一摄入服务 — 合并文件处理与数据采集

    单例模式，所有 import 使用函数级导入以避免循环依赖。
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, llm_client=None):
        if hasattr(self, "_initialized") and self._initialized:
            return

        # ——— 文件处理存储 & 处理器 (来自 design/ingestion/) ———
        from odap.biz.core.ontology.design.ingestion.storage import Storage
        from odap.biz.core.ontology.design.ingestion.impl.pdf_processor import PDFProcessor
        from odap.biz.core.ontology.design.ingestion.impl.word_processor import WordProcessor
        from odap.biz.core.ontology.design.ingestion.impl.ocr_processor import OCRProcessor
        from odap.biz.core.ontology.design.ingestion.impl.batch_importer import BatchImporter

        self.file_storage = Storage()
        self.pdf_processor = PDFProcessor()
        self.word_processor = WordProcessor()
        self.ocr_processor = OCRProcessor()
        self.batch_importer = BatchImporter(storage=None)

        # ——— 数据采集存储 & 处理器 (来自 design/) ———
        from odap.biz.core.ontology.design.storage import SQLiteIngestStorage
        from odap.biz.core.ontology.design.ingestion_split.news_ingester import NewsIngester
        from odap.biz.core.ontology.design.ingestion_split.manual_input import ManualInputHandler
        from odap.biz.core.ontology.design.ingestion_split.conflict_generator import ConflictEventGenerator
        from odap.biz.core.ontology.design.ingestion_split.web_scraper import WebScraper
        from odap.biz.core.ontology.design.ingestion_split.free_news_ingester import FreeNewsIngester
        from odap.biz.core.ontology.design.services.build_service import get_builder_service

        self.storage = SQLiteIngestStorage()

        if llm_client is None:
            llm_client = self._create_llm_client()
        self.llm_client = llm_client

        self.news_ingester = NewsIngester(llm_client=self.llm_client)
        self.manual_input_handler = ManualInputHandler(llm_client=self.llm_client)
        self.random_event_generator = ConflictEventGenerator(llm_client=self.llm_client)
        self.web_scraper = WebScraper()
        self.free_news_ingester = FreeNewsIngester(
            scraper=self.web_scraper,
            llm_client=self.llm_client,
        )
        self.builder_service = get_builder_service()

        self.web_search_service = _WebSearchService(llm_client=self.llm_client)
        self.record_manager = _IngestRecordManager(self.storage)
        self.document_processor = _DocumentProcessor(self.storage, self.builder_service)

        self._initialized = True

    # ======================================================================
    # LLM 客户端
    # ======================================================================

    @staticmethod
    def _create_llm_client():
        from odap.infra.config_composer import get_config
        api_key = get_config("llm.api_key", "")
        if not api_key:
            logger.warning("未配置 OPENAI_API_KEY，LLM 提取功能不可用")
            return None
        try:
            from odap.infra.llm.llm_service import ZhipuAIClient
            from graphiti_core.llm_client.config import LLMConfig
            api_base = get_config("llm.api_base", "https://open.bigmodel.cn/api/paas/v4")
            model = get_config("llm.model", "glm-4-flash")
            config = LLMConfig(model=model, api_key=api_key, base_url=api_base, temperature=0.7)
            client = ZhipuAIClient(config=config)
            logger.info("LLM 客户端初始化成功: model=%s, base_url=%s", model, api_base)
            return client
        except Exception as exc:
            logger.warning("LLM 客户端初始化失败: %s", exc)
            return None

    # ======================================================================
    # 文件处理方法 (来自 design/ingestion/services/ingest_service.py)
    # ======================================================================

    def upload_file(self, file_name: str, file_data: bytes, workspace_id: str,
                    content_type: str = "application/octet-stream") -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        file_type = self._detect_file_type(file_name)

        storage_key = None
        try:
            from odap.infra.storage.minio_client import get_minio_client
            minio = get_minio_client()
            if minio.available:
                bucket = "odap-ingestion"
                minio.ensure_bucket(bucket)
                key = f"{workspace_id}/{task_id}/{file_name}"
                upload_result = minio.upload_object(bucket, key, file_data, content_type=content_type)
                if upload_result.get("status") == "success":
                    storage_key = key
        except Exception as exc:
            logger.warning("MinIO upload failed, file stored in task only: %s", exc)

        task = {
            "task_id": task_id,
            "workspace_id": workspace_id,
            "file_name": file_name,
            "file_type": file_type,
            "storage_key": storage_key,
            "status": "uploaded",
            "source": "upload",
            "process_steps": [{"step": "upload", "status": "success", "timestamp": now}],
            "transform_rules": [],
            "created_at": now,
            "updated_at": now,
        }
        self.file_storage.save_task(task)

        return {
            "task_id": task_id,
            "workspace_id": workspace_id,
            "file_name": file_name,
            "file_type": file_type,
            "storage_key": storage_key,
            "status": "uploaded",
            "created_at": now,
        }

    def process_file(self, task_id: str) -> Dict[str, Any]:
        task = self.file_storage.get_task(task_id)
        if not task:
            return {"status": "error", "message": f"Task {task_id} not found"}

        if task.get("status") not in ("uploaded", "pending"):
            return {"status": "error", "message": f"Task {task_id} is in status '{task.get('status')}', cannot process"}

        file_type = task.get("file_type", "")
        file_data = self._retrieve_file_data(task)
        process_steps = task.get("process_steps", [])
        extracted_text = ""
        extracted_tables = []

        try:
            self.file_storage.update_task(task_id, {"status": "processing"})

            if file_type == "pdf":
                result = self.pdf_processor.extract_text(file_data or b"")
                if result.get("status") in ("success", "fallback"):
                    extracted_text = result.get("text", "")
                    process_steps.append({"step": "pdf_text_extract", "status": result.get("status"), "timestamp": datetime.now().isoformat()})

                table_result = self.pdf_processor.extract_tables(file_data or b"")
                if table_result.get("status") == "success":
                    extracted_tables = table_result.get("tables", [])
                    process_steps.append({"step": "pdf_table_extract", "status": "success", "table_count": len(extracted_tables), "timestamp": datetime.now().isoformat()})

            elif file_type in ("word", "docx"):
                result = self.word_processor.extract_text(file_data or b"")
                if result.get("status") in ("success", "fallback"):
                    extracted_text = result.get("text", "")
                    process_steps.append({"step": "word_text_extract", "status": result.get("status"), "timestamp": datetime.now().isoformat()})

                table_result = self.word_processor.extract_tables(file_data or b"")
                if table_result.get("status") == "success":
                    extracted_tables = table_result.get("tables", [])
                    process_steps.append({"step": "word_table_extract", "status": "success", "table_count": len(extracted_tables), "timestamp": datetime.now().isoformat()})

            elif file_type in ("image", "png", "jpg", "jpeg", "tiff", "bmp"):
                result = self.ocr_processor.extract_text(file_data or b"")
                if result.get("status") in ("success", "fallback"):
                    extracted_text = result.get("text", "")
                    process_steps.append({"step": "ocr_extract", "status": result.get("status"), "engine": result.get("engine"), "timestamp": datetime.now().isoformat()})
            else:
                extracted_text = file_data.decode("utf-8", errors="replace") if file_data else ""
                process_steps.append({"step": "raw_text_decode", "status": "success", "timestamp": datetime.now().isoformat()})

            self.file_storage.update_task(task_id, {
                "status": "completed",
                "extracted_text": extracted_text,
                "extracted_tables": extracted_tables,
                "process_steps": process_steps,
            })

            return {
                "task_id": task_id,
                "status": "completed",
                "extracted_text_length": len(extracted_text),
                "table_count": len(extracted_tables),
                "process_steps": process_steps,
            }
        except Exception as exc:
            logger.error("File processing failed for task %s: %s", task_id, exc)
            self.file_storage.update_task(task_id, {
                "status": "failed",
                "error_message": str(exc),
                "process_steps": process_steps,
            })
            return {"status": "error", "message": str(exc), "task_id": task_id}

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        task = self.file_storage.get_task(task_id)
        if not task:
            return {"status": "error", "message": f"Task {task_id} not found"}
        return task

    def batch_import(self, entity_type_id: str, data: Any, format: str,
                     workspace_id: str) -> Dict[str, Any]:
        if format == "csv":
            result = self.batch_importer.import_csv(entity_type_id, data, workspace_id)
        elif format == "json":
            result = self.batch_importer.import_json(entity_type_id, data, workspace_id)
        else:
            return {"status": "error", "message": f"Unsupported format: {format}"}

        try:
            from odap.biz.core.ontology.design.engine.impl.audit_recorder_impl import AuditRecorderImpl
            recorder = AuditRecorderImpl()
            recorder.record_ingest(
                entity_type_id=entity_type_id,
                source=f"batch_import_{format}",
                process_steps=[{"step": "batch_import", "format": format, "success_count": result.get("success_count", 0), "fail_count": result.get("fail_count", 0)}],
                transform_rules=[],
                result=result.get("status", "unknown"),
            )
        except Exception as exc:
            logger.warning("Audit recording failed for batch import: %s", exc)

        return result

    def _detect_file_type(self, file_name: str) -> str:
        if not file_name:
            return "unknown"
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        mapping = {
            "pdf": "pdf",
            "doc": "word", "docx": "word",
            "png": "image", "jpg": "image", "jpeg": "image", "tiff": "image", "bmp": "image", "gif": "image",
            "txt": "text", "csv": "csv", "json": "json",
        }
        return mapping.get(ext, "unknown")

    def _retrieve_file_data(self, task: Dict[str, Any]) -> Optional[bytes]:
        storage_key = task.get("storage_key")
        if not storage_key:
            return None

        try:
            from odap.infra.storage.minio_client import get_minio_client
            minio = get_minio_client()
            if minio.available:
                result = minio.download_object("odap-ingestion", storage_key)
                if result.get("status") == "success":
                    return result.get("data")
        except Exception as exc:
            logger.warning("MinIO download failed: %s", exc)

        return None

    # ======================================================================
    # 数据采集方法 (来自 design/services/ingest_service.py)
    # ======================================================================

    async def ingest_from_url(
        self, url: str, event_context: str = "", scenario_id: str = None
    ) -> str:
        """从URL摄入数据（免费网页抓取方案）"""
        url = url.strip()

        builder = _IngestRecordBuilder(
            source='url',
            source_details={'url': url, 'context': event_context},
            record_count=0,
            scenario_id=scenario_id,
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            documents = await self.free_news_ingester.ingest(url, event_context=event_context)

            scrape_result = None
            if hasattr(self.free_news_ingester, 'scraper'):
                scrape_result = self.free_news_ingester.scraper.scrape(url)
                if scrape_result.get('status') == 'success':
                    ingest_record['original_content'] = scrape_result.get('text', '')
                else:
                    ingest_record['original_content'] = "网页抓取失败: " + str(scrape_result.get('error', '未知错误'))

            source_data = self._build_source_data_from_scrape(scrape_result, documents, url)
            _, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id for doc in documents],
                'document_count': len(documents),
                **stats,
            }
            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    async def ingest_from_news(
        self, query: str, event_context: str = "", max_sources: int = 5,
        scenario_id: str = None,
    ) -> str:
        """从新闻搜索摄入数据（自动选择可用引擎）"""
        builder = _IngestRecordBuilder(
            source='news',
            source_details={'query': query, 'max_sources': max_sources},
            original_content=query,
            record_count=max_sources,
            scenario_id=scenario_id,
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
                logger.warning("新闻搜索未返回结果，使用查询词作为原始内容: %s", query)

            urls = [r.get("url", "") for r in search_results[:3]] if search_results else []
            raw_docs = await self.web_search_service.extract_with_llm(
                combined_text, event_context, urls,
            )

            from odap.biz.core.ontology.design.schema.document import (
                OntologyDocument, OntologyDocumentSchema,
            )
            documents = []
            for doc_data in raw_docs:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    documents.append(OntologyDocument.from_dict(doc_data))

            source_data = self._build_source_data_from_search(search_results, documents)
            _, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id for doc in documents],
                'document_count': len(documents),
                'search_engine': search_result.engine,
                **stats,
            }
            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    async def ingest_from_tavily(
        self, query: str, event_context: str = "", max_sources: int = 5,
        search_depth: str = "basic", scenario_id: str = None,
    ) -> str:
        """使用 Tavily API 摄入数据"""
        builder = _IngestRecordBuilder(
            source='tavily',
            source_details={
                'query': query,
                'search_depth': search_depth,
                'max_sources': max_sources,
            },
            original_content=query,
            record_count=max_sources,
            scenario_id=scenario_id,
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
                combined_text, event_context, urls,
            )

            from odap.biz.core.ontology.design.schema.document import (
                OntologyDocument, OntologyDocumentSchema,
            )
            documents = []
            for doc_data in raw_docs:
                result = OntologyDocumentSchema.validate(doc_data)
                if result.is_valid:
                    documents.append(OntologyDocument.from_dict(doc_data))

            source_data = self._build_source_data_from_search(search_results, documents)
            _, stats, builds = await self.document_processor.process(
                documents, ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id for doc in documents],
                'document_count': len(documents),
                'search_engine': 'tavily',
                **stats,
            }
            self.record_manager.complete(ingest_record, len(documents), extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    async def ingest_from_manual(
        self, form_data: Any, scenario_id: str = None,
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

        builder = _IngestRecordBuilder(
            source='manual',
            source_details={'form_data_keys': form_data_keys},
            original_content=original_content,
            record_count=1,
            created_by=form_data.get('author', 'system'),
            scenario_id=scenario_id,
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            doc = await self.manual_input_handler.from_form(form_data, scenario_id)

            source_data = [{
                'url': '',
                'title': doc.meta.title or '手动输入',
                'text': original_content,
                'description': doc.meta.description or '',
                'publish_date': doc.source.collected_at or '',
            }]

            _, stats, builds = await self.document_processor.process(
                [doc], ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id],
                'document_count': 1,
                **stats,
            }
            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    async def ingest_from_json(
        self, raw_json: str, scenario_id: str = None,
    ) -> str:
        """从 JSON 摄入数据"""
        builder = _IngestRecordBuilder(
            source='json',
            source_details={'json_length': len(raw_json)},
            original_content=raw_json,
            record_count=1,
            scenario_id=scenario_id,
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            doc = await self.manual_input_handler.from_json(raw_json, scenario_id)

            source_data = [{
                'url': '',
                'title': doc.meta.title or 'JSON输入',
                'text': raw_json,
                'description': doc.meta.description or '',
                'publish_date': doc.source.collected_at or '',
            }]

            _, stats, builds = await self.document_processor.process(
                [doc], ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id],
                'document_count': 1,
                **stats,
            }
            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    async def ingest_from_natural_language(
        self, text: str, scenario_id: str = None,
    ) -> str:
        """从自然语言摄入数据"""
        builder = _IngestRecordBuilder(
            source='natural_language',
            source_details={'text_length': len(text)},
            original_content=text,
            record_count=1,
            scenario_id=scenario_id,
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            doc = await self.manual_input_handler.from_natural_language(text, scenario_id)

            source_data = [{
                'url': '',
                'title': doc.meta.title or '自然语言输入',
                'text': text,
                'description': doc.meta.description or '',
                'publish_date': doc.source.collected_at or '',
            }]

            _, stats, builds = await self.document_processor.process(
                [doc], ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [doc.doc_id],
                'document_count': 1,
                **stats,
            }
            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    async def generate_random_events(
        self, parties: List[str], scenario_context: dict = None,
        count: int = 1, scenario_id: str = None,
        generator_type: str = "conflict", workspace_id: str = "default",
    ) -> str:
        """生成随机事件 — 调用真实的 pipeline"""
        from odap.biz.core.ontology.design.ingestion_split.generator_factory import RandomEventGeneratorFactory
        from odap.biz.core.ontology.design.services.pipeline_service import get_pipeline_service

        generator = RandomEventGeneratorFactory.get_generator(generator_type, self.llm_client)
        generator_name = generator.get_generator_name()

        documents = await generator.generate(
            parties, scenario_context, count, scenario_id,
        )

        event_descriptions = []
        for doc in documents:
            if doc.events:
                for event in doc.events:
                    event_descriptions.append(event.description)
            elif doc.entities:
                entity_names = [e.name for e in doc.entities]
                event_descriptions.append("实体: " + ", ".join(entity_names))

        if event_descriptions:
            detailed_text = " | ".join(event_descriptions)
        else:
            detailed_text = f"随机生成 {count} 个{generator_name}事件，参与方: {parties}"

        builder = _IngestRecordBuilder(
            source='random',
            source_details={
                'parties': parties,
                'count': count,
                'generator_type': generator_type,
                'generator_name': generator_name,
            },
            original_content=detailed_text,
            record_count=count,
            scenario_id=scenario_id,
            workspace_id=workspace_id,
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            async def _ws_progress_callback(stage, progress: float, message: str):
                try:
                    from odap.web.ws.routes import emit_build_progress
                    await emit_build_progress(
                        stage=stage.value if hasattr(stage, 'value') else str(stage),
                        progress=progress,
                        message=message,
                        ingest_id=record_id,
                        scenario_id=scenario_id or "default",
                    )
                except Exception as e:
                    logger.debug("WebSocket push failed (non-blocking): %s", e)

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
                    "content": detailed_text,
                },
                workspace_id=workspace_id,
                progress_callback=_ws_progress_callback,
            )

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
                'publish_date': _get_local_time().isoformat(),
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
        except Exception as exc:
            self.record_manager.fail(ingest_record, str(exc))
            raise

        return record_id

    def get_random_generator_types(self) -> List[Dict[str, str]]:
        """获取所有可用的随机事件生成器类型"""
        from odap.biz.core.ontology.design.ingestion_split.generator_factory import RandomEventGeneratorFactory
        types = RandomEventGeneratorFactory.list_generator_types()
        return [
            {
                "type": t,
                "name": RandomEventGeneratorFactory.get_generator(t, None).get_generator_name(),
                "description": RandomEventGeneratorFactory.get_generator(t, None).get_generator_description(),
            }
            for t in types
        ]

    def _build_source_data_from_scrape(
        self, scrape_result: Optional[Dict], documents, url: str,
    ) -> List[Dict[str, Any]]:
        """从抓取结果构建源数据"""
        source_data = []
        if scrape_result and scrape_result.get('status') == 'success':
            source_data.append({
                'url': scrape_result.get('url', ''),
                'title': scrape_result.get('title', ''),
                'text': scrape_result.get('text', ''),
                'description': scrape_result.get('description', ''),
                'publish_date': scrape_result.get('publish_date', ''),
            })
        elif documents:
            for doc in documents:
                source_data.append({
                    'url': url,
                    'title': doc.meta.title or '网页内容',
                    'text': doc.meta.description or '',
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or '',
                })
        else:
            source_data.append({
                'url': url,
                'title': '网页内容',
                'text': '',
                'description': '',
                'publish_date': '',
            })
        return source_data

    def _build_source_data_from_search(
        self, search_results: List[Dict[str, Any]], documents,
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
                    'publish_date': result.get('date', ''),
                })
        elif documents:
            for doc in documents:
                source_data.append({
                    'url': doc.source.url or '',
                    'title': doc.meta.title or '新闻内容',
                    'text': doc.meta.description or '',
                    'description': doc.meta.description or '',
                    'publish_date': doc.source.collected_at or '',
                })
        else:
            source_data.append({
                'url': '',
                'title': '新闻内容',
                'text': '',
                'description': '',
                'publish_date': '',
            })
        return source_data

    # ======================================================================
    # 查询方法
    # ======================================================================

    def get_ingest_status(self, ingest_id: str) -> Dict[str, Any]:
        """获取摄入状态"""
        return self.storage.get_ingest_record(ingest_id)

    def get_ingest_history(self, limit: int = 100,
                           scenario_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取摄入历史，可按场景ID过滤"""
        return self.storage.get_ingest_records(limit, scenario_id)

    def get_ontology_documents(
        self, scenario_id: Optional[str] = None, limit: int = 100,
    ):
        """获取本体文档"""
        return self.storage.list_ontology_documents(scenario_id, limit)

    def get_ontology_document(self, doc_id: str):
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

    async def ingest_from_database(
        self, connection_id: str, table_patterns: Optional[List[str]] = None,
        scenario_id: str = None, workspace_id: str = "default",
    ) -> str:
        """从数据库摄入数据 — 调用 DatabaseSchemaExtractor 提取 schema"""
        from odap.biz.core.ontology.design.ingestion_split.db_schema_ingester import DatabaseSchemaExtractor

        extractor = DatabaseSchemaExtractor()
        db_params = self._parse_connection_id(connection_id)

        builder = _IngestRecordBuilder(
            source='database',
            source_details={
                'connection_id': connection_id,
                'table_patterns': table_patterns,
            },
            original_content=f"Database schema from {connection_id}",
            record_count=0,
            scenario_id=scenario_id,
            workspace_id=workspace_id,
        )
        record_id, ingest_record = self.record_manager.create(builder)

        try:
            schema_result = extractor.extract_schema(
                db_type=db_params['db_type'],
                host=db_params.get('host', ''),
                port=db_params.get('port', 0),
                database=db_params.get('database', ''),
                username=db_params.get('username'),
                password=db_params.get('password'),
                table_filter=table_patterns,
            )

            if schema_result.get('status') == 'error':
                raise RuntimeError(schema_result.get('message', 'Schema extraction failed'))

            document = self._schema_to_ontology_document(schema_result, scenario_id)

            source_data = [{
                'url': connection_id,
                'title': 'Database Schema: ' + str(db_params.get("database", connection_id)),
                'text': str(schema_result.get('summary', {})),
                'description': "Extracted " + str(schema_result.get('summary', {}).get('tables', 0)) + " tables",
                'publish_date': _get_local_time().isoformat(),
            }]

            _, stats, builds = await self.document_processor.process(
                [document], ingest_record, scenario_id or "default",
            )

            extracted_data = {
                'source_data': source_data,
                'document_ids': [document.doc_id],
                'document_count': 1,
                'schema_summary': schema_result.get('summary', {}),
                **stats,
            }

            self.record_manager.complete(ingest_record, 1, extracted_data, builds)
        except Exception as exc:
            self.record_manager.fail(ingest_record, exc)

        return record_id

    @staticmethod
    def _parse_connection_id(connection_id: str) -> Dict[str, Any]:
        """解析 connection_id 为数据库连接参数"""
        if connection_id.startswith("sqlite:///"):
            return {
                'db_type': 'sqlite',
                'database': connection_id[len("sqlite:///"):],
            }

        rest = connection_id
        if "://" in rest:
            db_type_raw, rest = rest.split("://", 1)
        else:
            db_type_raw = "postgresql"

        type_map = {
            'pg': 'postgresql',
            'postgres': 'postgresql',
            'postgresql': 'postgresql',
            'mysql': 'mysql',
        }
        db_type = type_map.get(db_type_raw.lower(), db_type_raw.lower())

        username = None
        password = None
        host = ''
        port = 0
        database = ''

        if '@' in rest:
            user_part, rest = rest.rsplit('@', 1)
            if ':' in user_part:
                username, password = user_part.split(':', 1)
            else:
                username = user_part

        if '/' in rest:
            host_port, database = rest.split('/', 1)
        else:
            host_port = rest

        if ':' in host_port:
            host, port_str = host_port.rsplit(':', 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 0
        else:
            host = host_port

        return {
            'db_type': db_type,
            'host': host,
            'port': port,
            'database': database,
            'username': username,
            'password': password,
        }

    def _schema_to_ontology_document(
        self, schema_result: Dict[str, Any], scenario_id: Optional[str] = None,
    ):
        """将 DatabaseSchemaExtractor 的输出转换为 OntologyDocument"""
        from odap.biz.core.ontology.design.schema.document import (
            OntologyEntity, OntologyRelation, OntologyEvent, SourceInfo, OntologyDocument,
        )

        entities = []
        for obj_type in schema_result.get('object_types', []):
            entities.append(OntologyEntity(
                entity_id=f"db_{obj_type['name']}",
                entity_type="DatabaseTable",
                name=obj_type.get('display_name', obj_type['name']),
                name_en=obj_type['name'],
                basic_properties=obj_type,
            ))

        relations = []
        for link_type in schema_result.get('link_types', []):
            relations.append(OntologyRelation(
                relation_id=f"db_rel_{link_type['name']}",
                relation_type=link_type.get('link_type', 'ASSOCIATION'),
                source_entity=link_type.get('source_type', ''),
                target_entity=link_type.get('target_type', ''),
                temporal={},
            ))

        document = OntologyDocument(
            doc_type="entity",
            source=SourceInfo(type="database"),
            entities=entities,
            relations=relations,
            events=[],
        )

        if scenario_id:
            document.scenario_id = scenario_id

        return document

    # ======================================================================
    # 工具方法
    # ======================================================================

    def scan_data_conflicts(self) -> Dict[str, Any]:
        from odap.biz.core.ontology.design.impl.data_cleaner import DataCleaner
        cleaner = DataCleaner(storage=self.storage)
        return cleaner.scan()

    def repair_data_conflicts(self, dry_run: bool = True) -> Dict[str, Any]:
        from odap.biz.core.ontology.design.impl.data_cleaner import DataCleaner
        cleaner = DataCleaner(storage=self.storage)
        return cleaner.repair(dry_run=dry_run)


# ==============================================================================
# 工厂函数
# ==============================================================================

def get_unified_ingestion_service() -> UnifiedIngestionService:
    """获取统一摄入服务实例（单例）"""
    return UnifiedIngestionService()
