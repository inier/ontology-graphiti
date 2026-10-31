"""输出契约的 SHACL 分支（AC-31 / ADR-085）。

真实形状存储（SQLiteShaclStorage，tmp 库）+ 真实 pyshacl 校验；
只把「形状库不可读」这类外部故障用替身注入，验证 fail-closed。
"""

from __future__ import annotations

import pytest

from odap.biz.core.ontology.orchestration.contracts import (
    DraftAnswer,
    IntentFrame,
    MappedQuery,
)
from odap.biz.core.ontology.orchestration.impl.output_contract_gate import (
    StrictOutputContractGate,
)
from odap.biz.core.ontology.orchestration.impl.shacl_gate import ShaclPayloadValidator

SHAPE_TTL = """
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <urn:odap:type:> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ex:OrderShape a sh:NodeShape ;
    sh:targetClass ex:Order ;
    sh:property [
        sh:path ex:orderNo ;
        sh:minCount 1 ;
        sh:datatype xsd:string ;
    ] .
"""

GOOD_PAYLOAD = """
@prefix ex: <urn:odap:type:> .
ex:order-01J9ZK a ex:Order ; ex:orderNo "SO-2026-0001" .
"""

MISSING_FIELD_PAYLOAD = """
@prefix ex: <urn:odap:type:> .
ex:order-01J9ZK a ex:Order .
"""

WRONG_DATATYPE_PAYLOAD = """
@prefix ex: <urn:odap:type:> .
ex:order-01J9ZK a ex:Order ; ex:orderNo 2026001 .
"""

ONTOLOGY_VERSION = "ov-supply-2026Q3"
CONSTRAINT_REVISION = "cr-7"
TARGET_TYPE = "Order"
TARGET_IRI = "urn:odap:type:Order"


@pytest.fixture
def shacl_db(tmp_path):
    from odap.biz.semantic_admin.shacl_store.storage.sqlite_shacl_storage import (
        SQLiteShaclStorage,
    )

    return SQLiteShaclStorage(db_path=str(tmp_path / "shacl_store.db"))


@pytest.fixture
def seeded_store(shacl_db):
    shacl_db.save_shape({
        "workspace_id": "ws-supply",
        "ontology_version_id": ONTOLOGY_VERSION,
        "constraint_revision": CONSTRAINT_REVISION,
        "target_type": TARGET_TYPE,
        "shape_ttl": SHAPE_TTL,
        "source_type_defs": [{"id": "Order"}],
        "checksum": "sha256:order-shape",
    })
    return shacl_db


@pytest.fixture
def validator(seeded_store):
    return ShaclPayloadValidator(storage=seeded_store)


def _mapped(confidence: float = 0.95) -> MappedQuery:
    return MappedQuery(intent=IntentFrame(intent_type="query", confidence=confidence))


