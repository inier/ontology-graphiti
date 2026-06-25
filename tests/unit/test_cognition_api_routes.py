"""Cognition API 路由层 + 服务层单元测试

覆盖：
- odap/biz/core/cognition/api/routes.py — 路由 HTTP 状态码映射
- odap/biz/core/cognition/services/cognition_service.py — 服务层返回 dict 格式
- odap/biz/core/cognition/api/schemas.py — 请求/响应 schema

验证点（AGENTS.md 规则 2/3）：
- 服务层返回 {"status": "error"} 时路由翻译为 HTTPException
- 路由层 except HTTPException: raise 透传
- 400（参数校验） / 500（服务错误） / 503（引擎不可用） 状态码映射
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ============================================================
# Fixtures
# ============================================================


def _build_app():
    """构建仅含 cognition 路由的 FastAPI 应用。"""
    from odap.biz.core.cognition.api.routes import router
    from odap.infra.security.jwt_auth import get_current_user

    app = FastAPI()
    app.include_router(router)

    async def _mock_user():
        return {"sub": "u-test", "role": "admin", "ws_id": "ws-1", "ws_role": "owner"}

    app.dependency_overrides[get_current_user] = _mock_user
    return app


@pytest.fixture
def client():
    app = _build_app()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_service():
    """Mock get_cognition_service 返回的 CognitionService。"""
    svc = MagicMock()
    svc.recognize_intent = MagicMock(
        return_value={
            "intent_id": "i-001",
            "primary_intent": "query",
            "confidence": 0.88,
            "entities": ["销售"],
            "attributes": {"time": "Q1"},
            "alternative_intents": ["report"],
        }
    )
    svc.navigate = MagicMock(
        return_value={
            "navigation_id": "n-001",
            "entity_id": "Customer",
            "navigation_path": ["Customer", "Order"],
            "related_entities": [{"id": "Order", "type": "event"}],
            "entity_context": {"name": "客户"},
        }
    )
    svc.explain = MagicMock(
        return_value={
            "explanation_id": "e-001",
            "decision_id": "d-001",
            "query": "why approve?",
            "answer": "因为风险低",
            "confidence": 0.9,
            "reasoning_chain": [{"step": 1, "result": "low risk"}],
            "sources": ["rule-1"],
        }
    )
    svc.get_role_view = MagicMock(
        return_value={
            "view_id": "v-001",
            "role": "analyst",
            "name": "分析师视图",
            "description": "数据分析视图",
            "capabilities": ["query", "export"],
            "layout_config": {"columns": 2},
            "filters": {"date": "today"},
        }
    )
    svc.update_role_view = MagicMock(
        return_value={"status": "ok", "view_id": "v-001"}
    )
    with patch(
        "odap.biz.core.cognition.api.routes.get_cognition_service",
        return_value=svc,
    ):
        yield svc


# ============================================================
# 1. POST /api/cognition/recognize-intent
# ============================================================


class TestRecognizeIntent:
    """意图识别端点。"""

    def test_recognize_success(self, client, mock_service):
        """成功识别返回 200。"""
        resp = client.post(
            "/api/cognition/recognize-intent",
            json={"input_text": "分析销售数据", "role": "analyst"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent_id"] == "i-001"
        assert data["primary_intent"] == "query"
        assert data["confidence"] == 0.88

    def test_recognize_empty_input_returns_400(self, client, mock_service):
        """空 input_text 返回 400。"""
        resp = client.post(
            "/api/cognition/recognize-intent",
            json={"input_text": "", "role": "analyst"},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    def test_recognize_service_error_returns_500(self, client, mock_service):
        """服务层返回 status=error 时翻译为 500。"""
        mock_service.recognize_intent = MagicMock(
            return_value={"status": "error", "message": "model unavailable"}
        )
        resp = client.post(
            "/api/cognition/recognize-intent",
            json={"input_text": "x"},
        )
        assert resp.status_code == 500

    def test_recognize_exception_returns_503(self, client, mock_service):
        """服务层抛异常时返回 503（HTTPException 透传验证）。"""
        mock_service.recognize_intent = MagicMock(side_effect=RuntimeError("boom"))
        resp = client.post(
            "/api/cognition/recognize-intent",
            json={"input_text": "x"},
        )
        assert resp.status_code == 503


# ============================================================
# 2. POST /api/cognition/navigate
# ============================================================


class TestNavigate:
    """知识导航端点。"""

    def test_navigate_success(self, client, mock_service):
        """成功导航返回 200。"""
        resp = client.post(
            "/api/cognition/navigate",
            json={"entity_id": "Customer", "direction": "outbound", "depth": 2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["navigation_id"] == "n-001"
        assert data["entity_id"] == "Customer"
        assert len(data["navigation_path"]) == 2

    def test_navigate_empty_entity_returns_400(self, client, mock_service):
        """空 entity_id 返回 400。"""
        resp = client.post(
            "/api/cognition/navigate",
            json={"entity_id": ""},
        )
        assert resp.status_code == 400

    def test_navigate_service_error_returns_500(self, client, mock_service):
        """服务层返回 status=error 时翻译为 500。"""
        mock_service.navigate = MagicMock(
            return_value={"status": "error", "message": "graph disconnected"}
        )
        resp = client.post(
            "/api/cognition/navigate",
            json={"entity_id": "x"},
        )
        assert resp.status_code == 500


# ============================================================
# 3. POST /api/cognition/explain
# ============================================================


class TestExplain:
    """决策解释端点。"""

    def test_explain_success(self, client, mock_service):
        """成功解释返回 200。"""
        resp = client.post(
            "/api/cognition/explain",
            json={"decision_id": "d-001", "context": {"q": "why"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["explanation_id"] == "e-001"
        assert data["decision_id"] == "d-001"
        assert data["answer"] == "因为风险低"

    def test_explain_empty_decision_returns_400(self, client, mock_service):
        """空 decision_id 返回 400。"""
        resp = client.post(
            "/api/cognition/explain",
            json={"decision_id": ""},
        )
        assert resp.status_code == 400

    def test_explain_service_error_returns_500(self, client, mock_service):
        """服务层返回 status=error 时翻译为 500。"""
        mock_service.explain = MagicMock(
            return_value={"status": "error", "message": "no trace"}
        )
        resp = client.post(
            "/api/cognition/explain",
            json={"decision_id": "x"},
        )
        assert resp.status_code == 500


# ============================================================
# 4. CognitionService 服务层（返回 dict 格式验证）
# ============================================================


class TestCognitionService:
    """CognitionService 服务层返回值格式。"""

    def test_recognize_intent_returns_dict_on_success(self):
        """成功时返回扁平 dict（非 Pydantic 模型）。"""
        from odap.biz.core.cognition.services.cognition_service import CognitionService

        svc = CognitionService()
        with patch(
            "odap.biz.core.cognition.impl.intent_recognizer.IntentRecognizer"
        ) as mock_cls:
            mock_inst = MagicMock()
            mock_inst.recognize.return_value = {
                "intent_id": "i-1",
                "primary_intent": "query",
                "confidence": 0.9,
            }
            mock_cls.return_value = mock_inst
            result = svc.recognize_intent("test", "analyst")
            assert isinstance(result, dict)
            assert result["intent_id"] == "i-1"

    def test_recognize_intent_returns_error_dict_on_exception(self):
        """异常时返回 {"status": "error", "message": ...}（不抛 HTTPException）。"""
        from odap.biz.core.cognition.services.cognition_service import CognitionService

        svc = CognitionService()
        with patch(
            "odap.biz.core.cognition.impl.intent_recognizer.IntentRecognizer",
            side_effect=ImportError("missing dep"),
        ):
            result = svc.recognize_intent("test", "analyst")
            assert result["status"] == "error"
            assert "missing dep" in result["message"]

    def test_navigate_returns_error_dict_on_exception(self):
        """navigate 异常时返回 error dict。"""
        from odap.biz.core.cognition.services.cognition_service import CognitionService

        svc = CognitionService()
        with patch(
            "odap.biz.core.cognition.impl.knowledge_navigator.KnowledgeNavigator",
            side_effect=RuntimeError("no graph"),
        ):
            result = svc.navigate("x")
            assert result["status"] == "error"
            assert "no graph" in result["message"]


# ============================================================
# 5. Schema 验证
# ============================================================


class TestCognitionSchemas:
    """Cognition 请求/响应 schema 验证。"""

    def test_recognize_request_defaults(self):
        """RecognizeIntentRequest 默认值正确。"""
        from odap.biz.core.cognition.api.schemas import RecognizeIntentRequest

        req = RecognizeIntentRequest(input_text="x")
        assert req.input_text == "x"
        assert req.role == "guest"
        assert req.ontology_facts == []  # default_factory

    def test_navigate_request_defaults(self):
        """NavigateRequest 默认值正确。"""
        from odap.biz.core.cognition.api.schemas import NavigateRequest

        req = NavigateRequest(entity_id="x")
        assert req.entity_id == "x"
        assert req.direction == "outbound"
        assert req.depth == 1

    def test_explain_request_defaults(self):
        """ExplainRequest 默认值正确。"""
        from odap.biz.core.cognition.api.schemas import ExplainRequest

        req = ExplainRequest(decision_id="x")
        assert req.decision_id == "x"
        assert req.context == {}  # default_factory

    def test_response_models_use_default_factory(self):
        """响应模型的容器字段使用 default_factory。"""
        from odap.biz.core.cognition.api.schemas import (
            RecognizeIntentResponse,
            NavigateResponse,
        )

        r1 = RecognizeIntentResponse()
        assert r1.entities == []
        assert r1.attributes == {}

        r2 = NavigateResponse()
        assert r2.navigation_path == []
        assert r2.related_entities == []
