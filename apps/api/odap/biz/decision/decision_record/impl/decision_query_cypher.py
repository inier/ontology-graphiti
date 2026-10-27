"""决策 Cypher 过滤条件与排序白名单（ADR-091 §5.5）

抽成独立模块的三个理由：
1. list 与 count 必须用**同一份**过滤条件，否则会出现"列表为空但总数非零"
2. 排序键只能来自白名单拼入 Cypher（客户端原值绝不进语句），单点可审计
3. 纯函数，不需要 Neo4j 即可单测
"""

from typing import Any, Dict

from odap.biz.decision.decision_record.interfaces.decision_query import DecisionQuery

# 所有过滤条件用参数空值短路，不做字符串拼接。
# 时间列名由白名单映射成表达式（Cypher 无法参数化属性名）：
# - `decided_at` 缺值时回落 `updated_at`，与读侧派生口径一致
_TIME_EXPR = {
    "created_at": "n.created_at",
    "updated_at": "n.updated_at",
    "decided_at": "coalesce(n.decided_at, n.updated_at)",
}

_WHERE_TEMPLATE = """
($statuses = [] OR n.status IN $statuses)
  AND ($outcomes = [] OR n.outcome IN $outcomes)
  AND ($entry_source IS NULL OR n.entry_source = $entry_source)
  AND ($decision_type IS NULL OR n.decision_type = $decision_type)
  AND ($agent_id IS NULL OR n.agent_id = $agent_id)
  AND ($min_conf IS NULL OR n.confidence >= $min_conf)
  AND ($max_conf IS NULL OR n.confidence <= $max_conf)
  AND ($exclude_assumed = false OR coalesce(n.status_assumed, false) = false)
  AND ($q IS NULL OR n.context_summary CONTAINS $q OR n.recommended_option CONTAINS $q)
  AND ($from IS NULL OR {time} >= $from)
  AND ($to IS NULL OR {time} <= $to)
""".strip()


def where_clause(time_field: str = "created_at") -> str:
    """过滤片段（计时基准白名单内取值，未知值直接拒绝而不是退回默认）。"""
    expr = _TIME_EXPR.get(time_field)
    if expr is None:
        raise ValueError(f"不支持的计时基准: {time_field}")
    return _WHERE_TEMPLATE.format(time=expr)


# 排序白名单：键为 (sort_by, order)；evidence_count 在图上是派生数值属性
_ORDER_CLAUSES = {
    ("created_at", "desc"): "n.created_at DESC",
    ("created_at", "asc"): "n.created_at ASC",
    ("updated_at", "desc"): "n.updated_at DESC",
    ("updated_at", "asc"): "n.updated_at ASC",
    ("confidence", "desc"): "coalesce(n.confidence, 0) DESC",
    ("confidence", "asc"): "coalesce(n.confidence, 0) ASC",
    ("evidence_count", "desc"): "coalesce(n.evidence_count, 0) DESC",
    ("evidence_count", "asc"): "coalesce(n.evidence_count, 0) ASC",
}


def build_params(query: DecisionQuery) -> Dict[str, Any]:
    """把查询对象拍平成 Cypher 参数（None / 空列表即"不过滤"）。"""
    query.validate()
    return {
        "ws": query.workspace_id,
        "statuses": list(query.statuses),
        "outcomes": list(query.outcomes),
        "entry_source": query.entry_source,
        "decision_type": query.decision_type,
        "agent_id": query.agent_id,
        "min_conf": query.min_confidence,
        "max_conf": query.max_confidence,
        "q": query.text_query,
        "from": query.created_from,
        "to": query.created_to,
        "exclude_assumed": bool(query.exclude_assumed),
    }


def order_clause(sort_by: str, order: str) -> str:
    """排序片段（白名单内取值，未知值直接拒绝而不是退回默认）。"""
    clause = _ORDER_CLAUSES.get((sort_by, order))
    if clause is None:
        raise ValueError(f"不支持的排序: sort_by={sort_by}, order={order}")
    return clause
