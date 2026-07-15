import os
import json
import pytest
from datetime import datetime, timedelta


@pytest.fixture
def tmp_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return str(data_dir)


@pytest.fixture
def oms_storage(tmp_data_dir):
    from odap.biz.core.ontology.application.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
    db_path = os.path.join(tmp_data_dir, "oms.db")
    storage = SQLiteOMSStorage(db_path=db_path)
    return storage


@pytest.fixture
def runtime_storage(tmp_data_dir):
    from odap.biz.core.ontology.application.runtime.storage.sqlite_runtime_storage import SQLiteRuntimeStorage
    db_path = os.path.join(tmp_data_dir, "ontology_runtime.db")
    storage = SQLiteRuntimeStorage(db_path=db_path)
    return storage


@pytest.fixture
def memory_storage(tmp_data_dir):
    from odap.biz.platform.ontology_memory.storage.sqlite_ontology_memory_storage import SQLiteOntologyMemoryStorage
    db_path = os.path.join(tmp_data_dir, "ontology_memory.db")
    storage = SQLiteOntologyMemoryStorage(db_path=db_path)
    return storage


@pytest.fixture
def team_agent_storage(tmp_data_dir):
    from odap.biz.core.ontology.application.team_agent.storage.sqlite_team_agent_storage import SQLiteTeamAgentStorage
    db_path = os.path.join(tmp_data_dir, "team_agent.db")
    storage = SQLiteTeamAgentStorage(db_path=db_path)
    return storage


@pytest.fixture
def servitization_storage(tmp_data_dir):
    from odap.biz.core.ontology.application.servitization.storage.sqlite_servitization_storage import SQLiteServitizationStorage
    db_path = os.path.join(tmp_data_dir, "servitization.db")
    storage = SQLiteServitizationStorage(db_path=db_path)
    return storage


@pytest.fixture
def simulation_data():
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "odap", "biz", "core", "ontology", "mock_data", "simulation_data.json"
    )
    if not os.path.exists(data_path):
        pytest.skip("simulation_data.json not found")
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestOMSSeedDataIntegrity:
    def test_oms_seed_data_loaded(self, oms_storage):
        object_types = oms_storage.list_object_types()
        assert len(object_types) > 0, "OMS种子数据未加载"

    def test_oms_object_types_match_adr036(self, oms_storage):
        object_types = oms_storage.list_object_types()
        type_ids = {ot["type_id"] for ot in object_types}
        assert "Unit" in type_ids, f"缺少Unit对象类型, 实际: {type_ids}"
        assert "Location" in type_ids, f"缺少Location对象类型, 实际: {type_ids}"
        assert "Equipment" in type_ids, f"缺少Equipment对象类型, 实际: {type_ids}"
        assert "Event" in type_ids, f"缺少Event对象类型, 实际: {type_ids}"

    def test_oms_action_types_match_adr036(self, oms_storage):
        action_types = oms_storage.list_action_types()
        action_ids = {at["action_type_id"] for at in action_types}
        expected = {"move", "attack", "defend", "reinforce", "retreat", "observe", "communicate"}
        assert expected.issubset(action_ids), f"缺少动作类型: {expected - action_ids}"

    def test_unit_object_has_statistical_properties(self, oms_storage):
        unit_type = oms_storage.get_object_type("Unit")
        assert unit_type is not None, "Unit对象类型不存在"
        props = unit_type.get("properties", [])
        stat_props = [p for p in props if p.get("category") == "statistical_properties"]
        assert len(stat_props) > 0, "Unit缺少统计属性"
        stat_names = {p["name"] for p in stat_props}
        assert "combat_power" in stat_names, f"Unit缺少combat_power统计属性, 实际: {stat_names}"
        assert "morale" in stat_names, f"Unit缺少morale统计属性, 实际: {stat_names}"

    def test_attack_action_requires_confirmation(self, oms_storage):
        attack = oms_storage.get_action_type("attack")
        assert attack is not None, "attack动作类型不存在"
        assert attack.get("confirmation_required") is True or attack.get("requires_confirmation") is True, "attack动作应需确认"

    def test_unit_has_links(self, oms_storage):
        unit_type = oms_storage.get_object_type("Unit")
        assert unit_type is not None
        links = unit_type.get("links", [])
        link_names = {l["name"] for l in links}
        assert "located_at" in link_names, f"Unit缺少located_at链接, 实际: {link_names}"
        assert "engaged_with" in link_names, f"Unit缺少engaged_with链接, 实际: {link_names}"


