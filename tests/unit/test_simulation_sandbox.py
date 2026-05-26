import pytest
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from odap.biz.simulation.simulation_sandbox.sandbox import SimulationSandbox
from odap.biz.simulation.simulation_sandbox.schemas import (
    WhatIfScenario,
    WhatIfResult,
    WhatIfComparison,
    MetricChange,
    SimulationStatus,
)


@pytest.fixture
def sandbox():
    sb = SimulationSandbox()
    sb._graph_manager = MagicMock()
    sb._oms = MagicMock()
    sb._llm_client = None
    return sb


@pytest.fixture
def mock_graph(sandbox):
    sandbox._graph_manager.query_entities.return_value = []
    return sandbox._graph_manager


@pytest.fixture
def mock_oms(sandbox):
    sandbox._oms.get_action_type.return_value = {
        'action_type_id': 'attack',
        'parameters': [],
    }
    sandbox._oms.get_object_type.return_value = None
    sandbox._oms.list_action_types.return_value = []
    return sandbox._oms


def _make_scenario(**overrides):
    defaults = {
        'scenario_id': 'test_scenario_1',
        'name': 'Test Scenario',
        'description': 'A test what-if scenario',
        'action_type_id': 'attack',
        'target_object_id': 'unit_alpha',
        'target_object_type': 'military_unit',
        'parameters': {},
        'variant_parameters': [],
    }
    defaults.update(overrides)
    return WhatIfScenario(**defaults)


def _mock_projected(action_type_id='attack'):
    impact = {
        'attack': {'combat_power': -0.2, 'morale': -0.15, 'supply_level': -0.3, 'casualty_rate': 0.15},
        'defend': {'combat_power': -0.05, 'morale': 0.1, 'supply_level': -0.1},
        'move': {'supply_level': -0.1, 'morale': -0.05},
        'reinforce': {'strength': 0.3, 'morale': 0.15, 'supply_level': -0.15},
        'observe': {'supply_level': -0.02},
    }.get(action_type_id, {})

    return [{
        'target_id': 'unit_alpha',
        'action': action_type_id,
        'parameters': {},
        'estimated_impact': impact,
    }]


def _mock_baseline():
    return {
        'target_id': 'unit_alpha',
        'target_type': 'military_unit',
        'combat_power': 80,
        'morale': 70,
        'supply_level': 90,
    }


def test_create_scenario(sandbox, mock_graph, mock_oms):
    sandbox._capture_baseline = AsyncMock(return_value=_mock_baseline())
    sandbox._project_impact = AsyncMock(return_value=_mock_projected('attack'))

    scenario = _make_scenario()
    result = asyncio.run(sandbox.simulate(scenario))

    assert isinstance(result, WhatIfResult)
    assert result.scenario_id == 'test_scenario_1'
    assert result.status == SimulationStatus.COMPLETED
    assert result.baseline_metrics is not None
    assert result.projected_metrics is not None
    assert result.confidence == 0.6


def test_run_simulation(sandbox, mock_graph, mock_oms):
    baseline = {
        'target_id': 'unit_alpha',
        'target_type': 'military_unit',
        'combat_power': 80,
        'morale': 70,
        'supply_level': 90,
        'strength': 100,
    }
    sandbox._capture_baseline = AsyncMock(return_value=baseline)
    sandbox._project_impact = AsyncMock(return_value=_mock_projected('attack'))

    scenario = _make_scenario(action_type_id='attack')
    result = asyncio.run(sandbox.simulate(scenario))

    assert result.status == SimulationStatus.COMPLETED
    assert 'combat_power' in result.baseline_metrics
    assert 'morale' in result.baseline_metrics
    assert len(result.projected_metrics) > 0
    assert result.projected_metrics[0]['action'] == 'attack'
    assert 'estimated_impact' in result.projected_metrics[0]


def test_compare_scenarios(sandbox, mock_graph, mock_oms):
    sandbox._capture_baseline = AsyncMock(return_value=_mock_baseline())

    def project_side_effect(target_id, target_type, action_type_id, parameters):
        return _mock_projected(action_type_id)

    sandbox._project_impact = AsyncMock(side_effect=project_side_effect)

    scenario_a = _make_scenario(
        scenario_id='scenario_a',
        action_type_id='attack',
    )
    scenario_b = _make_scenario(
        scenario_id='scenario_b',
        action_type_id='defend',
    )

    comparison = asyncio.run(sandbox.compare([scenario_a, scenario_b]))

    assert isinstance(comparison, WhatIfComparison)
    assert len(comparison.scenarios) == 2
    assert comparison.best_scenario_id is not None
    assert comparison.summary != ''
    assert 'scenario_a' in comparison.summary
    assert 'scenario_b' in comparison.summary


