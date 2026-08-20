"""
多跳检索规划器 - 将复杂问题分解为多步检索链

功能：
- MultiHopPlanner: 复杂问题分解（**确定性规则驱动**，本体结构 + 术语字典）
- MultiHopExecutor: 多跳检索执行与结果聚合
- 复杂度检测: 判断问题是否需要多跳检索（**纯规则，无 LLM**）

本体论原则（严格）：
- LLM 不参与复杂度判断 / 查询分解 / 语义判断
- 分解完全由确定性规则 + 本体 schema（实体类型/关系类型）+ USL 术语字典驱动
- 同一查询在任何时刻规划结果确定且唯一
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
        # llm_client 参数保留以兼容旧调用方，但**不再使用**：
        # 复杂度判断与查询分解均为确定性规则驱动，LLM 不参与（本体论原则）。
        self._llm_client = None

    # ------------------------------------------------------------------
    # 复杂度检测（纯规则，无 LLM）
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

        # 确定性规则分解（本体 schema 辅助关系遍历，无 LLM）
        self._plan_with_rules(query, plan, schemas=schemas)
        logger.info(
            "MultiHopPlanner: deterministic rule-based decomposition produced %d sub-queries for '%s'",
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

        # 纯规则判断，无 LLM 二次确认（确定性）
        return QueryComplexity.SIMPLE

    # ------------------------------------------------------------------
    # 确定性规则分解（无 LLM）
    # ------------------------------------------------------------------

    def _plan_with_rules(self, query: str, plan: MultiHopPlan, schemas: Optional[List] = None) -> None:
        """基于规则的确定性查询分解。

        Args:
            query: 用户查询
            plan: 计划对象
            schemas: 本体 schema 列表（用于关系遍历时确定关系类型，非 LLM）
        """

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

        # 3. 关系型问题拆分（本体 schema 辅助确定关系类型）
        for pattern, rel_type in self.RELATIONAL_PATTERNS:
            match = re.search(pattern, query)
            if match:
                self._plan_relational(query, match, rel_type, plan, schemas=schemas)
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
        schemas: Optional[List] = None,
    ) -> None:
        """关系型问题分解（本体 schema 辅助确定关系类型，确定性）"""
        # 提取源实体描述
        source_desc = match.group(1).strip() if match.lastindex >= 1 else query

        # 第一步：查找源实体
        plan.add_sub_query(
            query_text=source_desc,
            hop_type=HopType.ENTITY_LOOKUP,
            description=f"查找源实体: {source_desc}",
        )

        # 第二步：沿关系遍历（关系类型由本体 schema 确定性匹配，非 LLM 推断）
        plan.add_sub_query(
            query_text=query,
            hop_type=HopType.RELATION_TRAVERSE,
            depends_on=0,
            description="基于源实体查找关联目标（关系类型由本体 schema 确定）",
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
