"""复合问句切分与主意图判定。

中文多意图问句的稳定结构是「主句 + 连接词 + 附加诉求」：
    上季度退货率是多少，然后删除订单
    └── 主句（指标）              └── 附加（动作）

切分规则只认**显式连接词与句读**（然后/并且/同时/顺便/还要看/再确认/以及/另外 + ，；）,
不做语义猜测。主意图取「证据最强的子句」，强度相同取最早子句 —— 主句在前是中文常态。
这样「帮我删除订单，然后看一下退货率」的主意图仍是动作，「退货率是多少，然后删除订单」
的主意图仍是指标，而不是「只要出现动作词就判动作」（上一版的问题）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

#: 连接词（长的在前，避免「并且对比」被「并且」截断）
CONNECTIVES: Tuple[str, ...] = (
    "并且对比", "同时关注", "还要看", "再确认", "并且", "同时", "然后", "顺便",
    "以及", "另外", "之后", "接着", "顺便看",
)

#: 句读分隔符
PUNCTUATION = "，,；;。！？!?：:\n"


@dataclass(frozen=True)
class Clause:
    """子句（保留原文偏移，便于把槽位归属回去）。"""

    text: str
    start: int
    end: int
    connective: str = ""

    @property
    def stripped(self) -> str:
        return self.text.strip()


def _split_points(text: str) -> List[Tuple[int, int, str]]:
    """返回切分点 (start, end, connective)：分隔符自身被切掉。"""
    points: List[Tuple[int, int, str]] = []
    for index, char in enumerate(text):
        if char in PUNCTUATION:
            points.append((index, index + 1, char))
    for connective in CONNECTIVES:
        start = text.find(connective)
        while start >= 0:
            points.append((start, start + len(connective), connective))
            start = text.find(connective, start + len(connective))
    return sorted(points, key=lambda p: (p[0], -p[1]))


def split_clauses(text: str) -> List[Clause]:
    """按连接词/句读切分子句；无分隔时返回单子句。"""
    source = text or ""
    points = _split_points(source)
    clauses: List[Clause] = []
    cursor = 0
    pending = ""
    for start, end, mark in points:
        if start < cursor:
            continue  # 与上一处分隔符重叠
        segment = source[cursor:start]
        if segment.strip():
            clauses.append(Clause(text=segment, start=cursor, end=start, connective=pending))
        pending = mark if mark in CONNECTIVES else ""
        cursor = end
    tail = source[cursor:]
    if tail.strip():
        clauses.append(Clause(text=tail, start=cursor, end=len(source), connective=pending))
    if not clauses:
        return [Clause(text=source, start=0, end=len(source))]
    return clauses


def strongest_clause(clauses: Sequence[Clause],
                     scores: Sequence[float]) -> int:
    """返回主意图子句下标：证据分最高者，同分取最早。"""
    if not clauses:
        return -1
    best_index = 0
    best_score = float("-inf")
    for index, _clause in enumerate(clauses):
        score = float(scores[index]) if index < len(scores) else 0.0
        if score > best_score + 1e-9:
            best_score = score
            best_index = index
    return best_index


__all__ = ["CONNECTIVES", "Clause", "split_clauses", "strongest_clause"]
