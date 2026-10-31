"""IntentFrame 组装：子意图、槽位分袋、溯源证据。

纯组装，不含召回与判定逻辑 —— 因此可以脱离词典/模型直接单测
「给定这批片段，产出的 frame 长什么样」。
"""

from __future__ import annotations

from typing import Any, Dict, List

from odap.biz.core.ontology.orchestration.contracts import (
    Evidence,
    IntentFrame,
    StepProv,
    SubIntent,
)
from odap.biz.core.ontology.orchestration.impl.intent_clauses import Clause
from odap.biz.core.ontology.orchestration.impl.intent_ranking import L3_CONFIDENCE_FLOOR
from odap.biz.core.ontology.orchestration.impl.intent_terms import TermSpan

ACTION_INTENT = "action_request"


def build_clarify_frame(question: str, prov: StepProv, level: str = "L0",
                        slots: Dict[str, Any] | None = None,
                        routing: Dict[str, Any] | None = None) -> IntentFrame:
    """澄清帧：`intent_type=unknown` + 反问句，绝不带猜测出来的意图。"""
    payload = dict(slots or {})
    if routing is not None:
        payload.setdefault("routing", routing)
    return IntentFrame(
        intent_type="unknown", primary_intent="unknown", confidence=0.0,
        level=level, slots=payload, clarify_question=question, prov=prov,
    )


def build_routed_frame(*, text: str, spans: List[TermSpan], clauses: List[Clause],
                       assignment: Dict[str, Any], primary_index: int,
                       primary_intent: str, confidence: float,
                       routing: Dict[str, Any], prov: StepProv,
                       l3_used: bool = False) -> IntentFrame:
    """命中的意图帧：主意图 + 子意图 + 槽位分袋 + 溯源证据。"""
    routing["chosen"] = {
        "intent": primary_intent,
        "confidence": confidence,
        "source": _chosen_source(confidence, l3_used),
    }
    carriers = [s for s in spans
                if s.intent == primary_intent or s.intent == ACTION_INTENT]
    others = [s for s in spans if s not in carriers]
    prov.evidence.extend(
        Evidence(kind="dict_hit", ref=f"USL:term:{s.canonical}")
        for s in spans if s.source == "dict"
    )
    prov.evidence.extend(
        Evidence(kind="intent_cue", ref=f"cue:{s.intent}:{s.surface}")
        for s in spans if s.source == "cue"
    )
    return IntentFrame(
        intent_type=primary_intent,
        primary_intent=primary_intent,
        sub_intents=_sub_intents(clauses, assignment, primary_index),
        slots={
            "terms": [s.surface for s in carriers],
            "entities": [s.surface for s in others],
            "query": text,
            "routing": routing,
        },
        confidence=confidence,
        level="L1" if all(s.source == "dict" for s in spans) else "L2",
        prov=prov,
    )


def _chosen_source(confidence: float, l3_used: bool) -> str:
    if l3_used:
        return "l3"
    return "primary_clause" if confidence >= L3_CONFIDENCE_FLOOR else "l2"


def _sub_intents(clauses: List[Clause], assignment: Dict[str, Any],
                 primary_index: int) -> List[SubIntent]:
    """复合问句里的次意图：非主句且意图不等于 unknown。"""
    return [
        SubIntent(intent_type=intent,
                  terms=[s.surface for s in assignment["members"][i]],
                  text=clauses[i].stripped,
                  confidence=assignment["confidences"][i])
        for i, intent in enumerate(assignment["intents"])
        if i != primary_index and intent != "unknown"
    ]


__all__ = ["ACTION_INTENT", "build_clarify_frame", "build_routed_frame"]
