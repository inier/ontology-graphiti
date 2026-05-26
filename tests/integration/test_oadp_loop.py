import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from odap.web.app import app

client = TestClient(app)


class TestPerceptionToCognition:
    @patch("odap.biz.data.perception.hub.PerceptionHub._extract", new_callable=AsyncMock)
    @patch("odap.biz.data.perception.hub.PerceptionHub._store_to_graphiti", new_callable=AsyncMock)
    @patch("odap.biz.data.perception.hub.PerceptionHub._map_to_oms")
    def test_perception_ingest(self, mock_map_oms, mock_store_graphiti, mock_extract):
        from odap.biz.data.perception.schemas import ExtractionResult

        mock_extract.return_value = ExtractionResult(
            entities=[{"entity_type": "Person", "name": "Alice"}],
            relations=[],
            events=[],
            actions=[],
            confidence=0.9,
        )
        mock_store_graphiti.return_value = f"ep_{uuid.uuid4().hex[:12]}"
        mock_map_oms.return_value = ["Person"]

        event_id = f"pe_{uuid.uuid4().hex[:12]}"
        payload = {
            "event_id": event_id,
            "source_type": "manual",
            "source_name": "test_source",
            "raw_content": "Alice observed unusual activity near sector 7",
            "metadata": {"test": True},
            "priority": "high",
        }

        response = client.post("/api/perception/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["event_id"] == event_id
        assert data["status"] == "stored"
        assert len(data["extraction"]["entities"]) == 1
        assert data["extraction"]["entities"][0]["entity_type"] == "Person"

    @patch("odap.biz.core.cognition.user_cognition_engine.get_cognition_engine")
    def test_intent_recognition_after_perception(self, mock_get_engine):
        mock_engine = MagicMock()
        mock_engine.process_query.return_value = {
            "intent": {"type": "alert", "confidence": 0.85, "keywords": ["unusual", "activity"]},
            "knowledge_results": [{"fact": "Sector 7 has prior incidents"}],
            "session_id": "sess_abc123",
        }
        mock_get_engine.return_value = mock_engine

        payload = {
            "input_text": "Unusual activity detected near sector 7",
            "role": "intelligence",
        }

        response = client.post("/cognition/intent", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "intent" in data
        assert data["intent"]["type"] == "alert"
        assert data["session_id"] == "sess_abc123"


class TestDecisionPipeline:
    @patch("odap.biz.decision.decision_pipeline.pipeline.DecisionPipeline._analyze", new_callable=AsyncMock)
    def test_analyze_input(self, mock_analyze):
        from odap.biz.decision.decision_pipeline.schemas import AnalysisResult

        mock_analyze.return_value = AnalysisResult(
            summary="Threat detected in sector 7",
            entities=[{"entity_type": "Location", "name": "Sector 7"}],
            relations=[{"source": "Alice", "target": "Sector 7", "relation": "observed"}],
            patterns=[{"pattern_type": "anomaly", "description": "Unusual movement pattern"}],
            risks=[{"risk_level": "high", "description": "Potential security breach"}],
            confidence=0.82,
            raw_context="Unusual activity near sector 7",
        )

        payload = {
            "query": "Analyze threat level in sector 7",
            "context": {"source": "perception"},
            "agent_id": "agent_001",
        }

        response = client.post("/api/decision-pipeline/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Threat detected in sector 7"
        assert data["confidence"] == 0.82
        assert len(data["risks"]) == 1

    @patch("odap.biz.decision.decision_pipeline.pipeline.DecisionPipeline._decide", new_callable=AsyncMock)
    @patch("odap.biz.decision.decision_pipeline.pipeline.DecisionPipeline._analyze", new_callable=AsyncMock)
    def test_decision_from_analysis(self, mock_analyze, mock_decide):
        from odap.biz.decision.decision_pipeline.schemas import AnalysisResult, DecisionResult, DecisionOption

        mock_analyze.return_value = AnalysisResult(
            summary="Threat detected in sector 7",
            entities=[],
            relations=[],
            patterns=[],
            risks=[{"risk_level": "high", "description": "Security breach"}],
            confidence=0.82,
        )

        mock_decide.return_value = DecisionResult(
            decision_id=f"dec_{uuid.uuid4().hex[:12]}",
            recommended_option=DecisionOption(
                option_id="opt_1",
                name="Deploy patrol",
                description="Send patrol to sector 7",
                action_type_id="deploy_unit",
                target_object_id="sector_7",
                target_object_type="Location",
                parameters={"unit_type": "patrol", "count": 2},
                risk_level="low",
                expected_outcome="Area secured",
                priority=1,
            ),
            alternative_options=[],
            opa_approved=True,
            reasoning="High risk detected, immediate response required",
            confidence=0.78,
        )

        payload = {
            "query": "Decide response for sector 7 threat",
            "context": {"risk_level": "high"},
            "agent_id": "agent_001",
        }

        response = client.post("/api/decision-pipeline/decide", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["decision_id"]
        assert data["recommended_option"]["name"] == "Deploy patrol"
        assert data["opa_approved"] is True
        assert data["recommended_option"]["action_type_id"] == "deploy_unit"


class TestActionExecution:
    @patch("odap.biz.decision.action_service.executor.get_action_executor")
    def test_submit_action(self, mock_get_executor):
        mock_executor = MagicMock()
        record_id = f"ar_{uuid.uuid4().hex[:12]}"
        mock_executor.submit_action = AsyncMock(return_value={
            "action_record_id": record_id,
            "action_type_id": "deploy_unit",
            "target_object_id": "sector_7",
            "target_object_type": "Location",
            "parameters": {"unit_type": "patrol", "count": 2},
            "status": "completed",
            "requested_by": "agent_001",
            "reason": "High risk response",
            "agent_id": "agent_001",
            "opa_decision": None,
            "validation_result": None,
            "execution_result": {"success": True, "message": "Patrol deployed"},
            "writeback_result": None,
            "created_at": "2026-05-21T10:00:00Z",
            "updated_at": "2026-05-21T10:00:01Z",
        })
        mock_get_executor.return_value = mock_executor

        payload = {
            "action_type_id": "deploy_unit",
            "target_object_id": "sector_7",
            "target_object_type": "Location",
            "parameters": {"unit_type": "patrol", "count": 2},
            "requested_by": "agent_001",
            "reason": "High risk response",
            "agent_id": "agent_001",
        }

        response = client.post("/api/actions/submit", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["action_record_id"] == record_id
        assert data["action_type_id"] == "deploy_unit"
        assert data["status"] == "completed"

    @patch("odap.biz.decision.action_service.executor.get_action_executor")
    def test_action_approval(self, mock_get_executor):
        mock_executor = MagicMock()
        record_id = f"ar_{uuid.uuid4().hex[:12]}"
        mock_executor.approve_and_execute = AsyncMock(return_value={
            "action_record_id": record_id,
            "action_type_id": "deploy_unit",
            "target_object_id": "sector_7",
            "target_object_type": "Location",
            "parameters": {"unit_type": "patrol", "count": 2},
            "status": "completed",
            "requested_by": "agent_001",
            "reason": "Approved deployment",
            "agent_id": "agent_001",
            "opa_decision": {"allow": True},
            "validation_result": {"valid": True},
            "execution_result": {"success": True, "message": "Patrol deployed successfully"},
            "writeback_result": None,
            "created_at": "2026-05-21T10:00:00Z",
            "updated_at": "2026-05-21T10:00:05Z",
        })
        mock_get_executor.return_value = mock_executor

        approval_payload = {
            "action_record_id": record_id,
            "approved": True,
            "approver": "commander_01",
            "comment": "Authorized deployment to sector 7",
        }

        response = client.post(f"/api/actions/{record_id}/approve", json=approval_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["action_record_id"] == record_id
        assert data["status"] == "completed"
        assert data["execution_result"]["success"] is True


class TestFeedbackLoop:
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackCollector.collect")
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackAnalyzer.analyze_deviation")
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackAnalyzer.generate_lesson")
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackAggregator.aggregate_and_update")
    def test_feedback_after_action(self, mock_aggregate, mock_lesson, mock_deviation, mock_collect):
        from odap.biz.decision.action_service.feedback_loop import ActionFeedback

        action_record = {
            "action_record_id": "ar_feedback_001",
            "action_type_id": "deploy_unit",
            "target_object_id": "sector_7",
            "target_object_type": "Location",
            "execution_result": {"success": True, "message": "Patrol deployed"},
            "requested_by": "agent_001",
            "agent_id": "agent_001",
        }

        collected_feedback = ActionFeedback(
            action_id="ar_feedback_001",
            decision_id="agent_001",
            outcome="success",
            result_data={"message": "Patrol deployed"},
            timestamp="2026-05-21T10:00:05Z",
        )
        mock_collect.return_value = collected_feedback

        analyzed_feedback = ActionFeedback(
            action_id="ar_feedback_001",
            decision_id="agent_001",
            outcome="success",
            result_data={"message": "Patrol deployed"},
            deviation_score=0.1,
            deviation_factors=[],
            root_causes=[],
            timestamp="2026-05-21T10:00:05Z",
        )
        mock_deviation.return_value = analyzed_feedback

        mock_lesson.return_value = "Action ar_feedback_001 completed successfully."

        mock_aggregate.return_value = {
            "action_id": "ar_feedback_001",
            "outcome": "success",
            "deviation_score": 0.1,
            "lesson_learned": "Action ar_feedback_001 completed successfully.",
        }

        from odap.biz.decision.action_service.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        result = loop.collector.collect(action_record)

        assert result.action_id == "ar_feedback_001"
        assert result.outcome == "success"

    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackCollector.collect")
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackAnalyzer.analyze_deviation")
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackAnalyzer.generate_lesson")
    @patch("odap.biz.decision.action_service.feedback_loop.FeedbackAggregator.aggregate_and_update")
    def test_feedback_analysis(self, mock_aggregate, mock_lesson, mock_deviation, mock_collect):
        from odap.biz.decision.action_service.feedback_loop import ActionFeedback

        action_record = {
            "action_record_id": "ar_fail_001",
            "action_type_id": "deploy_unit",
            "target_object_id": "sector_7",
            "target_object_type": "Location",
            "execution_result": {"success": False, "message": "Unit unavailable"},
            "requested_by": "agent_001",
            "agent_id": "agent_001",
        }

        collected_feedback = ActionFeedback(
            action_id="ar_fail_001",
            decision_id="agent_001",
            outcome="failure",
            result_data=None,
            error_message="Unit unavailable",
            timestamp="2026-05-21T10:00:05Z",
        )
        mock_collect.return_value = collected_feedback

        analyzed_feedback = ActionFeedback(
            action_id="ar_fail_001",
            decision_id="agent_001",
            outcome="failure",
            result_data=None,
            error_message="Unit unavailable",
            deviation_score=0.75,
            deviation_factors=["resource_shortage", "timing_mismatch"],
            root_causes=["insufficient_patrol_units"],
            timestamp="2026-05-21T10:00:05Z",
        )
        mock_deviation.return_value = analyzed_feedback

        mock_lesson.return_value = "Action ar_fail_001 failed. Factors: resource_shortage, timing_mismatch. Root causes: insufficient_patrol_units"

        mock_aggregate.return_value = {
            "action_id": "ar_fail_001",
            "outcome": "failure",
            "deviation_score": 0.75,
            "deviation_factors": ["resource_shortage", "timing_mismatch"],
            "root_causes": ["insufficient_patrol_units"],
            "lesson_learned": "Action ar_fail_001 failed. Factors: resource_shortage, timing_mismatch. Root causes: insufficient_patrol_units",
        }

        from odap.biz.decision.action_service.feedback_loop import FeedbackLoop

        loop = FeedbackLoop()
        feedback = loop.collector.collect(action_record)
        feedback = loop.analyzer.analyze_deviation(feedback, expected_outcome={"success": True})

        assert feedback.deviation_score == 0.75
        assert "resource_shortage" in feedback.deviation_factors
        assert len(feedback.root_causes) == 1
