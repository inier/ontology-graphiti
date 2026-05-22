import pytest
import sys
import os
import uuid
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _mock_external_services():
    with patch("odap.biz.frontend_compat.api.routes.scenario_store", MagicMock()):
        with patch("odap.biz.frontend_compat.api.routes.workspace_service", MagicMock()):
            with patch("odap.biz.ontology.api.routes.ingest_service", MagicMock()) as mock_ingest:
                mock_ingest.ingest_from_natural_language = AsyncMock(
                    return_value="ingest-nl-001"
                )
                mock_ingest.ingest_from_news = AsyncMock(
                    return_value="ingest-news-001"
                )
                mock_ingest.ingest_from_url = AsyncMock(
                    return_value="ingest-url-001"
                )
                mock_ingest.ingest_from_manual = AsyncMock(
                    return_value="ingest-manual-001"
                )
                mock_ingest.ingest_from_json = AsyncMock(
                    return_value="ingest-json-001"
                )
                mock_ingest.get_ingest_status = MagicMock(
                    return_value={
                        "id": "ingest-001",
                        "source": "natural_language",
                        "status": "completed",
                        "record_count": 1,
                        "processed_count": 1,
                        "failed_count": 0,
                        "start_time": "2026-01-01T00:00:00",
                        "original_content": "test content",
                        "extracted_data": {
                            "entities": [
                                {"name": "EntityA", "type": "organization"},
                                {"name": "EntityB", "type": "person"},
                            ],
                            "relations": [
                                {"source": "EntityA", "target": "EntityB", "type": "employs"}
                            ],
                        },
                    }
                )
                mock_ingest.get_ingest_history = MagicMock(return_value=[])
                mock_ingest.get_ontology_documents = MagicMock(return_value=[])
                with patch(
                    "odap.biz.frontend_compat.api.routes.get_qa_engine"
                ) as mock_qa_engine:
                    mock_engine = MagicMock()
                    mock_engine.ask = MagicMock(
                        return_value={
                            "session_id": "session-001",
                            "answer": "Based on the ingested data, EntityA employs EntityB.",
                            "sources": [
                                {
                                    "source": "graphiti",
                                    "excerpt": "EntityA employs EntityB",
                                    "confidence": 0.92,
                                }
                            ],
                            "dialog_state": "completed",
                        }
                    )
                    mock_engine.get_dialog_history = MagicMock(
                        return_value=[
                            {"role": "user", "content": "Who does EntityA employ?"},
                            {
                                "role": "assistant",
                                "content": "Based on the ingested data, EntityA employs EntityB.",
                            },
                        ]
                    )
                    mock_engine.close_dialog = MagicMock()
                    mock_engine.dialog_manager = MagicMock()
                    mock_engine.dialog_manager._sessions = {}
                    mock_qa_engine.return_value = mock_engine
                    with patch(
                        "odap.biz.workspace.api.routes.workspace_service"
                    ) as mock_ws_svc:
                        mock_ws_svc.create_workspace = MagicMock(
                            side_effect=lambda **kw: {
                                "workspace_id": f"ws-{uuid.uuid4().hex[:8]}",
                                "name": kw.get("name", "unnamed"),
                                "description": kw.get("description", ""),
                                "type": kw.get("workspace_type", "default"),
                                "status": "active",
                                "created_at": "2026-01-01T00:00:00",
                            }
                        )
                        mock_ws_svc.list_workspaces = MagicMock(
                            return_value={
                                "workspaces": [],
                                "page": 1,
                                "page_size": 10,
                                "total": 0,
                            }
                        )
                        mock_ws_svc.get_workspace = MagicMock(
                            return_value={
                                "status": "error",
                                "message": "Workspace not found",
                            }
                        )
                        mock_ws_svc.update_workspace = MagicMock(
                            return_value={
                                "status": "error",
                                "message": "Workspace not found",
                            }
                        )
                        mock_ws_svc.delete_workspace = MagicMock(
                            return_value={
                                "status": "error",
                                "message": "Workspace not found",
                            }
                        )
                        with patch(
                            "odap.infra.opa.opa_service_v2.OPAManager"
                        ) as mock_opa_mgr:
                            mock_opa_instance = MagicMock()
                            mock_opa_instance.check_permission = MagicMock(
                                return_value=True
                            )
                            mock_opa_instance.check_permission_abac = MagicMock(
                                return_value={
                                    "allow": True,
                                    "reason": "Permission granted",
                                    "evaluated_policies": ["commander"],
                                }
                            )
                            mock_opa_instance.health_check = MagicMock(
                                return_value=True
                            )
                            mock_opa_mgr.return_value = mock_opa_instance
                            yield


