"""
多跳检索规划器 - 将复杂问题分解为多步检索链

功能：
- MultiHopPlanner: 复杂问题分解（LLM 增强 + 规则回退）
- MultiHopExecutor: 多跳检索执行与结果聚合
- 复杂度检测: 判断问题是否需要多跳检索
"""

import logging
import re
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    """查询复杂度等级"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


class HopType(str, Enum):
    """跳类型"""
    ENTITY_LOOKUP = "entity_lookup"
    RELATION_TRAVERSE = "relation_traverse"
    ATTRIBUTE_FILTER = "attribute_filter"
    CAUSAL_CHAIN = "causal_chain"


class SubQuery:
    """子查询"""

    def __init__(
        self,
        query_text: str,
        hop_type: HopType,
        hop_index: int,
        depends_on: Optional[int] = None,
        description: str = "",
    ):
        self.query_id = f"hop-{uuid.uuid4().hex[:6]}"
        self.query_text = query_text
        self.hop_type = hop_type
        self.hop_index = hop_index
        self.depends_on = depends_on
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "hop_type": self.hop_type.value,
            "hop_index": self.hop_index,
            "depends_on": self.depends_on,
            "description": self.description,
        }


class MultiHopPlan:
    """多跳检索计划"""

    def __init__(self, original_query: str, complexity: QueryComplexity):
        self.plan_id = f"plan-{uuid.uuid4().hex[:6]}"
        self.original_query = original_query
        self.complexity = complexity
        self.sub_queries: List[SubQuery] = []

    def add_sub_query(
        self,
        query_text: str,
        hop_type: HopType,
        depends_on: Optional[int] = None,
        description: str = "",
    ) -> SubQuery:
        hop_index = len(self.sub_queries)
        sq = SubQuery(
            query_text=query_text,
            hop_type=hop_type,
            hop_index=hop_index,
            depends_on=depends_on,
            description=description,
        )
        self.sub_queries.append(sq)
        return sq

    @property
    def hop_count(self) -> int:
        return len(self.sub_queries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "original_query": self.original_query,
            "complexity": self.complexity.value,
            "hop_count": self.hop_count,
            "sub_queries": [sq.to_dict() for sq in self.sub_queries],
        }


class MultiHopPlanner:
    """
    多跳检索规划器

    将复杂问题分解为多步检索链：
    - LLM 增强分解（可选）
    - 规则回退分解（始终可用）
    - 复杂度检测
    """

    MAX_HOPS = 3
    HOP_TIMEOUT_SECONDS = 10

    # 复合连接词
    COMPOUND_CONNECTORS = ["和", "以及", "同时", "并且", "还有", "、", "与", "及"]

    # 因果关键词
    CAUSAL_KEYWORDS = ["为什么", "原因", "导致", "因为", "所以", "造成", "引起", "缘故"]

    # 关系型模式
    RELATIONAL_PATTERNS = [
        (r"哪些(.+?)(的|$)", "relational_which"),
        (r"属于(.+?)(的|$)", "relational_belong"),
        (r"关联的(.+)", "relational_associated"),
        (r"相关的(.+)", "relational_related"),
        (r"包含(.+?)(的|$)", "relational_contain"),
        (r"(?:^|(?<=[，。？！、\s]))有(.+?)(的|$)", "relational_has"),
    ]

    # 关系型关键词（不需要完整模式匹配）
    RELATIONAL_KEYWORDS = ["哪些", "属于", "关联", "相关", "包含"]

    # 简单事实型模式
    SIMPLE_PATTERNS = [
        r"^(什么是|什么是|何为|定义)",
        r"^(谁|谁的|who)",
        r"^(什么时候|何时|when)",
        r"^(在哪里|何地|where)",
        r"^(多少|几个|how many)",
    ]

    def __init__(self, llm_client=None):
        self._llm_client = llm_client
        self._complexity_llm_initialized = False
        self._complexity_llm_available = False

    # ------------------------------------------------------------------
    # LLM 复杂度检测（延迟初始化）
    # ------------------------------------------------------------------

    def _init_complexity_llm(self):
        """延迟初始化 LLM 客户端用于复杂度检测"""
        if self._complexity_llm_initialized:
            return
        self._complexity_llm_initialized = True
        try:
            import os
            api_key = os.getenv("OPENAI_API_KEY", "")
            if api_key:
                self._complexity_llm_available = True
            else:
                self._complexity_llm_available = False
        except Exception:
            self._complexity_llm_available = False

    def _detect_complexity_with_llm(self, query: str) -> Optional[QueryComplexity]:
        """使用 LLM 检测查询复杂度。

        Returns:
            QueryComplexity or None on failure (falls back to keyword-based).
        """
        self._init_complexity_llm()
        if not self._complexity_llm_available:
            return None

        try:
            import os
            import json as _json
            import requests as _requests

            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "deepseek-ai/deepseek-v4-pro")

            if not api_key:
                return None

            system_prompt = (
                "你是一个查询复杂度分类器。将用户的查询分为以下三类之一：\n"
                "- simple: 简单事实型查询，只需单次检索即可回答\n"
                "- medium: 中等复杂度，可能需要2步检索\n"
                "- complex: 复杂查询，需要多步推理、跨实体关联或因果分析\n\n"
                "只返回一个单词：simple、medium 或 complex。不要返回其他内容。"
            )
            user_prompt = f"请判断以下查询的复杂度：{query}"

            resp = _requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 16,
                    "temperature": 0.0,
                },
                timeout=3,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].strip().lower()

            # Map LLM response to QueryComplexity
            mapping = {
                "simple": QueryComplexity.SIMPLE,
                "medium": QueryComplexity.MEDIUM,
                "complex": QueryComplexity.COMPLEX,
            }
            # Handle potential extra text around the keyword
            for key, value in mapping.items():
                if key in content:
                    return value

            return None
        except Exception as e:
            logger.debug("MultiHopPlanner LLM complexity detection failed: %s", e)
            return None
    # ------------------------------------------------------------------

    def plan(self, query: str, schemas: Optional[List] = None) -> MultiHopPlan:
        """
        为查询生成多跳检索计划

        Args:
            query: 用户查询文本
            schemas: 本体 schema 列表（可选，用于本体感知分解）

        Returns:
            MultiHopPlan 实例
        """
        complexity = self.detect_complexity(query)
        plan = MultiHopPlan(original_query=query, complexity=complexity)

        if complexity == QueryComplexity.SIMPLE:
            plan.add_sub_query(
                query_text=query,
                hop_type=HopType.ENTITY_LOOKUP,
                description="简单查询，单跳检索",
            )
            return plan

        # 尝试 LLM 分解（注入本体 schema 信息）
        llm_plan = self._plan_with_llm(query, schemas)
        if llm_plan and len(llm_plan) >= 2:
            for i, sq_data in enumerate(llm_plan[: self.MAX_HOPS]):
                hop_type = self._infer_hop_type(sq_data, i)
                plan.add_sub_query(
                    query_text=sq_data["query"],
                    hop_type=hop_type,
                    depends_on=i - 1 if i > 0 else None,
                    description=sq_data.get("description", ""),
                )
            logger.info(
                "MultiHopPlanner: LLM decomposition produced %d sub-queries for '%s'",
                len(llm_plan),
                query[:50],
            )
            return plan

        # 规则回退分解
        self._plan_with_rules(query, plan)
        logger.info(
            "MultiHopPlanner: rule-based decomposition produced %d sub-queries for '%s'",
            plan.hop_count,
            query[:50],
        )
        return plan

    def detect_complexity(self, query: str) -> QueryComplexity:
        """
        检测查询复杂度

        规则：
        - 简单事实型 -> SIMPLE
        - 包含复合连接词 / 因果词 / 关系型模式 -> COMPLEX
        - 长度 > 20 且含实体引用 -> MEDIUM
        - LLM 增强：当关键词检测为 SIMPLE 但查询较长时，用 LLM 二次确认
        """
        if not query or not query.strip():
            return QueryComplexity.SIMPLE

        query_stripped = query.strip()

        # 简单事实型检测
        for pattern in self.SIMPLE_PATTERNS:
            if re.match(pattern, query_stripped):
                # 即使匹配简单模式，如果同时有复合连接词仍为复杂
                if any(conn in query_stripped for conn in self.COMPOUND_CONNECTORS):
                    return QueryComplexity.COMPLEX
                return QueryComplexity.SIMPLE

        # 复合连接词 -> COMPLEX
        connector_count = sum(1 for conn in self.COMPOUND_CONNECTORS if conn in query_stripped)
        if connector_count >= 2:
            return QueryComplexity.COMPLEX
        # 单个连接词 + 关系型关键词 -> COMPLEX（如"哪些装备需要维修和保养"）
        if connector_count == 1 and any(kw in query_stripped for kw in self.RELATIONAL_KEYWORDS):
            return QueryComplexity.COMPLEX
        # 单个连接词 + 足够长度 -> COMPLEX（如"装备维修和保养"）
        if connector_count == 1 and len(query_stripped) > 6:
            return QueryComplexity.COMPLEX

        # 因果关键词 -> COMPLEX
        if any(kw in query_stripped for kw in self.CAUSAL_KEYWORDS):
            return QueryComplexity.COMPLEX

        # 关系型模式 -> COMPLEX
        for pattern, _ in self.RELATIONAL_PATTERNS:
            if re.search(pattern, query_stripped):
                return QueryComplexity.COMPLEX

        # 关系型关键词 + 足够长度 -> COMPLEX（如"哪些装备需要维修"）
        if any(kw in query_stripped for kw in self.RELATIONAL_KEYWORDS) and len(query_stripped) > 8:
            return QueryComplexity.COMPLEX

        # 时间 + 实体引用 -> MEDIUM
        temporal_keywords = ["上周", "本周", "上个月", "最近", "当前", "过去", "之前", "期间"]
        has_temporal = any(kw in query_stripped for kw in temporal_keywords)
        if has_temporal and len(query_stripped) > 4:
            return QueryComplexity.MEDIUM

        # 长度 > 20 -> MEDIUM
        if len(query_stripped) > 20:
            return QueryComplexity.MEDIUM

        # LLM 增强：关键词检测为 SIMPLE 但查询较长（>15字符），用 LLM 二次确认
        keyword_result = QueryComplexity.SIMPLE
        if len(query_stripped) > 15:
            llm_result = self._detect_complexity_with_llm(query_stripped)
            if llm_result is not None and llm_result != keyword_result:
                logger.info(
                    "MultiHopPlanner: LLM overrode keyword result '%s' -> '%s' for query '%s'",
                    keyword_result.value, llm_result.value, query_stripped[:50],
                )
                return llm_result

        return keyword_result

    # ------------------------------------------------------------------
    # LLM 分解（可选）
    # ------------------------------------------------------------------

    def _plan_with_llm(self, query: str, schemas: Optional[List] = None) -> Optional[List[Dict[str, str]]]:
        """使用 LLM 分解复杂查询，返回子查询列表或 None"""
        if not self._llm_client:
            return None

        try:
            import os
            import json as _json
            import requests as _requests

            api_key = os.getenv("OPENAI_API_KEY", "")
            base_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
            model = os.getenv("OPENAI_MODEL", "deepseek-ai/deepseek-v4-pro")

            if not api_key:
                return None

            # 构建本体 schema 描述（如果可用）
            schema_desc = ""
            if schemas:
                entity_type_names = []
                relation_type_names = []
                for schema in schemas:
                    entity_type_names.extend(schema.entity_type_names)
                    relation_type_names.extend(schema.relation_type_names)
                if entity_type_names:
                    schema_desc += f"\n可用实体类型: {', '.join(entity_type_names[:20])}"
                if relation_type_names:
                    schema_desc += f"\n可用关系类型: {', '.join(relation_type_names[:20])}"

            system_prompt = (
                "你是一个查询分解专家。将用户的复杂问题分解为2-3个简单的子查询，"
                "每个子查询应该能通过单次知识库检索回答。"
                "返回JSON数组，每个元素包含 'query' 和 'description' 字段。"
                "只返回JSON，不要其他文字。"
                "示例: [{\"query\": \"查找所有装备\", \"description\": \"第一步：查找装备实体\"}]"
            )
            if schema_desc:
                system_prompt += (
                    f"\n\n当前知识图谱的本体 Schema：{schema_desc}"
                    "\n请在分解时优先使用上述实体类型和关系类型。"
                )
            user_prompt = f"请分解以下问题：{query}"

            resp = _requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 512,
                    "temperature": 0.3,
                },
                timeout=8,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

            # 提取 JSON
            json_match = re.search(r"\[.*\]", content, re.DOTALL)
            if json_match:
                sub_queries = _json.loads(json_match.group())
                if isinstance(sub_queries, list) and len(sub_queries) >= 2:
                    return sub_queries[: self.MAX_HOPS]

        except Exception as e:
            logger.warning("MultiHopPlanner LLM decomposition failed: %s", e)

        return None

    # ------------------------------------------------------------------
    # 规则回退分解
    # ------------------------------------------------------------------

    def _plan_with_rules(self, query: str, plan: MultiHopPlan) -> None:
        """基于规则的查询分解"""

        # 1. 复合问题拆分
        compound_parts = self._split_compound_query(query)
        if compound_parts and len(compound_parts) >= 2:
            for i, part in enumerate(compound_parts[: self.MAX_HOPS]):
                plan.add_sub_query(
                    query_text=part.strip(),
                    hop_type=HopType.ENTITY_LOOKUP,
                    depends_on=i - 1 if i > 0 else None,
                    description=f"复合问题子查询 #{i + 1}",
                )
            return

        # 2. 因果问题拆分
        if any(kw in query for kw in self.CAUSAL_KEYWORDS):
            self._plan_causal(query, plan)
            return

        # 3. 关系型问题拆分
        for pattern, rel_type in self.RELATIONAL_PATTERNS:
            match = re.search(pattern, query)
            if match:
                self._plan_relational(query, match, rel_type, plan)
                return

        # 4. 兜底：原始查询 + 扩展查询
        plan.add_sub_query(
            query_text=query,
            hop_type=HopType.ENTITY_LOOKUP,
            description="原始查询",
        )
        # 生成扩展查询：提取关键词重新组合
        expanded = self._expand_query(query)
        if expanded and expanded != query:
            plan.add_sub_query(
                query_text=expanded,
                hop_type=HopType.RELATION_TRAVERSE,
                depends_on=0,
                description="基于第一步结果的关联扩展检索",
            )

    def _split_compound_query(self, query: str) -> Optional[List[str]]:
        """拆分复合问题"""
        # 优先使用 "和" "以及" "并且" "还有" 拆分
        for conn in ["以及", "并且", "还有", "同时", "和", "与", "及"]:
            if conn in query:
                parts = query.split(conn, 1)
                parts = [p.strip() for p in parts if p.strip()]
                if len(parts) >= 2:
                    return parts

        # 使用顿号拆分
        if "、" in query:
            parts = query.split("、")
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                # 重新组合：第一个子查询取前两部分，后续各自独立
                result = []
                base = parts[0]
                for extra in parts[1:]:
                    result.append(f"{base}和{extra}")
                return result

        return None

    def _plan_causal(self, query: str, plan: MultiHopPlan) -> None:
        """因果问题分解"""
        # 第一步：查找相关实体/事件
        entity_query = re.sub(
            r"(为什么|原因|导致|因为|所以|造成|引起|缘故)", "", query
        ).strip()
        if not entity_query:
            entity_query = query

        plan.add_sub_query(
            query_text=entity_query,
            hop_type=HopType.ENTITY_LOOKUP,
            description="查找因果链中的实体/事件",
        )

        # 第二步：查找因果关系
        causal_query = f"{entity_query} 原因 关系"
        plan.add_sub_query(
            query_text=causal_query,
            hop_type=HopType.CAUSAL_CHAIN,
            depends_on=0,
            description="查找实体间的因果关联",
        )

    def _plan_relational(
        self,
        query: str,
        match: re.Match,
        rel_type: str,
        plan: MultiHopPlan,
    ) -> None:
        """关系型问题分解"""
        # 提取源实体描述
        source_desc = match.group(1).strip() if match.lastindex >= 1 else query

        # 第一步：查找源实体
        plan.add_sub_query(
            query_text=source_desc,
            hop_type=HopType.ENTITY_LOOKUP,
            description=f"查找源实体: {source_desc}",
        )

        # 第二步：沿关系遍历
        plan.add_sub_query(
            query_text=query,
            hop_type=HopType.RELATION_TRAVERSE,
            depends_on=0,
            description="基于源实体查找关联目标",
        )

    def _expand_query(self, query: str) -> Optional[str]:
        """基于原始查询生成扩展查询"""
        # 提取核心名词（简单启发式：去掉疑问词和助词）
        core = re.sub(
            r"(哪些|什么|怎么|如何|为什么|的|了|吗|呢|啊|是|有|在|被|把|给|对|与|和|及|以及)",
            "",
            query,
        ).strip()
        if not core or len(core) < 2:
            return None
        return f"{core} 关联 关系"

    def _infer_hop_type(self, sq_data: Dict[str, str], index: int) -> HopType:
        """根据子查询内容和位置推断跳类型"""
        query_text = sq_data.get("query", "").lower()
        desc = sq_data.get("description", "").lower()

        if index == 0:
            return HopType.ENTITY_LOOKUP

        if any(kw in query_text or kw in desc for kw in ["原因", "因果", "导致", "why", "cause"]):
            return HopType.CAUSAL_CHAIN
        if any(kw in query_text or kw in desc for kw in ["关系", "关联", "相关", "relation", "connect"]):
            return HopType.RELATION_TRAVERSE
        if any(kw in query_text or kw in desc for kw in ["属性", "状态", "特征", "attribute", "property"]):
            return HopType.ATTRIBUTE_FILTER

        return HopType.RELATION_TRAVERSE


class MultiHopExecutor:
    """
    多跳检索执行器

    依次执行 MultiHopPlan 中的子查询，
    每一步的结果累积为下一步的上下文，
    最终合并去重返回增强的 RAG 结果。
    """

    def __init__(self, rag_pipeline, planner: Optional[MultiHopPlanner] = None):
        """
        Args:
            rag_pipeline: RAGPipeline 实例，用于执行单次检索
            planner: MultiHopPlanner 实例（可选，默认内部创建）
        """
        self.rag_pipeline = rag_pipeline
        self.planner = planner or MultiHopPlanner()

    def execute(
        self,
        query: str,
        workspace_id: Optional[str] = None,
        scenario_id: Optional[str] = None,
        ontology_ids: Optional[List[str]] = None,
        top_k: int = 10,
        schemas: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        执行多跳检索

        Args:
            query: 用户查询
            workspace_id: 工作空间 ID
            scenario_id: 场景 ID
            ontology_ids: 本体 ID 列表
            top_k: 每跳返回的最大结果数
            schemas: 本体 schema 列表（可选，透传给 planner）

        Returns:
            包含合并结果和元数据的字典
        """
        plan = self.planner.plan(query, schemas=schemas)

        # 简单查询直接单跳
        if plan.complexity == QueryComplexity.SIMPLE:
            results = self._single_hop(
                query, workspace_id, scenario_id, ontology_ids, top_k
            )
            return {
                "status": "success",
                "results": results,
                "multihop_used": False,
                "hop_count": 1,
                "complexity": plan.complexity.value,
                "plan": plan.to_dict(),
                "hop_details": [
                    {
                        "hop_index": 0,
                        "query": query,
                        "result_count": len(results),
                    }
                ],
            }

        # 多跳执行
        all_results: List[Dict[str, Any]] = []
        seen_sources: set = set()
        hop_details: List[Dict[str, Any]] = []
        accumulated_context: str = ""

        for sub_query in plan.sub_queries[: MultiHopPlanner.MAX_HOPS]:
            hop_start = time.time()

            # 构造增强查询：将前序结果摘要注入
            enhanced_query = self._enhance_query_with_context(
                sub_query.query_text, accumulated_context
            )

            try:
                hop_results = self._single_hop(
                    enhanced_query,
                    workspace_id,
                    scenario_id,
                    ontology_ids,
                    top_k,
                )
            except Exception as e:
                logger.warning(
                    "MultiHopExecutor hop %d failed: %s", sub_query.hop_index, e
                )
                hop_results = []

            elapsed = time.time() - hop_start

            # 去重合并
            new_count = 0
            for r in hop_results:
                source_key = r.get("source", "")
                if source_key and source_key not in seen_sources:
                    seen_sources.add(source_key)
                    r["hop_index"] = sub_query.hop_index
                    r["hop_type"] = sub_query.hop_type.value
                    all_results.append(r)
                    new_count += 1

            # 累积上下文（取前 3 条结果的摘要）
            context_parts = []
            for r in hop_results[:3]:
                content = r.get("content", "")
                if content:
                    context_parts.append(content[:200])
            if context_parts:
                accumulated_context = "; ".join(context_parts)

            hop_detail = {
                "hop_index": sub_query.hop_index,
                "query": sub_query.query_text,
                "enhanced_query": enhanced_query if enhanced_query != sub_query.query_text else None,
                "hop_type": sub_query.hop_type.value,
                "result_count": len(hop_results),
                "new_count": new_count,
                "elapsed_seconds": round(elapsed, 2),
            }
            hop_details.append(hop_detail)

            logger.info(
                "MultiHopExecutor hop %d/%d: query='%s' results=%d new=%d elapsed=%.2fs",
                sub_query.hop_index + 1,
                plan.hop_count,
                sub_query.query_text[:40],
                len(hop_results),
                new_count,
                elapsed,
            )

            # 超时保护：如果总耗时超过 MAX_HOPS * HOP_TIMEOUT，停止
            total_elapsed = time.time() - hop_start + elapsed
            if total_elapsed > MultiHopPlanner.MAX_HOPS * MultiHopPlanner.HOP_TIMEOUT_SECONDS:
                logger.warning("MultiHopExecutor total timeout exceeded, stopping at hop %d", sub_query.hop_index)
                break

        # 按分数排序
        all_results.sort(key=lambda r: r.get("score", 0.0), reverse=True)

        return {
            "status": "success",
            "results": all_results[:top_k],
            "multihop_used": True,
            "hop_count": plan.hop_count,
            "complexity": plan.complexity.value,
            "plan": plan.to_dict(),
            "hop_details": hop_details,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _single_hop(
        self,
        query: str,
        workspace_id: Optional[str],
        scenario_id: Optional[str],
        ontology_ids: Optional[List[str]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """执行单跳检索，返回字典列表"""
        rag_results = self.rag_pipeline.retrieve(
            query,
            top_k=top_k,
            workspace_id=workspace_id,
            ontology_ids=ontology_ids,
            scenario_id=scenario_id,
        )
        # 将 RAGResult dataclass 转为 dict
        return [
            {
                "content": r.content,
                "source": r.source,
                "score": r.score,
                "metadata": r.metadata,
            }
            for r in rag_results
        ]

    def _enhance_query_with_context(
        self, query: str, accumulated_context: str
    ) -> str:
        """将累积上下文注入查询以增强检索效果"""
        if not accumulated_context:
            return query

        # 提取上下文中的关键实体名（简单启发式：取分号分隔的片段首部）
        context_entities = []
        for segment in accumulated_context.split(";"):
            segment = segment.strip()
            if not segment:
                continue
            # 取 "|" 分隔的第一个字段作为实体名
            name_part = segment.split("|")[0].strip()
            if name_part and len(name_part) <= 20:
                context_entities.append(name_part)

        if not context_entities:
            return query

        # 将实体名附加到查询后面
        entity_str = " ".join(context_entities[:3])
        return f"{query} {entity_str}"
