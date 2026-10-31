"""输出契约校验（AC-31）。

约束的可执行定义（ARCHITECTURE-v2 §2.2 输出侧）：
1. 非 no_answer 的回答必须有正文（`EMPTY_ANSWER`）。
2. 每条 citation 必须有 `ref` 且 `kind` 在五类合法枚举内（`INVALID_CITATION`）。
3. 正文出现数字、却没有任何 citation 支撑 → `UNCITED_NUMERIC_CLAIM`（禁止无来源数据）。
4. 低置信意图不得产出确定性答案（`LOW_CONFIDENCE_ANSWER`）。
5. 携带结构化载荷（`DraftAnswer.payload_ttl`）时，须通过已登记 SHACL 形状校验
   （`impl/shacl_gate.py`，ADR-085）：`SHACL_VIOLATION` / `SHACL_SHAPE_MISSING` /
   `SHACL_UNAVAILABLE` 均判违约，不静默放行。

违约不是「假通过」：`contract_ok=False` + `blocked_reasons[]`，答案降级为「部分答案 + 违约说明」。
"""

from __future__ import annotations

import logging
import re
from typing import List

from odap.biz.core.ontology.orchestration.contracts import (
    DraftAnswer,
    Evidence,
    GateResult,
    MappedQuery,
    StepProv,
)

_ALLOWED_KINDS = {"doc", "tbox_node", "metric", "graph_edge", "opa_decision"}
_LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.MULTILINE)
_DIGITS = re.compile(r"\d+(?:\.\d+)?")

logger = logging.getLogger(__name__)


class StrictOutputContractGate:
    """输出契约门（插槽实现）。"""

    name = "OutputContractGate"
    version = "v2.0"

    def __init__(self, shacl_validator=None) -> None:
        # 惰性默认：纯文本回答不构造 SHACL 校验器，也不碰形状库
        self._shacl_validator = shacl_validator

    async def validate(self, draft: DraftAnswer, mapped: MappedQuery) -> GateResult:
        prov = StepProv(component=self.name, version=self.version)
        blocked: List[str] = []

        if draft.no_answer:
            # no_answer 是合法结论，只需声明契约状态
            prov.evidence.append(Evidence(kind="decision", ref="decision:no_answer_accepted"))
            return GateResult(
                content=draft.no_answer_reason or "",
                citations=[],
                contract_ok=True,
                blocked_reasons=[],
                prov=prov,
            )

        if not (draft.content or "").strip():
            blocked.append("EMPTY_ANSWER: 非 no_answer 的回答正文为空")

        for citation in draft.citations:
            if not (citation.ref or "").strip():
                blocked.append("INVALID_CITATION: 存在 ref 为空的引用")
            elif citation.kind not in _ALLOWED_KINDS:
                blocked.append(
                    f"INVALID_CITATION: 非法引用类型 {citation.kind!r}（合法：{sorted(_ALLOWED_KINDS)}）"
                )

        body_without_markers = _LIST_MARKER.sub("", draft.content or "")
        if _DIGITS.search(body_without_markers) and not draft.citations:
            blocked.append(
                "UNCITED_NUMERIC_CLAIM: 回答包含数字但没有任何引用支撑（禁止无来源结论）"
            )

        if mapped.intent.confidence < 0.9 and mapped.intent.intent_type != "unknown":
            blocked.append(
                f"LOW_CONFIDENCE_ANSWER: 意图置信度 {mapped.intent.confidence:.2f} < 0.90"
            )

        if (draft.payload_ttl or "").strip():
            blocked.extend(self._validate_payload(draft))

        contract_ok = not blocked
        prov.evidence.append(
            Evidence(kind="decision",
                     ref="decision:contract_ok" if contract_ok else "decision:contract_violation")
        )
        return GateResult(
            content=draft.content,
            citations=list(draft.citations),
            contract_ok=contract_ok,
            blocked_reasons=blocked,
            prov=prov,
        )

    # ── SHACL 分支（AC-31）────────────────────────────────────────────────
    def _validate_payload(self, draft: DraftAnswer) -> List[str]:
        try:
            validator = self._shacl_validator or self._default_validator()
            return validator.validate(draft.payload_ttl or "", draft.payload_class or "")
        except Exception as exc:  # noqa: BLE001 - 校验器故障不得变成通过
            logger.error("SHACL 校验异常: %s", exc)
            return [f"SHACL_UNAVAILABLE: {type(exc).__name__}: {exc}"]

    def _default_validator(self):
        from odap.biz.core.ontology.orchestration.impl.shacl_gate import (
            ShaclPayloadValidator,
        )

        self._shacl_validator = ShaclPayloadValidator()
        return self._shacl_validator


__all__ = ["StrictOutputContractGate"]