class TestShapeValidation:
    def test_conforming_payload_passes(self, validator):
        assert validator.validate(GOOD_PAYLOAD, TARGET_IRI) == []

    def test_missing_required_property_is_violation(self, validator):
        reasons = validator.validate(MISSING_FIELD_PAYLOAD, TARGET_IRI)
        assert len(reasons) == 1
        assert reasons[0].startswith("SHACL_VIOLATION")
        assert "orderNo" in reasons[0]

    def test_wrong_datatype_is_violation(self, validator):
        reasons = validator.validate(WRONG_DATATYPE_PAYLOAD, TARGET_IRI)
        assert reasons and reasons[0].startswith("SHACL_VIOLATION")

    def test_unregistered_target_type_is_blocked(self, validator):
        reasons = validator.validate(GOOD_PAYLOAD, "urn:odap:type:Supplier")
        assert reasons and reasons[0].startswith("SHACL_SHAPE_MISSING")

    def test_registered_shape_without_ttl_is_blocked(self, shacl_db):
        shacl_db.save_shape({
            "ontology_version_id": ONTOLOGY_VERSION,
            "constraint_revision": "cr-empty",
            "target_type": "Shipment",
            "shape_ttl": "",
        })
        reasons = ShaclPayloadValidator(storage=shacl_db).validate(GOOD_PAYLOAD, "Shipment")
        assert reasons and reasons[0].startswith("SHACL_SHAPE_EMPTY")

    def test_invalid_payload_turtle_is_blocked(self, validator):
        reasons = validator.validate("this is not turtle <<<", TARGET_IRI)
        assert reasons and reasons[0].startswith("SHACL_PAYLOAD_INVALID")

    def test_empty_payload_and_missing_class_are_blocked(self, validator):
        assert validator.validate("   ", TARGET_IRI)[0].startswith("SHACL_PAYLOAD_EMPTY")
        assert validator.validate(GOOD_PAYLOAD, "")[0].startswith("SHACL_TARGET_CLASS_MISSING")

    def test_pinned_version_key_hits_exact_shape(self, seeded_store):
        pinned = ShaclPayloadValidator(
            storage=seeded_store,
            ontology_version_id=ONTOLOGY_VERSION,
            constraint_revision=CONSTRAINT_REVISION,
        )
        assert pinned.validate(GOOD_PAYLOAD, TARGET_TYPE) == []

    def test_latest_shape_used_when_version_not_pinned(self, seeded_store):
        """未指定失效键时取最近登记的同类形状，不因缺键而假通过。"""
        seeded_store.save_shape({
            "ontology_version_id": "ov-supply-2026Q4",
            "constraint_revision": "cr-8",
            "target_type": TARGET_TYPE,
            "shape_ttl": SHAPE_TTL,
        })
        reasons = ShaclPayloadValidator(storage=seeded_store).validate(
            MISSING_FIELD_PAYLOAD, TARGET_TYPE
        )
        assert reasons and reasons[0].startswith("SHACL_VIOLATION")

    def test_unreadable_store_is_fail_closed(self):
        class BrokenStore:
            def get_shape(self, **_kwargs):
                raise OSError("shacl_store.db 被占用")

            def list_shapes(self, **_kwargs):
                raise OSError("shacl_store.db 被占用")

        reasons = ShaclPayloadValidator(storage=BrokenStore()).validate(GOOD_PAYLOAD, TARGET_IRI)
        assert reasons and reasons[0].startswith("SHACL_UNAVAILABLE")


class TestGateIntegration:
    async def test_structured_answer_is_checked(self, validator):
        gate = StrictOutputContractGate(shacl_validator=validator)
        draft = DraftAnswer(
            content="订单已按契约登记到图谱。",
            payload_ttl=GOOD_PAYLOAD,
            payload_class=TARGET_IRI,
        )
        result = await gate.validate(draft, _mapped())
        assert result.contract_ok is True
        assert result.blocked_reasons == []

    async def test_violation_blocks_answer_without_losing_content(self, validator):
        gate = StrictOutputContractGate(shacl_validator=validator)
        draft = DraftAnswer(
            content="订单已按契约登记到图谱。",
            payload_ttl=MISSING_FIELD_PAYLOAD,
            payload_class=TARGET_IRI,
        )
        result = await gate.validate(draft, _mapped())
        assert result.contract_ok is False
        assert result.content == draft.content
        assert any(r.startswith("SHACL_VIOLATION") for r in result.blocked_reasons)

    async def test_plain_text_answer_does_not_touch_shacl(self):
        """未携带结构化载荷时走原有纯文本通道，不构造形状校验器。"""
        gate = StrictOutputContractGate()
        draft = DraftAnswer(content="退货率来自已纳管指标口径。")
        result = await gate.validate(draft, _mapped())
        assert result.contract_ok is True
        assert gate._shacl_validator is None

    async def test_validator_crash_does_not_pass(self):
        class ExplodingValidator:
            def validate(self, payload_ttl, target_type):
                raise RuntimeError("pyshacl 子进程启动失败")

        gate = StrictOutputContractGate(shacl_validator=ExplodingValidator())
        draft = DraftAnswer(
            content="订单已按契约登记到图谱。",
            payload_ttl=GOOD_PAYLOAD,
            payload_class=TARGET_IRI,
        )
        result = await gate.validate(draft, _mapped())
        assert result.contract_ok is False
        assert any(r.startswith("SHACL_UNAVAILABLE") for r in result.blocked_reasons)
