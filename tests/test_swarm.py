"""
Swarm 组件测试用例
测试 BattlefieldSwarm、FaultTolerance、StatePersistence 和 HealthMonitor
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.swarm_orchestrator import (
    BattlefieldSwarm,
    CommanderAgent,
    OperationsAgent,
    IntelligenceAgentSwarm,
    AgentType,
    OODAPhase,
    OODAStatus,
    AgentConfig,
    MissionResult,
)
from core.fault_tolerance import (
    FaultRecoveryManager,
    AgentState,
    FailureType,
    FailureRecord,
)
from core.state_persistence import StatePersistenceManager
from core.health_monitor import HealthMonitor, HealthMetric


def test_swarm_enums():
    """测试 Swarm 枚举定义"""
    print("=== 测试 Swarm 枚举 ===")
    assert AgentType.COMMANDER.value == "commander"
    assert AgentType.INTELLIGENCE.value == "intelligence"
    assert AgentType.OPERATIONS.value == "operations"
    assert OODAPhase.OBSERVE.value == "observe"
    assert OODAPhase.ORIENT.value == "orient"
    assert OODAPhase.DECIDE.value == "decide"
    assert OODAPhase.ACT.value == "act"
    print("枚举定义测试通过")
    return True


def test_agent_config():
    """测试 AgentConfig 配置"""
    print("\n=== 测试 AgentConfig ===")
    config = AgentConfig(
        name="TestAgent",
        agent_type=AgentType.COMMANDER,
        model="test-model",
        role="commander",
        tools=["*"],
        permission_level="commander",
    )
    assert config.name == "TestAgent"
    assert config.agent_type == AgentType.COMMANDER
    assert config.requires_opa_approval == False
    print("AgentConfig 测试通过")
    return True


def test_mission_result():
    """测试 MissionResult 数据类"""
    print("\n=== 测试 MissionResult ===")
    result = MissionResult(
        mission_id="test-123",
        success=True,
        phases_completed=[OODAPhase.OBSERVE, OODAPhase.ORIENT],
        final_decision={"action": "test"},
        execution_time_ms=100.5,
    )
    assert result.mission_id == "test-123"
    assert result.success == True
    assert len(result.phases_completed) == 2
    assert result.execution_time_ms == 100.5
    result_dict = result.to_dict()
    assert "mission_id" in result_dict
    print("MissionResult 测试通过")
    return True


def test_fault_tolerance_enums():
    """测试故障类型枚举"""
    print("\n=== 测试 FaultTolerance 枚举 ===")
    assert FailureType.AGENT_TIMEOUT.value == "agent_timeout"
    assert FailureType.OPA_DENIAL.value == "opa_denial"
    assert FailureType.GRAPHITI_UNAVAILABLE.value == "graphiti_unavailable"
    assert AgentState.IDLE.value == "idle"
    assert AgentState.RUNNING.value == "running"
    assert AgentState.DEGRADED.value == "degraded"
    print("FaultTolerance 枚举测试通过")
    return True


def test_fault_recovery_manager():
    """测试故障恢复管理器"""
    print("\n=== 测试 FaultRecoveryManager ===")
    fm = FaultRecoveryManager()
    assert fm.max_retries == 3
    assert fm.circuit_breaker_threshold == 5
    assert fm.circuit_breaker_reset_time == 300
    assert FailureType.AGENT_TIMEOUT in fm.recovery_strategies
    print("FaultRecoveryManager 测试通过")
    return True


def test_fault_classification():
    """测试故障分类"""
    print("\n=== 测试故障分类 ===")
    fm = FaultRecoveryManager()

    timeout_error = TimeoutError("operation timed out")
    assert fm._classify_failure(timeout_error) == FailureType.AGENT_TIMEOUT

    opa_error = PermissionError("OPA permission denied")
    assert fm._classify_failure(opa_error) == FailureType.OPA_DENIAL

    graphiti_error = ConnectionError("graphiti connection failed")
    assert fm._classify_failure(graphiti_error) == FailureType.GRAPHITI_UNAVAILABLE

    network_error = ConnectionError("network connection refused")
    assert fm._classify_failure(network_error) == FailureType.NETWORK_ERROR

    tool_error = AttributeError("tool execution failed")
    assert fm._classify_failure(tool_error) == FailureType.TOOL_EXECUTION_ERROR

    unknown_error = ValueError("unknown error")
    assert fm._classify_failure(unknown_error) == FailureType.UNEXPECTED_EXCEPTION
    print("故障分类测试通过")
    return True


def test_circuit_breaker():
    """测试断路器"""
    print("\n=== 测试断路器 ===")
    fm = FaultRecoveryManager()
    assert fm._is_circuit_breaker_open("test_agent") == False
    fm._trip_circuit_breaker("test_agent")
    assert fm._is_circuit_breaker_open("test_agent") == True
    print("断路器测试通过")
    return True


def test_agent_state_tracking():
    """测试 Agent 状态跟踪"""
    print("\n=== 测试 Agent 状态跟踪 ===")
    fm = FaultRecoveryManager()
    fm.agent_states["test_agent"] = AgentState.RUNNING
    assert fm.get_agent_state("test_agent") == AgentState.RUNNING
    assert fm.get_agent_state("unknown_agent") == AgentState.IDLE
    print("Agent 状态跟踪测试通过")
    return True


def test_failure_summary():
    """测试故障汇总"""
    print("\n=== 测试故障汇总 ===")
    fm = FaultRecoveryManager()
    fm.failure_count["agent1"] = 5
    fm.circuit_breaker_state["agent2"] = {"state": "open"}

    summary = fm.get_failure_summary()
    assert summary["total_failures"] == 0
    assert summary["agent_states"] == {}
    assert summary["failure_count"]["agent1"] == 5
    assert "agent2" in summary["open_circuit_breakers"]
    print("故障汇总测试通过")
    return True


def test_state_persistence_manager():
    """测试状态持久化管理器"""
    print("\n=== 测试 StatePersistenceManager ===")
    spm = StatePersistenceManager.get_instance("/tmp/test_swarm_state")
    assert spm.persistence_path == "/tmp/test_swarm_state"

    stats = spm.get_persistence_stats()
    assert "total_files" in stats
    assert "total_size_bytes" in stats
    print("StatePersistenceManager 测试通过")
    return True


def test_state_save_load():
    """测试状态保存和加载"""
    print("\n=== 测试状态保存和加载 ===")
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    try:
        spm = StatePersistenceManager(temp_dir)

        test_state = {"key": "value", "count": 42}
        save_result = asyncio.run(spm.save_state("test_agent", test_state))
        assert save_result == True

        loaded_state = asyncio.run(spm.load_state("test_agent"))
        assert loaded_state == test_state
        print("状态保存和加载测试通过")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return True


def test_checkpoint_operations():
    """测试检查点操作"""
    print("\n=== 测试检查点操作 ===")
    import tempfile
    import shutil

    temp_dir = tempfile.mkdtemp()
    try:
        spm = StatePersistenceManager(temp_dir)

        checkpoint_data = {"phase": "observe", "data": "test"}
        save_result = asyncio.run(spm.save_checkpoint("mission-123", checkpoint_data))
        assert save_result == True

        loaded = asyncio.run(spm.load_checkpoint("mission-123"))
        assert loaded == checkpoint_data

        checkpoints = spm.list_checkpoints()
        assert len(checkpoints) > 0
        print("检查点操作测试通过")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return True


def test_health_metric():
    """测试健康指标"""
    print("\n=== 测试 HealthMetric ===")
    metric = HealthMetric(
        name="test_metric",
        value=0.5,
        unit="percent",
        threshold_warning=0.7,
        threshold_critical=0.9,
    )
    assert metric.name == "test_metric"
    assert metric.value == 0.5
    assert metric.threshold_warning == 0.7
    print("HealthMetric 测试通过")
    return True


def test_health_monitor():
    """测试健康监控器"""
    print("\n=== 测试 HealthMonitor ===")
    hm = HealthMonitor.get_instance()
    assert hm.check_interval == 60
    assert len(hm.alerts) == 0
    print("HealthMonitor 测试通过")
    return True


def test_swarm_agents():
    """测试 Swarm Agent 实例化"""
    print("\n=== 测试 Swarm Agent 实例化 ===")
    from core.graph_manager import BattlefieldGraphManager
    from core.opa_manager import OPAManager

    gm = BattlefieldGraphManager()
    opa = OPAManager()

    intel_config = AgentConfig(
        name="Intelligence",
        agent_type=AgentType.INTELLIGENCE,
        model="test-model",
        role="intelligence_analyst",
        tools=["*"],
        permission_level="intelligence",
    )
    intel_agent = IntelligenceAgentSwarm(intel_config, gm, opa)
    assert intel_agent.state.value == "idle"

    commander_config = AgentConfig(
        name="Commander",
        agent_type=AgentType.COMMANDER,
        model="test-model",
        role="commander",
        tools=["*"],
        permission_level="commander",
    )
    commander_agent = CommanderAgent(commander_config, opa, gm)
    assert commander_agent.state.value == "idle"

    operations_config = AgentConfig(
        name="Operations",
        agent_type=AgentType.OPERATIONS,
        model="test-model",
        role="operations_officer",
        tools=["*"],
        permission_level="operations",
    )
    operations_agent = OperationsAgent(operations_config, opa, gm)
    assert operations_agent.state.value == "idle"
    print("Swarm Agent 实例化测试通过")
    return True


def test_swarm_initialization():
    """测试 BattlefieldSwarm 初始化"""
    print("\n=== 测试 BattlefieldSwarm 初始化 ===")

    async def run_test():
        swarm = BattlefieldSwarm()
        await swarm.initialize()
        assert len(swarm.agents) == 3
        assert AgentType.INTELLIGENCE in swarm.agents
        assert AgentType.COMMANDER in swarm.agents
        assert AgentType.OPERATIONS in swarm.agents
        await swarm.shutdown()
        return True

    result = asyncio.run(run_test())
    assert result == True
    print("BattlefieldSwarm 初始化测试通过")
    return True


def test_swarm_ooda_loop():
    """测试 OODA 循环"""
    print("\n=== 测试 OODA 循环 ===")

    async def run_test():
        swarm = BattlefieldSwarm()
        await swarm.initialize()

        result = await swarm.execute_mission("测试任务")
        assert isinstance(result, MissionResult)
        assert result.success == True
        assert len(result.phases_completed) == 4
        assert OODAPhase.OBSERVE in result.phases_completed
        assert OODAPhase.ORIENT in result.phases_completed
        assert OODAPhase.DECIDE in result.phases_completed
        assert OODAPhase.ACT in result.phases_completed
        assert result.mission_id is not None
        assert result.execution_time_ms > 0

        await swarm.shutdown()
        return True

    result = asyncio.run(run_test())
    assert result == True
    print("OODA 循环测试通过")
    return True


def test_swarm_mission_history():
    """测试任务历史记录"""
    print("\n=== 测试任务历史记录 ===")

    async def run_test():
        swarm = BattlefieldSwarm()
        await swarm.initialize()

        await swarm.execute_mission("任务1")
        await swarm.execute_mission("任务2")

        history = swarm.get_mission_history()
        assert len(history) >= 2
        print(f"任务历史记录: {len(history)} 条")
        await swarm.shutdown()
        return True

    result = asyncio.run(run_test())
    assert result == True
    print("任务历史记录测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行 Swarm 组件测试...")
    print("=" * 60)

    tests = [
        test_swarm_enums,
        test_agent_config,
        test_mission_result,
        test_fault_tolerance_enums,
        test_fault_recovery_manager,
        test_fault_classification,
        test_circuit_breaker,
        test_agent_state_tracking,
        test_failure_summary,
        test_state_persistence_manager,
        test_state_save_load,
        test_checkpoint_operations,
        test_health_metric,
        test_health_monitor,
        test_swarm_agents,
        test_swarm_initialization,
        test_swarm_ooda_loop,
        test_swarm_mission_history,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ❌ {test.__name__} 返回 False")
        except Exception as e:
            failed += 1
            print(f"  ❌ {test.__name__}: {e}")

    print("\n" + "=" * 60)
    print(f"测试结果: 成功 {passed}, 失败 {failed}")
    print("=" * 60)

    if failed == 0:
        print("🎉 所有测试通过！")
    else:
        print("❌ 有测试失败，请检查代码")

    return failed == 0


if __name__ == "__main__":
    run_all_tests()