class TestSimulationDataIntegrity:
    def test_simulation_data_has_all_entity_types(self, simulation_data):
        expected_keys = {"locations", "military_units", "weapon_systems", "civilian_infrastructures", "battle_events", "missions"}
        actual_keys = set(simulation_data.keys())
        assert expected_keys.issubset(actual_keys), f"缺少实体类型: {expected_keys - actual_keys}"

    def test_locations_have_coordinates(self, simulation_data):
        for loc in simulation_data.get("locations", []):
            coords = loc.get("properties", {}).get("coordinates")
            assert coords is not None, f"位置 {loc.get('id')} 缺少坐标"
            assert len(coords) == 2, f"位置 {loc.get('id')} 坐标格式错误"

    def test_military_units_have_strength(self, simulation_data):
        for unit in simulation_data.get("military_units", []):
            props = unit.get("properties", {})
            assert "strength" in props, f"单位 {unit.get('id')} 缺少strength属性"

    def test_entities_have_relationships(self, simulation_data):
        for unit in simulation_data.get("military_units", []):
            rels = unit.get("relationships", {})
            assert "located_at" in rels, f"单位 {unit.get('id')} 缺少located_at关系"


class TestActionTriggerWithRealOMSData:
    def test_register_trigger_for_unit_attack(self, runtime_storage, oms_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine
        engine = ActionTriggerEngine(storage=runtime_storage)

        unit_type = oms_storage.get_object_type("Unit")
        assert unit_type is not None

        trigger_data = {
            "name": "低士气触发撤退",
            "description": "当Unit士气低于30时自动触发撤退动作",
            "conditions": [{
                "trigger_type": "state_driven",
                "object_type": "Unit",
                "property_name": "morale",
                "operator": "lt",
                "threshold_value": 30,
                "description": "士气低于30",
            }],
            "action_type_id": "retreat",
            "action_name": "撤退",
            "target_object_type": "Unit",
        }
        result = engine.register_trigger(trigger_data)
        assert result.get("trigger_id") is not None
        assert result.get("name") == "低士气触发撤退"

    def test_evaluate_trigger_with_real_unit_state(self, runtime_storage, oms_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine
        engine = ActionTriggerEngine(storage=runtime_storage)

        engine.register_trigger({
            "name": "高战损触发增援",
            "conditions": [{
                "trigger_type": "state_driven",
                "object_type": "Unit",
                "property_name": "combat_power",
                "operator": "lt",
                "threshold_value": 50,
            }],
            "action_type_id": "reinforce",
            "action_name": "增援",
            "target_object_type": "Unit",
        })

        matched = engine.evaluate_triggers("Unit", "unit-001", {"combat_power": 30, "morale": 80})
        assert len(matched) > 0, "战损30应触发增援"
        assert matched[0]["action_type_id"] == "reinforce"

    def test_evaluate_trigger_no_match_high_combat_power(self, runtime_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine
        engine = ActionTriggerEngine(storage=runtime_storage)

        engine.register_trigger({
            "name": "高战损触发增援",
            "conditions": [{
                "trigger_type": "state_driven",
                "object_type": "Unit",
                "property_name": "combat_power",
                "operator": "lt",
                "threshold_value": 50,
            }],
            "action_type_id": "reinforce",
            "action_name": "增援",
            "target_object_type": "Unit",
        })

        matched = engine.evaluate_triggers("Unit", "unit-001", {"combat_power": 90, "morale": 80})
        assert len(matched) == 0, "战损90不应触发增援"

    def test_execute_trigger_records_mutation(self, runtime_storage, oms_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.core.ontology.application.runtime.impl.state_propagation_engine import StatePropagationEngine
        propagation_engine = StatePropagationEngine(runtime_storage)
        engine = ActionTriggerEngine(storage=runtime_storage, propagation_engine=propagation_engine)

        trigger = engine.register_trigger({
            "name": "低士气触发撤退",
            "conditions": [{
                "trigger_type": "state_driven",
                "object_type": "Unit",
                "property_name": "morale",
                "operator": "lt",
                "threshold_value": 30,
            }],
            "action_type_id": "retreat",
            "action_name": "撤退",
            "target_object_type": "Unit",
        })

        result = engine.execute_trigger(trigger["trigger_id"], {
            "object_type": "Unit",
            "object_id": "unit-001",
            "state_changes": {"morale": 20},
        })
        assert result.get("status") == "completed"
        assert result.get("action_type_id") == "retreat"

        history = engine.get_execution_history(trigger_id=trigger["trigger_id"])
        assert len(history) > 0

    def test_multiple_triggers_with_real_oms_actions(self, runtime_storage, oms_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine
        engine = ActionTriggerEngine(storage=runtime_storage)

        engine.register_trigger({
            "name": "低士气撤退",
            "conditions": [{"trigger_type": "state_driven", "object_type": "Unit", "property_name": "morale", "operator": "lt", "threshold_value": 30}],
            "action_type_id": "retreat", "action_name": "撤退", "target_object_type": "Unit",
        })
        engine.register_trigger({
            "name": "低战力增援",
            "conditions": [{"trigger_type": "state_driven", "object_type": "Unit", "property_name": "combat_power", "operator": "lt", "threshold_value": 40}],
            "action_type_id": "reinforce", "action_name": "增援", "target_object_type": "Unit",
        })

        matched = engine.evaluate_triggers("Unit", "unit-001", {"morale": 20, "combat_power": 30})
        assert len(matched) == 2, f"应触发2个动作，实际触发{len(matched)}个"
        action_ids = {m["action_type_id"] for m in matched}
        assert "retreat" in action_ids
        assert "reinforce" in action_ids


class TestOntologyMemoryWithRealData:
    def test_store_and_retrieve_military_knowledge(self, memory_storage):
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType
        engine = OntologyMemoryEngine(storage=memory_storage)

        entry = MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content="波斯湾地区是美军第五舰队驻扎地，控制着霍尔木兹海峡的战略通道",
            keywords=["波斯湾", "美军", "第五舰队", "霍尔木兹海峡"],
            entities=["Location:LOC_A_1", "MilitaryUnit:US_5th_Fleet"],
            importance=0.9,
        )
        result = engine.store(entry)
        assert result.memory_id is not None
        assert result.status.value == "active"

    def test_hybrid_retrieval_with_military_scenario(self, memory_storage):
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType
        engine = OntologyMemoryEngine(storage=memory_storage)

        engine.store(MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content="伊朗革命卫队在海湾地区部署了反舰导弹",
            keywords=["伊朗", "革命卫队", "反舰导弹", "海湾"],
            entities=["MilitaryUnit:IRGC_Navy", "WeaponSystem:AntiShip_Missile"],
            importance=0.85,
        ))
        engine.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="2026年3月15日，胡塞武装在红海袭击商船",
            keywords=["胡塞", "红海", "商船", "袭击"],
            entities=["MilitaryUnit:Houthi_Forces", "Location:Red_Sea"],
            importance=0.7,
        ))
        engine.store(MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content="以色列铁穹防空系统拦截率约90%",
            keywords=["以色列", "铁穹", "防空", "拦截率"],
            entities=["WeaponSystem:Iron_Dome", "MilitaryUnit:IDF"],
            importance=0.6,
        ))

        results = engine.retrieve(query="海湾地区军事部署", top_k=3)
        assert len(results) > 0, "混合检索应返回结果"
        assert any("伊朗" in r.get("content", "") or "海湾" in r.get("content", "") for r in results)

    def test_decay_with_real_time_intervals(self, memory_storage):
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType, MemoryStatus
        engine = OntologyMemoryEngine(storage=memory_storage)

        old_time = datetime.now() - timedelta(days=60)
        entry = MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="60天前的旧情报",
            keywords=["旧情报"],
            importance=0.3,
            created_at=old_time,
            last_accessed_at=old_time,
        )
        memory_storage.save_memory(entry)

        result = engine.decay_update()
        assert result.get("updated_count", 0) > 0
        updated = memory_storage.get_memory(entry.memory_id)
        assert updated is not None
        assert updated.decay_factor < 1.0, f"60天未访问的记忆应有衰减, 实际: {updated.decay_factor}"

    def test_consolidate_duplicate_intelligence(self, memory_storage):
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType
        engine = OntologyMemoryEngine(storage=memory_storage)

        m1 = engine.store(MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content="伊朗在波斯湾部署了无人机侦察系统",
            keywords=["伊朗", "波斯湾", "无人机"],
            entities=["MilitaryUnit:IRGC"],
            importance=0.7,
        ))
        m2 = engine.store(MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content="波斯湾发现伊朗无人机活动",
            keywords=["伊朗", "波斯湾", "无人机"],
            entities=["MilitaryUnit:IRGC"],
            importance=0.6,
        ))

        result = engine.consolidate(memory_ids=[m1.memory_id, m2.memory_id], strategy="merge")
        assert result.get("result_id") is not None

    def test_forget_low_importance_memories(self, memory_storage):
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType
        engine = OntologyMemoryEngine(storage=memory_storage)

        old_time = datetime.now() - timedelta(days=120)
        entry = MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content="120天前的低价值情报",
            keywords=["低价值"],
            importance=0.1,
            decay_factor=0.05,
            created_at=old_time,
            last_accessed_at=old_time,
        )
        memory_storage.save_memory(entry)

        result = engine.forget(threshold=0.1)
        assert result.get("forgotten_count", 0) > 0, "应遗忘低价值记忆"


