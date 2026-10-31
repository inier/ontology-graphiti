"""意图识别四级漏斗（ADR-095）：L1 词典 → L2 语义召回 → L3 受限 LLM → 澄清。

分层职责（每层都可单独关闭，评测用 `--layer` 度量增量）：

    L1  词典精确匹配（USL canonical / synonyms / near_synonyms / aliases）
    L2  语义召回：① 构词形态（未见过的领域名词按后缀判意图）
                 ② 动词+对象组合（「删掉这批订单」这类动作请求）
                 ③ 字符二元组模糊匹配（错别字/简写兜底）
                 ④ 可选向量召回（外部 embedder 注入时启用，见 `intent_embedding.py`）
    L3  受限 LLM 消歧：只在 L2 置信不足且候选≥2 时触发，候选封闭、不可用即澄清
    澄清 无候选或 L3 判不了 → 返回 clarify_question，绝不猜测作答

本模块只做**漏斗编排**；排序/置信度在 `intent_ranking.py`，
帧组装在 `intent_frame.py`，词典加载在 `intent_dictionary.py`。

槽位与主意图：
- 复合问句按连接词/句读切子句，**主意图取证据最强的子句**（同层取最早），
  动作词不再无脑抢占主意图；
- `slots["terms"]` 只放「承载意图的术语」（主意图类别 + 动作类），
  其余命中进 `slots["entities"]`，避免槽位袋污染。

溯源：`prov.evidence` 记 `dict_hit`（词典命中）与 `intent_cue`（形态命中），
`slots["routing"]` 记每层是否命中、候选集、最终选择理由 —— 回答"为什么是这个意图"。
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from odap.biz.core.ontology.orchestration.contracts import (
    Evidence,
    IntentFrame,
    StepProv,
)
from odap.biz.core.ontology.orchestration.impl.intent_actions import find_action_spans
from odap.biz.core.ontology.orchestration.impl.intent_clauses import (
    Clause,
    split_clauses,
    strongest_clause,
)
from odap.biz.core.ontology.orchestration.impl.intent_cues import extract_cue_spans
from odap.biz.core.ontology.orchestration.impl.intent_dictionary import UslDictionary
from odap.biz.core.ontology.orchestration.impl.intent_frame import (
    build_clarify_frame,
    build_routed_frame,
)
from odap.biz.core.ontology.orchestration.impl.intent_llm import (
    INTENT_LLM_UNAVAILABLE,
    LLMUnavailable,
    RestrictedLLMDisambiguator,
    build_default_disambiguator,
)
from odap.biz.core.ontology.orchestration.impl.intent_ranking import (
    L3_CONFIDENCE_FLOOR,
    anchor_key,
    clause_tier,
    confidence_for,
    dedupe_candidates,
)
from odap.biz.core.ontology.orchestration.impl.intent_terms import (
    TermIndex,
    TermSpan,
    classify_intent,
    merge_spans,
)

logger = logging.getLogger(__name__)

_CLARIFY_TEMPLATE = (
    "无法从术语表与业务词形态确定意图（query=「{query}」）。请补充：要分析的业务对象、"
    "指标口径与时间范围，例如「{example}」。"
)
_CLARIFY_EXAMPLE = "上个季度退货率最高的三个品类"


class L1IntentRouter:
    """意图识别器（类名保留兼容；实际跑 L1→L2→L3 漏斗）。"""

    name = "IntentRouter"
    version = "v3.0-L1L2L3"

    def __init__(self, dictionary: Optional[UslDictionary] = None,
                 confidence: float = 0.95, llm: Optional[RestrictedLLMDisambiguator] = None,
                 layers: str = "full", embedder=None) -> None:
        self.dictionary = dictionary or UslDictionary()
        self.base_confidence = confidence
        self.layers = layers  # full | l2 | l1（评测分层度量用）
        self._index: Optional[TermIndex] = None
        self._llm = llm
        self._llm_resolved = llm is not None
        self._embedder = embedder

    # ── 对外 ──────────────────────────────────────────────────────────────
    async def route(self, query: str, user_ctx: Dict[str, Any],
                    workspace_id: str) -> IntentFrame:
        text = (query or "").strip()
        prov = StepProv(component=self.name, version=self.version)
        if not text:
            return self._clarify("请输入要分析的问题（当前 query 为空）。", prov, text)

        self.dictionary.load()
        if self.dictionary.load_error:
            prov.evidence.append(
                Evidence(kind="decision", ref="decision:clarify_dictionary_unavailable")
            )
            return self._clarify(
                "USL 术语表不可用，无法确定意图（不猜测作答）。"
                f"原因：{self.dictionary.load_error}",
                prov, text, slots={"dictionary_error": self.dictionary.load_error},
            )

        spans = self._recall(text)
        if not spans:
            prov.evidence.append(
                Evidence(kind="decision", ref="decision:clarify_no_dictionary_hit")
            )
            return self._clarify(
                _CLARIFY_TEMPLATE.format(query=text[:60], example=_CLARIFY_EXAMPLE),
                prov, text, routing={"l1": {"hit": False}, "l2": {"hit": False}},
            )

        clauses = split_clauses(text)
        assignment = self._assign(spans, clauses)
        primary_index = strongest_clause(clauses, assignment["strengths"])
        primary_intent = assignment["intents"][primary_index]
        confidence = assignment["confidences"][primary_index]
        routing = _routing(spans, clauses, primary_index, text, self._embedder)

        decision = await self._maybe_l3(text, spans, confidence, routing, prov)
        if decision is not None:
            if decision.intent_type == "unknown":
                return decision
            primary_intent = decision.intent_type
            confidence = decision.confidence

        return build_routed_frame(
            text=text, spans=spans, clauses=clauses, assignment=assignment,
            primary_index=primary_index, primary_intent=primary_intent,
            confidence=confidence, routing=routing, prov=prov,
            l3_used=decision is not None,
        )

    # ── 召回 ──────────────────────────────────────────────────────────────
    def _recall(self, text: str) -> List[TermSpan]:
        index = self._index_or_build()
        dict_spans = index.find_dict_spans(text)
        if self.layers == "l1":
            return merge_spans(dict_spans)
        cue_spans = [
            TermSpan(surface=c.surface, start=c.start, end=c.end, intent=c.intent,
                     score=c.score, source="cue", canonical=c.surface)
            for c in extract_cue_spans(text)
        ]
        action_spans = find_action_spans(text, list(dict_spans) + list(cue_spans))
        vector_spans = self._vector_spans(text, dict_spans, cue_spans)
        fuzzy_spans = [] if dict_spans else index.find_fuzzy_spans(text, blocked=[])
        if self.layers == "l2":
            return merge_spans(dict_spans, cue_spans, action_spans, vector_spans)
        return merge_spans(dict_spans, cue_spans, action_spans, vector_spans, fuzzy_spans)

    def _vector_spans(self, text: str, dict_spans: List[TermSpan],
                      cue_spans: List[TermSpan]) -> List[TermSpan]:
        """向量召回只在词典与形态都没命中时补位（不与既有证据抢优先级）。"""
        if self._embedder is None or self.layers != "full":
            return []
        if dict_spans or cue_spans:
            return []
        return self._embedder.find_vector_spans(text, blocked=[])

    def _index_or_build(self) -> TermIndex:
        if self._index is None:
            self._index = TermIndex(self.dictionary.load())
        return self._index

    # ── 子句归属 ──────────────────────────────────────────────────────────
    @staticmethod
    def _assign(spans: List[TermSpan], clauses: List[Clause]) -> Dict[str, Any]:
        """把片段分派到子句，并按 `anchor_key` 选该子句的主锚点。

        锚点不只取分数最高：`华东区平均订单金额` 里 `订单`(精确,1.0) 是子串，
        真正的头名词是 `平均订单金额`(别名,0.93)，所以先比意图类别再比长度。
        """
        intents: List[str] = []
        strengths: List[float] = []
        confidences: List[float] = []
        members: List[List[TermSpan]] = []
        for clause in clauses:
            inside = [s for s in spans if clause.start <= s.start < clause.end]
            members.append(inside)
            if not inside:
                intents.append("unknown")
                strengths.append(0.0)
                confidences.append(0.0)
                continue
            anchor = max(inside, key=anchor_key)
            intents.append(anchor.intent)
            strengths.append(clause_tier(anchor))
            confidences.append(confidence_for(anchor.score))
        return {"intents": intents, "strengths": strengths,
                "confidences": confidences, "members": members}

    # ── L3 ────────────────────────────────────────────────────────────────
    async def _maybe_l3(self, text: str, spans: List[TermSpan], confidence: float,
                        routing: Dict[str, Any],
                        prov: StepProv) -> Optional[IntentFrame]:
        """置信不足且候选≥2 时请受限 LLM 在**封闭候选集**内选一个；不可用则澄清。"""
        if confidence >= L3_CONFIDENCE_FLOOR:
            return None
        candidates = dedupe_candidates(spans)
        if len(candidates) < 2:
            return None
        try:
            choice = self._get_llm().disambiguate(text, candidates)
        except LLMUnavailable as exc:
            routing["l3"] = {"used": False, "error_code": INTENT_LLM_UNAVAILABLE,
                             "reason": exc.reason}
            prov.evidence.append(
                Evidence(kind="decision", ref="decision:intent_l3_unavailable")
            )
            return self._clarify(
                "意图置信不足且消歧服务不可用，请补充业务对象与指标口径"
                f"（query=「{text[:40]}」，原因：{exc.reason}）。",
                prov, text, slots={"intent_error_code": INTENT_LLM_UNAVAILABLE,
                                   "routing": routing},
            )
        routing["l3"] = {"used": True, "choice_index": choice.choice_index,
                         "reason": choice.reason, "elapsed_ms": choice.elapsed_ms,
                         "model": choice.model, "endpoint": choice.endpoint}
        if choice.choice_index < 0:
            return self._clarify(
                f"意图无法判定（模型理由：{choice.reason}）。请补充业务对象与指标口径。",
                prov, text, slots={"routing": routing},
            )
        prov.evidence.append(Evidence(kind="decision", ref="decision:intent_l3_used"))
        picked = candidates[choice.choice_index]
        return IntentFrame(
            intent_type=picked.intent, primary_intent=picked.intent,
            confidence=max(choice.confidence, L3_CONFIDENCE_FLOOR),
            level="L3", slots={"terms": [picked.surface], "routing": routing},
            prov=prov,
        )

    def _get_llm(self) -> RestrictedLLMDisambiguator:
        if not self._llm_resolved:
            self._llm = build_default_disambiguator()
            self._llm_resolved = True
        return self._llm or RestrictedLLMDisambiguator(client=None)

    # ── 澄清 ──────────────────────────────────────────────────────────────
    def _clarify(self, question: str, prov: StepProv, text: str, level: str = "L0",
                 slots: Optional[Dict[str, Any]] = None,
                 routing: Optional[Dict[str, Any]] = None) -> IntentFrame:
        return build_clarify_frame(question, prov, level=level, slots=slots, routing=routing)


def _routing(spans: List[TermSpan], clauses: List[Clause], primary_index: int,
             text: str, embedder) -> Dict[str, Any]:
    """记录每层是否命中 + 候选集 + 选择理由（回答「为什么是这个意图」）。"""
    return {
        "l1": {"hit": any(s.source == "dict" for s in spans),
               "terms": [s.canonical for s in spans if s.source == "dict"]},
        "l2": {"hit": any(s.source in {"cue", "fuzzy", "compose", "vector"} for s in spans),
               "cues": [s.surface for s in spans if s.source == "cue"],
               "actions": [s.surface for s in spans if s.source == "compose"],
               "vector": [s.surface for s in spans if s.source == "vector"],
               "vector_degraded": getattr(embedder, "degraded_reason", None),
               "fuzzy": [s.surface for s in spans if s.source == "fuzzy"]},
        "candidates": [{"surface": s.surface, "intent": s.intent, "score": s.score,
                        "source": s.source} for s in spans],
        "primary_clause": clauses[primary_index].stripped if primary_index >= 0 else text,
        "reason": "主意图取证据最强的子句（同层取最早），动作类术语不抢占主意图",
    }


#: 兼容旧名（历史上只有 L1 实现）
IntentRouter = L1IntentRouter

__all__ = ["IntentRouter", "L1IntentRouter", "UslDictionary", "classify_intent"]
