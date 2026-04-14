"""
AIP Project Entry Point - 战场情报系统主入口
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import skills
from core.orchestrator import SelfCorrectingOrchestrator
from core.graph_manager import BattlefieldGraphManager
from core.intelligence_agent import IntelligenceAgent
from core.swarm_orchestrator import BattlefieldSwarm


def print_result(title, result):
    """格式化打印结果"""
    print(f"\n{'='*60}")
    print(f"📋 {title}")
    print('='*60)

    if result is None:
        print("❌ 结果: None")
    elif isinstance(result, list):
        if len(result) == 0:
            print("📭 未找到匹配结果")
        else:
            print(f"✅ 找到 {len(result)} 个结果:")
            for i, item in enumerate(result, 1):
                print(f"\n  [{i}] {item.get('id', 'N/A')}")
                print(f"      类型: {item.get('type', 'N/A')}")
                props = item.get('properties', {})
                if props:
                    for k, v in props.items():
                        if k not in ['name', 'type']:
                            print(f"      {k}: {v}")
    elif isinstance(result, dict):
        if result.get('status') == 'success':
            print(f"✅ 状态: 成功")
            if result.get('message'):
                print(f"📝 消息: {result['message']}")
            if result.get('result'):
                print(f"📊 结果: {result['result']}")
        elif result.get('status') == 'denied':
            print(f"🚫 状态: 权限不足")
            print(f"📝 消息: {result.get('message', '无详细信息')}")
        else:
            for k, v in result.items():
                print(f"  • {k}: {v}")
    else:
        print(f"📊 结果: {result}")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          🎯 战场情报系统 (Battlefield Intelligence)          ║
║              基于 Graphiti + OPA + Skill 架构               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("🔧 初始化系统...")
    print(f"   • 已加载技能: {', '.join(skills.SKILL_CATALOG.keys())}")

    manager = BattlefieldGraphManager()
    stats = manager.get_statistics()
    print(f"   • 图谱状态: {stats.get('mode', 'unknown')}")
    print(f"   • 实体数量: {stats.get('total_entities', 0)}")

    if stats.get('entity_types'):
        print("   • 实体分布:")
        for etype, count in stats['entity_types'].items():
            print(f"      - {etype}: {count}")

    print("\n" + "="*60)
    print("🧪 功能测试场景")
    print("="*60)

    # === 场景 1: 情报查询 (飞行员) ===
    print("\n📍 场景 1: 情报查询 (飞行员角色)")
    pilot = SelfCorrectingOrchestrator(user_role="pilot")
    result = pilot.run("帮我看看 B 区有没有雷达")
    print_result("B区雷达查询", result)

    # === 场景 2: 越权攻击 (飞行员) ===
    print("\n📍 场景 2: 权限测试 (飞行员尝试攻击)")
    pilot.run("攻击 WEAPON_Bl_1")

    # === 场景 3: 指挥官攻击 ===
    print("\n📍 场景 3: 指挥官权限攻击")
    commander = SelfCorrectingOrchestrator(user_role="commander")
    result = commander.run("攻击 WEAPON_Bl_1")
    print_result("攻击目标", result)

    # === 场景 4: 策略拦截 (指挥官攻击民用) ===
    print("\n📍 场景 4: 策略拦截 (禁止攻击民用设施)")
    result = commander.run("攻击 CIV_A_1")
    print_result("攻击民用目标", result)

    # === 场景 5: 情报分析 ===
    print("\n📍 场景 5: 情报分析 (情报分析员)")
    analyst = SelfCorrectingOrchestrator(user_role="intelligence_analyst")
    result = analyst.run("分析当前战场态势")
    print_result("战场态势分析", result)

    # === 场景 6: 实体搜索 ===
    print("\n📍 场景 6: 实体搜索")
    entities = manager.search("雷达")
    print_result("搜索'雷达'相关实体", entities)

    # === 场景 7: Intelligence Agent（LLM 驱动的 ReAct 分析） ===
    print("\n📍 场景 7: Intelligence Agent — LLM 情报分析")
    try:
        intel_agent = IntelligenceAgent(user_role="intelligence_analyst")
        report = intel_agent.analyze("分析B区威胁")
        print_result("Intelligence Agent 分析报告", report)

        # 打印元数据
        metadata = report.get("_metadata", {})
        trace = report.get("_trace", {})
        print(f"\n  📊 威胁等级: {report.get('threat_level', 'N/A')}")
        print(f"  ⏱️ 总耗时: {metadata.get('execution_time_ms', 'N/A')}ms")
        print(f"  🔄 推理轮次: {metadata.get('iterations', 'N/A')}")
        print(f"  🔗 Trace ID: {trace.get('trace_id', 'N/A')}")
        print(f"  🧠 RAG: {'已启用' if metadata.get('rag_context_provided') else '未启用'}")
        print(f"  📋 工具调用: {len(metadata.get('tool_calls', []))} 次")
    except Exception as e:
        print(f"❌ Intelligence Agent 执行失败: {e}")
        print("  提示: 请确保 .env 中配置了 OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL")

    # === 场景 8: Swarm OODA 协同（三 Agent 闭环）===
    print("\n📍 场景 8: Swarm OODA 协同 — 三 Agent 闭环")
    print("="*60)
    try:
        import asyncio

        async def run_swarm_demo():
            swarm = BattlefieldSwarm()
            await swarm.initialize()

            result = await swarm.execute_mission("分析B区威胁并采取行动")

            print(f"\n✅ Swarm OODA 执行完成")
            print(f"  Mission ID: {result.mission_id}")
            print(f"  成功: {result.success}")
            print(f"  完成阶段: {[p.value for p in result.phases_completed]}")
            print(f"  耗时: {result.execution_time_ms:.2f}ms")

            if result.final_decision:
                print(f"\n  📊 最终决策:")
                print(f"     态势摘要: {result.final_decision.get('situation_summary', 'N/A')}")
                print(f"     威胁等级: {result.final_decision.get('threat_level', 'N/A')}")
                rec = result.final_decision.get('recommended_action', {})
                if rec:
                    print(f"     推荐行动: {rec.get('description', 'N/A')}")
                    print(f"     行动类型: {rec.get('type', 'N/A')}")
                    print(f"     风险等级: {rec.get('risk_level', 'N/A')}")

            if result.error_message:
                print(f"  ⚠️ 错误: {result.error_message}")

            await swarm.shutdown()

        asyncio.run(run_swarm_demo())
    except Exception as e:
        print(f"❌ Swarm 执行失败: {e}")

    print("\n" + "="*60)
    print("✅ 测试完成!")
    print("="*60)
    print("""