class TestTeamAgentWithRealOMSData:
    def test_planning_with_military_requirement(self, team_agent_storage, oms_storage):
        from odap.biz.core.ontology.application.team_agent.impl.team_agent_engine import TeamAgentEngine
        engine = TeamAgentEngine(storage=team_agent_storage)

        session = engine.create_session(
            name="军事态势感知本体构建",
            requirement="构建一个军事态势感知系统，需要管理作战单位、武器装备、地理位置和战斗事件，支持移动、攻击、防御等行动",
            scenario_id="scenario-military-001",
        )
        assert session.get("session_id") is not None

        result = engine.run_planning(session["session_id"])
        planning_output = result.get("planning_output", {})
        business_objects = planning_output.get("business_objects", [])
        assert len(business_objects) > 0, f"规划应识别出业务对象, 实际: {result}"

    def test_ontology_modeling_with_real_types(self, team_agent_storage, oms_storage):
        from odap.biz.core.ontology.application.team_agent.impl.team_agent_engine import TeamAgentEngine
        engine = TeamAgentEngine(storage=team_agent_storage)

        session = engine.create_session(
            name="本体建模测试",
            requirement="管理作战单位的移动、攻击和防御行动",
        )
        engine.run_planning(session["session_id"])
        result = engine.run_ontology_modeling(session["session_id"])
        ontology_output = result.get("ontology_output", {})
        assert ontology_output.get("object_types") is not None or result.get("session_id") is not None

    def test_full_pipeline_produces_workflow(self, team_agent_storage):
        from odap.biz.core.ontology.application.team_agent.impl.team_agent_engine import TeamAgentEngine
        from odap.biz.core.ontology.application.team_agent.models import TaskStatus
        engine = TeamAgentEngine(storage=team_agent_storage)

        session = engine.create_session(
            name="完整流水线测试",
            requirement="构建军事单位管理系统，包含作战单位、位置、装备和战斗事件",
        )
        result = engine.run_full_pipeline(session["session_id"])
        assert result.get("execution_output") is not None or result.get("status") == TaskStatus.WAITING_APPROVAL.value
        assert result.get("sub_tasks") is not None


