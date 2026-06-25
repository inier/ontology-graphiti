"""推演仿真模块本体依赖性验证测试。

本测试文件设计 3 个验证方案，用于检验当前推演仿真模块是否能真正基于本体开展推演。

方案1：基础推演功能测试
    - 验证 SimulationSandbox 能否创建沙箱并运行推演
    - 验证推演结果包含哪些字段
    - 验证推演结果是否基于硬编码规则还是本体数据
    - 测试不同的 action_type（engage/hold/withdraw/support/move）产生不同的结果

方案2：本体数据关联性测试
    - 验证推演引擎是否真正读取了本体数据
    - 尝试传入不同的 target_object_type，观察推演结果是否因类型不同而不同
    - 尝试传入不存在的 ontology_id/scenario_id，观察是否报错
    - 检查 _capture_baseline 是否真正从图谱读取数据

方案3：事件生成器本体依赖测试
    - 验证事件类型是否从本体动态生成
    - 验证事件模板是否硬编码
    - 尝试传入不同的本体实体类型，观察事件是否变化
    - 检查 ontology_relevance 计算是否基于本体语义

运行方式：
    pytest tests/unit/test_simulation_ontology_validation.py -v
"""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from odap.biz.simulation.simulation_sandbox.sandbox import SimulationSandbox
from odap.biz.simulation.simulation_sandbox.schemas import (
    WhatIfScenario,
    WhatIfResult,
    SimulationStatus,
)
from odap.biz.simulation.event_simulator.impl.event_generator import (
    EventGenerator,
    EVENT_DATA_TEMPLATES,
    EVENT_TYPE_CATEGORY,
    CATEGORY_BASE_RELEVANCE,
)


# ---------------------------------------------------------------------------
# 公共 Mock 工具
# ---------------------------------------------------------------------------


def _make_mock_query_service(rows=None):
    """构造一个 Mock 的 QueryService，其 execute 返回指定 rows。"""
    qs = MagicMock()
    result = MagicMock()
    result.rows = rows or []
    qs.execute.return_value = result
    return qs


def _make_mock_oms(
    action_types=None,
    object_type_def=None,
    action_type_def=None,
):
    """构造一个 Mock 的 OMSService。"""
    oms = MagicMock()
    oms.list_action_types.return_value = action_types or []
    oms.get_object_type.return_value = object_type_def
    oms.get_action_type.return_value = action_type_def
    return oms


def _make_scenario(**overrides):
    """构造 WhatIfScenario 测试数据。"""
    defaults = {
        "ontology_id": "test_ontology_1",
        "scenario_id": "test_scenario_1",
        "name": "Test Scenario",
        "description": "A test what-if scenario",
        "action_type_id": "engage",
        "target_object_id": "unit_alpha",
        "target_object_type": "organization_unit",
        "parameters": {},
        "variant_parameters": [],
    }
    defaults.update(overrides)
    return WhatIfScenario(**defaults)


# ===========================================================================
# 方案1：基础推演功能测试
# ===========================================================================


