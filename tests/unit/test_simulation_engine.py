"""
SimulationEngine 测试用例
"""

import sys
import os
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.simulation_engine import (
    SimulationEngine,
    SandboxState,
    ScenarioVersion,
    SimulationResult,
)


def test_simulation_engine_singleton():
    """测试单例模式"""
    print("=== 测试 SimulationEngine 单例 ===")
    engine1 = SimulationEngine.get_instance()
    engine2 = SimulationEngine.get_instance()
    assert engine1 is engine2
    print("单例模式测试通过")
    return True


def test_sandbox_state_enum():
    """测试沙箱状态枚举"""
    print("\n=== 测试 SandboxState 枚举 ===")
    assert SandboxState.CREATED.value == "created"
    assert SandboxState.RUNNING.value == "running"
    assert SandboxState.PAUSED.value == "paused"
    assert SandboxState.COMPLETED.value == "completed"
    assert SandboxState.FAILED.value == "failed"
    assert SandboxState.TERMINATED.value == "terminated"
    print("SandboxState 枚举测试通过")
    return True


def test_scenario_version():
    """测试 ScenarioVersion 数据类"""
    print("\n=== 测试 ScenarioVersion ===")
    from datetime import datetime
    version = ScenarioVersion(
        version_id="v1",
        scenario_id="s1",
        parent_version=None,
        parameters={"key": "value"},
        created_at=datetime.now(),
        message="test",
    )
    assert version.version_id == "v1"
    assert version.scenario_id == "s1"
    assert version.parameters == {"key": "value"}
    print("ScenarioVersion 测试通过")
    return True


def test_simulation_result():
    """测试 SimulationResult 数据类"""
    print("\n=== 测试 SimulationResult ===")
    result = SimulationResult(
        result_id="r1",
        scenario_id="s1",
        version_id="v1",
        final_state={"status": "completed"},
        events=[],
        metrics={"score": 85.0},
        success=True,
        execution_time_ms=150.5,
    )
    assert result.result_id == "r1"
    assert result.success == True
    assert result.execution_time_ms == 150.5
    print("SimulationResult 测试通过")
    return True


def test_create_scenario():
    """测试创建推演方案"""
    print("\n=== 测试创建推演方案 ===")

    async def run():
        engine = SimulationEngine.get_instance("/tmp/test_sim_engine")
        params = {
            "threat_level": "medium",
            "friendly_strength": 60,
            "enemy_strength": 40,
        }
        scenario_id = await engine.create_scenario("测试方案", params)
        assert scenario_id is not None
        versions = engine.get_scenario_versions(scenario_id)
        assert len(versions) == 1
        assert versions[0]["parameters"] == params
        return True

    result = asyncio.run(run())
    assert result == True
    print("创建推演方案测试通过")
    return True


def test_create_branch():
    """测试创建分支"""
    print("\n=== 测试创建分支 ===")

    async def run():
        engine = SimulationEngine.get_instance("/tmp/test_sim_engine_branch")
        params = {"threat_level": "medium", "friendly_strength": 50, "enemy_strength": 50}
        scenario_id = await engine.create_scenario("测试分支", params)

        versions = engine.get_scenario_versions(scenario_id)
        original_version_id = versions[0]["version_id"]

        new_params = {"threat_level": "high", "friendly_strength": 70, "enemy_strength": 30}
        branch_version_id = await engine.create_branch(
            scenario_id, original_version_id, new_params, "增加友军力量"
        )

        assert branch_version_id is not None
        assert branch_version_id != original_version_id

        versions = engine.get_scenario_versions(scenario_id)
        assert len(versions) == 2

        return True

    result = asyncio.run(run())
    assert result == True
    print("创建分支测试通过")
    return True


def test_run_simulation():
    """测试运行推演"""
    print("\n=== 测试运行推演 ===")

    async def run():
        engine = SimulationEngine.get_instance("/tmp/test_sim_run")
        params = {"threat_level": "medium", "friendly_strength": 60, "enemy_strength": 40}
        scenario_id = await engine.create_scenario("测试推演", params)

        versions = engine.get_scenario_versions(scenario_id)
        version_id = versions[0]["version_id"]

        result = await engine.run_simulation(scenario_id, version_id, max_steps=5)

        assert isinstance(result, SimulationResult)
        assert result.success == True
        assert result.scenario_id == scenario_id
        assert result.version_id == version_id
        assert len(result.events) == 5
        assert result.final_state is not None
        print(f"  执行时间: {result.execution_time_ms:.2f}ms")
        print(f"  事件数: {len(result.events)}")
        print(f"  指标: {result.metrics}")
        return True

    result = asyncio.run(run())
    assert result == True
    print("运行推演测试通过")
    return True


def test_compare_versions():
    """测试版本对比"""
    print("\n=== 测试版本对比 ===")

    async def run():
        engine = SimulationEngine.get_instance("/tmp/test_sim_compare")
        params = {"threat_level": "medium", "friendly_strength": 50, "enemy_strength": 50}
        scenario_id = await engine.create_scenario("测试对比", params)

        versions = engine.get_scenario_versions(scenario_id)
        original_version_id = versions[0]["version_id"]

        new_params = {"threat_level": "high", "friendly_strength": 70, "enemy_strength": 30}
        branch_version_id = await engine.create_branch(
            scenario_id, original_version_id, new_params, "修改参数"
        )

        diff = engine.compare_versions(scenario_id, original_version_id, branch_version_id)

        assert "differences" in diff
        assert "threat_level" in diff["differences"]
        assert "friendly_strength" in diff["differences"]
        assert diff["differences"]["threat_level"]["version_a"] == "medium"
        assert diff["differences"]["threat_level"]["version_b"] == "high"

        return True

    result = asyncio.run(run())
    assert result == True
    print("版本对比测试通过")
    return True


def test_rollback():
    """测试回退功能"""
    print("\n=== 测试回退功能 ===")

    async def run():
        engine = SimulationEngine.get_instance("/tmp/test_sim_rollback")
        params = {"threat_level": "medium", "friendly_strength": 50, "enemy_strength": 50}
        scenario_id = await engine.create_scenario("测试回退", params)

        versions = engine.get_scenario_versions(scenario_id)
        original_version_id = versions[0]["version_id"]

        new_params = {"threat_level": "critical", "friendly_strength": 90, "enemy_strength": 10}
        await engine.create_branch(scenario_id, original_version_id, new_params, "危险参数")

        rollback_success = await engine.rollback_to_version(scenario_id, original_version_id)
        assert rollback_success == True

        return True

    result = asyncio.run(run())
    assert result == True
    print("回退功能测试通过")
    return True


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("开始运行 SimulationEngine 测试...")
    print("=" * 60)

    tests = [
        test_simulation_engine_singleton,
        test_sandbox_state_enum,
        test_scenario_version,
        test_simulation_result,
        test_create_scenario,
        test_create_branch,
        test_run_simulation,
        test_compare_versions,
        test_rollback,
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