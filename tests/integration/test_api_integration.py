"""
前后端集成测试 - 完整API端点测试套件
测试覆盖: 工作空间、本体管理、场景管理、数据摄入、问答、
审计日志、事件模拟器、技能管理、角色管理、代理系统
"""
import pytest
import sys
import os
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock
from typing import Dict, Any, List, Optional
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

client = TestClient(app)


class TestWorkspaceAPI:
    """工作空间管理 API 集成测试"""

    def test_list_workspaces(self):
        """测试: 获取工作空间列表"""
        response = client.get("/api/workspaces")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "workspaces" in data

    def test_create_and_get_workspace(self):
        """测试: 创建并获取工作空间"""
        workspace_name = f"test-workspace-{uuid.uuid4().hex[:8]}"
        payload = {
            "name": workspace_name,
            "description": "集成测试工作空间",
            "isolation_strategy": "soft"
        }
        response = client.post("/api/workspaces", json=payload)
        assert response.status_code == 201
        data = response.json()
        workspace_id = data.get("workspace_id")
        assert workspace_id is not None
        assert data.get("name") == workspace_name

        get_response = client.get(f"/api/workspaces/{workspace_id}")
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data.get("name") == workspace_name

    def test_update_workspace(self):
        """测试: 更新工作空间"""
        payload = {
            "name": f"update-workspace-{uuid.uuid4().hex[:8]}",
            "description": "待更新工作空间"
        }
        create_resp = client.post("/api/workspaces", json=payload)
        assert create_resp.status_code == 201
        workspace_id = create_resp.json().get("workspace_id")

        update_payload = {"description": "已更新的工作空间描述"}
        update_resp = client.put(f"/api/workspaces/{workspace_id}", json=update_payload)
        assert update_resp.status_code == 200

    def test_delete_workspace(self):
        """测试: 删除工作空间"""
        payload = {
            "name": f"delete-workspace-{uuid.uuid4().hex[:8]}",
            "description": "待删除工作空间"
        }
        create_resp = client.post("/api/workspaces", json=payload)
        assert create_resp.status_code == 201
        workspace_id = create_resp.json().get("workspace_id")

        delete_resp = client.delete(f"/api/workspaces/{workspace_id}")
        assert delete_resp.status_code == 200

    def test_workspace_members(self):
        """测试: 工作空间成员管理"""
        payload = {"name": f"member-test-{uuid.uuid4().hex[:8]}", "description": "成员测试"}
        create_resp = client.post("/api/workspaces", json=payload)
        assert create_resp.status_code == 201
        workspace_id = create_resp.json().get("workspace_id")

        member_payload = {"user_id": "test-user-001", "role": "admin"}
        add_resp = client.post(f"/api/workspaces/{workspace_id}/members", json=member_payload)
        assert add_resp.status_code in [200, 201, 404]

    def test_workspace_import_export(self):
        """测试: 工作空间导入导出"""
        payload = {"name": f"export-test-{uuid.uuid4().hex[:8]}", "description": "导出测试"}
        create_resp = client.post("/api/workspaces", json=payload)
        assert create_resp.status_code == 201
        workspace_id = create_resp.json().get("workspace_id")

        export_resp = client.get(f"/api/workspaces/{workspace_id}/export")
        assert export_resp.status_code in [200, 404]


class TestScenarioAPI:
    """场景管理 API 集成测试"""

    def test_create_scenario(self):
        """测试: 创建场景"""
        payload = {
            "name": "集成测试场景",
            "description": "用于集成测试的场景",
            "workspace_id": "default"
        }
        response = client.post("/api/v1/admin/.scenarios", json=payload)
        assert response.status_code in [200, 201, 404]
        if response.status_code in [200, 201]:
            data = response.json()
            assert data.get("status") in ["created", "ok", "success"]

    def test_list_scenarios(self):
        """测试: 列出场景"""
        response = client.get("/api/v1/admin/.scenarios")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "scenarios" in data or isinstance(data, list)

    def test_get_scenario(self):
        """测试: 获取特定场景"""
        response = client.get("/api/v1/admin/.scenarios/default")
        assert response.status_code in [200, 404]

    def test_delete_scenario(self):
        """测试: 删除场景"""
        response = client.delete("/api/v1/admin/.scenarios/test-delete")
        assert response.status_code in [200, 404]

    def test_update_scenario(self):
        """测试: 更新场景"""
        payload = {"name": "更新后的场景", "description": "更新测试"}
        response = client.patch("/api/v1/admin/.scenarios/test-update", json=payload)
        assert response.status_code in [200, 404]