💡 提示:
   • 启动 Web 模拟器: python main.py --web
   • 访问地址: http://localhost:8765/ui/
   • Swagger API: http://localhost:8765/docs
    """)


def run_web_simulator():
    """场景 8: 启动 ODAP Simulator Web 服务

    提供:
    - REST API: 场景管理 / 数据写入 / 版本管理
    - WebSocket: 实时本体更新事件流
    - 前端 UI: 时间线 + 关系图谱 + 态势地图

    用法: python main.py --web [--port 8765]
    """
    import argparse

    parser = argparse.ArgumentParser(description="ODAP Simulator Web 服务")
    parser.add_argument("--web", action="store_true", help="启动 Web 模拟器")
    parser.add_argument("--port", type=int, default=8765, help="服务端口 (默认 8765)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    try:
        from core.simulator_web_service import SimulatorWebService
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║            🏛️ ODAP Simulator Web Service v2.0               ║
╚══════════════════════════════════════════════════════════════╝

📡 前端 UI:  http://{args.host}:{args.port}/ui/
📖 API 文档: http://{args.host}:{args.port}/docs
🔌 WebSocket: ws://{args.host}:{args.port}/ws/events

启动中...
""")

        service = SimulatorWebService(host=args.host, port=args.port)
        service.run()

    except ImportError as e:
        print(f"❌ 依赖缺失: {e}")
        print("请安装: pip install fastapi uvicorn python-multipart")


if __name__ == "__main__":
    import sys

    if "--web" in sys.argv:
        run_web_simulator()
    else:
        main()
