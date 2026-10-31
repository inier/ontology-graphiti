"""答案生成：证据驱动、拒绝编造（AC-30）。

本轮**不接 LLM**（F6 范围明确排除 L3 LLM 消歧与开放式生成）。因此本实现是
「抽取式摘要」：只把检索到的证据按可读结构呈现，不对事实做推断、不产生无来源数字。

规则：
- 证据为空 → `no_answer=True` + 具体原因（AC-30：禁止生成无来源答案）。
- 证据非空 → 逐条列出证据 ref 与（若行内有值）真实字段值，全部可回溯到 `citations`。

TODO(SPEC-v2 F6 / AC-30 的 LLM 合成路径)：接入受限候选集 LLM 生成时，必须复用本类的
`no_answer` 前置判定，且生成文本的数字必须能对上 citations（由 OutputContractGate 复核）。
"""

from __future__ import annotations

from typing import List

from odap.biz.core.ontology.orchestration.contracts import (
    DraftAnswer,
    Evidence,
    RetrievalResult,
    StepProv,
)


class EvidenceOnlyAnswerComposer:
    """抽取式答案生成器（插槽实现）。"""

    name = "AnswerComposer"
    version = "v2.0-extractive"

    async def compose(self, retrieval: RetrievalResult, query: str) -> DraftAnswer:
        prov = StepProv(component=self.name, version=self.version)

        if retrieval.evidence_count == 0 or not retrieval.citations:
            prov.evidence.append(Evidence(kind="decision", ref="decision:no_evidence"))
            engines = ", ".join(retrieval.degraded_engines) or "无"
            return DraftAnswer(
                no_answer=True,
                no_answer_reason=(
                    f"检索未返回任何可引用证据（已尝试引擎降级链，降级引擎：{engines}）。"
                    "按「不编造」原则不生成答案；建议先补齐该问题涉及的本体元素或数据源。"
                ),
                citations=[],
                prov=prov,
            )

        engines = ", ".join(
            str(chain.get("engine") or "") for chain in retrieval.chains if chain.get("engine")
        ) or "无"
        lines: List[str] = [
            f"针对「{query}」检索到 {retrieval.evidence_count} 条可引用证据"
            f"（引擎：{engines}）："
        ]
        for index, evidence in enumerate(retrieval.citations, start=1):
            lines.append(f"{index}. [{evidence.kind}] {evidence.ref}")
            value_line = _value_line(evidence, retrieval)
            if value_line:
                lines.append(f"   取值：{value_line}")

        if retrieval.degraded_engines:
            lines.append(
                f"注意：以下检索引擎在本次执行中不可用，已降级："
                f"{', '.join(retrieval.degraded_engines)}。"
            )
        lines.append("以上结论仅基于所列证据，未做推断性补充。")
        prov.evidence.extend(retrieval.citations)
        return DraftAnswer(
            content="\n".join(lines),
            citations=list(retrieval.citations),
            no_answer=False,
            prov=prov,
        )


def _value_line(evidence: Evidence, retrieval: RetrievalResult) -> str:
    """从检索行里取「真实存在」的值字段（不做换算、不做插值）。"""
    for chain in retrieval.chains:
        for row in chain.get("rows") or []:
            if not isinstance(row, dict):
                continue
            ref = (row.get("source_ref") or row.get("doc_id") or row.get("chunk_id")
                   or row.get("entity_id") or row.get("id"))
            if str(ref) != evidence.ref:
                continue
            for key in ("metric_value", "value", "name", "title", "snippet"):
                if key in row and row[key] not in (None, ""):
                    return f"{key}={row[key]}"
    return ""


__all__ = ["EvidenceOnlyAnswerComposer"]
