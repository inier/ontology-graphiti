"""溯源模型 + 聚合器 + 机械校验（F8，ARCHITECTURE-v2 §2.3 / AC-36~AC-39）。

四条机械规则（校验脚本 `scripts/verify_provenance.py` 与运行时共用同一实现）：
    R1 trace_id 全局唯一且形如 `urn:odap:trace:<ulid>`（唯一性由 qa_traces 主键保证）
    R2 steps 必须覆盖 intent/map/guard/retrieve/compose/gate 六步，且不得重复
    R3 每个 evidence.ref 必须可被 EvidenceResolver 解析
    R4 tbox_version 必须与本次 TBox 快照哈希一致（版本锚定）

兼容口径：openapi-v2 把第 6 步写作 `contract`，SPEC/DB 写作 `gate`。
本模块以 `gate` 为规范值，校验时把 `contract` 归一化为 `gate`（不视为缺步）。
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Protocol, Tuple

from pydantic import BaseModel, ConfigDict, Field

from odap.biz.core.ontology.orchestration.contracts import (
    STEP_ORDER,
    Evidence,
    Step,
    StepProv,
)

_TRACE_ID = re.compile(r"^urn:odap:trace:[0-9A-HJKMNP-TV-Z]{26}$")
_STEP_ALIASES = {"contract": Step.GATE.value}


class ProvenanceStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step: str
    component: str
    version: str = "v2.0"
    evidence: List[Evidence] = Field(default_factory=list)
    ts: str


class Provenance(BaseModel):
    """溯源证据链（openapi-v2 `Provenance`）。"""

    model_config = ConfigDict(extra="ignore")

    trace_id: str
    steps: List[ProvenanceStep] = Field(default_factory=list)
    citations: List[Evidence] = Field(default_factory=list)
    tbox_version: str = ""
    contract_ok: bool = True


class ProvenanceViolation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rule: str
    detail: str
    step: Optional[str] = None


class EvidenceResolver(Protocol):
    """证据解析器：判断一条 evidence 在其归属系统里是否真实存在/可复算。"""

    def resolve(self, kind: str, ref: str) -> Tuple[bool, str]: ...


def normalize_step(step: str) -> str:
    value = (step or "").strip().lower()
    return _STEP_ALIASES.get(value, value)


class ProvenanceBuilder:
    """按管线执行顺序累积 steps。"""

    def __init__(self, trace_id: str, ts_factory=None) -> None:
        self.trace_id = trace_id
        self._steps: List[ProvenanceStep] = []
        self._ts_factory = ts_factory

    @property
    def steps(self) -> List[ProvenanceStep]:
        return list(self._steps)

    def add(self, step: str, prov: StepProv) -> ProvenanceStep:
        normalized = normalize_step(step)
        if normalized not in STEP_ORDER:
            raise ValueError(f"未知步骤：{step!r}（合法：{STEP_ORDER}）")
        ts = self._ts_factory() if self._ts_factory else _now()
        record = ProvenanceStep(
            step=normalized,
            component=prov.component,
            version=prov.version,
            evidence=list(prov.evidence),
            ts=ts,
        )
        # 同步替换同名步骤（重试场景保留最后一次）
        self._steps = [s for s in self._steps if s.step != normalized]
        self._steps.append(record)
        self._steps.sort(key=lambda s: STEP_ORDER.index(s.step))
        return record

    def build(
        self,
        *,
        tbox_version: str,
        contract_ok: bool,
        citations: Optional[Iterable[Evidence]] = None,
    ) -> Provenance:
        return Provenance(
            trace_id=self.trace_id,
            steps=list(self._steps),
            citations=list(citations or []),
            tbox_version=tbox_version,
            contract_ok=contract_ok,
        )


def validate_provenance(
    prov: Provenance,
    resolver: Optional[EvidenceResolver] = None,
    expected_tbox_version: Optional[str] = None,
) -> List[ProvenanceViolation]:
    """按 R1~R4 机械校验，返回违规清单（空 = 通过）。"""
    violations: List[ProvenanceViolation] = []

    # R1 trace_id
    if not prov.trace_id:
        violations.append(ProvenanceViolation(rule="R1", detail="trace_id 为空"))
    elif not _TRACE_ID.match(prov.trace_id):
        violations.append(
            ProvenanceViolation(
                rule="R1", detail=f"trace_id 格式非法（应为 urn:odap:trace:<ULID>）：{prov.trace_id}"
            )
        )

    # R2 六步齐全且不重复
    present: List[str] = []
    for step in prov.steps:
        normalized = normalize_step(step.step)
        if normalized in present:
            violations.append(
                ProvenanceViolation(rule="R2", step=normalized, detail="步骤重复出现")
            )
        present.append(normalized)
    for required in STEP_ORDER:
        if required not in present:
            violations.append(
                ProvenanceViolation(rule="R2", step=required, detail=f"缺少步骤：{required}")
            )
    for unknown in [s for s in present if s not in STEP_ORDER]:
        violations.append(
            ProvenanceViolation(rule="R2", step=unknown, detail=f"步骤不在六步枚举内：{unknown}")
        )

    # R3 证据可解析
    if resolver is not None:
        for step in prov.steps:
            for evidence in step.evidence:
                if not (evidence.ref or "").strip():
                    violations.append(
                        ProvenanceViolation(
                            rule="R3", step=normalize_step(step.step),
                            detail=f"证据 ref 为空（kind={evidence.kind}）",
                        )
                    )
                    continue
                ok, reason = resolver.resolve(evidence.kind, evidence.ref)
                if not ok:
                    violations.append(
                        ProvenanceViolation(
                            rule="R3", step=normalize_step(step.step),
                            detail=f"证据无法解析：kind={evidence.kind} ref={evidence.ref} 原因={reason}",
                        )
                    )

    # R4 版本锚定
    if expected_tbox_version is not None:
        if not prov.tbox_version:
            violations.append(ProvenanceViolation(rule="R4", detail="tbox_version 为空，未做版本锚定"))
        elif prov.tbox_version != expected_tbox_version:
            violations.append(
                ProvenanceViolation(
                    rule="R4",
                    detail=(
                        "tbox_version 与当前 TBox 快照不一致："
                        f"溯源={prov.tbox_version} 当前={expected_tbox_version}"
                    ),
                )
            )
    return violations


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "Provenance",
    "ProvenanceStep",
    "ProvenanceViolation",
    "ProvenanceBuilder",
    "EvidenceResolver",
    "validate_provenance",
    "normalize_step",
]
