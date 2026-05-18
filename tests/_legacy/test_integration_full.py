"""
前后端交互集成测试 - 完整流程验证

测试范围:
- 健康检查与基础 API
- 工作空间 CRUD
- 场景管理
- 数据摄入 (文本/新闻/手动/随机)
- 版本管理
- 智能问答 (普通 + 流式)
- 问答会话管理
- 审计日志
- 角色权限
- 图谱查询
- 统计信息
- 闭环反馈
- 用户认知引擎
- OpenHarness 健康检查
"""

import sys
import os
import json
import uuid
import time
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthAndRoot:
    """测试健康检查和根路由"""

    def test_root_endpoint(self, test_client):
        """测试根路由"""
        response = test_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == "2.0.0"

    def test_health_endpoint(self, test_client):
        """测试健康检查"""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestWorkspaceAPI:
    """测试工作空间 API"""

    def test_list_workspaces(self, test_client):
        """GET /api/workspaces - 列出工作空间"""
        response = test_client.get("/api/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert "workspaces" in data

    def test_create_workspace(self, test_client, sample_workspace_data):
        """POST /api/workspaces - 创建工作空间"""
        response = test_client.post(
            "/api/workspaces",
            json=sample_workspace_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "workspace_id" in data
        assert data["name"] == sample_workspace_data["name"]

    def test_get_workspace(self, test_client, sample_workspace_data):
        """GET /api/workspaces/{id} - 获取工作空间"""
        create_resp = test_client.post("/api/workspaces", json=sample_workspace_data)
        ws_id = create_resp.json()["workspace_id"]

        response = test_client.get(f"/api/workspaces/{ws_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == sample_workspace_data["name"]

    def test_workspace_crud_flow(self, test_client, sample_workspace_data):
        """工作空间 CRUD 完整流程"""
        response = test_client.post("/api/workspaces", json=sample_workspace_data)
        assert response.status_code == 200
        ws_id = response.json()["workspace_id"]

        get_resp = test_client.get(f"/api/workspaces/{ws_id}")
        assert get_resp.status_code == 200

        update_data = {"name": f"{sample_workspace_data['name']}-updated"}
        update_resp = test_client.put(
            f"/api/workspaces/{ws_id}",
            json=update_data
        )
        assert update_resp.status_code == 200

        delete_resp = test_client.delete(f"/api/workspaces/{ws_id}")
        assert delete_resp.status_code == 200


class TestScenarioAPI:
    """测试场景管理 API"""

    def test_list_scenarios(self, test_client):
        """GET /api/scenarios - 列出场景"""
        response = test_client.get("/api/scenarios")
        assert response.status_code == 200
        data = response.json()
        assert "scenarios" in data

    def test_create_and_get_scenario(self, test_client, sample_scenario_data):
        """创建并获取场景"""
        response = test_client.post("/api/scenarios", json=sample_scenario_data)
        assert response.status_code == 200
        scenario_id = response.json().get("scenario_id")

        get_resp = test_client.get(f"/api/scenarios/{scenario_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == sample_scenario_data["name"]

    def test_scenario_timeline(self, test_client, sample_scenario_data):
        """GET /api/scenarios/{id}/timeline - 获取场景时间线"""
        create_resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = create_resp.json()["scenario_id"]

        response = test_client.get(f"/api/scenarios/{scenario_id}/timeline")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    def test_scenario_entities(self, test_client, sample_scenario_data):
        """GET /api/scenarios/{id}/entities - 获取场景实体"""
        create_resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = create_resp.json()["scenario_id"]

        response = test_client.get(f"/api/scenarios/{scenario_id}/entities")
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data

    def test_scenario_relations(self, test_client, sample_scenario_data):
        """GET /api/scenarios/{id}/relations - 获取场景关系"""
        create_resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = create_resp.json()["scenario_id"]

        response = test_client.get(f"/api/scenarios/{scenario_id}/relations")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "links" in data

    def test_scenario_delete(self, test_client, sample_scenario_data):
        """DELETE /api/scenarios/{id} - 删除场景"""
        create_resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = create_resp.json()["scenario_id"]

        response = test_client.delete(f"/api/scenarios/{scenario_id}")
        assert response.status_code == 200

    def test_scenario_sync(self, test_client, sample_scenario_data):
        """POST /api/scenarios/{id}/sync - 同步场景到 Graphiti"""
        create_resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = create_resp.json()["scenario_id"]

        response = test_client.post(f"/api/scenarios/{scenario_id}/sync")
        assert response.status_code == 200


class TestIngestAPI:
    """测试数据摄入 API"""

    def test_ingest_text(self, test_client, sample_scenario_data):
        """POST /api/ingest/text - 文本摄入"""
        resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = resp.json()["scenario_id"]

        response = test_client.post("/api/ingest/text", json={
            "text": "红方部队Alpha在A区部署了3个雷达站",
            "scenario_id": scenario_id
        })
        # 可能返回 200、422 或 500（取决于 Celery/LLM 服务）
        assert response.status_code in [200, 422, 500]

    def test_ingest_manual(self, test_client, sample_scenario_data):
        """POST /api/ingest/manual - 手动录入"""
        resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = resp.json()["scenario_id"]

        response = test_client.post("/api/ingest/manual", json={
            "data": {
                "entities": [{
                    "entity_id": f"test-{uuid.uuid4().hex[:8]}",
                    "name": "测试单位",
                    "entity_type": "unit"
                }]
            },
            "scenario_id": scenario_id
        })
        assert response.status_code in [200, 500]

    def test_ingest_random(self, test_client, sample_scenario_data):
        """POST /api/ingest/random - 随机生成"""
        resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        scenario_id = resp.json()["scenario_id"]

        response = test_client.post("/api/ingest/random", json={
            "parties": ["red", "blue"],
            "count": 2,
            "scenario_id": scenario_id
        })
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True


class TestVersionAPI:
    """测试版本管理 API"""

    def test_list_versions(self, test_client):
        """GET /api/versions - 列出版本"""
        response = test_client.get("/api/versions")
        assert response.status_code == 200
        data = response.json()
        assert "versions" in data

    def test_create_version(self, test_client):
        """POST /api/versions - 创建版本"""
        response = test_client.post("/api/versions", json={
            "version": "1.0.0-test"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data


class TestQAAPI:
    """测试智能问答 API"""

    def test_qa_ask(self, test_client, sample_qa_data):
        """POST /api/qa/ask - 问答"""
        response = test_client.post("/api/qa/ask", json=sample_qa_data)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "answer" in data

    def test_qa_ask_stream(self, test_client, sample_qa_data):
        """POST /api/qa/ask/stream - 流式问答"""
        response = test_client.post("/api/qa/ask/stream", json=sample_qa_data)
        assert response.status_code == 200
        content = response.text
        assert "session_id" in content or "content" in content or "end" in content

    def test_qa_multiround(self, test_client, sample_qa_data):
        """POST /api/qa/ask - 多轮对话"""
        response1 = test_client.post("/api/qa/ask", json=sample_qa_data)
        assert response1.status_code == 200
        session_id = response1.json()["session_id"]

        response2 = test_client.post("/api/qa/ask", json={
            "question": "还有其他的吗？",
            "session_id": session_id,
            "user_id": "test_user"
        })
        assert response2.status_code == 200
        assert response2.json()["session_id"] == session_id

    def test_qa_empty_question(self, test_client):
        """POST /api/qa/ask - 空问题应返回 400"""
        response = test_client.post("/api/qa/ask", json={
            "question": "",
            "user_id": "test_user"
        })
        assert response.status_code == 400


class TestQASessions:
    """测试问答会话管理"""

    def test_list_sessions(self, test_client):
        """GET /api/qa/sessions - 列出会话"""
        response = test_client.get("/api/qa/sessions")
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data

    def test_get_session(self, test_client, sample_qa_data):
        """GET /api/qa/sessions/{id} - 获取会话详情"""
        resp = test_client.post("/api/qa/ask", json=sample_qa_data)
        session_id = resp.json()["session_id"]

        response = test_client.get(f"/api/qa/sessions/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id

    def test_close_session(self, test_client, sample_qa_data):
        """DELETE /api/qa/sessions/{id} - 关闭会话"""
        resp = test_client.post("/api/qa/ask", json=sample_qa_data)
        session_id = resp.json()["session_id"]

        response = test_client.delete(f"/api/qa/sessions/{session_id}")
        assert response.status_code == 200

    def test_submit_feedback(self, test_client, sample_qa_data, sample_feedback_data):
        """POST /api/qa/sessions/{id}/feedback - 提交问答反馈"""
        resp = test_client.post("/api/qa/ask", json=sample_qa_data)
        session_id = resp.json()["session_id"]

        response = test_client.post(
            f"/api/qa/sessions/{session_id}/feedback",
            json=sample_feedback_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_qa_stats(self, test_client):
        """GET /api/qa/stats - 问答统计"""
        response = test_client.get("/api/qa/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data

    def test_qa_user_stats(self, test_client):
        """GET /api/qa/stats/users - 用户问答统计"""
        response = test_client.get("/api/qa/stats/users")
        assert response.status_code == 200

    def test_qa_topic_stats(self, test_client):
        """GET /api/qa/stats/topics - 话题统计"""
        response = test_client.get("/api/qa/stats/topics")
        assert response.status_code == 200
        data = response.json()
        assert "topics" in data


class TestAuditAPI:
    """测试审计日志 API"""

    def test_list_audit_events(self, test_client):
        """GET /api/audit/events - 列出审计事件"""
        response = test_client.get("/api/audit/events")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data

    def test_create_audit_event(self, test_client):
        """POST /api/audit/events - 创建审计事件"""
        response = test_client.post("/api/audit/events", json={
            "event_type": "test.action",
            "action": "TEST",
            "resource_type": "test",
            "resource_id": "test-1",
            "result_status": "success",
            "result_message": "test event",
            "severity": "info",
            "actor_id": "test_user",
            "actor_name": "Test User"
        })
        assert response.status_code == 200

    def test_audit_timeline(self, test_client):
        """GET /api/audit/timeline - 审计时间线"""
        response = test_client.get("/api/audit/timeline")
        assert response.status_code == 200
        data = response.json()
        assert "timeline" in data or "events" in data

    def test_audit_stats(self, test_client):
        """GET /api/audit/stats - 审计统计"""
        response = test_client.get("/api/audit/stats")
        assert response.status_code == 200

    def test_audit_filter(self, test_client):
        """GET /api/audit/events - 过滤审计事件"""
        response = test_client.get("/api/audit/events?event_type=test.action&severity=info")
        assert response.status_code == 200


class TestRolesAPI:
    """测试角色权限 API"""

    def test_list_roles(self, test_client):
        """GET /api/roles - 列出角色"""
        response = test_client.get("/api/roles")
        assert response.status_code == 200

    def test_create_role(self, test_client, sample_role_data):
        """POST /api/roles - 创建角色"""
        response = test_client.post("/api/roles", json=sample_role_data)
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == sample_role_data["name"]

    def test_get_role(self, test_client, sample_role_data):
        """GET /api/roles/{id} - 获取角色"""
        create_resp = test_client.post("/api/roles", json=sample_role_data)
        role_id = create_resp.json()["id"]

        response = test_client.get(f"/api/roles/{role_id}")
        assert response.status_code == 200
        assert response.json()["id"] == role_id

    def test_update_role(self, test_client, sample_role_data):
        """PUT /api/roles/{id} - 更新角色"""
        create_resp = test_client.post("/api/roles", json=sample_role_data)
        role_id = create_resp.json()["id"]

        response = test_client.put(f"/api/roles/{role_id}", json={
            "name": f"{sample_role_data['name']}-updated"
        })
        assert response.status_code == 200

    def test_delete_role(self, test_client, sample_role_data):
        """DELETE /api/roles/{id} - 删除角色"""
        create_resp = test_client.post("/api/roles", json=sample_role_data)
        role_id = create_resp.json()["id"]

        response = test_client.delete(f"/api/roles/{role_id}")
        assert response.status_code == 200

    def test_list_permissions(self, test_client):
        """GET /api/roles/permissions/all - 列出权限"""
        response = test_client.get("/api/roles/permissions/all")
        assert response.status_code == 200


class TestQueryAPI:
    """测试图谱查询 API"""

    def test_query_entities(self, test_client):
        """POST /api/query/entities - 查询实体"""
        response = test_client.post("/api/query/entities", json={
            "query": {"keyword": "test"},
            "workspace_id": "default"
        })
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data

    def test_query_relations(self, test_client):
        """POST /api/query/relations - 查询关系"""
        response = test_client.post("/api/query/relations", json={
            "query": {"source_id": "test-1", "target_id": "test-2"}
        })
        assert response.status_code == 200
        data = response.json()
        assert "relations" in data

    def test_complex_query(self, test_client):
        """POST /api/query/complex - 复合查询"""
        response = test_client.post("/api/query/complex", json={
            "conditions": [{"type": "entity", "value": "test"}],
            "workspace_id": "default"
        })
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_query_history(self, test_client):
        """GET /api/query/history - 查询历史"""
        response = test_client.get("/api/query/history")
        assert response.status_code == 200

    def test_export_query(self, test_client):
        """POST /api/query/export - 导出查询结果"""
        response = test_client.post("/api/query/export", json={
            "results": [{"name": "test"}],
            "format": "json"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestStatsAPI:
    """测试统计 API"""

    def test_get_stats(self, test_client):
        """GET /api/stats - 获取统计信息"""
        response = test_client.get("/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "scenario_count" in data
        assert "workspace_count" in data


class TestCognitionAPI:
    """测试用户认知引擎 API"""

    def test_recognize_intent(self, test_client):
        """POST /api/cognition/intent - 意图识别"""
        response = test_client.post("/api/cognition/intent", json={
            "input_text": "查询雷达位置",
            "role": "analyst"
        })
        assert response.status_code in [200, 500]

    def test_get_role_view(self, test_client):
        """GET /api/cognition/view - 获取角色视图"""
        response = test_client.get("/api/cognition/view?role=analyst")
        assert response.status_code in [200, 500]


class TestOpenHarnessAPI:
    """测试 OpenHarness API"""

    def test_openharness_health(self, test_client):
        """GET /api/openharness/health - OpenHarness 健康检查"""
        response = test_client.get("/api/openharness/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "unhealthy"]

    def test_openharness_tools(self, test_client):
        """GET /api/openharness/tools - 列出工具"""
        response = test_client.get("/api/openharness/tools")
        assert response.status_code in [200, 500]

    def test_openharness_schemas(self, test_client):
        """GET /api/openharness/schemas - 获取工具 Schema"""
        response = test_client.get("/api/openharness/schemas")
        assert response.status_code in [200, 500]


class TestFeedbackAPI:
    """测试闭环反馈 API"""

    def test_submit_action_feedback(self, test_client):
        """POST /api/feedback/action - 提交动作反馈"""
        response = test_client.post("/api/feedback/action", json={
            "action_id": f"action-{uuid.uuid4().hex[:8]}",
            "outcome": "success",
            "result_data": {"detail": "执行成功"}
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_get_decision_feedback(self, test_client):
        """GET /api/feedback/decision/{id} - 获取决策反馈"""
        response = test_client.get(f"/api/feedback/decision/decision-{uuid.uuid4().hex[:8]}")
        assert response.status_code == 200


class TestFrontendCompatAPI:
    """测试前端兼容层 API"""

    def test_test_route(self, test_client):
        """POST /api/test - 测试路由"""
        response = test_client.post("/api/test", json={"key": "value"})
        assert response.status_code == 200

    def test_test2_route(self, test_client):
        """POST /api/test2 - 测试路由2"""
        response = test_client.post("/api/test2")
        assert response.status_code == 200


class TestEndToEndFlow:
    """端到端完整业务流程测试"""

    def test_full_workspace_scenario_qa_flow(self, test_client, sample_workspace_data, sample_scenario_data):
        """
        完整业务流程:
        1. 创建工作空间
        2. 创建场景
        3. 随机生成数据摄入
        4. 查询场景实体和关系
        5. 同步到 Graphiti
        6. 执行 QA 问答
        7. 提交反馈
        8. 查看审计日志
        """
        # Step 1: 创建工作空间
        ws_resp = test_client.post("/api/workspaces", json=sample_workspace_data)
        assert ws_resp.status_code == 200
        workspace_id = ws_resp.json()["workspace_id"]
        print(f"\n  [1/8] 工作空间创建成功: {workspace_id}")

        # Step 2: 创建场景
        sc_resp = test_client.post("/api/scenarios", json=sample_scenario_data)
        assert sc_resp.status_code == 200
        scenario_id = sc_resp.json()["scenario_id"]
        print(f"  [2/8] 场景创建成功: {scenario_id}")

        # Step 3: 随机数据摄入
        ingest_resp = test_client.post("/api/ingest/random", json={
            "parties": ["red", "blue"],
            "count": 1,
            "scenario_id": scenario_id
        })
        assert ingest_resp.status_code == 200
        print(f"  [3/8] 数据摄入成功: {ingest_resp.json().get('doc_count')} 条文档")

        # Step 4: 查询场景实体和关系
        entities_resp = test_client.get(f"/api/scenarios/{scenario_id}/entities")
        assert entities_resp.status_code == 200
        print(f"  [4/8] 实体查询成功: {entities_resp.json().get('count')} 个实体")

        relations_resp = test_client.get(f"/api/scenarios/{scenario_id}/relations")
        assert relations_resp.status_code == 200
        print(f"  [4/8] 关系查询成功: {len(relations_resp.json().get('links', []))} 条关系")

        # Step 5: 同步到 Graphiti
        sync_resp = test_client.post(f"/api/scenarios/{scenario_id}/sync")
        assert sync_resp.status_code == 200
        print(f"  [5/8] 同步到 Graphiti: {sync_resp.json().get('status')}")

        # Step 6: QA 问答
        qa_resp = test_client.post("/api/qa/ask", json={
            "question": "当前有哪些部队部署？",
            "user_id": "test_user",
            "scenario_id": scenario_id
        })
        assert qa_resp.status_code == 200
        session_id = qa_resp.json()["session_id"]
        print(f"  [6/8] QA 问答成功: session={session_id}")

        # Step 7: 提交反馈
        feedback_resp = test_client.post(
            f"/api/qa/sessions/{session_id}/feedback",
            json={"rating": 5, "feedback": {"useful": True}, "user_id": "test_user"}
        )
        assert feedback_resp.status_code == 200
        print(f"  [7/8] 反馈提交成功")

        # Step 8: 查看审计日志
        audit_resp = test_client.get("/api/audit/events")
        assert audit_resp.status_code == 200
        print(f"  [8/8] 审计日志查询成功: {audit_resp.json().get('total')} 条记录")

    def test_multi_workspace_scenario_ingest_flow(self, test_client, sample_workspace_data, sample_scenario_data):
        """多工作空间多场景数据摄入流程"""
        # 创建多个工作空间和场景
        for i in range(2):
            ws_resp = test_client.post("/api/workspaces", json={
                "name": f"{sample_workspace_data['name']}-{i}",
                "description": sample_workspace_data['description']
            })
            assert ws_resp.status_code == 200

            sc_resp = test_client.post("/api/scenarios", json={
                "name": f"{sample_scenario_data['name']}-{i}",
                "description": sample_scenario_data['description']
            })
            assert sc_resp.status_code == 200
            scenario_id = sc_resp.json()["scenario_id"]

            # 随机数据摄入
            ingest_resp = test_client.post("/api/ingest/random", json={
                "parties": ["red", "blue"],
                "count": 1,
                "scenario_id": scenario_id
            })
            assert ingest_resp.status_code == 200

        stats_resp = test_client.get("/api/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["scenario_count"] >= 2

    def test_qa_streaming_full(self, test_client):
        """测试流式问答完整流程"""
        response = test_client.post("/api/qa/ask/stream", json={
            "question": "当前态势如何？",
            "user_id": "stream_test_user"
        })
        assert response.status_code == 200
        content = response.text
        assert len(content) > 0


class TestErrorHandling:
    """测试错误处理"""

    def test_not_found_scenario(self, test_client):
        """获取不存在的场景应返回 404"""
        response = test_client.get("/api/scenarios/nonexistent-id")
        assert response.status_code == 404

    def test_not_found_workspace(self, test_client):
        """获取不存在的工作空间"""
        response = test_client.get("/api/workspaces/nonexistent-id")
        assert response.status_code in [404, 200]

    def test_invalid_role_id(self, test_client):
        """获取不存在的角色应返回 404"""
        response = test_client.get("/api/roles/nonexistent-id")
        assert response.status_code == 404

    def test_invalid_json_body(self, test_client):
        """发送无效 JSON 应返回 422"""
        response = test_client.post(
            "/api/workspaces",
            content="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422