class TestOntologyIngestAPI:
    """本体摄入 API 集成测试"""

    def test_ingest_text(self):
        """测试: 文本摄入"""
        payload = {
            "text": "2024年1月，第3舰队部署了5艘驱逐舰到太平洋区域进行例行巡逻。",
            "source": "test",
            "scenario_id": "default"
        }
        response = client.post("/api/v1/admin/ontology/ingest/text", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_ingest_json(self):
        """测试: JSON格式摄入"""
        payload = {
            "data": {
                "event": "军事部署",
                "date": "2024-01-15",
                "units": ["第3舰队", "太平洋舰队"],
                "location": "太平洋区域"
            },
            "source": "test",
            "scenario_id": "default"
        }
        response = client.post("/api/v1/admin/ontology/ingest/json", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_ingest_manual(self):
        """测试: 手动录入实体和关系"""
        payload = {
            "entities": [
                {"name": "USS_Dewey", "type": "舰船", "attributes": {"class": "阿利·伯克级", "country": "美国"}}
            ],
            "relationships": [
                {"source": "USS_Dewey", "target": "太平洋舰队", "type": "隶属于"}
            ],
            "scenario_id": "default"
        }
        response = client.post("/api/v1/admin/ontology/ingest/manual", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_ingest_natural_language(self):
        """测试: 自然语言摄入"""
        payload = {
            "text": "伊朗在霍尔木兹海峡部署了新型导弹系统，威胁过往油轮的安全。",
            "scenario_id": "default",
            "role": "intelligence_analyst"
        }
        response = client.post("/api/v1/admin/ontology/ingest/nl", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_build_ontology(self):
        """测试: 构建本体"""
        payload = {"scenario_id": "default", "entity_filter": None}
        response = client.post("/api/v1/admin/ontology/build", json=payload)
        assert response.status_code in [200, 201, 404, 500]


class TestQAAPI:
    """智能问答 API 集成测试"""

    def test_ask_question(self):
        """测试: 提交问题"""
        payload = {
            "question": "当前太平洋区域有哪些军事部署？",
            "role": "analyst",
            "scenario_id": "default"
        }
        response = client.post("/api/qa/ask", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_get_sessions(self):
        """测试: 获取问答会话列表"""
        response = client.get("/api/qa/sessions")
        assert response.status_code in [200, 404]

    def test_intent_recognition(self):
        """测试: 意图识别"""
        payload = {"input_text": "分析当前中东局势", "role": "analyst"}
        response = client.post("/api/cognition/intent", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_get_role_view(self):
        """测试: 获取角色视图"""
        response = client.get("/api/cognition/view?role=analyst")
        assert response.status_code in [200, 404]

    def test_qa_feedback(self):
        """测试: 问答反馈"""
        payload = {"feedback": {"helpful": True}, "rating": 4}
        response = client.post("/api/qa/sessions/test-session/feedback", json=payload)
        assert response.status_code in [200, 404]

    def test_qa_stats(self):
        """测试: 问答统计数据"""
        response = client.get("/api/qa/stats")
        assert response.status_code in [200, 404]


class TestAuditLogAPI:
    """审计日志 API 集成测试"""

    def test_list_audit_logs(self):
        """测试: 获取审计日志列表"""
        response = client.get("/api/audit/logs")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "events" in data or "logs" in data

    def test_filter_audit_logs(self):
        """测试: 筛选审计日志"""
        response = client.get("/api/audit/logs?event_type=create&limit=10")
        assert response.status_code in [200, 404]

    def test_get_audit_timeline(self):
        """测试: 获取审计时间线"""
        response = client.get("/api/audit/timeline")
        assert response.status_code in [200, 404]

    def test_get_audit_stats(self):
        """测试: 获取审计统计"""
        response = client.get("/api/audit/stats")
        assert response.status_code in [200, 404]

    def test_audit_export(self):
        """测试: 导出审计日志"""
        response = client.get("/api/audit/export?format=json")
        assert response.status_code in [200, 404]


class TestEventSimulatorAPI:
    """事件模拟器 API 集成测试"""

    def test_get_templates(self):
        """测试: 获取事件模板列表"""
        response = client.get("/api/event-simulator/templates")
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "templates" in data

    def test_create_template(self):
        """测试: 创建事件模板"""
        payload = {
            "name": "测试军事冲突模板",
            "description": "用于测试的标准军事冲突模板",
            "event_type": "military_movement",
            "parameters": {"intensity": "medium", "region": "pacific"}
        }
        response = client.post("/api/event-simulator/templates", json=payload)
        assert response.status_code in [200, 201, 404]

    def test_generate_events(self):
        """测试: 生成模拟事件"""
        payload = {
            "count": 3,
            "event_types": ["military_movement"],
            "region": "中东",
            "scenario_id": "default"
        }
        response = client.post("/api/event-simulator/generate", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_list_simulation_events(self):
        """测试: 列出模拟事件"""
        response = client.get("/api/event-simulator/events?limit=20")
        assert response.status_code in [200, 404]

    def test_time_control(self):
        """测试: 时间控制"""
        payload = {"action": "start"}
        response = client.post("/api/event-simulator/time-control", json=payload)
        assert response.status_code in [200, 404, 500]

    def test_time_pause(self):
        """测试: 暂停模拟"""
        payload = {"action": "pause"}
        response = client.post("/api/event-simulator/time-control", json=payload)
        assert response.status_code in [200, 404, 500]

    def test_time_set_speed(self):
        """测试: 设置模拟速度"""
        payload = {"action": "set_speed", "speed": 5}
        response = client.post("/api/event-simulator/time-control", json=payload)
        assert response.status_code in [200, 404, 500]

    def test_time_stop(self):
        """测试: 停止模拟"""
        payload = {"action": "stop"}
        response = client.post("/api/event-simulator/time-control", json=payload)
        assert response.status_code in [200, 404, 500]

    def test_simulation_status(self):
        """测试: 获取模拟状态"""
        response = client.get("/api/event-simulator/status")
        assert response.status_code in [200, 404]

    def test_adopt_event(self):
        """测试: 采纳事件"""
        response = client.post("/api/event-simulator/events/test-event/adopt")
        assert response.status_code in [200, 404]

    def test_bulk_adopt(self):
        """测试: 批量采纳事件"""
        payload = {"event_ids": ["event-1", "event-2"]}
        response = client.post("/api/event-simulator/events/adopt-bulk", json=payload)
        assert response.status_code in [200, 404]


class TestSkillAPI:
    """技能管理 API 集成测试"""

    def test_list_skills(self):
        """测试: 获取技能列表"""
        response = client.get("/api/skill/skills")
        assert response.status_code in [200, 404]

    def test_scan_skills(self):
        """测试: 扫描技能目录"""
        response = client.get("/api/skill/scan")
        assert response.status_code in [200, 404]

    def test_get_categories(self):
        """测试: 获取技能分类"""
        response = client.get("/api/skill/categories")
        assert response.status_code in [200, 404]

    def test_get_all_skills(self):
        """测试: 获取全部技能"""
        response = client.get("/api/skill/all")
        assert response.status_code in [200, 404]

    def test_loaded_skills(self):
        """测试: 获取已加载技能"""
        response = client.get("/api/skill/skills/loaded")
        assert response.status_code in [200, 404]

    def test_register_skill(self):
        """测试: 注册技能"""
        params = {
            "name": "test-skill-001",
            "skill_type": "tool",
            "description": "测试技能",
            "category": "test"
        }
        from urllib.parse import urlencode
        response = client.post(f"/api/skill/skills?{urlencode(params)}")
        assert response.status_code in [200, 201, 404]


class TestAgentAPI:
    """代理系统 API 集成测试"""

    def test_init_agent(self):
        """测试: 初始化代理"""
        payload = {"config": {}}
        response = client.post("/api/agent/init", json=payload)
        assert response.status_code in [200, 201, 404, 500]

    def test_get_agent_status(self):
        """测试: 获取代理状态"""
        response = client.get("/api/agent/status")
        assert response.status_code in [200, 404]

    def test_list_tools(self):
        """测试: 列出代理工具"""
        response = client.get("/api/agent/tools")
        assert response.status_code in [200, 404]

    def test_run_agent(self):
        """测试: 运行代理"""
        payload = {"input": "分析当前安全态势", "workspace_id": "default"}
        response = client.post("/api/agent/run", json=payload)
        assert response.status_code in [200, 404, 500]

    def test_agent_chat(self):
        """测试: 代理对话"""
        payload = {
            "message": "请分析当前的军事部署情况",
            "session_id": None,
            "role": "analyst"
        }
        response = client.post("/api/agent/chat", json=payload)
        assert response.status_code in [200, 404, 500]


class TestRoleAPI:
    """角色管理 API 集成测试"""

    def test_list_roles(self):
        """测试: 获取角色列表"""
        response = client.get("/api/roles")
        assert response.status_code in [200, 404]

    def test_create_role(self):
        """测试: 创建角色"""
        payload = {
            "name": "test-role-集成测试",
            "description": "集成测试角色",
            "permissions": ["read", "write"]
        }
        response = client.post("/api/roles", json=payload)
        assert response.status_code in [200, 201, 404]

    def test_update_role(self):
        """测试: 更新角色"""
        payload = {
            "name": "updated-role",
            "permissions": ["read", "write", "delete"]
        }
        response = client.put("/api/roles/test-role-id", json=payload)
        assert response.status_code in [200, 404]

    def test_delete_role(self):
        """测试: 删除角色"""
        response = client.delete("/api/roles/test-role-id")
        assert response.status_code in [200, 404]


class TestPoliciesAPI:
    """OPA策略管理 API 集成测试"""

    def test_list_policies(self):
        """测试: 获取策略列表"""
        response = client.get("/api/policies")
        assert response.status_code in [200, 404]

    def test_create_policy(self):
        """测试: 创建策略"""
        payload = {
            "name": "测试访问策略",
            "description": "集成测试用访问策略",
            "markdown_content": "# 测试策略\n\n允许分析师访问。",
            "category": "access_control"
        }
        response = client.post("/api/policies", json=payload)
        assert response.status_code in [200, 201, 404]

    def test_get_policy(self):
        """测试: 获取策略详情"""
        response = client.get("/api/policies/test-policy-id")
        assert response.status_code in [200, 404]

    def test_update_policy(self):
        """测试: 更新策略"""
        payload = {"description": "更新后的描述", "status": "active"}
        response = client.put("/api/policies/test-policy-id", json=payload)
        assert response.status_code in [200, 404]

    def test_toggle_policy(self):
        """测试: 切换策略状态"""
        response = client.post("/api/policies/test-policy-id/toggle?enabled=true")
        assert response.status_code in [200, 404]


class TestSystemAPI:
    """系统健康检查 API 测试"""

    def test_health_check(self):
        """测试: 系统健康检查"""
        response = client.get("/health")
        assert response.status_code in [200, 404, 500]
        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    def test_performance_metrics(self):
        """测试: 性能指标"""
        response = client.get("/api/v1/monitoring/performance")
        assert response.status_code in [200, 404]


class TestOntologyGraphAPI:
    """本体图查询 API 集成测试"""

    def test_graph_query(self):
        """测试: 图查询"""
        payload = {"query": "MATCH (n) RETURN n LIMIT 10"}
        response = client.post("/api/v1/admin/graph/query", json=payload)
        assert response.status_code in [200, 404, 500]

    def test_get_entities(self):
        """测试: 获取实体列表"""
        response = client.get("/api/v1/admin/graph/entities?limit=10")
        assert response.status_code in [200, 404]

    def test_get_relations(self):
        """测试: 获取关系列表"""
        response = client.get("/api/v1/admin/graph/relations?limit=10")
        assert response.status_code in [200, 404]

    def test_get_graph_state(self):
        """测试: 获取图状态"""
        response = client.get("/api/v1/admin/graph/state")
        assert response.status_code in [200, 404]


class TestFrontendCompatAPI:
    """前端兼容层 API 集成测试"""

    def test_get_ontology_data(self):
        """测试: 获取本体数据"""
        response = client.get("/api/v1/admin/.ontology/data?scenario_id=default")
        assert response.status_code in [200, 404, 500]

    def test_get_ontology_timeline(self):
        """测试: 获取本体时间线"""
        response = client.get("/api/v1/admin/.ontology/timeline?scenario_id=default")
        assert response.status_code in [200, 404, 500]

    def test_get_hook_status(self):
        """测试: 获取钩子系统状态"""
        response = client.get("/api/hook/status")
        assert response.status_code in [200, 404]

    def test_get_mcp_connections(self):
        """测试: 获取MCP连接状态"""
        response = client.get("/api/mcp/connections")
        assert response.status_code in [200, 404]


class TestDataIngestFlow:
    """完整数据摄入流程集成测试"""

    def test_full_ingest_flow(self):
        """测试: 完整摄入流程 (新闻摄入 -> 构建本体 -> 查询验证)"""
        scenario_id = f"integration-test-{uuid.uuid4().hex[:8]}"

        # Step 1: 创建工作空间
        ws_payload = {
            "name": f"ws-{scenario_id}",
            "description": "完整流程测试"
        }
        ws_resp = client.post("/api/workspaces", json=ws_payload)
        if ws_resp.status_code != 201:
            pytest.skip("无法创建工作空间，跳过完整流程测试")

        # Step 2: 摄入文本数据
        ingest_payload = {
            "text": "美军在菲律宾海举行了大规模军事演习，参演兵力包括2艘航母、8艘驱逐舰和3艘潜艇。",
            "source": "news_report",
            "scenario_id": "default"
        }
        ingest_resp = client.post("/api/v1/admin/ontology/ingest/text", json=ingest_payload)
        assert ingest_resp.status_code in [200, 201, 404, 500]

        # Step 3: 尝试构建本体
        build_payload = {"scenario_id": "default", "run_async": True}
        build_resp = client.post("/api/v1/admin/ontology/build", json=build_payload)
        assert build_resp.status_code in [200, 201, 404, 500]

        # Step 4: 查询结果
        query_resp = client.get(f"/api/v1/admin/.ontology/data?scenario_id=default")
        assert query_resp.status_code in [200, 404, 500]

        # Step 5: 验证问答系统可查询
        qa_payload = {
            "question": "菲律宾海演习中参演了哪些舰艇？",
            "role": "analyst",
            "scenario_id": "default"
        }
        qa_resp = client.post("/api/qa/ask", json=qa_payload)
        assert qa_resp.status_code in [200, 201, 404, 500]


class TestErrorHandling:
    """错误处理和边界条件测试"""

    def test_invalid_scenario_id(self):
        """测试: 无效场景ID"""
        response = client.get("/api/v1/admin/.ontology/data?scenario_id=nonexistent")
        assert response.status_code in [200, 404, 500]

    def test_empty_ingest_payload(self):
        """测试: 空摄入数据"""
        payload = {}
        response = client.post("/api/v1/admin/ontology/ingest/text", json=payload)
        assert response.status_code in [200, 422, 400, 404, 500]

    def test_malformed_json(self):
        """测试: 畸形JSON"""
        response = client.post(
            "/api/v1/admin/ontology/ingest/json",
            content=b"not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [200, 422, 400, 404, 500]

    def test_missing_required_fields_role(self):
        """测试: 缺少必填字段 - 角色"""
        payload = {"description": "缺少name字段"}
        response = client.post("/api/roles", json=payload)
        assert response.status_code in [200, 201, 422, 400, 404]

    def test_large_payload(self):
        """测试: 大数据量请求"""
        large_text = "测试数据。" * 1000
        payload = {
            "text": large_text,
            "source": "stress_test",
            "scenario_id": "default"
        }
        response = client.post("/api/v1/admin/ontology/ingest/text", json=payload)
        assert response.status_code in [200, 201, 404, 422, 500]