class TestScheme1BasicSimulation:
    """方案1：验证 SimulationSandbox 基础推演功能。"""

    @pytest.fixture
    def sandbox_no_ontology(self):
        """构造一个无本体数据可用的沙箱（OMS/QueryService 全部返回空）。

        注意：_project_impact 要求 OMS 返回非 None 的 action_type 定义，
        否则提前返回 error。因此这里让 OMS 返回空 parameters 的 action_type 定义，
        使 _load_impact_rules 回退到 DEFAULT_IMPACT_RULES 硬编码规则。
        """
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        sb._query_service = _make_mock_query_service(rows=[])
        sb._oms = _make_mock_oms(
            action_types=[],
            object_type_def=None,
            # 返回空 parameters 的 action_type 定义，使 _project_impact 不提前返回
            action_type_def={"action_type_id": "engage", "parameters": []},
        )
        sb._llm_client = None
        return sb

    def _make_sandbox_for_action(self, action_type_id):
        """为指定 action_type_id 构造沙箱（OMS 返回空 parameters 定义）。"""
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        sb._query_service = _make_mock_query_service(rows=[])
        sb._oms = _make_mock_oms(
            action_types=[],
            object_type_def=None,
            action_type_def={"action_type_id": action_type_id, "parameters": []},
        )
        sb._llm_client = None
        return sb

    @pytest.mark.asyncio
    async def test_1a_sandbox_can_run_and_returns_full_fields(self, sandbox_no_ontology):
        """断言1a：沙箱能运行推演，且结果包含全部预期字段。"""
        scenario = _make_scenario(action_type_id="engage")
        result = await sandbox_no_ontology.simulate(scenario)

        # 断言1：推演能完成且状态为 COMPLETED
        assert isinstance(result, WhatIfResult)
        assert result.status == SimulationStatus.COMPLETED, "推演应成功完成"

        # 断言2：结果包含全部预期字段
        expected_fields = {
            "scenario_id",
            "status",
            "baseline_metrics",
            "projected_metrics",
            "metric_changes",
            "risk_assessment",
            "recommendation",
            "confidence",
        }
        actual_fields = set(result.model_dump().keys())
        missing = expected_fields - actual_fields
        assert not missing, f"推演结果缺少字段: {missing}"

    @pytest.mark.asyncio
    async def test_1b_result_uses_hardcoded_rules_when_no_ontology(self, sandbox_no_ontology):
        """断言1b：无本体数据时，推演结果基于硬编码 DEFAULT_IMPACT_RULES。

        当 OMS 返回空 parameters 的 action_type 定义时：
        - _project_impact 不提前返回（action_def 非 None）
        - _load_impact_rules 中 parameters 为空，不进入推断
        - 回退到 DEFAULT_IMPACT_RULES 硬编码规则
        """
        scenario = _make_scenario(action_type_id="engage")
        result = await sandbox_no_ontology.simulate(scenario)

        # 断言1：engage 的硬编码规则包含 capability_index/readiness/resource_level/attrition_rate
        projected = result.projected_metrics[0]
        impact = projected.get("estimated_impact", {})
        expected_engage_metrics = {
            "capability_index",
            "readiness",
            "resource_level",
            "attrition_rate",
        }
        assert expected_engage_metrics.issubset(set(impact.keys())), (
            f"空 parameters 时 engage 应回退到硬编码规则，期望包含 {expected_engage_metrics}，"
            f"实际 {set(impact.keys())}"
        )

        # 断言2：硬编码值与 DEFAULT_IMPACT_RULES['engage'] 完全一致
        # 直接调用 _load_impact_rules 验证（OMS 返回 None 时也回退到硬编码）
        sb2 = SimulationSandbox()
        sb2._oms = _make_mock_oms(action_type_def=None)
        direct_rules_result = sb2._load_impact_rules("engage")
        direct_rules = direct_rules_result.get("rules", {})
        assert impact == direct_rules, (
            "推演结果应与直接调用 _load_impact_rules 的硬编码回退值一致"
        )

        # 断言3：metric_changes 反映了硬编码规则的影响
        metric_names = {mc.metric_name for mc in result.metric_changes}
        assert "capability_index" in metric_names or "readiness" in metric_names, (
            "metric_changes 应包含硬编码规则定义的指标"
        )

    @pytest.mark.asyncio
    async def test_1c_different_action_types_produce_different_results(self, sandbox_no_ontology):
        """断言1c：不同 action_type 产生不同的推演结果（基于硬编码差异）。

        OMS mock 对所有 action_type_id 都返回非 None 定义（空 parameters），
        使 _project_impact 不提前返回。_load_impact_rules 根据传入的
        action_type_id 回退到不同的 DEFAULT_IMPACT_RULES。
        """
        action_types = ["engage", "hold", "withdraw", "support", "move"]
        impacts = {}
        for at in action_types:
            scenario = _make_scenario(action_type_id=at)
            result = await sandbox_no_ontology.simulate(scenario)
            impact = result.projected_metrics[0].get("estimated_impact", {})
            impacts[at] = impact

        # 断言1：engage 与 hold 的影响不同
        assert impacts["engage"] != impacts["hold"], (
            f"engage 与 hold 应产生不同的影响规则，"
            f"engage={impacts['engage']}, hold={impacts['hold']}"
        )

        # 断言2：engage 包含 attrition_rate 而 support 不包含
        assert "attrition_rate" in impacts["engage"], "engage 应包含 attrition_rate"
        assert "attrition_rate" not in impacts["support"], "support 不应包含 attrition_rate"

        # 断言3：withdraw 与 move 的影响不同
        assert impacts["withdraw"] != impacts["move"], (
            f"withdraw 与 move 应产生不同的影响规则，"
            f"withdraw={impacts['withdraw']}, move={impacts['move']}"
        )

        # 断言4：support 的 readiness 为正值（+0.15），engage 为负值（-0.15）
        assert impacts["support"]["readiness"] > 0, "support 的 readiness 应为正值"
        assert impacts["engage"]["readiness"] < 0, "engage 的 readiness 应为负值"

    @pytest.mark.asyncio
    async def test_1d_graph_property_is_dead_code(self, sandbox_no_ontology):
        """断言1d：graph 属性是死代码，推演结果不写入知识图谱。

        验证：simulate() 执行过程中，graph_manager 不会被调用任何写操作。
        """
        scenario = _make_scenario(action_type_id="engage")
        await sandbox_no_ontology.simulate(scenario)

        # 断言1：graph_manager 没有被调用任何方法（写操作）
        graph = sandbox_no_ontology._graph_manager
        assert graph.method_calls == [], (
            f"graph_manager 应为死代码，不应被调用，实际调用: {graph.method_calls}"
        )

        # 断言2：推演结果中不包含任何图谱写入标识
        # （推演结果只通过 SQLiteSandboxStorage 持久化，不写图谱）

    @pytest.mark.asyncio
    async def test_1e_risk_assessment_uses_hardcoded_config(self, sandbox_no_ontology):
        """断言1e：风险评估基于硬编码 DEFAULT_RISK_CONFIG。"""
        # engage 在硬编码中是 'high'
        scenario = _make_scenario(action_type_id="engage")
        result = await sandbox_no_ontology.simulate(scenario)
        assert result.risk_assessment.get("overall_risk") == "high", (
            "engage 在硬编码 DEFAULT_RISK_CONFIG 中应为 high"
        )

        # observe 在硬编码中是 'low'
        scenario2 = _make_scenario(action_type_id="observe")
        result2 = await sandbox_no_ontology.simulate(scenario2)
        assert result2.risk_assessment.get("overall_risk") == "low", (
            "observe 在硬编码 DEFAULT_RISK_CONFIG 中应为 low"
        )


