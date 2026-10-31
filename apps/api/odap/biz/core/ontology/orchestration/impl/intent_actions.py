"""动作意图的组合式召回（动词 + 对象，允许被修饰语隔开）。

词典只能登记连写的动作（`删除订单` / `导出报表`），但用户真实说法是
「删除一批测试订单」「把滞销商品清单导出来」——动词与对象被数量词、修饰语隔开。
本模块用「动作动词表 + 对象术语窗口」把这类说法还原成 `action_request` 槽位：

    <动词> …(≤8 字)… <对象术语>     删除 一批测试 订单
    <对象术语> …(≤8 字)… <动词>     滞销商品清单 导出 来

只在对象是**已登记/已召回术语**时才成立（不做开放式动词猜测）；
动词表是业务动作白名单，域外动词（投递/申请/寄出/修）不在表内，因此不会把
「把简历投递出去」判成写操作。
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from odap.biz.core.ontology.orchestration.impl.intent_terms import TermSpan

#: 业务动作动词白名单（按语义：写入/导出/审批类）
ACTION_VERBS: Tuple[str, ...] = (
    "删除", "删掉", "清除", "移除", "导出", "下载", "冻结", "解冻", "调整",
    "修改", "更新", "新增", "创建", "下发", "生成", "停用", "启用", "合并",
    "拆分", "导入", "归档", "驳回", "发布", "合并",
)

#: 动词与对象之间允许的最大间隔（覆盖「一批测试」「这家」「上个月的」等修饰）
MAX_GAP = 8

#: 可被动作施加的对象意图类别（指标不是动作对象）
_OBJECT_INTENTS = {"concept_lookup", "property_lookup", "relation_lookup"}


def find_action_spans(text: str, term_spans: Sequence[TermSpan]) -> List[TermSpan]:
    """把「动词 + 对象」组合成 action_request 槽位；对象必须是已召回术语。"""
    source = text or ""
    objects = [s for s in term_spans if s.intent in _OBJECT_INTENTS]
    if not objects:
        return []
    out: List[TermSpan] = []
    for verb in ACTION_VERBS:
        cursor = source.find(verb)
        while cursor >= 0:
            verb_start, verb_end = cursor, cursor + len(verb)
            cursor = source.find(verb, verb_end)
            match = _nearest_object(objects, verb_start, verb_end)
            if match is None:
                continue
            start = min(verb_start, match.start)
            end = max(verb_end, match.end)
            out.append(TermSpan(
                surface=source[start:end], start=start, end=end,
                intent="action_request", score=0.90, source="compose",
                canonical=verb,
            ))
    return _dedupe(out)


def _nearest_object(objects: Sequence[TermSpan], verb_start: int,
                    verb_end: int):
    candidates = [
        obj for obj in objects
        if (obj.start >= verb_end and obj.start - verb_end <= MAX_GAP)
        or (obj.end <= verb_start and verb_start - obj.end <= MAX_GAP)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda o: abs(o.start - verb_end))


def _dedupe(spans: Sequence[TermSpan]) -> List[TermSpan]:
    """同一段文字被多个动词命中时只保留一条（最长优先）。"""
    ordered = sorted(spans, key=lambda s: (-s.length, s.start))
    picked: List[TermSpan] = []
    for span in ordered:
        if any(span.start < p.end and p.start < span.end for p in picked):
            continue
        picked.append(span)
    picked.sort(key=lambda s: s.start)
    return picked


__all__ = ["ACTION_VERBS", "find_action_spans"]
