import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, PropertyMock


@pytest.fixture(autouse=True)
def _stub_decision_persistence():
    """单测隔离：execute() 经 get_decision_service() 触达真实 Neo4j 决策存储
    （pipeline.py:250 record_decision / :621 link_triggered_action / :682
    update_decision_outcome）。容器停时 Neo4jDecisionStore 自建 driver 按
    max_transaction_retry_time 默认 30s 逐操作重试，串行多操作累积阻塞数分钟，
    而外层 try/except 抓不住网络阻塞（非异常）→ 永久挂死。

    在存储边界打桩（规则 14 #6：仅在 infra/存储边界 stub，被测 SUT
    DecisionPipeline.execute 仍走真实函数体——阶段流转/OPA 门禁/perform/feedback
    全部真实执行）。这些用例本就断言编排结果而非持久化副作用，故打桩不削弱任何断言。
    """
    svc = MagicMock()
    saved = MagicMock()
    saved.decision_id = "dec_stub"
    svc.record_decision = AsyncMock(return_value=saved)
    svc.update_decision_outcome = AsyncMock(return_value=True)
    svc.link_triggered_action = AsyncMock(return_value=None)
    with patch("odap.biz.decision.decision_record.get_decision_service", return_value=svc):
        yield svc


class TestPipelineStageStatus:
    def test_pending(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineStageStatus
        assert PipelineStageStatus.PENDING == "pending"

    def test_running(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineStageStatus
        assert PipelineStageStatus.RUNNING == "running"

    def test_completed(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineStageStatus
        assert PipelineStageStatus.COMPLETED == "completed"

    def test_failed(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineStageStatus
        assert PipelineStageStatus.FAILED == "failed"

    def test_skipped(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineStageStatus
        assert PipelineStageStatus.SKIPPED == "skipped"

    def test_all_values(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineStageStatus
        values = {s.value for s in PipelineStageStatus}
        assert values == {"pending", "running", "completed", "failed", "skipped"}


class TestAnalysisInput:
    def test_creation_with_defaults(self):
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput
        inp = AnalysisInput(query="test query")
        assert inp.query == "test query"
        assert inp.context == {}
        assert inp.workspace_id is None
        assert inp.scenario_id is None
        assert inp.agent_id is None

    def test_creation_with_all_fields(self):
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput
        inp = AnalysisInput(
            query="analyze threat",
            context={"region": "east"},
            workspace_id="ws_123",
            scenario_id="sc_456",
            agent_id="agent_789",
        )
        assert inp.context["region"] == "east"
        assert inp.workspace_id == "ws_123"
        assert inp.scenario_id == "sc_456"
        assert inp.agent_id == "agent_789"


class TestAnalysisResult:
    def test_defaults(self):
        from odap.biz.decision.decision_pipeline.schemas import AnalysisResult
        result = AnalysisResult()
        assert result.summary == ""
        assert result.entities == []
        assert result.relations == []
        assert result.patterns == []
        assert result.risks == []
        assert result.confidence == 0.0
        assert result.raw_context == ""

    def test_with_data(self):
        from odap.biz.decision.decision_pipeline.schemas import AnalysisResult
        result = AnalysisResult(
            summary="Found 3 entities",
            entities=[{"id": "e1", "type": "Person"}],
            confidence=0.85,
        )
        assert result.summary == "Found 3 entities"
        assert len(result.entities) == 1
        assert result.confidence == 0.85


class TestDecisionOption:
    def test_defaults(self):
        from odap.biz.decision.decision_pipeline.schemas import DecisionOption
        opt = DecisionOption()
        assert opt.option_id == ""
        assert opt.name == ""
        assert opt.risk_level == "low"
        assert opt.priority == 0
        assert opt.parameters == {}

    def test_with_data(self):
        from odap.biz.decision.decision_pipeline.schemas import DecisionOption
        opt = DecisionOption(
            option_id="opt_1",
            name="Evacuate",
            description="Evacuate the area",
            action_type_id="action_evacuate",
            target_object_id="obj_zone_a",
            target_object_type="Zone",
            risk_level="high",
            priority=1,
        )
        assert opt.option_id == "opt_1"
        assert opt.risk_level == "high"
        assert opt.action_type_id == "action_evacuate"


class TestDecisionResult:
    def test_defaults(self):
        from odap.biz.decision.decision_pipeline.schemas import DecisionResult
        result = DecisionResult()
        assert result.decision_id == ""
        assert result.recommended_option is None
        assert result.alternative_options == []
        assert result.opa_approved is False
        assert result.opa_decision is None
        assert result.reasoning == ""
        assert result.confidence == 0.0

    def test_with_opa_approved(self):
        from odap.biz.decision.decision_pipeline.schemas import DecisionResult, DecisionOption
        opt = DecisionOption(option_id="opt_1", name="Act")
        result = DecisionResult(
            decision_id="dec_123",
            recommended_option=opt,
            opa_approved=True,
            opa_decision={"allow": True},
            reasoning="Safe to proceed",
            confidence=0.9,
        )
        assert result.opa_approved is True
        assert result.opa_decision["allow"] is True
        assert result.recommended_option.name == "Act"


class TestPipelineResult:
    def test_defaults(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineResult
        result = PipelineResult()
        assert result.pipeline_id == ""
        assert result.analysis is None
        assert result.decision is None
        assert result.action_record is None
        assert result.feedback is None
        assert result.stages == {}
        assert result.error is None

    def test_with_stages(self):
        from odap.biz.decision.decision_pipeline.schemas import PipelineResult, PipelineStageStatus
        result = PipelineResult(
            pipeline_id="dp_abc123",
            stages={
                "analyze": PipelineStageStatus.COMPLETED,
                "decide": PipelineStageStatus.RUNNING,
                "validate": PipelineStageStatus.PENDING,
                "perform": PipelineStageStatus.PENDING,
                "feedback": PipelineStageStatus.PENDING,
            },
        )
        assert result.pipeline_id == "dp_abc123"
        assert result.stages["analyze"] == PipelineStageStatus.COMPLETED
        assert result.stages["decide"] == PipelineStageStatus.RUNNING


class TestDecisionPipelineInit:
    def test_init(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        pipeline = DecisionPipeline()
        assert pipeline._semantic_retriever is None
        assert pipeline._decision_engine is None
        assert pipeline._action_executor is None
        assert pipeline._feedback_loop is None
        assert pipeline._opa_manager is None


def _make_pipeline_with_mocks():
    from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
    from odap.biz.decision.decision_pipeline.schemas import (
        AnalysisInput, AnalysisResult, DecisionResult, DecisionOption,
    )

    pipeline = DecisionPipeline()

    mock_retriever = AsyncMock()
    mock_retriever.retrieve = AsyncMock(return_value=Mock(
        answer_context="Test context about threats",
        objects=[
            Mock(
                object_id="obj_1",
                object_type="Person",
                properties={"name": "Target"},
                links=[{"target_id": "obj_2", "link_type": "associated"}],
                score=0.8,
            )
        ],
    ))
    pipeline._semantic_retriever = mock_retriever

    mock_engine = Mock()
    mock_recommendation = Mock()
    mock_option = Mock()
    mock_option.option_id = "opt_1"
    mock_option.name = "Monitor"
    mock_option.description = "Continue monitoring"
    mock_option.risk_level = "low"
    mock_option.expected_outcome = "Stable situation"
    mock_option.rationale = "Low risk detected"
    mock_recommendation.recommended_option = mock_option
    mock_recommendation.reasoning = "Low risk detected"
    mock_recommendation.decision_summary = "Low risk detected"
    mock_recommendation.confidence = 0.8
    # D3 对齐：生产 _decide await 的是 generate_recommendation（ADR-076），非同步 recommend。
    mock_engine.generate_recommendation = AsyncMock(return_value=mock_recommendation)
    pipeline._decision_engine = mock_engine

    mock_opa = Mock()
    mock_opa.check_permission_abac = Mock(return_value={"allow": True})
    pipeline._opa_manager = mock_opa

    mock_executor = AsyncMock()
    mock_executor.submit_action = AsyncMock(return_value={
        "action_id": "act_1",
        "status": "completed",
        "result": "Action executed",
    })
    pipeline._action_executor = mock_executor

    mock_feedback = AsyncMock()
    mock_feedback.close_loop = AsyncMock(return_value={
        "feedback_id": "fb_1",
        "status": "closed",
        "outcome": "positive",
    })
    pipeline._feedback_loop = mock_feedback

    return pipeline


class TestDecisionPipelineExecuteSuccess:
    @pytest.mark.asyncio
    async def test_full_success_path(self):
        pipeline = _make_pipeline_with_mocks()
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        inp = AnalysisInput(query="analyze threats", workspace_id="ws_1", agent_id="agent_1")
        result = await pipeline.execute(inp)

        assert result.error is None
        assert result.analysis is not None
        assert result.decision is not None
        assert result.decision.opa_approved is True
        assert result.action_record is not None
        assert result.action_record["status"] == "completed"
        assert result.feedback is not None
        assert result.stages["analyze"] == PipelineStageStatus.COMPLETED
        assert result.stages["decide"] == PipelineStageStatus.COMPLETED
        assert result.stages["validate"] == PipelineStageStatus.COMPLETED
        assert result.stages["perform"] == PipelineStageStatus.COMPLETED
        assert result.stages["feedback"] == PipelineStageStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_pipeline_id_generated(self):
        pipeline = _make_pipeline_with_mocks()
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        inp = AnalysisInput(query="test", workspace_id="ws_1")
        result = await pipeline.execute(inp)
        assert result.pipeline_id.startswith("dp_")

    @pytest.mark.asyncio
    async def test_analysis_entities_populated(self):
        pipeline = _make_pipeline_with_mocks()
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        inp = AnalysisInput(query="analyze threats", workspace_id="ws_1")
        result = await pipeline.execute(inp)
        assert len(result.analysis.entities) >= 1
        assert result.analysis.entities[0]["object_id"] == "obj_1"


class TestDecisionPipelineAnalyzeFailure:
    @pytest.mark.asyncio
    async def test_analyze_failure(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(side_effect=Exception("Retriever down"))
        pipeline._semantic_retriever = mock_retriever

        inp = AnalysisInput(query="test", workspace_id="ws_1")
        result = await pipeline.execute(inp)

        assert result.stages["analyze"] == PipelineStageStatus.FAILED
        assert "Analyze failed" in result.error
        assert result.decision is None
        assert result.stages["decide"] == PipelineStageStatus.PENDING


class TestDecisionPipelineDecideFailure:
    @pytest.mark.asyncio
    async def test_decide_failure(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context="ctx",
            objects=[],
        ))
        pipeline._semantic_retriever = mock_retriever

        pipeline._decision_engine = Mock()
        pipeline._decision_engine.generate_recommendation = AsyncMock(side_effect=Exception("Engine error"))

        with patch("odap.biz.decision.decision_pipeline.pipeline.DecisionPipeline._fallback_decide",
                    new_callable=AsyncMock, side_effect=Exception("Fallback also failed")):
            inp = AnalysisInput(query="test", workspace_id="ws_1")
            result = await pipeline.execute(inp)

        assert result.stages["decide"] == PipelineStageStatus.FAILED
        assert "Decide failed" in result.error
        assert result.stages["analyze"] == PipelineStageStatus.COMPLETED
        assert result.stages["validate"] == PipelineStageStatus.PENDING


class TestDecisionPipelineOPARejection:
    @pytest.mark.asyncio
    async def test_opa_rejection_skips_perform(self):
        pipeline = _make_pipeline_with_mocks()
        pipeline._opa_manager.check_permission_abac = Mock(return_value={"allow": False})

        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        inp = AnalysisInput(query="test", agent_id="agent_1", workspace_id="ws_1")
        result = await pipeline.execute(inp)

        assert result.decision.opa_approved is False
        assert result.stages["validate"] == PipelineStageStatus.COMPLETED
        assert result.stages["perform"] == PipelineStageStatus.SKIPPED
        assert result.stages["feedback"] == PipelineStageStatus.SKIPPED
        assert result.action_record is None


class TestDecisionPipelineValidateFailClosed:
    @pytest.mark.asyncio
    async def test_fail_closed_no_opa(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import (
            AnalysisInput, AnalysisResult, DecisionResult, DecisionOption,
            PipelineStageStatus,
        )

        pipeline = DecisionPipeline()

        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context="ctx", objects=[],
        ))
        pipeline._semantic_retriever = mock_retriever

        mock_engine = Mock()
        mock_rec = Mock()
        mock_opt = Mock()
        mock_opt.option_id = "opt_1"
        mock_opt.name = "Act"
        mock_opt.description = "Do something"
        mock_opt.risk_level = "low"
        mock_opt.expected_outcome = "Good"
        mock_opt.rationale = "test"
        mock_rec.recommended_option = mock_opt
        mock_rec.reasoning = "test"
        mock_rec.decision_summary = "test"
        mock_rec.confidence = 0.5
        mock_engine.generate_recommendation = AsyncMock(return_value=mock_rec)
        pipeline._decision_engine = mock_engine

        with patch.object(type(pipeline), 'opa', new_callable=PropertyMock, return_value=None):
            inp = AnalysisInput(query="test", workspace_id="ws_1")
            result = await pipeline.execute(inp)

        assert result.decision.opa_approved is False
        assert result.decision.opa_decision is not None
        assert result.decision.opa_decision["allow"] is False
        assert "fail-closed" in result.decision.opa_decision["reason"]
        assert result.stages["perform"] == PipelineStageStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_fail_closed_opa_exception(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        pipeline = _make_pipeline_with_mocks()
        pipeline._opa_manager.check_permission_abac = Mock(side_effect=Exception("OPA unreachable"))

        inp = AnalysisInput(query="test", agent_id="agent_1", workspace_id="ws_1")
        result = await pipeline.execute(inp)

        assert result.decision.opa_approved is False
        assert result.decision.opa_decision["allow"] is False
        assert "fail-closed" in result.decision.opa_decision["reason"]
        assert result.stages["perform"] == PipelineStageStatus.SKIPPED


class TestPipelineStagesTracking:
    @pytest.mark.asyncio
    async def test_all_stages_initialized_as_pending(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(side_effect=Exception("fail"))
        pipeline._semantic_retriever = mock_retriever

        inp = AnalysisInput(query="test", workspace_id="ws_1")
        result = await pipeline.execute(inp)

        assert "analyze" in result.stages
        assert "decide" in result.stages
        assert "validate" in result.stages
        assert "perform" in result.stages
        assert "feedback" in result.stages

    @pytest.mark.asyncio
    async def test_stages_progress_on_partial_failure(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context="ctx", objects=[],
        ))
        pipeline._semantic_retriever = mock_retriever

        with patch.object(type(pipeline), 'decision_engine', new_callable=PropertyMock, return_value=None):
            with patch("odap.biz.decision.decision_pipeline.pipeline.DecisionPipeline._fallback_decide",
                        new_callable=AsyncMock, side_effect=Exception("No fallback")):
                inp = AnalysisInput(query="test", workspace_id="ws_1")
                result = await pipeline.execute(inp)

        assert result.stages["analyze"] == PipelineStageStatus.COMPLETED
        assert result.stages["decide"] == PipelineStageStatus.FAILED
        assert result.stages["validate"] == PipelineStageStatus.PENDING
        assert result.stages["perform"] == PipelineStageStatus.PENDING
        assert result.stages["feedback"] == PipelineStageStatus.PENDING

    @pytest.mark.asyncio
    async def test_perform_failure_stops_pipeline(self):
        pipeline = _make_pipeline_with_mocks()
        pipeline._action_executor.submit_action = AsyncMock(side_effect=Exception("Executor down"))

        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        inp = AnalysisInput(query="test", agent_id="agent_1", workspace_id="ws_1")
        result = await pipeline.execute(inp)

        assert result.stages["analyze"] == PipelineStageStatus.COMPLETED
        assert result.stages["decide"] == PipelineStageStatus.COMPLETED
        assert result.stages["validate"] == PipelineStageStatus.COMPLETED
        assert result.stages["perform"] == PipelineStageStatus.FAILED
        assert result.stages["feedback"] == PipelineStageStatus.PENDING
        assert "Perform failed" in result.error

    @pytest.mark.asyncio
    async def test_feedback_failure_does_not_fail_pipeline(self):
        pipeline = _make_pipeline_with_mocks()
        pipeline._feedback_loop.close_loop = AsyncMock(side_effect=Exception("Feedback error"))

        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        inp = AnalysisInput(query="test", agent_id="agent_1", workspace_id="ws_1")
        result = await pipeline.execute(inp)

        assert result.stages["feedback"] == PipelineStageStatus.FAILED
        assert result.action_record is not None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_no_recommended_option_skips_perform(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context="ctx", objects=[],
        ))
        pipeline._semantic_retriever = mock_retriever

        mock_engine = Mock()
        mock_rec = Mock()
        mock_rec.recommended_option = None
        mock_rec.reasoning = "No options"
        mock_rec.decision_summary = "No options"
        mock_rec.confidence = 0.1
        mock_engine.generate_recommendation = AsyncMock(return_value=mock_rec)
        pipeline._decision_engine = mock_engine

        with patch.object(type(pipeline), 'opa', new_callable=PropertyMock, return_value=None):
            inp = AnalysisInput(query="test", workspace_id="ws_1")
            result = await pipeline.execute(inp)

        assert result.decision.recommended_option is None
        assert result.stages["perform"] == PipelineStageStatus.SKIPPED


class TestDecisionPipelineSingleton:
    def test_get_decision_pipeline_returns_instance(self):
        """get_decision_pipeline 返回单例实例"""
        from odap.biz.decision.decision_pipeline.pipeline import get_decision_pipeline, DecisionPipeline
        # Reset singleton for test
        import odap.biz.decision.decision_pipeline.pipeline as mod
        mod._pipeline_instance = None
        pipeline = get_decision_pipeline()
        assert isinstance(pipeline, DecisionPipeline)

    def test_get_decision_pipeline_returns_same_instance(self):
        """多次调用返回同一实例"""
        from odap.biz.decision.decision_pipeline.pipeline import get_decision_pipeline
        import odap.biz.decision.decision_pipeline.pipeline as mod
        mod._pipeline_instance = None
        p1 = get_decision_pipeline()
        p2 = get_decision_pipeline()
        assert p1 is p2


class TestDecisionPipelineAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_extracts_entity_links(self):
        """分析阶段提取实体关联链接"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context="Context with links",
            objects=[
                Mock(
                    object_id="obj_1",
                    object_type="Person",
                    properties={"name": "Alice"},
                    links=[{"target_id": "obj_2", "link_type": "knows"}],
                    score=0.9,
                )
            ],
        ))
        pipeline._semantic_retriever = mock_retriever

        inp = AnalysisInput(query="find connections")
        analysis = await pipeline._analyze(inp)

        assert len(analysis.entities) == 1
        assert analysis.entities[0]["object_id"] == "obj_1"
        assert len(analysis.entities[0]["links"]) == 1
        assert analysis.entities[0]["links"][0]["target_id"] == "obj_2"

    @pytest.mark.asyncio
    async def test_analyze_truncates_long_context(self):
        """分析阶段截断超长上下文"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        pipeline = DecisionPipeline()
        long_context = "x" * 1000
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context=long_context,
            objects=[],
        ))
        pipeline._semantic_retriever = mock_retriever

        inp = AnalysisInput(query="test", workspace_id="ws_1")
        analysis = await pipeline._analyze(inp)

        assert len(analysis.summary) <= 500


class TestDecisionPipelineValidate:
    @pytest.mark.asyncio
    async def test_validate_no_recommended_option_sets_not_approved(self):
        """无推荐选项时 OPA 不批准"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, DecisionResult

        pipeline = DecisionPipeline()
        decision = DecisionResult(recommended_option=None)
        inp = AnalysisInput(query="test", workspace_id="ws_1")

        result = await pipeline._validate(decision, inp)
        assert result.opa_approved is False

    @pytest.mark.asyncio
    async def test_validate_with_opa_allow(self):
        """OPA 允许时设置 opa_approved"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, DecisionResult, DecisionOption

        pipeline = DecisionPipeline()
        mock_opa = Mock()
        mock_opa.check_permission_abac = Mock(return_value={"allow": True})
        pipeline._opa_manager = mock_opa

        option = DecisionOption(option_id="opt_1", action_type_id="act_1", target_object_id="obj_1")
        decision = DecisionResult(recommended_option=option)
        inp = AnalysisInput(query="test", agent_id="agent_1", workspace_id="ws_1")

        result = await pipeline._validate(decision, inp)
        assert result.opa_approved is True
        assert result.opa_decision["allow"] is True


# ── confidence 真算：替换硬编码 0.7 / 0.5 ─────────────────────────────

class TestConfidenceDerivedNotHardcoded:
    """_analyze 曾恒定 confidence=0.7、_fallback_decide 曾恒定 0.5，与检索到的真实证据
    强度无关——前端把假精确值当真，违反"宁可未知绝不谎报"。修复后从 ObjectQueryResult.score
    （Pydantic 校验的 Optional[float]）派生真实置信度。
    """

    def test_mean_of_available_scores(self):
        from odap.biz.decision.decision_pipeline.pipeline import _compute_retrieval_confidence

        objects = [Mock(score=0.8), Mock(score=0.6)]
        assert _compute_retrieval_confidence(objects) == 0.7

    def test_skips_none_scores(self):
        """score=None 的条目不参与均值（真实语义：该条无相关性得分）"""
        from odap.biz.decision.decision_pipeline.pipeline import _compute_retrieval_confidence

        objects = [Mock(score=0.9), Mock(score=None), Mock(score=0.5)]
        assert _compute_retrieval_confidence(objects) == 0.7

    def test_no_scores_returns_zero_not_fabricated(self):
        """全部无得分 → 0.0（"无证据可支撑置信度"），绝不回填 0.7"""
        from odap.biz.decision.decision_pipeline.pipeline import _compute_retrieval_confidence

        assert _compute_retrieval_confidence([]) == 0.0
        assert _compute_retrieval_confidence([Mock(score=None)]) == 0.0

    def test_clamps_to_unit_interval(self):
        from odap.biz.decision.decision_pipeline.pipeline import _compute_retrieval_confidence

        assert _compute_retrieval_confidence([Mock(score=1.5), Mock(score=1.5)]) == 1.0
        assert _compute_retrieval_confidence([Mock(score=-0.5)]) == 0.0

    @pytest.mark.asyncio
    async def test_analyze_confidence_tracks_real_scores(self):
        """_analyze 的 confidence 必须随检索得分变化，不再是常量 0.7"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(
            answer_context="ctx",
            objects=[Mock(object_id="o1", object_type="T", properties={}, links=[], score=0.42)],
        ))
        pipeline._semantic_retriever = mock_retriever

        analysis = await pipeline._analyze(AnalysisInput(query="q"))

        assert analysis.confidence == 0.42
        assert analysis.confidence != 0.7

    @pytest.mark.asyncio
    async def test_analyze_confidence_zero_when_no_evidence(self):
        """检索为空 → confidence 0.0，暴露"无证据"而非伪装 0.7"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        pipeline = DecisionPipeline()
        mock_retriever = AsyncMock()
        mock_retriever.retrieve = AsyncMock(return_value=Mock(answer_context="", objects=[]))
        pipeline._semantic_retriever = mock_retriever

        analysis = await pipeline._analyze(AnalysisInput(query="q"))

        assert analysis.confidence == 0.0

    @pytest.mark.asyncio
    async def test_fallback_decide_propagates_analysis_confidence(self):
        """降级决策路径不得伪造 0.5，必须继承分析阶段的真实置信度"""
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, AnalysisResult

        pipeline = DecisionPipeline()
        analysis = AnalysisResult(entities=[], confidence=0.0)
        inp = AnalysisInput(query="q", workspace_id="ws_1")

        with patch("odap.biz.core.ontology.public.get_oms_service", return_value=Mock()):
            decision = await pipeline._fallback_decide(analysis, inp)

        assert decision.confidence == 0.0
        assert decision.confidence != 0.5

    @pytest.mark.asyncio
    async def test_fallback_decide_keeps_real_confidence_when_evidence_exists(self):
        from odap.biz.decision.decision_pipeline.pipeline import DecisionPipeline
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, AnalysisResult

        pipeline = DecisionPipeline()
        analysis = AnalysisResult(entities=[], confidence=0.33)
        inp = AnalysisInput(query="q", workspace_id="ws_1")

        with patch("odap.biz.core.ontology.public.get_oms_service", return_value=Mock()):
            decision = await pipeline._fallback_decide(analysis, inp)

        assert decision.confidence == 0.33


class TestExecuteNoBlockingInfra:
    """回归护栏：execute() 是单测，容器不可达时也必须快速完成，绝不阻塞。

    根因（faulthandler + asyncio 任务栈定位到 pipeline.py:250）：ADR-076 在 execute()
    加了决策持久化（:250 record_decision）与结果回填（:323 update_decision_outcome），
    二者经 get_decision_service() 触达真实 Neo4jDecisionStore。容器停时 Neo4j driver 按
    max_transaction_retry_time 默认 30s 逐操作重试，record_decision 串行多次调用累积阻塞
    数分钟；外层 try/except 只能抓异常，抓不住网络阻塞（非异常）→ 表现为永久挂死。

    本护栏用 asyncio.wait_for 把"execute 再次泄漏到阻塞基建"从静默挂死转为响亮失败
    （TimeoutError），是 fixture 被误删/新增未打桩 infra 调用时的绊线。
    """

    @pytest.mark.asyncio
    async def test_execute_completes_without_blocking_on_store(self):
        import asyncio
        pipeline = _make_pipeline_with_mocks()
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput, PipelineStageStatus

        inp = AnalysisInput(query="analyze threats", workspace_id="ws_1", agent_id="agent_1")
        result = await asyncio.wait_for(pipeline.execute(inp), timeout=10)

        assert result.error is None
        assert result.stages["feedback"] == PipelineStageStatus.COMPLETED