class TestServitizationWithRealOMSData:
    def test_generate_query_skill_from_unit_type(self, servitization_storage, oms_storage):
        from odap.biz.core.ontology.application.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        engine = KnowledgeServitizationEngine(storage=servitization_storage)

        template = engine.create_template({
            "name": "query_unit_template",
            "description": "查询作战单位信息模板",
            "service_type": "skill",
            "object_type": "Unit",
            "parameter_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"results": {"type": "array"}}},
            "code_template": "class QueryUnitSkill: pass",
        })

        result = engine.generate_service(template["template_id"], {
            "name": "query_unit_skill",
            "description": "查询作战单位信息",
            "source_ontology_id": "military",
            "source_object_type": "Unit",
        })
        assert result.get("service_id") is not None
        assert result.get("status") == "completed"

    def test_generate_action_skill_from_attack_type(self, servitization_storage, oms_storage):
        from odap.biz.core.ontology.application.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        engine = KnowledgeServitizationEngine(storage=servitization_storage)

        attack_type = oms_storage.get_action_type("attack")
        assert attack_type is not None

        template = engine.create_template({
            "name": "action_attack_template",
            "description": "攻击动作模板",
            "service_type": "skill",
            "object_type": "Unit",
            "parameter_schema": {"type": "object", "properties": {"target_id": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"success": {"type": "boolean"}}},
            "code_template": "class AttackSkill: pass",
        })

        result = engine.generate_service(template["template_id"], {
            "name": "action_attack_skill",
            "description": "执行攻击动作",
            "source_ontology_id": "military",
            "source_object_type": "Unit",
        })
        assert result.get("service_id") is not None

    def test_generate_from_ontology_creates_multiple_services(self, servitization_storage, oms_storage):
        from odap.biz.core.ontology.application.servitization.impl.servitization_engine import KnowledgeServitizationEngine
        engine = KnowledgeServitizationEngine(storage=servitization_storage)

        result = engine.generate_from_ontology(ontology_id="military", service_type="skill")
        assert result.get("generated_count", 0) > 0, "应从OMS本体生成至少1个服务"
        services = result.get("services", [])
        assert len(services) > 0


