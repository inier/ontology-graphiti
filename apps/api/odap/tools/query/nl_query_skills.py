"""NL 查询技能注册 - nl_query / nl_search / nl_explain"""

import asyncio
import logging
from typing import Any, Dict, Optional

from odap.tools import register_skill

logger = logging.getLogger(__name__)


def _nl_query_handler(query: str, mode: str = "auto", top_k: int = 10,
                      workspace_id: str = "", scenario_id: Optional[str] = None,
                      user_id: str = "agent") -> Dict[str, Any]:
    """自然语言本体查询 Skill handler"""
    try:
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline()
        request = QueryRequest(
            query=query,
            mode=mode,
            top_k=top_k,
            workspace_id=workspace_id or None,
            scenario_id=scenario_id,
            user_id=user_id,
        )
        # 同步运行异步管线
        response = asyncio.run(pipeline.query(request))
        return {
            "status": "success",
            "answer": response.answer,
            "sources": [s.model_dump() for s in response.sources],
            "intent": response.understanding.intent.value if response.understanding else "",
            "pillars": response.pillar_contributions,
            "time_ms": response.total_time_ms,
        }
    except Exception as e:
        logger.error(f"nl_query skill error: {e}")
        return {"status": "error", "message": str(e)}


def _nl_search_handler(query: str, mode: str = "auto", top_k: int = 10,
                       workspace_id: str = "", scenario_id: Optional[str] = None,
                       user_id: str = "agent") -> Dict[str, Any]:
    """自然语言纯检索 Skill handler"""
    try:
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline()
        request = QueryRequest(
            query=query,
            mode=mode,
            top_k=top_k,
            workspace_id=workspace_id or None,
            scenario_id=scenario_id,
            user_id=user_id,
        )
        result_set = asyncio.run(pipeline.search(request))
        return {
            "status": "success",
            "results": [r.model_dump() for r in result_set.results],
            "total": len(result_set.results),
            "pillar_scores": result_set.pillar_scores,
        }
    except Exception as e:
        logger.error(f"nl_search skill error: {e}")
        return {"status": "error", "message": str(e)}


def _nl_explain_handler(query: str, mode: str = "auto", top_k: int = 10,
                        workspace_id: str = "", scenario_id: Optional[str] = None) -> Dict[str, Any]:
    """查询解释 Skill handler"""
    try:
        from odap.biz.data.qa.models import QueryRequest
        from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

        pipeline = QueryPipeline()
        request = QueryRequest(
            query=query,
            mode=mode,
            top_k=top_k,
            workspace_id=workspace_id or None,
            scenario_id=scenario_id,
        )
        explanation = pipeline.explain(request)
        return {
            "status": "success",
            **explanation,
        }
    except Exception as e:
        logger.error(f"nl_explain skill error: {e}")
        return {"status": "error", "message": str(e)}


def register_nl_query_skills():
    """注册 NL 查询技能到 SKILL_CATALOG"""
    register_skill(
        name="nl_query",
        description="自然语言本体查询 - 支持关键词/语义/图关联三模式检索，返回完整回答",
        handler=_nl_query_handler,
        category="query",
    )
    register_skill(
        name="nl_search",
        description="自然语言纯检索 - 仅返回检索结果，不生成回答",
        handler=_nl_search_handler,
        category="query",
    )
    register_skill(
        name="nl_explain",
        description="查询解释 - 展示自然语言如何被理解和转换为查询计划",
        handler=_nl_explain_handler,
        category="query",
    )
    logger.info("NL query skills registered: nl_query, nl_search, nl_explain")
