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
import asyncio
from typing import Any, Dict, List, Optional

from odap.infra.config_composer import get_config
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
        self._llm_client_cache: Optional[Any] = None

    @classmethod
    def get_instance(cls) -> "NLDispatcher":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def dispatch(
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
            return await self._dispatch_structured(query, workspace_id, ontology_id, limit)
        if intent == QueryIntent.UNSTRUCTURED:
            return await self._dispatch_unstructured(query, workspace_id, ontology_id, limit)
        if intent == QueryIntent.HYBRID:
            return await self._dispatch_hybrid(query, workspace_id, ontology_id, limit)
        if intent == QueryIntent.ACTION:
            return await self._dispatch_action(query, workspace_id, ontology_id)
        return {
            "status": "error",
            "intent": intent.value,
            "message": "无法识别查询意图",
            "query": query,
        }

    async def _dispatch_structured(
        self, query: str, workspace_id: str, ontology_id: Optional[str], limit: int,
    ) -> Dict[str, Any]:
        dsl = await self._nl_to_dsl(query, ontology_id)
        try:
            result = await self._query_service.execute_async(
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
            return await self._dispatch_unstructured(query, workspace_id, ontology_id, limit)

    async def _dispatch_unstructured(
        self, query: str, workspace_id: str, ontology_id: Optional[str], limit: int,
    ) -> Dict[str, Any]:
        ontology_part = f", ontology_id='{ontology_id}'" if ontology_id else ""
        dsl = f".unstructured with(query='{query}'{ontology_part})"
        try:
            result = await self._query_service.execute_async(
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

    async def _dispatch_hybrid(
        self, query: str, workspace_id: str, ontology_id: Optional[str], limit: int,
    ) -> Dict[str, Any]:
        structured = await self._dispatch_structured(query, workspace_id, ontology_id, limit)
        unstructured = await self._dispatch_unstructured(query, workspace_id, ontology_id, limit)

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

    async def _dispatch_action(
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

    # ------------------------------------------------------------------
    # NL → DSL 转换：LLM 优先 + 关键词回退
    # ------------------------------------------------------------------

    @property
    def _llm_client(self) -> Optional[Any]:
        """懒加载 LLM 客户端（ZhipuAIClient），无 API Key 时返回 None。"""
        if self._llm_client_cache is None:
            try:
                from odap.infra.llm.llm_service import ZhipuAIClient
                from graphiti_core.llm_client.config import LLMConfig

                api_key = get_config("llm.api_key", "")
                api_base = get_config(
                    "llm.api_base", "https://open.bigmodel.cn/api/paas/v4"
                )
                model = get_config("llm.model", "glm-4")
                if api_key:
                    config = LLMConfig(
                        model=model, api_key=api_key,
                        base_url=api_base, temperature=0.3,
                    )
                    self._llm_client_cache = ZhipuAIClient(config=config)
                    logger.debug("NLDispatcher: LLM client initialized")
                else:
                    logger.debug("NLDispatcher: no OPENAI_API_KEY, LLM disabled")
                    self._llm_client_cache = None
            except Exception as e:
                logger.warning("NLDispatcher: LLM client init failed: %s", e)
                self._llm_client_cache = None
        return self._llm_client_cache

    # DSL 系统 prompt —— 指导 LLM 生成合法 DSL
    _DSL_SYSTEM_PROMPT = (
        "You are a query translator. Convert the user's natural language question "
        "to ODAP Query DSL.\n"
        "\n"
        "DSL syntax: .source with(filters) action(params)\n"
        "\n"
        "Sources:\n"
        "- .schema — query type definitions (object_types, link_types, action_types, etc.)\n"
        "- .entity — query entity instances (search, filter by type/property)\n"
        "- .topo — topology queries (neighbors, path, relations)\n"
        "- .temporal — temporal queries (history, at, range)\n"
        "- .unstructured — search unstructured documents\n"
        "\n"
        "Actions: list(), get(id), search('keyword'), neighbors(entity_id), "
        "path(from, to), history(entity_id), at(time), range(start, end)\n"
        "\n"
        "Filters: type='TypeName', property='value', search='keyword'\n"
        "\n"
        "Examples:\n"
        "- \"查找所有装备\" → .entity with(type='装备') list()\n"
        "- \"XX的邻居\" → .topo neighbors(XX)\n"
        "- \"装备A到装备B的路径\" → .topo path(from='装备A', to='装备B')\n"
        "- \"XX的历史变更\" → .temporal history(XX)\n"
        "- \"装备类型的定义\" → .schema with(type='object_type') list()\n"
        "- \"关于XX的文档\" → .unstructured with(search='XX') list()\n"
        "\n"
        "Rules:\n"
        "1. Output ONLY the DSL string, no explanation.\n"
        "2. DSL must start with a dot (e.g. .entity, .topo, .schema, .temporal, .unstructured).\n"
        "3. Use Chinese entity names as-is from the user query.\n"
    )

    async def _nl_to_dsl(self, query: str, ontology_id: Optional[str]) -> str:
        """NL→DSL 转换：LLM 优先 + 超时保护，关键词启发式回退。"""
        try:
            llm_result = await asyncio.wait_for(
                self._nl_to_dsl_with_llm(query, ontology_id),
                timeout=5.0,
            )
            if llm_result:
                return llm_result
        except (asyncio.TimeoutError, Exception) as e:
            logger.info("NLDispatcher: LLM path timed out or failed (%s), using keyword fallback", type(e).__name__)
        return self._nl_to_dsl_with_keywords(query, ontology_id)

    async def _nl_to_dsl_with_llm(
        self, query: str, ontology_id: Optional[str]
    ) -> Optional[str]:
        """使用 LLM 将自然语言转换为 DSL，失败时返回 None。"""
        client = self._llm_client
        if client is None:
            return None

        try:
            ont_hint = f"\nCurrent ontology_id: {ontology_id}" if ontology_id else ""
            user_prompt = f"{query}{ont_hint}"

            from graphiti_core.prompts.models import Message

            messages = [
                Message(role="system", content=self._DSL_SYSTEM_PROMPT),
                Message(role="user", content=user_prompt),
            ]
            result_dict, _, _ = await client._generate_response(
                messages, max_tokens=256,
            )
            # result_dict 可能是 {"response": "..."} 或直接字符串
            if isinstance(result_dict, dict):
                raw_dsl = (
                    result_dict.get("dsl", "")
                    or result_dict.get("response", "")
                    or result_dict.get("query", "")
                    or str(result_dict)
                )
            else:
                raw_dsl = str(result_dict) if result_dict else ""

            # 清理 LLM 输出：去除 markdown 代码块包裹
            dsl = raw_dsl.strip()
            code_block = re.search(r"```(?:\w+)?\s*\n?(.*?)\n?\s*```", dsl, re.DOTALL)
            if code_block:
                dsl = code_block.group(1).strip()

            # 验证：DSL 必须以 . 开头
            if dsl.startswith("."):
                logger.info(
                    "NLDispatcher: LLM DSL conversion succeeded: %s → %s",
                    query, dsl,
                )
                return dsl

            logger.warning(
                "NLDispatcher: LLM output not valid DSL (no leading dot): %s", dsl,
            )
            return None

        except Exception as e:
            logger.warning("NLDispatcher: LLM DSL conversion failed: %s", e)
            return None

    def _nl_to_dsl_with_keywords(self, query: str, ontology_id: Optional[str]) -> str:
        """轻量 NL→DSL 启发式：识别实体/拓扑/时序关键词（回退方案）。"""
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
