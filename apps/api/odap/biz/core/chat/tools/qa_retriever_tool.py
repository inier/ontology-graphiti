"""QARetrieverTool — 知识图谱 RAG 检索工具。

将 QAEngineV2 的五阶段 RAG Pipeline（BM25 + Vector + Graph 三支柱检索）
封装为 OpenHarness BaseTool，让 LLM 在 Agent Loop 中自主决定何时调用检索。

Phase A 实现：桥接到现有 QAEngineV2。
Phase B 实现：内化为 chat/retrieval/ 的直接调用。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

try:
    from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
    _OH_AVAILABLE = True
except ImportError:
    _OH_AVAILABLE = False
    # Fallback stub for when OpenHarness is not available
    class BaseTool:
        name: str = ""
        description: str = ""

    class ToolExecutionContext:
        pass

    class ToolResult:
        def __init__(self, output: str = "", is_error: bool = False):
            self.output = output
            self.is_error = is_error

logger = logging.getLogger(__name__)


class QARetrieverInput(BaseModel):
    """QA 检索工具输入参数。

    LLM 在看到此工具定义后，会自行决定传入什么参数。
    """
    query: str = Field(
        ..., min_length=2, max_length=2000,
        description="自然语言查询，如「最近有哪些异常事件」「User 类型的完整性怎么样」",
    )
    retrieval_mode: Literal["hybrid", "bm25", "vector", "graph"] = Field(
        "hybrid",
        description="检索模式：hybrid=三支柱融合(推荐), bm25=关键词, vector=语义, graph=图关联",
    )
    top_k: int = Field(
        10, ge=1, le=50,
        description="返回结果数量，1-50",
    )
    include_temporal: bool = Field(
        False,
        description="是否包含时序推理结果（如「最近一周」「上个月」）",
    )
    workspace_id: str = Field(
        "default",
        description="工作空间ID，用于知识隔离",
    )
    ontology_id: Optional[str] = Field(
        None,
        description="本体ID，用于限定搜索范围",
    )


class QARetrieverTool(BaseTool):
    """三支柱 RAG 检索工具 — 从知识图谱中检索相关信息。

    用途：
    - 用户问「查一下...」「帮我找...」「有哪些...」等查询类问题时调用
    - 支持 BM25 关键词检索、向量语义检索、图关联推理三种模式
    - hybrid 模式自动融合三种结果，推荐首选

    此工具是 QAPipeline 的 BaseTool 封装，底层复用 QAEngineV2 的
    RAGPipeline 和 UnifiedRetriever。
    """

    name: str = "qa_retrieve"
    description: str = """三支柱 RAG 检索工具。从知识图谱中检索与用户查询相关的信息。

检索模式：
- hybrid: 三支柱融合（BM25 + 向量 + 图谱），推荐首选
- bm25:  精准关键词匹配
- vector: 语义相似度搜索
- graph:  图关联推理检索

返回结构化的检索结果列表，包含内容、来源、相关度分数。
如 include_temporal=True，额外返回时序推理结果（时间范围内的实体和事件）。

使用场景：
- 用户查找实体/事件/关系时
- 用户问「有哪些...」「最近...」「帮我查...」
- 作为其他写操作工具的前置步骤（先查后改）
"""

    input_model = QARetrieverInput

    def __init__(self):
        super().__init__()
        self._rag_pipeline = None
        self._temporal_reasoner = None

    @property
    def rag_pipeline(self):
        """懒加载 RAG Pipeline（复用 QAEngineV2 实例）。"""
        if self._rag_pipeline is None:
            try:
                from odap.biz.data.qa.qa_engine import QAEngineV2
                engine = QAEngineV2()
                self._rag_pipeline = engine.rag_pipeline
            except Exception as e:
                logger.warning("QARetrieverTool: QAEngineV2 init failed: %s", e)
                self._rag_pipeline = None
        return self._rag_pipeline

    @property
    def temporal_reasoner(self):
        """懒加载时序推理器。"""
        if self._temporal_reasoner is None:
            try:
                from odap.biz.data.qa.impl.temporal_reasoner import TemporalQueryParser
                self._temporal_reasoner = TemporalQueryParser()
            except Exception as e:
                logger.warning("QARetrieverTool: TemporalQueryParser init failed: %s", e)
                self._temporal_reasoner = None
        return self._temporal_reasoner

    def is_read_only(self, context=None) -> bool:
        return True

    async def execute(
        self,
        args: QARetrieverInput,
        context: ToolExecutionContext,
    ) -> ToolResult:
        """执行检索并返回结构化结果。

        返回 JSON 格式：
        {
            "results": [{"content": ..., "source": ..., "score": 0.85}, ...],
            "total": N,
            "mode": "hybrid",
            "temporal": {...}  // 如果 include_temporal=True
        }
        """
        results = []
        temporal_result = None

        try:
            # ── 三支柱检索 ──
            if self.rag_pipeline:
                try:
                    raw_results = self.rag_pipeline.retrieve(
                        query=args.query,
                        top_k=args.top_k,
                        workspace_id=args.workspace_id,
                    )
                    for r in raw_results:
                        results.append({
                            "content": r.content[:500],
                            "source": getattr(r, "source", "unknown"),
                            "score": round(getattr(r, "score", 0.0), 3),
                            "type": getattr(r, "metadata", {}).get("type", "entity")
                            if isinstance(getattr(r, "metadata", {}), dict) else "entity",
                        })
                except Exception as e:
                    logger.warning("QARetrieverTool: RAG retrieve failed: %s", e)
                    # Graceful degradation: return empty results
            else:
                # 无 RAG Pipeline 可用时的降级信息
                logger.info("QARetrieverTool: no RAG pipeline available, returning empty")

            # ── 时序推理 ──
            if args.include_temporal and self.temporal_reasoner:
                try:
                    temporal_params = self.temporal_reasoner.parse(args.query)
                    if temporal_params:
                        temporal_result = {
                            "detected_time_range": str(temporal_params),
                            "query": args.query,
                            "note": "基于时序参数，建议限定时间范围查询",
                        }
                except Exception as e:
                    logger.warning("QARetrieverTool: temporal parse failed: %s", e)

            # ── 构建返回 ──
            output = {
                "results": results,
                "total": len(results),
                "mode": args.retrieval_mode,
                "query": args.query,
            }
            if temporal_result:
                output["temporal"] = temporal_result

            return ToolResult(output=json.dumps(output, ensure_ascii=False))

        except Exception as e:
            logger.exception("QARetrieverTool: execute failed")
            return ToolResult(
                output=json.dumps({
                    "error": str(e),
                    "results": [],
                    "total": 0,
                }),
                is_error=True,
            )


# ── 便捷函数 ──

def get_qa_retriever_tool() -> QARetrieverTool:
    """获取 QARetrieverTool 单例。"""
    return QARetrieverTool()


__all__ = ["QARetrieverTool", "QARetrieverInput", "get_qa_retriever_tool"]