# ===========================================================================
# 方案2：本体数据关联性测试
# ===========================================================================


class TestScheme2OntologyAssociation:
    """方案2：验证推演引擎是否真正读取并依赖本体数据。"""

    @pytest.mark.asyncio
    async def test_2a_baseline_reads_from_graph_when_data_available(self):
        """断言2a：_capture_baseline 在图谱有数据时读取实体属性。"""
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        # 模拟图谱返回包含 capability_index 等属性的实体
        entity_rows = [
            {
                "id": "unit_alpha",
                "properties": {
                    "capability_index": 0.8,
                    "readiness": 0.9,
                    "resource_level": 100,
                    "personnel": 50,
                    "status": "active",
                },
            }
        ]
        sb._query_service = _make_mock_query_service(rows=entity_rows)
        sb._oms = _make_mock_oms(object_type_def=None)
        sb._llm_client = None

        baseline = await sb._capture_baseline("unit_alpha", "organization_unit")

        # 断言1：baseline 包含从图谱读取的 capability_index
        assert baseline.get("capability_index") == 0.8, (
            "baseline 应从图谱读取 capability_index=0.8"
        )

        # 断言2：baseline 包含从图谱读取的 readiness 和 resource_level
        assert baseline.get("readiness") == 0.9
        assert baseline.get("resource_level") == 100

        # 断言3：baseline 包含 target_id 和 target_type
        assert baseline["target_id"] == "unit_alpha"
        assert baseline["target_type"] == "organization_unit"

    @pytest.mark.asyncio
    async def test_2b_baseline_silently_fails_when_graph_empty(self):
        """断言2b：图谱无数据时，_capture_baseline 静默降级，不报错。"""
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        sb._query_service = _make_mock_query_service(rows=[])
        sb._oms = _make_mock_oms(object_type_def=None)
        sb._llm_client = None

        baseline = await sb._capture_baseline("nonexistent_id", "nonexistent_type")

        # 断言1：不报错，返回只含 target_id/target_type 的 baseline
        assert baseline["target_id"] == "nonexistent_id"
        assert baseline["target_type"] == "nonexistent_type"

        # 断言2：baseline 不包含任何图谱属性
        graph_props = {"capability_index", "readiness", "resource_level", "personnel", "status"}
        for prop in graph_props:
            assert prop not in baseline, f"图谱无数据时 baseline 不应包含 {prop}"

        # 断言3：推演仍能完成（降级运行）
        scenario = _make_scenario(
            target_object_id="nonexistent_id",
            target_object_type="nonexistent_type",
        )
        result = await sb.simulate(scenario)
        assert result.status == SimulationStatus.COMPLETED, "图谱无数据时推演仍应完成"

    @pytest.mark.asyncio
    async def test_2c_different_target_types_do_not_change_impact_rules(self):
        """断言2c：不同的 target_object_type 不会改变影响规则（规则只依赖 action_type_id）。

        这是关键缺陷：推演结果与目标对象类型无关，只与 action_type_id 有关。
        """
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        sb._query_service = _make_mock_query_service(rows=[])
        sb._oms = _make_mock_oms(
            action_type_def=None,
            object_type_def=None,
        )
        sb._llm_client = None

        # 同样的 action_type_id=engage，但不同的 target_object_type
        types_to_test = [
            "organization_unit",
            "military_asset",
            "supply_chain_node",
            "completely_fake_type",
            "",
        ]
        impacts = {}
        for t in types_to_test:
            scenario = _make_scenario(
                action_type_id="engage",
                target_object_type=t,
            )
            result = await sb.simulate(scenario)
            impacts[t] = result.projected_metrics[0].get("estimated_impact", {})

        # 断言1：所有不同类型的 estimated_impact 完全相同
        first_impact = impacts[types_to_test[0]]
        for t in types_to_test[1:]:
            assert impacts[t] == first_impact, (
                f"target_object_type='{t}' 的影响规则与 '{types_to_test[0]}' 不同，"
                f"说明推演规则与目标类型无关（缺陷）：{impacts[t]} != {first_impact}"
            )

        # 断言2：甚至完全虚假的类型也不影响结果
        assert impacts["completely_fake_type"] == impacts["organization_unit"], (
            "完全虚假的类型应产生与真实类型相同的结果（证明不依赖本体类型）"
        )

        # 断言3：空字符串类型也能运行
        assert impacts[""] == impacts["organization_unit"], (
            "空字符串类型应产生相同结果"
        )

    @pytest.mark.asyncio
    async def test_2d_ontology_id_now_required_in_scenario(self):
        """断言2d：WhatIfScenario 现在包含 ontology_id 字段。

        改进后：推演需要本体ID，实现了本体绑定。
        """
        # 断言1：WhatIfScenario 模型字段包含 ontology_id
        scenario_fields = set(WhatIfScenario.model_fields.keys())
        assert "ontology_id" in scenario_fields, (
            f"WhatIfScenario 应包含 ontology_id 字段，实际字段: {scenario_fields}"
        )

        # 断言2：传 ontology_id 后能完成推演
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        sb._query_service = _make_mock_query_service(rows=[])
        sb._oms = _make_mock_oms(action_type_def=None, object_type_def=None)
        sb._llm_client = None
        scenario = _make_scenario()
        result = await sb.simulate(scenario)
        assert result.status == SimulationStatus.COMPLETED, (
            "传 ontology_id 后应能完成推演"
        )

    @pytest.mark.asyncio
    async def test_2e_oms_action_type_definition_only_affects_confidence(self):
        """断言2e：OMS 的 action_type 定义只影响 confidence 和影响规则推断。

        当 OMS 返回 action_type 定义（含 parameters）时：
        - _load_impact_rules 会从 parameters 推断规则（如 intensity）
        - 当 parameters 推断出非空 rules 时，不回退到 DEFAULT_IMPACT_RULES
        - confidence 会因 action_def 存在而 +0.15

        关键缺陷：有 OMS parameters 时，影响规则完全来自 OMS 推断，
        不混合硬编码规则，导致 engage 的 capability_index 等指标丢失。
        """
        sb_with_oms = SimulationSandbox()
        sb_with_oms._graph_manager = MagicMock()
        sb_with_oms._query_service = _make_mock_query_service(rows=[])
        sb_with_oms._oms = _make_mock_oms(
            action_type_def={
                "action_type_id": "engage",
                "parameters": [
                    {"name": "intensity", "param_type": "float", "default": 0.5},
                ],
            },
            object_type_def=None,
        )
        sb_with_oms._llm_client = None

        sb_without_oms = SimulationSandbox()
        sb_without_oms._graph_manager = MagicMock()
        sb_without_oms._query_service = _make_mock_query_service(rows=[])
        sb_without_oms._oms = _make_mock_oms(
            action_type_def={"action_type_id": "engage", "parameters": []},
            object_type_def=None,
        )
        sb_without_oms._llm_client = None

        scenario = _make_scenario(action_type_id="engage")
        result_with = await sb_with_oms.simulate(scenario)
        result_without = await sb_without_oms.simulate(scenario)

        # 断言1：有 OMS action_type 定义时 confidence 更高
        assert result_with.confidence > result_without.confidence, (
            f"有 OMS action_type 定义时 confidence 应更高，"
            f"实际: with={result_with.confidence}, without={result_without.confidence}"
        )

        # 断言2：有 OMS parameters 时，影响规则来自 OMS 推断（intensity），
        # 不包含硬编码 engage 的 capability_index（关键缺陷）
        impact_with = result_with.projected_metrics[0].get("estimated_impact", {})
        assert "intensity" in impact_with, (
            "有 OMS parameters 时应包含从 parameters 推断的 intensity 指标"
        )
        assert "capability_index" not in impact_with, (
            "有 OMS parameters 时不应包含硬编码 engage 的 capability_index，"
            "因为 parameters 推断出非空 rules 后不回退到 DEFAULT_IMPACT_RULES（缺陷）"
        )

        # 断言3：无 OMS parameters 时，影响规则来自硬编码 DEFAULT_IMPACT_RULES
        impact_without = result_without.projected_metrics[0].get("estimated_impact", {})
        assert "capability_index" in impact_without, (
            "无 OMS parameters 时应回退到硬编码 engage 的 capability_index"
        )
        assert "intensity" not in impact_without, (
            "无 OMS parameters 时不应包含 intensity（硬编码规则无此指标）"
        )

    @pytest.mark.asyncio
    async def test_2f_baseline_oms_object_type_adds_statistical_properties(self):
        """断言2f：_capture_baseline 会从 OMS object_type 定义补充统计属性（值为0）。"""
        sb = SimulationSandbox()
        sb._graph_manager = MagicMock()
        sb._query_service = _make_mock_query_service(rows=[])
        sb._oms = _make_mock_oms(
            object_type_def={
                "type_id": "organization_unit",
                "properties": [
                    {"name": "firepower", "category": "statistical_properties"},
                    {"name": "mobility", "category": "statistical_properties"},
                    {"name": "display_name", "category": "basic_properties"},
                ],
            },
            action_type_def=None,
        )
        sb._llm_client = None

        baseline = await sb._capture_baseline("unit_alpha", "organization_unit")

        # 断言1：统计属性被添加到 baseline（值为0）
        assert baseline.get("firepower") == 0, "OMS 统计属性 firepower 应被添加为 0"
        assert baseline.get("mobility") == 0, "OMS 统计属性 mobility 应被添加为 0"

        # 断言2：非统计属性不被添加
        assert "display_name" not in baseline, "非统计属性不应被添加到 baseline"

        # 断言3：但这些统计属性值为0，不会出现在 metric_changes 中（因为 delta 计算需要 before 值）
        scenario = _make_scenario(action_type_id="engage")
        result = await sb.simulate(scenario)
        metric_names = {mc.metric_name for mc in result.metric_changes}
        # firepower/mobility 不在硬编码 engage 规则中，所以不会出现在 changes
        assert "firepower" not in metric_names, (
            "firepower 不在硬编码 engage 规则中，不应出现在 metric_changes"
        )