def test_get_scenario(sandbox, mock_graph, mock_oms):
    sandbox._capture_baseline = AsyncMock(return_value=_mock_baseline())
    sandbox._project_impact = AsyncMock(return_value=_mock_projected('attack'))

    scenario = _make_scenario(scenario_id='unique_scenario_42')
    result = asyncio.run(sandbox.simulate(scenario))

    assert result.scenario_id == 'unique_scenario_42'
    assert isinstance(result, WhatIfResult)
    assert result.status == SimulationStatus.COMPLETED


def test_list_scenarios(sandbox, mock_graph, mock_oms):
    sandbox._capture_baseline = AsyncMock(return_value=_mock_baseline())

    def project_side_effect(target_id, target_type, action_type_id, parameters):
        return _mock_projected(action_type_id)

    sandbox._project_impact = AsyncMock(side_effect=project_side_effect)

    scenario_a = _make_scenario(scenario_id='list_s1', action_type_id='attack')
    scenario_b = _make_scenario(scenario_id='list_s2', action_type_id='defend')

    result_a = asyncio.run(sandbox.simulate(scenario_a))
    result_b = asyncio.run(sandbox.simulate(scenario_b))

    scenario_ids = [result_a.scenario_id, result_b.scenario_id]
    assert 'list_s1' in scenario_ids
    assert 'list_s2' in scenario_ids

    sandbox.create_plan_branch('plan_1')
    sandbox.create_plan_branch('plan_1')
    versions = sandbox.list_plan_versions('plan_1')
    assert len(versions) == 3


def test_delete_scenario(sandbox, mock_graph, mock_oms):
    sandbox.create_plan_branch('plan_delete')
    sandbox.create_plan_branch('plan_delete')
    sandbox.create_plan_branch('plan_delete')

    versions_before = sandbox.list_plan_versions('plan_delete')
    assert len(versions_before) == 4

    rollback_result = sandbox.rollback_plan('plan_delete', 'v2')
    assert rollback_result['current_version'] == 'v2'

    versions_after = sandbox.list_plan_versions('plan_delete')
    assert len(versions_after) == 2
    assert all(v['version'] <= 'v2' for v in versions_after)


def test_simulation_with_parameters(sandbox, mock_graph, mock_oms):
    sandbox._capture_baseline = AsyncMock(return_value=_mock_baseline())

    projected = [{
        'target_id': 'unit_alpha',
        'action': 'move',
        'parameters': {'speed': 50, 'route': 'northern_pass'},
        'estimated_impact': {'supply_level': -0.1, 'morale': -0.05},
    }]
    sandbox._project_impact = AsyncMock(return_value=projected)

    scenario = _make_scenario(
        action_type_id='move',
        parameters={'speed': 50, 'route': 'northern_pass'},
    )
    result = asyncio.run(sandbox.simulate(scenario))

    assert result.status == SimulationStatus.COMPLETED
    assert len(result.projected_metrics) > 0
    assert result.projected_metrics[0]['parameters'] == {'speed': 50, 'route': 'northern_pass'}
    assert result.projected_metrics[0]['action'] == 'move'


def test_risk_assessment(sandbox, mock_graph, mock_oms):
    sandbox._capture_baseline = AsyncMock(return_value=_mock_baseline())
    sandbox._project_impact = AsyncMock(return_value=_mock_projected('attack'))

    scenario = _make_scenario(action_type_id='attack')
    result = asyncio.run(sandbox.simulate(scenario))

    risk = result.risk_assessment
    assert 'overall_risk' in risk
    assert 'risk_factors' in risk
    assert 'negative_impact_count' in risk
    assert risk['overall_risk'] in ('low', 'medium', 'high')

    attack_risk = sandbox._assess_risk('attack', result.metric_changes)
    assert attack_risk['overall_risk'] == 'high'

    observe_risk = sandbox._assess_risk('observe', result.metric_changes)
    assert observe_risk['overall_risk'] in ('low', 'medium', 'high')
