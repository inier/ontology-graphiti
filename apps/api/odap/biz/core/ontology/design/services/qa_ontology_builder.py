"""
QA驱动的本体构建服务
实现智能问答触发联网搜索和本体更新的全流程

流程:
1. 用户提问 → 意图分析
2. 意图分析 → 联网搜索（如果需要最新信息）
3. 联网搜索 → 数据摄入 → OntologyDocument
4. OntologyDocument → 本体构建 → 图谱更新
5. 图谱更新 → 智能回复
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("ontology_qa_builder")


class QABuildStatus(str, Enum):
    PENDING = "pending"
    INTENT_ANALYZING = "intent_analyzing"
    SEARCHING = "searching"
    INGESTING = "ingesting"
    BUILDING = "building"
    COMPLETED = "completed"
    FAILED = "failed"


# IntentType 已迁移到 ontology/common/types.py（消除与 cognition/ 的重复定义）
from odap.biz.core.ontology.common.types import IntentType  # noqa: E402


@dataclass
class QABuildProgress:
    """QA构建进度"""
    task_id: str
    status: QABuildStatus = QABuildStatus.PENDING
    current_step: str = ""
    progress_percent: float = 0.0
    message: str = ""
    intent_result: Optional[Dict] = None
    search_results: List[Dict] = field(default_factory=list)
    ontology_document: Optional[Dict] = None
    build_result: Optional[Dict] = None
    answer: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class IntentResult:
    """意图分析结果"""
    intent_type: IntentType
    confidence: float
    requires_search: bool
    entities_to_update: List[str] = field(default_factory=list)
    suggested_ontology_id: Optional[str] = None
    analysis_details: Dict[str, Any] = field(default_factory=dict)


class QAOntologyBuilder:
    """
    QA驱动的本体构建引擎

    核心功能:
    1. 意图分析 - 判断用户问题需要查询还是更新本体
    2. 联网搜索 - 获取最新信息
    3. 数据摄入 - 将搜索结果转换为 OntologyDocument
    4. 本体构建 - 更新本体和图谱
    5. 回答生成 - 生成最终回答
    """

    def __init__(self):
        self._progress_tasks: Dict[str, QABuildProgress] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._news_ingester = None
        self._transform_service = None

    async def process_question(
        self,
        question: str,
        user_id: str = "anonymous",
        session_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        scenario_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        处理用户问题，触发本体构建流程

        Args:
            question: 用户问题
            user_id: 用户ID
            session_id: 会话ID
            workspace_id: 工作空间ID
            scenario_id: 场景ID

        Returns:
            Dict: 包含 answer, sources, progress_id 等
        """
        from odap.infra.llm.prompt_sanitizer import PromptSanitizer
        question = PromptSanitizer.sanitize_input(question)
        task_id = f"qatask_{uuid.uuid4().hex[:12]}"

        # 创建进度跟踪
        progress = QABuildProgress(
            task_id=task_id,
            status=QABuildStatus.PENDING,
            current_step="创建任务"
        )
        self._progress_tasks[task_id] = progress

        try:
            # 步骤1: 意图分析
            await self._update_progress(task_id, QABuildStatus.INTENT_ANALYZING, "分析问题意图")
            intent_result = await self._analyze_intent(question)
            progress.intent_result = {
                "intent_type": intent_result.intent_type.value,
                "confidence": intent_result.confidence,
                "requires_search": intent_result.requires_search,
                "analysis": intent_result.analysis_details
            }

            # 步骤2: 联网搜索（如果需要）
            if intent_result.requires_search:
                await self._update_progress(task_id, QABuildStatus.SEARCHING, "联网搜索最新信息")
                search_results = await self._search_online(question, intent_result)
                progress.search_results = search_results

            # 步骤3: 数据摄入和本体构建
            await self._update_progress(task_id, QABuildStatus.INGESTING, "处理数据")
            if progress.search_results:
                ontology_doc = await self._ingest_and_build(
                    task_id,
                    progress.search_results,
                    scenario_id
                )
                progress.ontology_document = ontology_doc

            # 步骤4: 生成回答
            await self._update_progress(task_id, QABuildStatus.BUILDING, "生成回答")
            answer = await self._generate_answer(question, intent_result, progress)
            progress.answer = answer

            # 完成
            await self._update_progress(
                task_id,
                QABuildStatus.COMPLETED,
                "处理完成",
                progress_percent=100.0
            )

            return {
                "task_id": task_id,
                "answer": answer,
                "sources": self._extract_sources(progress.search_results),
                "intent": progress.intent_result,
                "status": "completed"
            }

        except Exception as e:
            logger.error(f"QA本体构建失败: {e}")
            await self._update_progress(
                task_id,
                QABuildStatus.FAILED,
                f"处理失败: {str(e)}",
                error=str(e)
            )
            return {
                "task_id": task_id,
                "answer": f"处理您的问题时遇到错误: {str(e)}",
                "status": "failed",
                "error": str(e)
            }

    async def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务进度"""
        progress = self._progress_tasks.get(task_id)
        if not progress:
            return None

        return {
            "task_id": progress.task_id,
            "status": progress.status.value,
            "current_step": progress.current_step,
            "progress_percent": progress.progress_percent,
            "message": progress.message,
            "answer": progress.answer,
            "error": progress.error,
            "created_at": progress.created_at,
            "updated_at": progress.updated_at
        }

    async def subscribe_progress(
        self,
        task_id: str,
        callback: Callable[[Dict], None]
    ):
        """订阅进度更新"""
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)

    async def _update_progress(
        self,
        task_id: str,
        status: QABuildStatus,
        current_step: str,
        progress_percent: float = None,
        message: str = None,
        error: str = None
    ):
        """更新任务进度"""
        progress = self._progress_tasks.get(task_id)
        if not progress:
            return

        progress.status = status
        progress.current_step = current_step
        progress.updated_at = datetime.now(timezone.utc).isoformat()

        if progress_percent is not None:
            progress.progress_percent = progress_percent
        if message is not None:
            progress.message = message
        if error is not None:
            progress.error = error

        # 计算默认进度
        if progress_percent is None:
            progress.progress_percent = self._calculate_progress(status)

        # 通知订阅者
        await self._notify_callbacks(task_id, await self.get_progress(task_id))

    def _calculate_progress(self, status: QABuildStatus) -> float:
        progress_map = {
            QABuildStatus.PENDING: 0,
            QABuildStatus.INTENT_ANALYZING: 20,
            QABuildStatus.SEARCHING: 40,
            QABuildStatus.INGESTING: 60,
            QABuildStatus.BUILDING: 80,
            QABuildStatus.COMPLETED: 100,
            QABuildStatus.FAILED: 100
        }
        return progress_map.get(status, 0)

    async def _analyze_intent(self, question: str) -> IntentResult:
        """
        意图分析

        分析用户问题是:
        1. 查询现有本体
        2. 需要更新本体
        3. 需要创建新本体
        4. 需要分析趋势
        """
        # 简化的意图分析
        # 实际应该使用 LLM 进行更精确的分析

        question_lower = question.lower()

        # 分析关键词
        update_keywords = ["最新", "现在", "最近", "当前", "今日", "今天", "最新消息"]
        analyze_keywords = ["分析", "走势", "趋势", "预测", "评估", "判断"]
        query_keywords = ["什么是", "在哪", "是谁", "如何", "怎么", "多少"]

        requires_search = any(kw in question_lower for kw in update_keywords)
        is_analyze = any(kw in question_lower for kw in analyze_keywords)
        is_query = any(kw in question_lower for kw in query_keywords)

        if is_analyze:
            intent_type = IntentType.ANALYZE
            requires_search = True
        elif requires_search:
            intent_type = IntentType.UPDATE
        elif is_query:
            intent_type = IntentType.QUERY
        else:
            intent_type = IntentType.UNKNOWN

        # 估算置信度
        confidence = 0.7
        if sum([requires_search, is_analyze, is_query]) > 1:
            confidence = 0.85

        return IntentResult(
            intent_type=intent_type,
            confidence=confidence,
            requires_search=requires_search,
            analysis_details={
                "keywords_detected": {
                    "update": requires_search,
                    "analyze": is_analyze,
                    "query": is_query
                },
                "original_question": question
            }
        )

    async def _search_online(
        self,
        question: str,
        intent_result: IntentResult
    ) -> List[Dict[str, Any]]:
        """
        联网搜索

        使用 DuckDuckGo 或其他搜索引擎获取最新信息
        """
        try:
            # 导入新闻摄入器
            from odap.biz.core.ontology.design.ingestion_split import NewsIngester

            if self._news_ingester is None:
                self._news_ingester = NewsIngester()

            # 执行搜索
            search_results = await self._news_ingester.ingest(
                query=question,
                event_context=intent_result.analysis_details.get("context", ""),
                max_sources=5
            )

            # 转换为字典格式
            results = []
            for doc in search_results:
                results.append({
                    "title": doc.meta.title,
                    "description": doc.meta.description,
                    "url": doc.source.url,
                    "entities": [e.to_dict() for e in doc.entities],
                    "events": [e.to_dict() for e in doc.events],
                    "confidence": doc.source.confidence
                })

            return results

        except Exception as e:
            logger.error(f"联网搜索失败: {e}")
            return []

    async def _ingest_and_build(
        self,
        task_id: str,
        search_results: List[Dict],
        scenario_id: Optional[str]
    ) -> Dict[str, Any]:
        """
        数据摄入和本体构建

        将搜索结果转换为 OntologyDocument 并构建本体
        """
        try:
            from odap.biz.core.ontology.design.services.transform_service import get_transform_service

            if self._transform_service is None:
                self._transform_service = get_transform_service()

            # 转换搜索结果为 OntologyDocument
            documents = []
            for idx, result in enumerate(search_results):
                doc_data = {
                    "doc_id": f"search-{task_id}-{idx}",
                    "doc_type": "event",
                    "meta": {
                        "title": result.get("title", ""),
                        "description": result.get("description", ""),
                        "tags": ["联网搜索"]
                    },
                    "entities": result.get("entities", []),
                    "events": result.get("events", [])
                }

                try:
                    doc = await self._transform_service.transform(
                        data=doc_data,
                        source_type="json",
                        metadata={"source": "search"}
                    )
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"文档转换失败: {e}")

            # 如果转换失败，生成默认文档
            if not documents:
                from odap.biz.core.ontology.design.schema.document import (
                    OntologyDocument, SourceInfo, DocumentMeta
                )
                now = datetime.now(timezone.utc).isoformat()
                doc = OntologyDocument(
                    doc_id=f"search-{task_id}-0",
                    doc_type="event",
                    source=SourceInfo(
                        type="news_ingest",
                        collected_at=now,
                        confidence=0.7
                    ),
                    meta=DocumentMeta(
                        title="联网搜索结果",
                        description=f"基于搜索生成的结果，共 {len(search_results)} 条"
                    )
                )
                documents.append(doc)

            # 保存到存储（如果可用）
            try:
                from ..storage.sqlite_ingest_storage import SQLiteIngestStorage
                storage = SQLiteIngestStorage()
                for doc in documents:
                    storage.save_ontology_document(doc)
            except Exception as e:
                logger.warning(f"存储文档失败: {e}")

            return {
                "document_count": len(documents),
                "documents": [doc.to_dict() for doc in documents]
            }

        except Exception as e:
            logger.error(f"数据摄入失败: {e}")
            raise

    async def _generate_answer(
        self,
        question: str,
        intent_result: IntentResult,
        progress: QABuildProgress
    ) -> str:
        """生成回答"""
        # 简化回答生成
        # 实际应该使用 LLM 根据本体数据生成更精确的回答

        if progress.search_results:
            source_count = len(progress.search_results)
            answer = f"根据我获取的最新信息，我可以为您提供以下回答：\n\n"
            answer += f"针对您的问题「{question}」，"

            if intent_result.intent_type == IntentType.ANALYZE:
                answer += "我已分析相关数据和趋势。\n\n"
                answer += "主要发现：\n"
                for i, result in enumerate(progress.search_results[:3], 1):
                    title = result.get("title", "未知")
                    answer += f"{i}. {title}\n"
            elif intent_result.intent_type == IntentType.UPDATE:
                answer += "已为您更新相关本体信息。\n\n"
                if progress.ontology_document:
                    doc_count = progress.ontology_document.get("document_count", 0)
                    answer += f"已处理 {doc_count} 条最新信息。"
            else:
                answer += "以下是相关信息：\n"
                for i, result in enumerate(progress.search_results[:3], 1):
                    title = result.get("title", "未知")
                    desc = result.get("description", "")[:100]
                    answer += f"\n{i}. {title}\n   {desc}.."
        else:
            answer = f"您的问题「{question}」已收到。\n\n"
            answer += "根据当前本体数据，"
            answer += "这个问题涉及的信息正在分析中。\n\n"
            answer += "建议：您可以提供更多具体信息以便我更好地回答。"

        return answer

    def _extract_sources(self, search_results: List[Dict]) -> List[Dict]:
        """提取来源信息"""
        sources = []
        for result in search_results:
            if result.get("url"):
                sources.append({
                    "source": result.get("title", "未知来源"),
                    "excerpt": result.get("description", "")[:200],
                    "url": result.get("url"),
                    "confidence": result.get("confidence", 0.8)
                })
        return sources

    async def _notify_callbacks(self, task_id: str, progress_data: Dict):
        """通知订阅者"""
        callbacks = self._callbacks.get(task_id, [])
        for callback in callbacks:
            try:
                await callback(progress_data)
            except Exception as e:
                logger.error(f"回调通知失败: {e}")


# 全局实例
_qa_builder: Optional[QAOntologyBuilder] = None


def get_qa_builder() -> QAOntologyBuilder:
    """获取QA构建器单例"""
    global _qa_builder
    if _qa_builder is None:
        _qa_builder = QAOntologyBuilder()
    return _qa_builder