class TestCrossModuleIntegration:
    def test_trigger_to_memory_flow(self, runtime_storage, memory_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine
        from odap.biz.platform.ontology_memory.impl.memory_engine import OntologyMemoryEngine
        from odap.biz.platform.ontology_memory.models import MemoryEntry, MemoryType

        trigger_engine = ActionTriggerEngine(storage=runtime_storage)
        memory_engine = OntologyMemoryEngine(storage=memory_storage)

        memory_engine.store(MemoryEntry(
            memory_type=MemoryType.SEMANTIC,
            content="Unit-001的士气通常维持在60以上",
            keywords=["士气", "Unit-001"],
            entities=["Unit:unit-001"],
            importance=0.5,
        ))

        trigger = trigger_engine.register_trigger({
            "name": "士气异常低触发警报",
            "conditions": [{"trigger_type": "state_driven", "object_type": "Unit", "property_name": "morale", "operator": "lt", "threshold_value": 30}],
            "action_type_id": "retreat", "action_name": "撤退", "target_object_type": "Unit",
        })

        matched = trigger_engine.evaluate_triggers("Unit", "unit-001", {"morale": 15})
        assert len(matched) > 0

        execution = trigger_engine.execute_trigger(trigger["trigger_id"], {
            "object_type": "Unit", "object_id": "unit-001", "state_changes": {"morale": 15},
        })
        assert execution.get("status") == "completed"

        memory_engine.store(MemoryEntry(
            memory_type=MemoryType.EPISODIC,
            content=f"Unit-001士气降至15，触发撤退动作，执行ID: {execution.get('execution_id')}",
            keywords=["士气", "撤退", "触发"],
            entities=["Unit:unit-001"],
            importance=0.8,
        ))

        results = memory_engine.retrieve(query="Unit-001 撤退", top_k=5)
        assert len(results) > 0

    def test_team_agent_to_servitization_flow(self, team_agent_storage, servitization_storage, oms_storage):
        from odap.biz.core.ontology.application.team_agent.impl.team_agent_engine import TeamAgentEngine
        from odap.biz.core.ontology.application.servitization.impl.servitization_engine import KnowledgeServitizationEngine

        team_engine = TeamAgentEngine(storage=team_agent_storage)
        serv_engine = KnowledgeServitizationEngine(storage=servitization_storage)

        session = team_engine.create_session(
            name="跨模块集成测试",
            requirement="构建军事单位管理系统",
        )
        pipeline_result = team_engine.run_full_pipeline(session["session_id"])
        assert pipeline_result.get("execution_output") is not None

        svc_result = serv_engine.generate_from_ontology(ontology_id="military", service_type="skill")
        assert svc_result.get("generated_count", 0) > 0

    def test_runtime_contract_to_trigger_flow(self, runtime_storage, oms_storage):
        from odap.biz.core.ontology.application.runtime.impl.action_contract_engine import ActionContractEngine
        from odap.biz.core.ontology.application.runtime.impl.action_trigger_engine import ActionTriggerEngine

        contract_engine = ActionContractEngine(runtime_storage)
        trigger_engine = ActionTriggerEngine(storage=runtime_storage)

        contract = contract_engine.create_contract({
            "action_type_id": "attack",
            "action_name": "攻击",
            "read_set": [{"object_type": "Unit", "property_name": "combat_power", "description": "读取战斗力"}],
            "write_set": [{"object_type": "Unit", "property_name": "combat_power", "description": "修改战斗力"}],
            "side_effect_set": [{"object_type": "Unit", "property_name": "morale", "description": "影响士气"}],
        })
        assert contract.get("contract_id") is not None

        trigger = trigger_engine.register_trigger({
            "name": "攻击后士气下降触发检查",
            "conditions": [{"trigger_type": "state_driven", "object_type": "Unit", "property_name": "morale", "operator": "lt", "threshold_value": 40}],
            "action_type_id": "reinforce", "action_name": "增援", "target_object_type": "Unit",
        })

        matched = trigger_engine.evaluate_triggers("Unit", "unit-001", {"morale": 30, "combat_power": 60})
        assert len(matched) > 0
        assert matched[0]["action_type_id"] == "reinforce"
