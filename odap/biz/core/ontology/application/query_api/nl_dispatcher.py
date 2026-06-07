"""
NLDispatcher — 自然语言查询统一调度器。

输入：NL 查询 + 上下文
处理：intent_classifier → 路径选择 → 调用底层服务
输出：QueryResult 兼容的 dict（含 source + rows）

支持 4 类 intent：
- STRUCTURED   → QueryService.execute (DSL 由 NL 启发式生成)
- UNSTRUCTURED → QueryService.execute with .unstructured
- HYBRID       → 双路并行 + result_merger
- ACTION       → ontology_app_skill 调度
"""
import logging
import re
from typing import Any, Dict, List, Optional

from odap.infra.query import get_query_service, QuerySource
from odap.biz.core.ontology.application.skill_registry import get_app_skill_registry

from .intent_classifier import IntentClassifier, QueryIntent
from . import result_merger

logger = logging.getLogger(__name__)


class NLDispatcher:
    """NL 查询统一调度器（单例）。"""

    _instance: Optional["NLDispatcher"] = None

    def __init__(self, classifier: Optional[IntentClassifier] = None) -> None:
        self._classifier = classifier or IntentClassifier()
        self._query_service = get_query_service()

    @classmethod
    def get_instance(cls) -> "NLDispatcher":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def dispatch(
        self,
        query: str,
        workspace_id: str = "default",
        ontology_id: Optional[str] = None,
        limit: int = 20,
        hints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """主入口。"""
        try:
            intent = self._classifier.classify(query, hints=hints)
        except Exception as e:
            logger.warning("Intent classification failed: %s, fallback to STRUCTURED", e)
            intent = QueryIntent.STRUCTURED

        if intent == QueryIntent.STRUCTURED:
            return self._dispatch_structured(query, workspace_id, ontology_id, limit)
        if intent == QueryIntent.UNSTRUCTURED:
            return self._dispatch_unstructured(query, workspace_id, ontology_id, limit)
        if intent == QueryIntent.HYBRID:
            return self._dispatch_hybrid(query, workspace_id, ontology_id, limit)
        if intent == QueryIntent.ACTION:
            return self._dispatch_action(query, workspace_id, ontology_id)
        return {
            "status": "error",
            "intent": intent.value,
            "message": "无法识别查询意图",
            "query": query,
        }

    def _dispatch_structured(
        self, query: str, workspace_id: str, ontology_id: Optional[str], limit: int,
    ) -> Dict[str, Any]:
        dsl = self._nl_to_dsl(query, ontology_id)
        try:
            result = self._query_service.execute(
                workspace_id=workspace_id, query=dsl, limit=limit,
            )
            return {
                "status": "success",
                "intent": QueryIntent.STRUCTURED.value,
                "query": query,
                "translated_dsl": dsl,
                "source": result.source.value,
                "rows": result.rows,
                "total": result.total,
            }
        except Exception as e:
            logger.warning("STRUCTURED dispatch failed: %s, fallback to UNSTRUCTURED", e)
            return self._dispatch_unstructured(query, workspace_id, ontology_id, limit)

    def _dispatch_unstructured(
        self, query: str, workspace_id: str, ontology_id: Optional[str], limit: int,
    ) -> Dict[str, Any]:
        ontology_part = f", ontology_id='{ontology_id}'" if ontology_id else ""
        dsl = f".unstructured with(query='{query}'{ontology_part})"
        try:
            result = self._query_service.execute(
                workspace_id=workspace_id, query=dsl, limit=limit,
            )
            return {
                "status": "success",
                "intent": QueryIntent.UNSTRUCTURED.value,
                "query": query,
                "translated_dsl": dsl,
                "source": result.source.value,
                "rows": result.rows,
                "total": result.total,
            }
        except Exception as e:
            logger.error("UNSTRUCTURED dispatch failed: %s", e)
            return {
                "status": "error",
                "intent": QueryIntent.UNSTRUCTURED.value,
                "query": query,
                "error": str(e),
            }

    def _dispatch_hybrid(
        self, query: str, workspace_id: str, ontology_id: Optional[str], limit: int,
    ) -> Dict[str, Any]:
        structured = self._dispatch_structured(query, workspace_id, ontology_id, limit)
        unstructured = self._dispatch_unstructured(query, workspace_id, ontology_id, limit)

        s_rows = structured.get("rows", []) if structured.get("status") == "success" else []
        u_rows = unstructured.get("rows", []) if unstructured.get("status") == "success" else []

        merged_rows = result_merger.merge(s_rows, u_rows, max_size=limit)

        return {
            "status": "success",
            "intent": QueryIntent.HYBRID.value,
            "query": query,
            "structured_count": len(s_rows),
            "unstructured_count": len(u_rows),
            "rows": merged_rows,
            "total": len(merged_rows),
        }

    def _dispatch_action(
        self, query: str, workspace_id: str, ontology_id: Optional[str],
    ) -> Dict[str, Any]:
        registry = get_app_skill_registry()
        skills = registry.list(workspace_id=workspace_id, ontology_id=ontology_id)
        if not skills:
            return {
                "status": "error",
                "intent": QueryIntent.ACTION.value,
                "query": query,
                "message": f"no app skills registered for ws={workspace_id}, ont={ontology_id}",
            }

        target_skill = self._pick_skill(query, skills)
        from odap.tools.base import SkillInput
        import time
        start = time.perf_counter()
        try:
            input_data = SkillInput(
                action=self._infer_action(query),
                request_id=f"nl-{int(start * 1000)}",
            )
            output = target_skill.run(input_data.model_dump())
            return {
                "status": "success" if output.success else "error",
                "intent": QueryIntent.ACTION.value,
                "query": query,
                "skill_name": target_skill.metadata.name,
                "data": output.data,
                "error": output.error,
            }
        except Exception as e:
            logger.error("ACTION dispatch failed: %s", e)
            return {
                "status": "error",
                "intent": QueryIntent.ACTION.value,
                "query": query,
                "skill_name": target_skill.metadata.name,
                "error": str(e),
            }

    def _nl_to_dsl(self, query: str, ontology_id: Optional[str]) -> str:
        """轻量 NL→DSL 启发式：识别实体/拓扑/时序关键词。"""
        q = query.lower()
        if any(kw in q for kw in ("邻居", "neighbor", "邻接", "相关实体", "neighbours")):
            return f".topo neighbors({query})"
        if any(kw in q for kw in ("路径", "path", "从", "到")):
            return f".topo path({query})"
        if any(kw in q for kw in ("历史", "history", "变更记录")):
            return f".temporal history({query})"
        if any(kw in q for kw in ("类型", "schema", "定义", "object_type")):
            return f".schema with({query})"
        ont_part = f", ontology_id='{ontology_id}'" if ontology_id else ""
        return f".entity with(search='{query}'{ont_part})"

    def _pick_skill(self, query: str, skills: list) -> Any:
        q = query.lower()
        if any(kw in q for kw in ("执行", "运行", "function", "函数")):
            for s in skills:
                if "runtime" in s.metadata.name:
                    return s
        if any(kw in q for kw in ("会话", "session", "蓝图", "blueprint")):
            for s in skills:
                if "harness" in s.metadata.name:
                    return s
        if any(kw in q for kw in ("服务", "service", "发布")):
            for s in skills:
                if "servitization" in s.metadata.name:
                    return s
        if any(kw in q for kw in ("agent", "调度", "dispatch")):
            for s in skills:
                if "team_agent" in s.metadata.name:
                    return s
        return skills[0]

    def _infer_action(self, query: str) -> str:
        q = query.lower()
        if any(kw in q for kw in ("列表", "list", "查询", "获取")):
            return "list"
        if any(kw in q for kw in ("执行", "run", "execute")):
            return "execute"
        if any(kw in q for kw in ("创建", "create", "新建")):
            return "create"
        return "list"


__all__ = ["NLDispatcher"]
