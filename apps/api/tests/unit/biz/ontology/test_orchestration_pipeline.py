"""六步约束管线测试（AC-26 / AC-28 / AC-29 / AC-30 / AC-31 / AC-36 / AC-37 / AC-38 / AC-39）。

全部走真实实现（意图 L1 词典、TBox 对齐、OPA 守卫、降级链检索、抽取式合成、契约门），
只在外部系统边界（SQLite 后端 / OPA HTTP / 检索引擎）注入替身。
断言聚焦机械可校验项：六步齐全、证据可解析、版本锚定、no_answer 不编造、fail-closed、降级显式。
"""

from __future__ import annotations

import re

import pytest

from odap.common.api_errors import ApiError
from odap.biz.core.ontology.orchestration.contracts import STEP_ORDER, QaStatus

TRACE_PATTERN = re.compile(r"^urn:odap:trace:[0-9A-HJKMNP-TV-Z]{26}$")
QUERY = "上个季度退货率最高的三个品类是什么"
USER = {"sub": "u-analyst", "roles": ["analyst"], "workspace_id": "ws-supply"}
WORKSPACE = "ws-supply"


class TestAnsweredPath:
    async def test_six_steps_present_and_valid(self, build_pipeline, resolver, tbox_catalog):
        from odap.biz.core.ontology.orchestration.provenance import validate_provenance

        answer, provenance = await build_pipeline().run(query=QUERY, user_ctx=USER,
                                                        workspace_id=WORKSPACE)
        assert answer.status is QaStatus.ANSWERED
        assert TRACE_PATTERN.match(answer.trace_id)
        assert [s.step for s in provenance.steps] == list(STEP_ORDER)

        violations = validate_provenance(
            provenance, resolver=resolver,
            expected_tbox_version=tbox_catalog.snapshot_hash(WORKSPACE),
        )
        assert violations == [], [v.detail for v in violations]

    async def test_answer_lists_citations_and_keeps_contract(self, build_pipeline):
        answer, provenance = await build_pipeline().run(
            query=QUERY, user_ctx=USER, workspace_id=WORKSPACE
        )
        assert answer.contract_ok is True
        assert answer.blocked_reasons == []
        assert [c.ref for c in answer.citations] == ["doc-01J9ZK8P3Q7N2M4R5T6V7W8X9A"]
        assert "0.184" in (answer.answer or "")  # 取值为证据里的真实值，不是编造
        assert provenance.tbox_version.startswith("sha256:")
        assert provenance.contract_ok is True

    async def test_intent_and_mapping_come_from_real_tables(self, build_pipeline):
        answer, _ = await build_pipeline().run(
            query=QUERY, user_ctx=USER, workspace_id=WORKSPACE
        )
        assert answer.intent.intent_type == "metric_query"
        assert answer.intent.confidence == pytest.approx(0.95)
        refs = {(r.kind, r.ref) for r in answer.mapped_refs}
        assert ("metric", "metric:order_return_rate") in refs

    async def test_trace_is_persisted_and_reloadable(self, build_pipeline, trace_repo):
        answer, provenance = await build_pipeline().run(
            query=QUERY, user_ctx=USER, workspace_id=WORKSPACE
        )
        assert trace_repo.exists(answer.trace_id)
        reloaded = trace_repo.get_provenance(answer.trace_id)
        assert reloaded is not None
        assert [s.step for s in reloaded.steps] == list(STEP_ORDER)
        assert reloaded.trace_id == provenance.trace_id


class TestNoEvidenceNoAnswer:
    async def test_empty_retrieval_yields_no_answer(self, build_pipeline, fake_engine):
        pipeline = build_pipeline(engines={"graph": lambda: fake_engine([])})
        answer, provenance = await pipeline.run(
            query=QUERY, user_ctx=USER, workspace_id=WORKSPACE
        )
        assert answer.status is QaStatus.NO_ANSWER
        assert answer.no_answer is True
        assert answer.answer is None
        assert "未返回任何可引用证据" in (answer.no_answer_reason or "")
        assert [s.step for s in provenance.steps] == list(STEP_ORDER)

    async def test_all_engines_failing_degrades_and_reports(self, build_pipeline, fake_engine):
        pipeline = build_pipeline(engines={
            "graph": lambda: fake_engine(fail=True),
            "nl": lambda: fake_engine(fail=True),
        })
        answer, _ = await pipeline.run(query=QUERY, user_ctx=USER, workspace_id=WORKSPACE)
        assert answer.status is QaStatus.NO_ANSWER
        assert set(answer.degraded_engines) >= {"graph", "nl", "mdl", "metric"}
        assert answer.degraded is True