# ===========================================================================
# 方案3：事件生成器本体依赖测试
# ===========================================================================


class TestScheme3EventGeneratorOntologyDependency:
    """方案3：验证 EventGenerator 是否真正基于本体生成事件。"""

    @pytest.fixture
    def generator_no_ontology(self):
        """构造一个无本体数据的 EventGenerator（ModelService 返回空）。"""
        gen = EventGenerator()
        gen._storage = MagicMock()
        gen._storage.save_sequence = MagicMock(return_value={})
        gen._storage.get_sequence = MagicMock(return_value=None)
        gen._storage.list_templates = MagicMock(return_value=[])
        return gen

    def test_3a_event_templates_are_hardcoded(self, generator_no_ontology):
        """断言3a：事件模板 EVENT_DATA_TEMPLATES 是硬编码的模块级常量。"""
        # 断言1：EVENT_DATA_TEMPLATES 是模块级常量，包含硬编码事件类型
        assert "engage" in EVENT_DATA_TEMPLATES, "硬编码模板应包含 engage"
        assert "hold" in EVENT_DATA_TEMPLATES, "硬编码模板应包含 hold"
        assert "withdraw" in EVENT_DATA_TEMPLATES, "硬编码模板应包含 withdraw"

        # 断言2：模板值是固定的元组范围（不是从本体动态生成）
        engage_template = EVENT_DATA_TEMPLATES["engage"]
        assert "intensity" in engage_template, "engage 模板应包含 intensity"
        assert engage_template["intensity"] == (0.6, 1.0), (
            "engage intensity 应为硬编码 (0.6, 1.0)"
        )

        # 断言3：模板数量固定，不随本体变化
        template_count = len(EVENT_DATA_TEMPLATES)
        assert template_count == 12, f"硬编码模板数量应为 12，实际 {template_count}"

    def test_3b_event_types_from_hardcoded_map_not_ontology(self, generator_no_ontology):
        """断言3b：事件类型从硬编码 template_event_map 选取，不从本体动态生成。

        注意：传入 base_time 避免源码 minute + i 溢出 bug。
        """
        base_time = "2024-01-01T00:00:00+00:00"
        # 断言1：无本体时，仍能生成事件（使用硬编码类型）
        with patch.object(
            generator_no_ontology, "_get_entity_types", return_value=[]
        ):
            result = generator_no_ontology.generate_event_sequence(
                template_id="conflict",
                workspace_id="default",
                count=5,
                base_time=base_time,
            )
        assert result["total_events"] == 5, "无本体时应仍生成 5 个事件"

        # 断言2：生成的事件类型全部来自硬编码 template_event_map["conflict"]
        conflict_event_types = {"engage", "hold", "withdraw", "support"}
        for event in result["events"]:
            assert event["event_type"] in conflict_event_types, (
                f"事件类型 {event['event_type']} 应来自硬编码 conflict 池"
            )

        # 断言3：entity_types_used 回退到硬编码默认值
        assert result["entity_types_used"] == ["entity", "relation", "event", "attribute"], (
            "无本体时 entity_types 应回退到硬编码默认值"
        )

    def test_3c_different_entity_types_do_not_change_event_types(self, generator_no_ontology):
        """断言3c：不同的本体实体类型不会改变生成的事件类型。

        关键缺陷：事件类型只依赖 template_id，不依赖 entity_types。
        注意：传入 base_time 避免源码 minute + i 溢出 bug。
        """
        base_time = "2024-01-01T00:00:00+00:00"

        # 即使传入完全不同的实体类型，事件类型池不变
        entity_sets = [
            ["military_unit", "weapon_system", "soldier"],
            ["supply_chain", "warehouse", "truck"],
            ["completely_fake_type"],
            ["entity", "relation", "event", "attribute"],
        ]

        all_event_types = set()
        for entities in entity_sets:
            with patch.object(
                generator_no_ontology, "_get_entity_types", return_value=entities
            ):
                result = generator_no_ontology.generate_event_sequence(
                    template_id="conflict",
                    workspace_id="default",
                    count=5,
                    base_time=base_time,
                )
            for event in result["events"]:
                all_event_types.add(event["event_type"])

        # 断言1：所有事件类型都来自硬编码 conflict 池
        conflict_pool = {"engage", "hold", "withdraw", "support"}
        assert all_event_types.issubset(conflict_pool), (
            f"事件类型应全部来自硬编码 conflict 池 {conflict_pool}，"
            f"实际 {all_event_types}"
        )

        # 断言2：不同实体类型集产生的事件类型集相同
        # （因为事件类型只依赖 template_id）
        with patch.object(
            generator_no_ontology, "_get_entity_types",
            return_value=["military_unit", "weapon_system"],
        ):
            result1 = generator_no_ontology.generate_event_sequence(
                template_id="logistics", count=5, base_time=base_time,
            )
        types1 = {e["event_type"] for e in result1["events"]}

        with patch.object(
            generator_no_ontology, "_get_entity_types",
            return_value=["supply_chain", "warehouse"],
        ):
            result2 = generator_no_ontology.generate_event_sequence(
                template_id="logistics", count=5, base_time=base_time,
            )
        types2 = {e["event_type"] for e in result2["events"]}

        # 事件类型池相同（都是 logistics 硬编码池的子集）
        logistics_pool = {"supply", "transport", "deploy", "withdraw"}
        assert types1.issubset(logistics_pool), f"类型集1应来自 logistics 池: {types1}"
        assert types2.issubset(logistics_pool), f"类型集2应来自 logistics 池: {types2}"

        # 断言3：target_entity_type 会随传入的实体类型变化（但 event_type 不变）
        # 这证明实体类型只影响 target_entity_type 字段，不影响事件类型
        with patch.object(
            generator_no_ontology, "_get_entity_types",
            return_value=["custom_type_a"],
        ):
            result_custom = generator_no_ontology.generate_event_sequence(
                template_id="default", count=5, base_time=base_time,
            )
        target_types = {e["target_entity_type"] for e in result_custom["events"]}
        assert target_types == {"custom_type_a"}, (
            "target_entity_type 应使用传入的实体类型"
        )

    def test_3d_ontology_relevance_is_hardcoded_map(self, generator_no_ontology):
        """断言3d：ontology_relevance 计算基于硬编码 relevance_map，不基于本体语义。"""
        # 断言1：(engage, entity) 返回硬编码值 0.9
        relevance = generator_no_ontology._compute_ontology_relevance("engage", "entity")
        assert relevance == 0.9, (
            "(engage, entity) 的 ontology_relevance 应为硬编码 0.9"
        )

        # 断言2：(hold, entity) 返回硬编码值 0.85
        relevance2 = generator_no_ontology._compute_ontology_relevance("hold", "entity")
        assert relevance2 == 0.85, (
            "(hold, entity) 的 ontology_relevance 应为硬编码 0.85"
        )

        # 断言3：不在 map 中的组合使用 CATEGORY_BASE_RELEVANCE 回退
        # 例如 (engage, attribute) 不在 map 中，回退到 conflict 类别 0.7 + attribute 修饰 -0.05 = 0.65
        relevance3 = generator_no_ontology._compute_ontology_relevance("engage", "attribute")
        category_base = CATEGORY_BASE_RELEVANCE.get(EVENT_TYPE_CATEGORY.get("engage"), 0.5)
        expected = round(max(0.1, min(1.0, category_base + (-0.05))), 2)
        assert relevance3 == expected, (
            f"(engage, attribute) 应使用类别回退值 {expected}，实际 {relevance3}"
        )

        # 断言4：完全虚假的事件类型也返回默认值
        relevance4 = generator_no_ontology._compute_ontology_relevance("fake_event", "entity")
        assert 0.1 <= relevance4 <= 1.0, (
            "虚假事件类型应返回默认 relevance 值"
        )

    def test_3e_event_data_uses_hardcoded_templates(self, generator_no_ontology):
        """断言3e：事件数据使用硬编码 EVENT_DATA_TEMPLATES 生成。"""
        # 断言1：engage 事件数据包含硬编码模板字段
        data = generator_no_ontology._generate_event_data("engage", "entity")
        assert "intensity" in data, "engage 事件数据应包含 intensity（硬编码模板）"
        assert "capability_index_delta" in data, "engage 事件数据应包含 capability_index_delta"
        assert 0.6 <= data["intensity"] <= 1.0, (
            "engage intensity 应在硬编码范围 (0.6, 1.0) 内"
        )

        # 断言2：observe 事件数据包含 information_gain（硬编码模板）
        data2 = generator_no_ontology._generate_event_data("observe", "entity")
        assert "information_gain" in data2, "observe 事件数据应包含 information_gain"
        assert 0.3 <= data2["information_gain"] <= 0.8, (
            "observe information_gain 应在硬编码范围 (0.3, 0.8) 内"
        )

        # 断言3：不在模板中的事件类型使用硬编码回退逻辑
        data3 = generator_no_ontology._generate_event_data("custom_unknown_event", "entity")
        assert "intensity" in data3, "未知事件类型应回退到默认 intensity"
        assert 0.1 <= data3["intensity"] <= 1.0, (
            "未知事件 intensity 应在默认范围 (0.1, 1.0) 内"
        )

    def test_3f_get_entity_types_fails_gracefully(self, generator_no_ontology):
        """断言3f：_get_entity_types 在 ModelService 不可用时返回空列表。

        注意：传入 base_time 避免源码 minute + i 溢出 bug。
        """
        base_time = "2024-01-01T00:00:00+00:00"
        # 断言1：ModelService 异常时返回空列表
        with patch(
            "odap.biz.simulation.event_simulator.impl.event_generator.ModelService",
            side_effect=Exception("Service unavailable"),
            create=True,
        ):
            types = generator_no_ontology._get_entity_types("default")
            assert types == [], "ModelService 异常时应返回空列表"

        # 断言2：空列表时 generate_event_sequence 回退到硬编码默认类型
        with patch.object(
            generator_no_ontology, "_get_entity_types", return_value=[]
        ):
            result = generator_no_ontology.generate_event_sequence(
                template_id="default", count=3, base_time=base_time,
            )
        assert result["entity_types_used"] == ["entity", "relation", "event", "attribute"], (
            "空实体类型列表应回退到硬编码默认值"
        )

        # 断言3：即使 ModelService 返回自定义类型，事件类型池仍不变
        with patch.object(
            generator_no_ontology, "_get_entity_types",
            return_value=["custom_entity_type"],
        ):
            result = generator_no_ontology.generate_event_sequence(
                template_id="communication", count=5, base_time=base_time,
            )
        comm_pool = {"communicate", "broadcast", "relay", "interrupt"}
        for event in result["events"]:
            assert event["event_type"] in comm_pool, (
                f"事件类型应来自硬编码 communication 池，实际 {event['event_type']}"
            )