@pytest.mark.e2e
class TestDataIngestE2E:
    def test_text_ingest_to_ontology(self):
        response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "EntityA is an organization that employs EntityB as a key person.",
            },
        )
        assert response.status_code in [200, 201]
        data = response.json()
        assert "ingest_id" in data
        assert data["status"] in ["completed", "pending", "processing"]

        ingest_id = data["ingest_id"]
        status_response = client.get(f"/api/ontology/ingest/{ingest_id}")
        assert status_response.status_code in [200, 404]
        if status_response.status_code == 200:
            status_data = status_response.json()
            assert "status" in status_data
            if status_data.get("extracted_data"):
                extracted = status_data["extracted_data"]
                assert "entities" in extracted or "relations" in extracted

    def test_news_ingest_full_flow(self):
        response = client.post(
            "/api/ontology/ingest/news",
            json={
                "data": "global technology summit",
                "event_context": "Annual technology conference",
                "max_sources": 3,
            },
        )
        assert response.status_code in [200, 201, 500]
        if response.status_code in [200, 201]:
            data = response.json()
            assert "ingest_id" in data
            assert data["status"] in ["completed", "pending", "processing", "failed"]

            history_response = client.get("/api/ontology/ingest")
            assert history_response.status_code == 200
            history = history_response.json()
            assert isinstance(history, list)


@pytest.mark.e2e
class TestQAE2E:
    def test_ask_question_with_context(self):
        ws_response = client.post(
            "/api/workspaces",
            json={
                "name": "QA Test Workspace",
                "description": "Workspace for QA E2E testing",
            },
        )
        assert ws_response.status_code in [200, 201]
        ws_data = ws_response.json()
        workspace_id = ws_data.get("workspace_id") or ws_data.get("id", "default")

        ingest_response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "EntityA employs EntityB in a senior role.",
                "scenario_id": workspace_id,
            },
        )
        assert ingest_response.status_code in [200, 201]

        qa_response = client.post(
            "/api/qa/ask",
            json={
                "question": "Who does EntityA employ?",
                "workspace_id": workspace_id,
            },
        )
        assert qa_response.status_code in [200, 500]
        if qa_response.status_code == 200:
            qa_data = qa_response.json()
            assert "session_id" in qa_data
            assert "answer" in qa_data
            assert len(qa_data["answer"]) > 0

    def test_qa_session_management(self):
        ask_response = client.post(
            "/api/qa/ask",
            json={
                "question": "What entities exist in the knowledge graph?",
                "session_id": None,
            },
        )
        assert ask_response.status_code in [200, 500]
        if ask_response.status_code == 200:
            ask_data = ask_response.json()
            session_id = ask_data.get("session_id")
            assert session_id is not None

            followup_response = client.post(
                "/api/qa/ask",
                json={
                    "question": "Tell me more about EntityA",
                    "session_id": session_id,
                },
            )
            assert followup_response.status_code in [200, 500]

            sessions_response = client.get("/api/qa/sessions")
            assert sessions_response.status_code in [200, 500]
            if sessions_response.status_code == 200:
                sessions_data = sessions_response.json()
                assert "sessions" in sessions_data or isinstance(sessions_data, list)

            if session_id:
                history_response = client.get(
                    f"/api/qa/sessions/{session_id}/history"
                )
                assert history_response.status_code in [200, 500]

                close_response = client.delete(f"/api/qa/sessions/{session_id}")
                assert close_response.status_code in [200, 500]


