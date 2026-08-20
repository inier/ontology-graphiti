"""Allen 13 区间关系时态推理（纯 Python 零依赖）。

实现在时间区间上判定/推导 Allen 区间代数 13 种基本关系，
供确定性推理引擎的时态规则（valid_at 场景）使用。

支持关系：
    before(a,b)     a 完全在 b 之前（a.end < b.start）
    meets(a,b)      a 紧接 b（a.end == b.start）
    overlaps(a,b)   a 与 b 交叠（a.start < b.start < a.end < b.end）
    starts(a,b)     a 与 b 同起点且更短
    during(a,b)     a 在 b 内部
    finishes(a,b)   a 与 b 同终点且更短
    equals(a,b)     a == b
及其 6 个逆关系：
    after(a,b) = before(b,a)
    met_by(a,b) = meets(b,a)
    overlapped_by(a,b) = overlaps(b,a)
    started_by(a,b) = starts(b,a)
    contains(a,b) = during(b,a)
    finished_by(a,b) = finishes(b,a)
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

# ── 13 种 Allen 关系 ──

BEFORE = "before"
MEETS = "meets"
OVERLAPS = "overlaps"
STARTS = "starts"
DURING = "during"
FINISHES = "finishes"
EQUALS = "equals"
AFTER = "after"
MET_BY = "met_by"
OVERLAPPED_BY = "overlapped_by"
STARTED_BY = "started_by"
CONTAINS = "contains"
FINISHED_BY = "finished_by"

ALLEN_RELATIONS: Tuple[str, ...] = (
    BEFORE, MEETS, OVERLAPS, STARTS, DURING, FINISHES, EQUALS,
    AFTER, MET_BY, OVERLAPPED_BY, STARTED_BY, CONTAINS, FINISHED_BY,
)

# 逆关系映射
INVERSE: dict = {
    BEFORE: AFTER, AFTER: BEFORE,
    MEETS: MET_BY, MET_BY: MEETS,
    OVERLAPS: OVERLAPPED_BY, OVERLAPPED_BY: OVERLAPS,
    STARTS: STARTED_BY, STARTED_BY: STARTS,
    DURING: CONTAINS, CONTAINS: DURING,
    FINISHES: FINISHED_BY, FINISHED_BY: FINISHES,
    EQUALS: EQUALS,
}


@dataclass(frozen=True)
class Interval:
    """时间区间 [start, end]（数值或 datetime，可比较即可）"""
    start: object
    end: object


def _lt(a: object, b: object) -> bool:
    return operator.lt(a, b)


def _eq(a: object, b: object) -> bool:
    return operator.eq(a, b)


def relation(a: Interval, b: Interval) -> str:
    """判定两个区间间的 Allen 关系（13 种之一）。"""
    a_end_lt_b_start = _lt(a.end, b.start)
    if a_end_lt_b_start:
        return BEFORE

    b_end_lt_a_start = _lt(b.end, a.start)
    if b_end_lt_a_start:
        return AFTER

    # meets / met_by：一端紧贴另一端起点
    if _eq(a.end, b.start) and not _eq(a.start, b.start):
        return MEETS
    if _eq(b.end, a.start) and not _eq(a.end, b.start):
        return MET_BY

    # 端点相等判定
    start_eq = _eq(a.start, b.start)
    end_eq = _eq(a.end, b.end)
    a_end_lt_b_end = _lt(a.end, b.end)
    b_end_lt_a_end = _lt(b.end, a.end)
    a_start_lt_b_start = _lt(a.start, b.start)
    b_start_lt_a_start = _lt(b.start, a.start)

    if start_eq and end_eq:
        return EQUALS
    if start_eq:
        return STARTS if a_end_lt_b_end else STARTED_BY
    if end_eq:
        return FINISHES if b_start_lt_a_start else FINISHED_BY

    # 包含 / 交叠
    if b_start_lt_a_start and a_end_lt_b_end:
        return DURING
    if a_start_lt_b_start and b_end_lt_a_end:
        return CONTAINS
    if a_start_lt_b_start and a_end_lt_b_end:
        return OVERLAPS
    if b_start_lt_a_start and b_end_lt_a_end:
        return OVERLAPPED_BY

    # 理论不可达（保证 13 覆盖完整）
    return OVERLAPS


def inverse(rel: str) -> str:
    """返回给定关系的逆关系"""
    return INVERSE.get(rel, rel)


def compose(rel1: str, rel2: str) -> Optional[str]:
    """组合两个 Allen 关系（路径一致性）。

    返回 rel1 ∘ rel2 可能成立的关系；无法判定时返回 None（开放）。
    """
    # 定义常用组合矩阵（部分：可靠判定项）
    table = {
        (BEFORE, BEFORE): {BEFORE},
        (BEFORE, MEETS): {BEFORE},
        (BEFORE, OVERLAPS): {BEFORE},
        (BEFORE, AFTER): None,
        (MEETS, BEFORE): {BEFORE},
        (MEETS, MEETS): {MEETS},
        (MEETS, OVERLAPS): {OVERLAPS, MEETS},
        (OVERLAPS, BEFORE): {BEFORE},
        (OVERLAPS, MEETS): {OVERLAPS},
        (OVERLAPS, OVERLAPS): {OVERLAPS, DURING, STARTS, CONTAINS, OVERLAPPED_BY},
        (DURING, BEFORE): {BEFORE},
        (DURING, MEETS): {BEFORE, MEETS},
        (DURING, OVERLAPS): {OVERLAPS, STARTS, DURING},
        (STARTS, BEFORE): {BEFORE},
        (STARTS, MEETS): {MEETS},
        (STARTS, OVERLAPS): {OVERLAPS},
        (FINISHES, BEFORE): {BEFORE},
        (FINISHES, MEETS): {BEFORE, MEETS},
        (FINISHES, OVERLAPS): {OVERLAPS, DURING},
        (EQUALS, EQUALS): {EQUALS},
        (EQUALS, BEFORE): {BEFORE},
        (EQUALS, MEETS): {MEETS},
        (EQUALS, OVERLAPS): {OVERLAPS},
        (EQUALS, DURING): {DURING},
        (EQUALS, STARTS): {STARTS},
        (EQUALS, FINISHES): {FINISHES},
        (EQUALS, AFTER): {AFTER},
    }
    result = table.get((rel1, rel2))
    if result is None:
        return None
    if len(result) == 1:
        return next(iter(result))
    return None


def path_consistent(
    chain: List[Tuple[Interval, Interval]], expected: List[str]
) -> bool:
    """路径一致性校验：断言链上每对区间的关系是否满足期望集合。

    Args:
        chain: [(interval_a, interval_b), ...] 区间对
        expected: [set_of_allowed_relations, ...] 每对允许的关系列表

    Returns:
        全部满足返回 True，任一不满足返回 False。
    """
    if len(chain) != len(expected):
        raise ValueError("chain 与 expected 长度不一致")
    for (a, b), allowed in zip(chain, expected):
        rel = relation(a, b)
        if rel not in allowed:
            return False
    return True


def interval_from_props(props: dict, start_key: str = "start", end_key: str = "end") -> Optional[Interval]:
    """从属性字典构造 Interval；缺失端点返回 None"""
    if start_key not in props or end_key not in props:
        return None
    return Interval(props[start_key], props[end_key])


__all__ = [
    "BEFORE", "MEETS", "OVERLAPS", "STARTS", "DURING", "FINISHES", "EQUALS",
    "AFTER", "MET_BY", "OVERLAPPED_BY", "STARTED_BY", "CONTAINS", "FINISHED_BY",
    "ALLEN_RELATIONS", "INVERSE",
    "Interval", "relation", "inverse", "compose", "path_consistent",
    "interval_from_props",
]