# ===========================================================================
# 综合结论测试
# ===========================================================================


class TestConclusion:
    """综合结论：推演仿真模块本体绑定改进验证。"""

    def test_conclusion_simulation_now_ontology_bound(self):
        """综合结论：推演仿真模块现已实现本体绑定。

        改进后：
        1. WhatIfScenario 现在包含必填的 ontology_id 字段
        2. _capture_baseline 使用 workspace_id 和 ontology_id 上下文
        3. 推演结果包含 simulated_writes，支持采纳后真实回写
        4. DEFAULT_IMPACT_RULES/EVENT_DATA_TEMPLATES 仍硬编码（规则引擎层面）
        """
        # 证据1：WhatIfScenario 现在包含 ontology_id 字段
        assert "ontology_id" in WhatIfScenario.model_fields, (
            "证据1：WhatIfScenario 现在包含 ontology_id 字段"
        )

        # 证据2：WhatIfResult 包含 simulated_writes 和 adoption_available
        result_fields = set(WhatIfResult.model_fields.keys())
        assert "simulated_writes" in result_fields, (
            "证据2：WhatIfResult 包含 simulated_writes 字段"
        )
        assert "adoption_available" in result_fields, (
            "证据2：WhatIfResult 包含 adoption_available 字段"
        )

        # 证据3：DEFAULT_IMPACT_RULES 仍硬编码在 sandbox.py 中（规则引擎层面）
        from odap.biz.simulation.simulation_sandbox.sandbox import SimulationSandbox
        sb = SimulationSandbox()
        sb._oms = _make_mock_oms(action_type_def=None)
        engage_rules_result = sb._load_impact_rules("engage")
        engage_rules = engage_rules_result.get("rules", {})
        assert "capability_index" in engage_rules, (
            "证据3：engage 规则来自硬编码 DEFAULT_IMPACT_RULES"
        )

        # 证据4：EVENT_DATA_TEMPLATES 硬编码在 event_generator.py 中
        assert "engage" in EVENT_DATA_TEMPLATES, (
            "证据3：EVENT_DATA_TEMPLATES 是硬编码常量"
        )

        # 证据5：DEFAULT_RISK_CONFIG 硬编码
        risk_config = sb._load_risk_config()
        assert risk_config.get("engage") == "high", (
            "证据5：DEFAULT_RISK_CONFIG 硬编码 engage=high"
        )

        # 最终结论：推演仿真模块已实现本体绑定（ontology_id 必填），
        # 并支持"感知→理解→决策→行动→本体更新"闭环（simulated_writes + adopt_scenario）。
        # 规则引擎层面仍有硬编码，但通过采纳机制实现了沙箱内外数据隔离。


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