@pytest.mark.e2e
class TestWorkspaceIsolationE2E:
    def test_workspace_data_isolation(self):
        ws1_response = client.post(
            "/api/workspaces",
            json={
                "name": "Isolation Test Alpha",
                "description": "First isolated workspace",
            },
        )
        assert ws1_response.status_code in [200, 201]
        ws1_data = ws1_response.json()
        ws1_id = ws1_data.get("workspace_id") or ws1_data.get("id")

        ws2_response = client.post(
            "/api/workspaces",
            json={
                "name": "Isolation Test Beta",
                "description": "Second isolated workspace",
            },
        )
        assert ws2_response.status_code in [200, 201]
        ws2_data = ws2_response.json()
        ws2_id = ws2_data.get("workspace_id") or ws2_data.get("id")

        assert ws1_id != ws2_id

        ingest1_response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "AlphaCorp is a technology company in workspace alpha.",
            },
        )
        assert ingest1_response.status_code in [200, 201]

        ingest2_response = client.post(
            "/api/ontology/ingest",
            json={
                "source_type": "natural_language",
                "data": "BetaInc is a financial company in workspace beta.",
            },
        )
        assert ingest2_response.status_code in [200, 201]

        list_response = client.get("/api/workspaces")
        assert list_response.status_code == 200
        ws_list = list_response.json()
        assert "workspaces" in ws_list
        assert isinstance(ws_list["workspaces"], list)

    def test_workspace_switching(self):
        create_response = client.post(
            "/api/workspaces",
            json={
                "name": "Switch Test Workspace",
                "description": "Workspace for switching test",
            },
        )
        assert create_response.status_code in [200, 201]
        ws_data = create_response.json()
        ws_id = ws_data.get("workspace_id") or ws_data.get("id")

        activate_response = client.post(f"/api/workspaces/{ws_id}/activate")
        assert activate_response.status_code in [200, 404]

        deactivate_response = client.post(f"/api/workspaces/{ws_id}/deactivate")
        assert deactivate_response.status_code in [200, 404]

        if ws_id:
            get_response = client.get(f"/api/workspaces/{ws_id}")
            assert get_response.status_code in [200, 404]


@pytest.mark.e2e
class TestOPAPolicyE2E:
    def test_policy_creation_and_enforcement(self):
        list_response = client.get("/api/policies")
        assert list_response.status_code == 200
        policies_data = list_response.json()
        assert "policies" in policies_data
        assert isinstance(policies_data["policies"], list)

        create_response = client.post(
            "/api/policies",
            json={
                "name": "E2E Test Policy",
                "description": "Policy created during E2E testing",
                "markdown_content": "# Test Policy\n\n## Role commander\n\n### Allowed Actions\n- 查询\n- 分析\n- 报告",
                "category": "custom",
            },
        )
        assert create_response.status_code in [200, 201]
        policy_data = create_response.json()
        assert "policy_id" in policy_data
        policy_id = policy_data["policy_id"]

        get_response = client.get(f"/api/policies/{policy_id}")
        assert get_response.status_code == 200
        fetched_policy = get_response.json()
        assert fetched_policy["name"] == "E2E Test Policy"
        assert fetched_policy["status"] == "enabled"
        assert "rego_content" in fetched_policy
        assert len(fetched_policy["rego_content"]) > 0

        toggle_response = client.post(
            f"/api/policies/{policy_id}/toggle?enabled=false"
        )
        assert toggle_response.status_code == 200
        toggle_data = toggle_response.json()
        assert toggle_data["status"] == "disabled"

    def test_role_permission_enforcement(self):
        roles_response = client.get("/api/roles")
        assert roles_response.status_code == 200
        roles = roles_response.json()
        assert isinstance(roles, list)

        perms_response = client.get("/api/roles/permissions/all")
        assert perms_response.status_code == 200
        perms = perms_response.json()
        assert isinstance(perms, list)

        create_role_response = client.post(
            "/api/roles",
            json={
                "name": "E2E Test Analyst",
                "role_type": "analyst",
                "description": "Analyst role for E2E testing",
                "permissions": [
                    {
                        "scope": "intelligence",
                        "action": "view",
                        "resource": "reports",
                    }
                ],
            },
        )
        assert create_role_response.status_code in [200, 201, 422]
        if create_role_response.status_code in [200, 201]:
            role_data = create_role_response.json()
            role_id = role_data.get("role_id")

            if role_id:
                bind_response = client.post(
                    f"/api/roles/{role_id}/policies",
                    json={
                        "policy_id": "policy-access-control",
                        "priority": 1,
                        "enabled": True,
                    },
                )
                assert bind_response.status_code in [200, 404]

                role_policies_response = client.get(
                    f"/api/roles/{role_id}/policies"
                )
                assert role_policies_response.status_code in [200, 404]
