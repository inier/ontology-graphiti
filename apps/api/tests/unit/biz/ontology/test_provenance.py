"""溯源模型与机械校验测试（AC-36 / AC-37 / AC-38 / AC-39）。

R1 trace_id 唯一+格式 / R2 六步齐全 / R3 证据可解析 / R4 版本锚定。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.contracts import Evidence, StepProv
from odap.biz.core.ontology.orchestration.provenance import (
    ProvenanceBuilder,
    normalize_step,
    validate_provenance,
)

TRACE = "urn:odap:trace:01J9ZK8P3Q7N2M4R5T6V7W8X9A"
TBOX = "sha256:9f2c1a"


class _Resolver:
    """按白名单判定证据是否可解析（验证 R3 的接线，不验具体域逻辑）。"""

    def __init__(self, valid=None):
        self.valid = valid or {"decision:contract_ok"}
        self.calls = []

    def resolve(self, kind, ref):
        self.calls.append((kind, ref))
        return (True, "") if ref in self.valid else (False, "不存在")


def _builder(trace_id=TRACE):
    builder = ProvenanceBuilder(trace_id)
    for step in ("intent", "map", "guard", "retrieve", "compose", "gate"):
        builder.add(step, StepProv(component=f"Test-{step}",
                                  evidence=[Evidence(kind="decision",
                                                     ref="decision:contract_ok")]))
    return builder


class TestBuilder:
    def test_steps_are_ordered_by_pipeline_sequence(self):
        builder = ProvenanceBuilder(TRACE)
        for step in ("gate", "intent", "retrieve"):
            builder.add(step, StepProv(component="X"))
        assert [s.step for s in builder.steps] == ["intent", "retrieve", "gate"]

    def test_same_step_is_replaced_not_duplicated(self):
        builder = ProvenanceBuilder(TRACE)
        builder.add("intent", StepProv(component="First"))
        builder.add("intent", StepProv(component="Second"))
        assert [s.component for s in builder.steps] == ["Second"]

    def test_unknown_step_raises(self):
        with pytest.raises(ValueError) as excinfo:
            ProvenanceBuilder(TRACE).add("rethink", StepProv(component="X"))
        assert "未知步骤" in str(excinfo.value)

    def test_contract_alias_normalizes_to_gate(self):
        assert normalize_step("contract") == "gate"
        assert normalize_step("  GATE ") == "gate"


class TestRules:
    def test_full_chain_passes(self):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        assert validate_provenance(provenance, resolver=_Resolver(),
                                   expected_tbox_version=TBOX) == []

    def test_r1_rejects_bad_trace_id(self):
        provenance = _builder("trace-2026").build(tbox_version=TBOX, contract_ok=True)
        rules = {v.rule for v in validate_provenance(provenance)}
        assert rules == {"R1"}

    def test_r1_rejects_empty_trace_id(self):
        provenance = _builder("").build(tbox_version=TBOX, contract_ok=True)
        assert any(v.rule == "R1" for v in validate_provenance(provenance))

    def test_r2_detects_missing_step_with_step_name(self):
        builder = _builder()
        provenance = builder.build(tbox_version=TBOX, contract_ok=True)
        trimmed = provenance.model_copy(
            update={"steps": [s for s in provenance.steps if s.step != "retrieve"]}
        )
        violations = validate_provenance(trimmed)
        assert [(v.rule, v.step) for v in violations] == [("R2", "retrieve")]

    def test_r2_detects_duplicate_step(self):
        builder = ProvenanceBuilder(TRACE)
        for step in ("intent", "intent", "map", "guard", "retrieve", "compose", "gate"):
            builder.add(step, StepProv(component="X"))
        # builder 会去重同名步骤，这里直接构造脏数据验证校验器
        provenance = builder.build(tbox_version=TBOX, contract_ok=True)
        duplicated = provenance.model_copy(
            update={"steps": list(provenance.steps) + [provenance.steps[0]]}
        )
        assert any(v.rule == "R2" and "重复" in v.detail
                   for v in validate_provenance(duplicated))

    def test_r2_rejects_unknown_step(self):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        dirty = provenance.model_copy(update={
            "steps": list(provenance.steps) + [
                provenance.steps[0].model_copy(update={"step": "rethink"})
            ]
        })
        assert any(v.rule == "R2" and "不在六步枚举内" in v.detail
                   for v in validate_provenance(dirty))

    def test_r3_reports_unresolvable_ref(self):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        bad = provenance.model_copy(update={
            "steps": [
                s.model_copy(update={"evidence": [Evidence(kind="doc", ref="doc-gone")]})
                if s.step == "gate" else s
                for s in provenance.steps
            ]
        })
        resolver = _Resolver()
        violations = validate_provenance(bad, resolver=resolver)
        assert [(v.rule, v.step) for v in violations] == [("R3", "gate")]
        assert ("doc", "doc-gone") in resolver.calls

    def test_r3_reports_empty_ref(self):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        bad = provenance.model_copy(update={
            "steps": [
                s.model_copy(update={"evidence": [Evidence(kind="doc", ref=" ")]})
                if s.step == "map" else s
                for s in provenance.steps
            ]
        })
        violations = validate_provenance(bad, resolver=_Resolver())
        assert "ref 为空" in violations[0].detail

    def test_r3_skipped_when_no_resolver(self):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        assert validate_provenance(provenance, resolver=None) == []

    def test_r4_detects_version_drift(self):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        violations = validate_provenance(provenance, expected_tbox_version="sha256:other")
        assert [(v.rule) for v in violations] == ["R4"]
        assert "不一致" in violations[0].detail

    def test_r4_detects_missing_version(self):
        provenance = _builder().build(tbox_version="", contract_ok=True)
        violations = validate_provenance(provenance, expected_tbox_version=TBOX)
        assert violations[0].rule == "R4"
        assert "未做版本锚定" in violations[0].detail


class TestStorageUniqueness:
    def test_duplicate_trace_id_rejected_by_primary_key(self, trace_repo):
        provenance = _builder().build(tbox_version=TBOX, contract_ok=True)
        trace = {"trace_id": TRACE, "query": "上个季度退货率最高的三个品类",
                 "created_at": "2026-10-17T00:00:00+00:00"}
        trace_repo.save(trace, provenance)
        assert trace_repo.exists(TRACE)
        with pytest.raises(Exception):
            trace_repo.save(dict(trace), provenance)

    def test_provenance_roundtrip_keeps_order_and_evidence(self, trace_repo):
        provenance = _builder().build(
            tbox_version=TBOX, contract_ok=True,
            citations=[Evidence(kind="doc", ref="doc-01JABC")],
        )
        trace_repo.save({"trace_id": TRACE, "query": "退货率口径是什么",
                         "created_at": "2026-10-17T00:00:00+00:00"}, provenance)
        reloaded = trace_repo.get_provenance(TRACE)
        assert [s.step for s in reloaded.steps] == [
            "intent", "map", "guard", "retrieve", "compose", "gate"
        ]
        assert reloaded.citations[0].ref == "doc-01JABC"
        assert reloaded.tbox_version == TBOX
