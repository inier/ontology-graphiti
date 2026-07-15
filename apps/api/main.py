"""
AIP Project Entry Point - 领域情报系统主入口
"""

import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from odap.biz.core.agent import DomainSwarm
from odap.biz.core.agent.intelligence_agent import IntelligenceAgent
from odap.biz.core.agent.orchestrator import SelfCorrectingOrchestrator
from odap.infra.graph import GraphManager


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
║          🎯 领域情报系统 (Domain Intelligence)          ║
║              基于 Graphiti + OPA + Skill 架构               ║
╚══════════════════════════════════════════════════════════════╝
    """)

    print("🔧 初始化系统...")
    # 手动导入技能模块以确保技能被注册
    from odap.tools import SKILL_CATALOG
    
    # 导入各个技能模块
    try:
        from odap.tools.operations import operations
        from odap.tools.intelligence import intelligence
        from odap.tools.analysis import analysis
        from odap.tools.recommendation import recommendation
        from odap.tools.task_management import task_management
        from odap.tools.policy import policy
        from odap.tools.computation import computation
        from odap.tools.planning import planning
    except ImportError as e:
        print(f"技能模块导入失败: {e}")
    
    print(f"   • 已加载技能: {', '.join(SKILL_CATALOG.keys())}")

    manager = GraphManager()
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
    result = analyst.run("分析当前领域态势")
    print_result("领域态势分析", result)

    # === 场景 6: 实体搜索 ===
    print("\n📍 场景 6: 实体搜索")
    entities = manager.search("雷达")
    print_result("搜索'雷达'相关实体", entities)

    # === 场景 7: Intelligence Agent（LLM 驱动的 ReAct 分析） ===
    print("\n📍 场景 7: Intelligence Agent — LLM 情报分析")
    try:
        import asyncio
        
        async def run_intelligence_agent():
            intel_agent = IntelligenceAgent(user_role="intelligence_analyst")
            try:
                report = await intel_agent.analyze("分析B区威胁")
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
            finally:
                # 关闭资源
                await intel_agent.shutdown()
        
        asyncio.run(run_intelligence_agent())
    except Exception as e:
        print(f"❌ Intelligence Agent 执行失败: {e}")
        print("  提示: 请确保 .env 中配置了 OPENAI_API_KEY / OPENAI_API_BASE / OPENAI_MODEL")

    # === 场景 8: Swarm OODA 协同（三 Agent 闭环）===
    print("\n📍 场景 8: Swarm OODA 协同 — 三 Agent 闭环")
    print("="*60)
    try:
        import asyncio

        async def run_swarm_demo():
            swarm = DomainSwarm()
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
    """场景 8: 启动 ODAP Mock Data Web 服务

    提供:
    - REST API: 场景管理 / 数据写入 / 版本管理
    - WebSocket: 实时本体更新事件流
    - 前端 UI: 时间线 + 关系图谱 + 态势地图

    用法: python main.py --web [--port 8765]
    """
    import argparse

    parser = argparse.ArgumentParser(description="ODAP Mock Data Web 服务")
    parser.add_argument("--web", action="store_true", help="启动 Web 模拟器")
    parser.add_argument("--port", type=int, default=8765, help="服务端口 (默认 8765)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址 (默认 0.0.0.0)")
    args = parser.parse_args()

    try:
        from odap.web.api.app import MockDataWebService
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║            🏛️ ODAP Mock Data Web Service v2.0               ║
╚══════════════════════════════════════════════════════════════╝

📡 前端 UI:  http://{args.host}:{args.port}/ui/
📖 API 文档: http://{args.host}:{args.port}/docs
🔌 WebSocket: ws://{args.host}:{args.port}/ws/events

启动中...
""")

        service = MockDataWebService(host=args.host, port=args.port)
        service.run()

    except ImportError as e:
        print(f"❌ 依赖缺失: {e}")
        print("请安装: pip install fastapi uvicorn python-multipart")


def _run_query_cli(argv):
    """NL 本体查询 CLI"""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="NL 本体查询服务 CLI")
    parser.add_argument("query", nargs="?", help="自然语言查询")
    parser.add_argument("--mode", default="auto", choices=["auto", "keyword", "semantic", "graph"],
                        help="检索模式")
    parser.add_argument("--top-k", type=int, default=10, help="返回结果数")
    parser.add_argument("--workspace", default="", help="工作空间 ID")
    parser.add_argument("--scenario", default="", help="场景 ID")
    parser.add_argument("--explain", action="store_true", help="显示查询解释")
    parser.add_argument("--eval", action="store_true", help="运行评估基准测试")

    # 跳过 argv[0] 和 "query"
    args = parser.parse_args(argv[2:])

    if args.eval:
        from odap.biz.data.qa.evaluation.benchmark import BenchmarkRunner, get_default_benchmark
        print("运行评估基准测试...")
        runner = BenchmarkRunner()
        dataset = get_default_benchmark()
        report = asyncio.run(runner.run(dataset))
        print(f"\n{'='*60}")
        print(f"评估报告: {report.dataset_name}")
        print(f"{'='*60}")
        print(f"总用例数: {report.total_cases}")
        print(f"检索 MRR: {report.retrieval_metrics.mrr:.4f}")
        print(f"检索 NDCG@K: {report.retrieval_metrics.ndcg_at_k:.4f}")
        print(f"检索 Recall@K: {report.retrieval_metrics.recall_at_k:.4f}")
        print(f"QA EM: {report.qa_metrics.exact_match:.4f}")
        print(f"QA F1: {report.qa_metrics.f1:.4f}")
        print(f"延迟 P50: {report.latency_p50_ms:.1f}ms")
        print(f"延迟 P95: {report.latency_p95_ms:.1f}ms")
        return

    if not args.query:
        print("请提供查询内容: python main.py query \"你的查询\"")
        return

    from odap.biz.data.qa.models import QueryRequest
    from odap.biz.data.qa.pipeline.query_pipeline import QueryPipeline

    pipeline = QueryPipeline()
    request = QueryRequest(
        query=args.query,
        mode=args.mode,
        top_k=args.top_k,
        workspace_id=args.workspace or None,
        scenario_id=args.scenario or None,
    )

    if args.explain:
        explanation = pipeline.explain(request)
        print(f"\n{'='*60}")
        print(f"查询解释")
        print(f"{'='*60}")
        print(explanation.get("explanation", ""))
        return

    response = asyncio.run(pipeline.query(request))
    print(f"\n{'='*60}")
    print(f"查询: {args.query}")
    print(f"{'='*60}")
    print(f"回答: {response.answer}")
    if response.sources:
        print(f"\n来源 ({len(response.sources)} 条):")
        for i, s in enumerate(response.sources[:5], 1):
            print(f"  {i}. [{s.pillar}:{s.source}] {s.content[:80]}...")
    print(f"\n意图: {response.understanding.intent.value if response.understanding else 'N/A'}")
    print(f"支柱: {response.pillar_contributions}")
    print(f"耗时: {response.total_time_ms:.1f}ms")


if __name__ == "__main__":
    import sys

    if "--web" in sys.argv:
        run_web_simulator()
    elif "query" in sys.argv:
        _run_query_cli(sys.argv)
    else:
        main()
