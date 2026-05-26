import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock, PropertyMock


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
    mock_recommendation.recommended_option = mock_option
    mock_recommendation.reasoning = "Low risk detected"
    mock_recommendation.confidence = 0.8
    mock_engine.recommend = Mock(return_value=mock_recommendation)
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

        inp = AnalysisInput(query="test")
        result = await pipeline.execute(inp)
        assert result.pipeline_id.startswith("dp_")

    @pytest.mark.asyncio
    async def test_analysis_entities_populated(self):
        pipeline = _make_pipeline_with_mocks()
        from odap.biz.decision.decision_pipeline.schemas import AnalysisInput

        inp = AnalysisInput(query="analyze threats")
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

        inp = AnalysisInput(query="test")
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
        pipeline._decision_engine.recommend = Mock(side_effect=Exception("Engine error"))

        with patch("odap.biz.decision.decision_pipeline.pipeline.DecisionPipeline._fallback_decide",
                    new_callable=AsyncMock, side_effect=Exception("Fallback also failed")):
            inp = AnalysisInput(query="test")
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

        inp = AnalysisInput(query="test", agent_id="agent_1")
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
        mock_rec.recommended_option = mock_opt
        mock_rec.reasoning = "test"
        mock_rec.confidence = 0.5
        mock_engine.recommend = Mock(return_value=mock_rec)
        pipeline._decision_engine = mock_engine

        with patch.object(type(pipeline), 'opa', new_callable=PropertyMock, return_value=None):
            inp = AnalysisInput(query="test")
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

        inp = AnalysisInput(query="test", agent_id="agent_1")
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

        inp = AnalysisInput(query="test")
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
                inp = AnalysisInput(query="test")
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

        inp = AnalysisInput(query="test", agent_id="agent_1")
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

        inp = AnalysisInput(query="test", agent_id="agent_1")
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
        mock_rec.confidence = 0.1
        mock_engine.recommend = Mock(return_value=mock_rec)
        pipeline._decision_engine = mock_engine

        with patch.object(type(pipeline), 'opa', new_callable=PropertyMock, return_value=None):
            inp = AnalysisInput(query="test")
            result = await pipeline.execute(inp)

        assert result.decision.recommended_option is None
        assert result.stages["perform"] == PipelineStageStatus.SKIPPED
