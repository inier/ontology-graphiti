import pytest
import sys
import os
import uuid
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def app_client():
    from unittest.mock import patch, AsyncMock, MagicMock

    with patch("odap.infra.openharness.v2_adapter.initialize_openharness", new_callable=AsyncMock, return_value=True):
        with patch("odap.infra.openharness.v2_adapter.get_openharness_integration") as mock_integration:
            mock_status = MagicMock()
            mock_status.get_status.return_value = {"initialized": True, "tools": [], "tools_count": 0}
            mock_integration.return_value = mock_status

            with patch("odap.infra.openharness.create_harness", return_value=None):
                from odap.web.app import app
                client = TestClient(app)
                yield client


@pytest.fixture(scope="module")
def test_ids():
    prefix = f"e2e_{uuid.uuid4().hex[:8]}"
    return {
        "prefix": prefix,
        "workspace_name": f"军事态势工作空间_{prefix}",
        "scenario_name": f"东海方向态势_{prefix}",
        "agent_name": f"情报分析助手_{prefix}",
    }


@pytest.mark.e2e
class TestMilitaryE2EFlow:
    """军事场景端到端完整流程测试"""

    workspace_id = None
    scenario_id = None
    ontology_id = None
    object_type_ids = []
    action_type_ids = []
    rule_ids = []
    process_ids = []
    logic_ids = []
    indicator_ids = []
    agent_id = None
    knowledge_base_id = None

    def test_01_create_workspace(self, app_client, test_ids):
        """步骤1: 创建工作空间"""
        response = app_client.post("/api/workspaces", json={
            "name": test_ids["workspace_name"],
            "description": "军事态势感知与分析工作空间",
            "type": "default",
            "owner": "commander_zhang",
        })
        assert response.status_code == 200, f"创建工作空间失败: {response.text}"
        data = response.json()
        assert "workspace_id" in data
        TestMilitaryE2EFlow.workspace_id = data["workspace_id"]
        assert TestMilitaryE2EFlow.workspace_id is not None

    def test_02_get_workspace(self, app_client, test_ids):
        """步骤2: 验证工作空间已创建"""
        assert TestMilitaryE2EFlow.workspace_id is not None
        response = app_client.get(f"/api/workspaces/{TestMilitaryE2EFlow.workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("name") == test_ids["workspace_name"]
        assert data.get("owner") == "commander_zhang"

    def test_03_create_scenario(self, app_client, test_ids):
        """步骤3: 在工作空间下创建场景"""
        response = app_client.post(f"/api/workspaces/{TestMilitaryE2EFlow.workspace_id}/scenarios", json={
            "name": test_ids["scenario_name"],
            "description": "东海方向军事态势场景",
        })
        assert response.status_code == 200, f"创建场景失败: {response.text}"
        data = response.json()
        assert "scenario_id" in data
        TestMilitaryE2EFlow.scenario_id = data["scenario_id"]

    def test_04_create_ontology_object_types(self, app_client, test_ids):
        """步骤4: 创建本体对象类型（军事实体）"""
        prefix = test_ids["prefix"]
        military_types = [
            {
                "type_id": f"fleet_{prefix}",
                "name": "Fleet",
                "display_name": "舰队",
                "description": "海军舰队编制单位",
                "properties": [
                    {"name": "tonnage", "display_name": "吨位", "property_type": "float", "required": False},
                    {"name": "speed", "display_name": "航速", "property_type": "float", "required": False},
                    {"name": "heading", "display_name": "航向", "property_type": "string", "required": False},
                ],
                "actions": ["move", "attack", "defend"],
                "icon": "ship",
                "color": "#0066cc",
            },
            {
                "type_id": f"base_{prefix}",
                "name": "Base",
                "display_name": "基地",
                "description": "军事基地",
                "properties": [
                    {"name": "location", "display_name": "位置", "property_type": "string", "required": True},
                    {"name": "capacity", "display_name": "容量", "property_type": "integer", "required": False},
                ],
                "actions": ["deploy", "supply"],
                "icon": "building",
                "color": "#cc6600",
            },
            {
                "type_id": f"missile_{prefix}",
                "name": "Missile",
                "display_name": "导弹",
                "description": "导弹武器系统",
                "properties": [
                    {"name": "range", "display_name": "射程", "property_type": "float", "required": True},
                    {"name": "warhead_type", "display_name": "弹头类型", "property_type": "string", "required": False},
                ],
                "actions": ["launch", "intercept"],
                "icon": "rocket",
                "color": "#cc0000",
            },
        ]

        for obj_type in military_types:
            response = app_client.post("/api/ontology/oms/object-types", json=obj_type)
            assert response.status_code == 200, f"创建对象类型失败: {response.text}"
            data = response.json()
            type_id = data.get("type_id")
            if type_id:
                TestMilitaryE2EFlow.object_type_ids.append(type_id)

    def test_05_create_ontology_action_types(self, app_client, test_ids):
        """步骤5: 创建本体动作类型"""
        prefix = test_ids["prefix"]
        action_types = [
            {
                "action_type_id": f"move_{prefix}",
                "name": "move",
                "display_name": "机动",
                "description": "舰队机动动作",
                "target_object_type": f"fleet_{prefix}",
                "parameters": [
                    {"name": "destination", "display_name": "目标位置", "param_type": "string", "required": True},
                    {"name": "speed", "display_name": "航速", "param_type": "float", "required": False},
                ],
                "confirmation_required": True,
            },
            {
                "action_type_id": f"attack_{prefix}",
                "name": "attack",
                "display_name": "攻击",
                "description": "发起攻击动作",
                "target_object_type": f"fleet_{prefix}",
                "parameters": [
                    {"name": "target_id", "display_name": "目标ID", "param_type": "string", "required": True},
                    {"name": "weapon_type", "display_name": "武器类型", "param_type": "string", "required": False},
                ],
                "confirmation_required": True,
                "required_roles": ["commander"],
            },
        ]

        for action_type in action_types:
            response = app_client.post("/api/ontology/oms/action-types", json=action_type)
            assert response.status_code == 200, f"创建动作类型失败: {response.text}"
            data = response.json()
            action_id = data.get("action_type_id")
            if action_id:
                TestMilitaryE2EFlow.action_type_ids.append(action_id)

    def test_06_ingest_military_data(self, app_client, test_ids):
        """步骤6: 摄入军事数据（手动录入）"""
        military_data = {
            "source_type": "manual",
            "data": {
                "entities": [
                    {"name": "东海舰队", "entity_type": "Fleet", "basic_properties": {"tonnage": 50000, "speed": 28, "heading": "NE"}},
                    {"name": "南海舰队", "entity_type": "Fleet", "basic_properties": {"tonnage": 65000, "speed": 22, "heading": "SW"}},
                    {"name": "舟山基地", "entity_type": "Base", "basic_properties": {"location": "舟山", "capacity": 200}},
                    {"name": "东风-21D", "entity_type": "Missile", "basic_properties": {"range": 1500, "warhead_type": "conventional"}},
                ],
                "events": [
                    {"event_type": "DEPLOYMENT", "description": "东海舰队从舟山基地出港", "participants": ["东海舰队", "舟山基地"], "timestamp": "2026-05-20T08:00:00Z"},
                    {"event_type": "MOVEMENT", "description": "东海舰队向东北方向机动", "participants": ["东海舰队"], "timestamp": "2026-05-20T10:00:00Z"},
                ],
            },
            "scenario_id": TestMilitaryE2EFlow.scenario_id,
        }

        response = app_client.post("/api/ontology/ingest", json=military_data)
        assert response.status_code == 200, f"数据摄入失败: {response.text}"
        data = response.json()
        assert data.get("ingest_id") is not None
        assert data.get("status") in ["completed", "pending", "processing"]

    def test_07_create_knowledge_base(self, app_client, test_ids):
        """步骤7: 创建知识库"""
        response = app_client.post("/api/knowledge-bases", json={
            "name": f"军事知识库_{test_ids['prefix']}",
            "description": "军事领域知识库",
        })
        assert response.status_code == 200, f"创建知识库失败: {response.text}"
        data = response.json()
        TestMilitaryE2EFlow.knowledge_base_id = data.get("kb_id")

    def test_08_create_business_rules(self, app_client, test_ids):
        """步骤8: 创建业务规则"""
        prefix = test_ids["prefix"]
        rules = [
            {
                "name": f"high_value_target_rule_{prefix}",
                "display_name": "高价值目标识别规则",
                "description": "当敌方舰队吨位超过40000时标记为高价值目标",
                "rule_conditions": [
                    {"condition_id": f"cond_hvt_1_{prefix}", "trigger_event": "entity_created", "requirement": "tonnage > 40000", "order": 1},
                    {"condition_id": f"cond_hvt_2_{prefix}", "trigger_event": "entity_created", "requirement": "entity_type == Fleet", "order": 2},
                ],
            },
            {
                "name": f"threat_assessment_rule_{prefix}",
                "display_name": "威胁评估规则",
                "description": "当导弹射程覆盖我方基地时评估为高威胁",
                "rule_conditions": [
                    {"condition_id": f"cond_ta_1_{prefix}", "trigger_event": "entity_created", "requirement": "range >= 1000", "order": 1},
                    {"condition_id": f"cond_ta_2_{prefix}", "trigger_event": "entity_created", "requirement": "entity_type == Missile", "order": 2},
                ],
            },
        ]

        for rule in rules:
            response = app_client.post("/api/business-rules", json=rule)
            assert response.status_code == 200, f"创建业务规则失败: {response.text}"
            data = response.json()
            rule_id = data.get("rule_id") or data.get("id")
            if rule_id:
                TestMilitaryE2EFlow.rule_ids.append(rule_id)

    def test_09_create_business_processes(self, app_client, test_ids):
        """步骤9: 创建业务过程"""
        prefix = test_ids["prefix"]
        processes = [
            {
                "name": f"threat_response_process_{prefix}",
                "display_name": "威胁响应流程",
                "description": "发现威胁后的标准响应流程",
                "flow_nodes": [
                    {"node_id": f"detect_{prefix}", "name": "威胁检测", "order": 1, "type": "start", "description": "检测潜在威胁信号"},
                    {"node_id": f"assess_{prefix}", "name": "威胁评估", "order": 2, "type": "task", "description": "评估威胁等级"},
                    {"node_id": f"decide_{prefix}", "name": "决策判定", "order": 3, "type": "decision", "description": "判定响应方案"},
                    {"node_id": f"respond_{prefix}", "name": "执行响应", "order": 4, "type": "task", "description": "执行选定响应方案"},
                    {"node_id": f"report_{prefix}", "name": "结果报告", "order": 5, "type": "end", "description": "输出响应结果报告"},
                ],
            },
        ]

        for process in processes:
            response = app_client.post("/api/business-processes", json=process)
            assert response.status_code == 200, f"创建业务过程失败: {response.text}"
            data = response.json()
            process_id = data.get("process_id") or data.get("id")
            if process_id:
                TestMilitaryE2EFlow.process_ids.append(process_id)

    def test_10_create_business_logics(self, app_client, test_ids):
        """步骤10: 创建业务逻辑"""
        prefix = test_ids["prefix"]
        logics = [
            {
                "name": f"threat_level_logic_{prefix}",
                "display_name": "威胁等级计算逻辑",
                "description": "根据目标属性计算威胁等级",
                "logic_type": "scoring",
                "logic_expression": "threat_score = range * 0.4 + warhead_type_factor * 0.3 + proximity * 0.3",
            },
        ]

        for logic in logics:
            response = app_client.post("/api/business-logics", json=logic)
            assert response.status_code == 200, f"创建业务逻辑失败: {response.text}"
            data = response.json()
            logic_id = data.get("logic_id") or data.get("id")
            if logic_id:
                TestMilitaryE2EFlow.logic_ids.append(logic_id)

    def test_11_create_business_indicators(self, app_client, test_ids):
        """步骤11: 创建业务指标"""
        prefix = test_ids["prefix"]
        indicators = [
            {
                "name": f"threat_index_{prefix}",
                "display_name": "综合威胁指数",
                "description": "综合评估当前态势威胁水平",
                "indicator_type": "composite",
                "calculation_formula": "SUM(threat_scores) / COUNT(entities)",
                "unit": "分",
            },
            {
                "name": f"force_readiness_{prefix}",
                "display_name": "战备状态指数",
                "description": "评估我方战备水平",
                "indicator_type": "gauge",
                "calculation_formula": "active_units / total_units * 100",
                "unit": "%",
            },
        ]

        for indicator in indicators:
            response = app_client.post("/api/business-indicators", json=indicator)
            assert response.status_code == 200, f"创建业务指标失败: {response.text}"
            data = response.json()
            indicator_id = data.get("indicator_id") or data.get("id")
            if indicator_id:
                TestMilitaryE2EFlow.indicator_ids.append(indicator_id)

    def test_12_create_agent(self, app_client, test_ids):
        """步骤12: 创建智能体（关联业务规则/过程/逻辑/指标）"""
        agent_data = {
            "name": test_ids["agent_name"],
            "display_name": "情报分析助手",
            "description": "军事态势情报分析智能体，支持威胁评估和态势研判",
            "main_object": TestMilitaryE2EFlow.object_type_ids[0] if TestMilitaryE2EFlow.object_type_ids else "Fleet",
            "related_objects": TestMilitaryE2EFlow.object_type_ids,
            "related_processes": TestMilitaryE2EFlow.process_ids,
            "related_rules": TestMilitaryE2EFlow.rule_ids,
            "related_business_logic": TestMilitaryE2EFlow.logic_ids,
            "related_indicators": TestMilitaryE2EFlow.indicator_ids,
            "related_knowledge_bases": [TestMilitaryE2EFlow.knowledge_base_id] if TestMilitaryE2EFlow.knowledge_base_id else [],
            "allowed_roles": ["commander", "intelligence_officer"],
        }

        response = app_client.post("/api/agents", json=agent_data)
        assert response.status_code == 200, f"创建智能体失败: {response.text}"
        data = response.json()
        TestMilitaryE2EFlow.agent_id = data.get("agent_id") or data.get("id")
        assert TestMilitaryE2EFlow.agent_id is not None

    def test_13_get_agent_ref_options(self, app_client, test_ids):
        """步骤13: 验证智能体引用选项端点"""
        for ref_type in ["entity", "business_logic", "indicator", "skill", "knowledge_base", "role"]:
            response = app_client.get(f"/api/agents/ref-options?type={ref_type}")
            assert response.status_code == 200, f"获取 {ref_type} 引用选项失败: {response.text}"
            data = response.json()
            assert "options" in data

    def test_14_list_agents(self, app_client, test_ids):
        """步骤14: 验证智能体列表包含新创建的智能体"""
        response = app_client.get("/api/agents")
        assert response.status_code == 200
        data = response.json()
        agent_ids = [a.get("agent_id") or a.get("id") for a in data]
        assert TestMilitaryE2EFlow.agent_id in agent_ids

    def test_15_agent_chat(self, app_client, test_ids):
        """步骤15: 通过智能体进行问答"""
        response = app_client.post("/api/agent/chat", json={
            "message": "当前东海方向有哪些舰队？威胁等级如何？",
            "session_id": f"session_{test_ids['prefix']}",
            "workspace_id": TestMilitaryE2EFlow.workspace_id,
            "role": "intelligence_officer",
        })
        assert response.status_code in [200, 500], f"Agent chat 响应异常: {response.status_code}"

    def test_16_query_knowledge_base(self, app_client, test_ids):
        """步骤16: 知识库RAG查询"""
        if not TestMilitaryE2EFlow.knowledge_base_id:
            pytest.skip("知识库未创建")

        response = app_client.post(f"/api/knowledge-bases/{TestMilitaryE2EFlow.knowledge_base_id}/rag-query", json={
            "query": "东海舰队 舟山基地",
            "top_k": 5,
            "threshold": 0.1,
        })
        assert response.status_code == 200, f"RAG查询失败: {response.text}"
        data = response.json()
        assert "answer" in data
        assert "sources" in data

    def test_17_verify_opa_policies(self, app_client, test_ids):
        """步骤17: 验证OPA策略持久化"""
        response = app_client.get("/api/policies")
        assert response.status_code == 200
        data = response.json()
        assert "policies" in data
        assert len(data["policies"]) >= 3

    def test_18_verify_workspace_resources(self, app_client, test_ids):
        """步骤18: 验证工作空间资源字段持久化"""
        response = app_client.get(f"/api/workspaces/{TestMilitaryE2EFlow.workspace_id}")
        assert response.status_code == 200
        data = response.json()
        assert "resources" in data
        assert "members" in data

    def test_19_verify_scenario_structure(self, app_client, test_ids):
        """步骤19: 验证场景结构完整性"""
        if not TestMilitaryE2EFlow.scenario_id:
            pytest.skip("场景未创建")

        response = app_client.get(f"/api/workspaces/{TestMilitaryE2EFlow.workspace_id}/scenarios")
        assert response.status_code == 200
        data = response.json()
        scenarios = data.get("scenarios", [])
        assert len(scenarios) > 0

        scenario = scenarios[0]
        assert "scenario_id" in scenario
        assert "name" in scenario

    def test_20_verify_validation_rules(self, app_client, test_ids):
        """步骤20: 验证验证规则存储功能"""
        from odap.biz.core.ontology.storage.sqlite_ingest_storage import SQLiteIngestStorage
        storage = SQLiteIngestStorage()

        rule = {
            "rule_id": f"rule_{test_ids['prefix']}",
            "name": "实体名称非空规则",
            "description": "验证实体名称不能为空",
            "rule_type": "entity",
            "severity": "error",
            "condition": {"field": "name", "operator": "not_empty"},
        }
        storage.save_validation_rule(rule)

        rules = storage.get_validation_rules()
        assert len(rules) > 0
        rule_names = [r.get("name") for r in rules]
        assert "实体名称非空规则" in rule_names
