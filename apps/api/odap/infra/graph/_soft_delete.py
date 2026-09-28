"""图谱软删除共享工具（模块内私有单一真源）。

约定：节点与边统一用 invalid_at（ISO-8601 UTC 字符串）标记失效时刻。
缺失或空 = 活跃；非空 = 已软删。

注意区分：graphiti 原生的 valid_at/invalid_at/expired_at 在 EntityEdge 上，
本模块的 invalid_at 是应用层对 EntityNode 与关系边的自定约定，同名不同物。
"""
from datetime import datetime, timezone

# 用于 Cypher WHERE 组合的活跃谓词（读路径逐点引用，语义只改此处）
ACTIVE_NODE_PREDICATE = "n.invalid_at IS NULL"
ACTIVE_REL_PREDICATE = "r.invalid_at IS NULL"


def is_active(props: dict | None) -> bool:
    """节点/边属性 dict 是否未被软删（invalid_at 缺失或空）。"""
    return not (props or {}).get("invalid_at")


def now_iso() -> str:
    """统一失效时间戳：ISO-8601 UTC 字符串（含 +00:00）。"""
    # WHY 必须用本函数产出：invalid_at/valid_time 仅允许等长同格式 ISO-8601 UTC 串——时态 as-of 依赖字符串序比较（valid_time <= vt < invalid_at），若混入 Z 后缀或 +08:00 偏移会错序。
    return datetime.now(timezone.utc).isoformat()
