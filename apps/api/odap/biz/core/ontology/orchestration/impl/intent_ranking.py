"""召回片段的排序、层级与置信度换算（纯函数，无 IO、无状态）。

拆成独立模块的原因：这三件事决定「哪个片段当主意图」，
是最容易被指标驱动的改动污染的地方，独立成文件才能单独用单测钉住。
"""

from __future__ import annotations

from typing import Dict, List

from odap.biz.core.ontology.orchestration.impl.intent_llm import Candidate
from odap.biz.core.ontology.orchestration.impl.intent_terms import TermSpan

#: L2 置信度低于此值且候选≥2 时才请 L3 复核；也是「结果可信」的对外分界线。
L3_CONFIDENCE_FLOOR = 0.80

#: 子句锚点选择时的意图类别优先级：数据类 > 写操作 > 定义类 > 概念类。
#: 「上个季度退货率最高的三个品类」里 `品类` 只是分组维度，主意图必须是指标，
#: 因此不能简单取「最长」或「最靠右」的片段。
INTENT_RANK: Dict[str, int] = {
    "metric_query": 5,
    "action_request": 4,
    "process_lookup": 3,
    "rule_lookup": 3,
    "property_lookup": 3,
    "relation_lookup": 2,
    "concept_lookup": 1,
}

#: 子句层级权重：词典事实与动词组合同层（都是直接证据），形态推断次之，模糊兜底最弱。
_SOURCE_TIER: Dict[str, float] = {"dict": 1.0, "compose": 1.0, "cue": 0.6, "fuzzy": 0.2}
_DEFAULT_TIER = 0.3


def confidence_for(score: float) -> float:
    """召回分 → 意图置信度（词典 > 别名 > 形态/动词 > 向量/模糊）。"""
    if score >= 1.0:
        return 0.95
    if score >= 0.93:
        return 0.93
    if score >= 0.90:
        return 0.91
    return round(min(0.79, max(0.5, score)), 2)


def anchor_key(span: TermSpan) -> tuple:
    """子句锚点排序键：意图类别 > 片段长度 > 召回分 > 靠右位置。"""
    return (INTENT_RANK.get(span.intent, 0), span.length, span.score, span.end)


def clause_tier(span: TermSpan) -> float:
    """子句主意图的**层级**（不是连续分，避免长短片段互相压制）。

    同层时由 `strongest_clause` 取最早子句 —— 中文主句在前，
    因此「帮我删掉这批订单，然后看下履约率」主意图是动作，
    「上季度退货率是多少，然后删除订单」主意图是指标，
    不再由「动作优先」这种硬编码规则决定。
    """
    return _SOURCE_TIER.get(span.source, _DEFAULT_TIER)


def dedupe_candidates(spans: List[TermSpan]) -> List[Candidate]:
    """按 (intent, surface) 去重保留最高分，按分数降序编号；供 L3 封闭候选集使用。"""
    seen: Dict[tuple, TermSpan] = {}
    for span in spans:
        key = (span.intent, span.surface)
        current = seen.get(key)
        if current is None or span.score > current.score:
            seen[key] = span
    ordered = sorted(seen.values(), key=lambda s: -s.score)
    return [Candidate(index=i, surface=s.surface, intent=s.intent, score=s.score)
            for i, s in enumerate(ordered)]


__all__ = [
    "L3_CONFIDENCE_FLOOR",
    "INTENT_RANK",
    "confidence_for",
    "anchor_key",
    "clause_tier",
    "dedupe_candidates",
]