class TestDegradation:
    async def test_single_engine_failure_falls_through_chain(self, build_pipeline, fake_engine,
                                                             evidence_rows_factory):
        pipeline = build_pipeline(engines={
            "graph": lambda: fake_engine(fail=True),
            "nl": lambda: fake_engine(evidence_rows_factory(0.211)),
        })
        answer, _ = await pipeline.run(query=QUERY, user_ctx=USER, workspace_id=WORKSPACE)
        assert answer.status is QaStatus.ANSWERED
        assert answer.degraded is True
        assert answer.degraded_engines == ["graph"]
        assert "0.211" in (answer.answer or "")

    async def test_opa_unavailable_read_only_degrades(self, build_pipeline, fake_opa):
        pipeline = build_pipeline(opa=fake_opa(fail=True))
        answer, _ = await pipeline.run(query=QUERY, user_ctx=USER, workspace_id=WORKSPACE)
        assert answer.status is QaStatus.ANSWERED
        assert answer.degraded is True


class TestGuardFailClosed:
    async def test_high_risk_without_opa_raises_503(self, build_pipeline, fake_opa):
        pipeline = build_pipeline(opa=fake_opa(fail=True))
        with pytest.raises(ApiError) as excinfo:
            await pipeline.run(query="删除订单的全部退货记录", user_ctx=USER,
                               workspace_id=WORKSPACE)
        assert excinfo.value.error_code == "GUARD_FAIL_CLOSED"
        assert excinfo.value.status_code == 503
        assert excinfo.value.detail["risk_level"] == "high"

    async def test_policy_denial_blocks_without_503(self, build_pipeline, fake_opa):
        pipeline = build_pipeline(opa=fake_opa(allow=False, reason="角色无权读取财务口径"))
        answer, provenance = await pipeline.run(
            query=QUERY, user_ctx=USER, workspace_id=WORKSPACE
        )
        assert answer.status is QaStatus.BLOCKED
        assert answer.contract_ok is False
        assert answer.blocked_reasons == ["角色无权读取财务口径"]
        assert [s.step for s in provenance.steps] == list(STEP_ORDER)


class TestClarify:
    async def test_unknown_query_asks_for_clarification(self, build_pipeline, trace_repo):
        from odap.biz.core.ontology.orchestration.provenance import validate_provenance

        pipeline = build_pipeline()
        answer, provenance = await pipeline.run(query="你好", user_ctx=USER,
                                                workspace_id=WORKSPACE)
        assert answer.status is QaStatus.CLARIFY
        assert answer.answer is None
        assert "退货率" in (answer.clarify_question or "")
        assert [s.step for s in provenance.steps] == list(STEP_ORDER)
        assert validate_provenance(provenance, resolver=None,
                                   expected_tbox_version=None) == []
        assert trace_repo.get_trace(answer.trace_id) is not None

    async def test_dictionary_unavailable_does_not_guess(self, build_pipeline):
        from odap.biz.core.ontology.orchestration.impl.intent_router import (
            L1IntentRouter,
            UslDictionary,
        )

        def _broken_loader():
            raise RuntimeError("usl.db 被锁（database is locked）")

        pipeline = build_pipeline(
            router=L1IntentRouter(dictionary=UslDictionary(loader=_broken_loader))
        )
        answer, _ = await pipeline.run(query=QUERY, user_ctx=USER, workspace_id=WORKSPACE)
        assert answer.status is QaStatus.CLARIFY
        assert "usl.db" in (answer.clarify_question or "")


class TestTBoxFailClosed:
    async def test_unreadable_tbox_raises_503(self, build_pipeline):
        from odap.biz.core.ontology.orchestration.tbox import TBoxCatalog

        class _BrokenService:
            def list_ontologies(self, workspace_id=None):
                return {"status": "error", "message": "ontology_api.db 不可读"}

        broken = TBoxCatalog(ontology_service_factory=lambda: _BrokenService())
        with pytest.raises(ApiError) as excinfo:
            await build_pipeline(catalog=broken).run(query=QUERY, user_ctx=USER,
                                                     workspace_id=WORKSPACE)
        assert excinfo.value.error_code == "TBOX_UNAVAILABLE"
        assert excinfo.value.status_code == 503
