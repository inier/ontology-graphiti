"""术语索引：把 USL 词典变成可召回、可打分的槽位（L1 精确 + L2 模糊）。

职责边界：
- **不管意图编排**（那是 `intent_router.py`），只回答「query 里哪些片段是术语、各是什么
  意图、置信多少、证据来源是什么」；
- 术语意图由 `classify_intent()` 决定：语义类型优先（动作/过程/规则/属性/关系），
  对象类型再按**构词形态**判断是不是指标（`客单价`/`库存量` 这类不含「率」但确属指标的
  词，仅靠语义类型会被误判成概念查询）；
- 模糊召回用字符二元组 Jaccard（不引第三方依赖），阈值取高，只用于错别字/简写兜底。

同一 query 的槽位冲突按「词典命中 > 形态召回 > 模糊召回、长片段优先」裁决，
保证同一输入输出确定（无随机、无网络）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from odap.biz.core.ontology.orchestration.impl.intent_cues import METRIC_CUES

_INTENT_BY_SEMANTIC_TYPE: Dict[str, str] = {
    "动作类型": "action_request",
    "关系类型": "relation_lookup",
    "过程类型": "process_lookup",
    "规则类型": "rule_lookup",
    "属性": "property_lookup",
}

#: 各召回来源的分数（同一术语多渠道命中时取最高）
SCORE_DICT_EXACT = 1.0
SCORE_DICT_ALIAS = 0.93
SCORE_FUZZY_MIN = 0.72
SCORE_FUZZY_MAX = 0.9

FUZZY_JACCARD = 0.8
FUZZY_MIN_CHARS = 4


def looks_metric(text: str) -> bool:
    """构词判断：中文指标名词几乎都落在固定后缀上（率/额/量/价/均值…）。"""
    value = text or ""
    return any(cue in value for cue in METRIC_CUES)


def classify_intent(semantic_type: str, canonical: str) -> str:
    """语义类型优先，对象类型再按构词形态细分指标/概念。"""
    base = _INTENT_BY_SEMANTIC_TYPE.get(semantic_type or "")
    if base:
        return base
    return "metric_query" if looks_metric(canonical) else "concept_lookup"


def char_bigrams(text: str) -> set:
    value = (text or "").strip()
    if len(value) < 2:
        return {value} if value else set()
    return {value[i:i + 2] for i in range(len(value) - 1)}


def jaccard(left: str, right: str) -> float:
    a, b = char_bigrams(left), char_bigrams(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass(frozen=True)
class TermSpan:
    """一个术语槽位（含证据来源，便于写进 provenance）。"""

    surface: str
    start: int
    end: int
    intent: str
    score: float
    source: str  # dict | cue | fuzzy
    canonical: str = ""

    @property
    def length(self) -> int:
        return self.end - self.start


def _priority(span: TermSpan) -> Tuple[int, int, float]:
    """对齐优先级：来源等级 > 片段长度 > 召回分。

    长度必须在分数之前：`平均订单金额`(6) 与 `订单`(2) 同为词典精确命中时，
    长片段才是真正的术语，短片段只是被包含的子串。
    """
    rank = {"dict": 2, "cue": 1, "compose": 1, "vector": 1}.get(span.source, 0)
    return (rank, span.length, span.score)


def _overlaps(left: TermSpan, right: TermSpan) -> bool:
    return left.start < right.end and right.start < left.end


def _resolve_dict_vs_soft(dict_spans: Sequence[TermSpan],
                          soft_spans: Sequence[TermSpan]) -> Tuple[List[TermSpan], List[TermSpan]]:
    """词典命中与软召回（形态/模糊/动词组合）的重叠裁决。

    形态命中（`cue`）：
    1. 形态名词的结尾正好是某个词典术语（`华东区平均订单金额` / 同 span）：词典胜，
       形态规则把地点、时间等修饰语扩进了名词边界；
    2. 词典术语是形态名词的**前缀**（`供应商协同评分` 里的 `供应商`）：形态胜，
       真正的术语是更长的组合词。

    动词组合（`compose`，如 `删除一批测试订单`）：对象本来就在动作短语内部，
    被包含的词典对象让位给动作槽位，否则动作会消失。
    """
    dropped_dict: List[TermSpan] = []
    dropped_soft: List[TermSpan] = []
    for soft in soft_spans:
        overlapping = [d for d in dict_spans if _overlaps(d, soft)]
        if not overlapping:
            continue
        if soft.source == "compose":
            contained = [d for d in overlapping
                         if soft.start <= d.start and d.end <= soft.end]
            if len(contained) == len(overlapping):
                dropped_dict.extend(contained)
            else:
                dropped_soft.append(soft)
            continue
        spurious = any(
            (d.start, d.end) == (soft.start, soft.end)
            or (d.end == soft.end and d.start > soft.start)
            for d in overlapping
        )
        if spurious:
            dropped_soft.append(soft)
            continue
        if any(d.start == soft.start and d.end < soft.end for d in overlapping):
            dropped_dict.extend(overlapping)
    return dropped_dict, dropped_soft


def merge_spans(*groups: Sequence[TermSpan]) -> List[TermSpan]:
    """合并多渠道召回：重叠裁决 + 优先级消解，输出互不重叠的槽位。"""
    candidates: List[TermSpan] = []
    for group in groups:
        candidates.extend(group)
    dict_spans = [s for s in candidates if s.source == "dict"]
    soft_spans = [s for s in candidates if s.source != "dict"]

    dropped_dict, dropped_soft = _resolve_dict_vs_soft(dict_spans, soft_spans)
    kept_dict = [s for s in dict_spans if not any(s is d for d in dropped_dict)]
    kept_soft = [s for s in soft_spans if not any(s is d for d in dropped_soft)]
    # 模糊命中只在没有任何更可靠证据覆盖它时才保留
    survivors = kept_dict + [
        s for s in kept_soft
        if s.source != "fuzzy" or not any(_overlaps(s, k) for k in kept_dict + kept_soft)
    ]

    # 优先级降序贪心：先放词典/长片段/高分，后续与之重叠者丢弃（顺序无关、确定）
    kept: List[TermSpan] = []
    for span in sorted(survivors, key=lambda s: (-_priority(s)[0], -s.length,
                                                 -s.score, s.start)):
        if any(_overlaps(span, other) for other in kept):
            continue
        kept.append(span)
    kept.sort(key=lambda s: s.start)
    return kept


class TermIndex:
    """USL 词典索引（构造一次，多次召回）。"""

    def __init__(self, mapping: Dict[str, Dict[str, Any]]) -> None:
        self._entries: List[Tuple[str, Dict[str, Any], str]] = []
        for expression, entry in mapping.items():
            canonical = str(entry.get("canonical") or expression)
            intent = classify_intent(str(entry.get("semantic_type") or ""), canonical)
            score = SCORE_DICT_EXACT if expression == canonical else SCORE_DICT_ALIAS
            self._entries.append((expression, {**entry, "intent": intent, "score": score},
                                  intent))
        # 长表达式优先，保证「库存周转率」不会被「库存」抢先
        self._entries.sort(key=lambda item: -len(item[0]))

    @property
    def size(self) -> int:
        return len(self._entries)

    def find_dict_spans(self, text: str) -> List[TermSpan]:
        source = text or ""
        spans: List[TermSpan] = []
        for expression, entry, intent in self._entries:
            start = source.find(expression)
            while start >= 0:
                spans.append(TermSpan(
                    surface=expression, start=start, end=start + len(expression),
                    intent=intent, score=float(entry["score"]), source="dict",
                    canonical=str(entry.get("canonical") or expression),
                ))
                start = source.find(expression, start + 1)
        return spans

    def find_fuzzy_spans(self, text: str, blocked: Iterable[TermSpan]) -> List[TermSpan]:
        """错别字/简写兜底：滑窗与词典表达式做二元组相似度比较（阈值高、只兜底）。"""
        source = text or ""
        blocked_ranges = [(s.start, s.end) for s in blocked]
        out: List[TermSpan] = []
        for start in range(len(source)):
            for size in range(FUZZY_MIN_CHARS, min(7, len(source) - start + 1)):
                window = source[start:start + size]
                if any(ch in " ，。！？；：、（）()" for ch in window):
                    continue
                if any(start < end and b_start < start + size for b_start, end in blocked_ranges):
                    continue
                best = self._best_match(window)
                if best is None:
                    continue
                expression, entry, intent, score = best
                out.append(TermSpan(
                    surface=window, start=start, end=start + size, intent=intent,
                    score=score, source="fuzzy", canonical=expression,
                ))
        # 同一区域只保留最高分的一条
        out.sort(key=lambda s: (-s.score, -s.length))
        picked: List[TermSpan] = []
        for span in out:
            if any(span.start < p.end and p.start < span.end for p in picked):
                continue
            picked.append(span)
        return picked

    def _best_match(self, window: str) -> Optional[Tuple[str, Dict[str, Any], str, float]]:
        best: Optional[Tuple[str, Dict[str, Any], str, float]] = None
        for expression, entry, intent in self._entries:
            if abs(len(expression) - len(window)) > 1:
                continue
            similarity = jaccard(window, expression)
            if similarity < FUZZY_JACCARD:
                continue
            score = min(SCORE_FUZZY_MAX, SCORE_FUZZY_MIN + (similarity - FUZZY_JACCARD))
            if best is None or score > best[3]:
                best = (expression, entry, intent, round(score, 3))
        return best


__all__ = [
    "FUZZY_JACCARD",
    "SCORE_DICT_ALIAS",
    "SCORE_DICT_EXACT",
    "TermIndex",
    "TermSpan",
    "char_bigrams",
    "classify_intent",
    "jaccard",
    "looks_metric",
    "merge_spans",
]
