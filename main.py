"""
AIP Project Entry Point - 战场情报系统主入口
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import skills
from core.orchestrator import SelfCorrectingOrchestrator
from core.graph_manager import BattlefieldGraphManager


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

    print("\n" + "="*60)
    print("✅ 测试完成!")
    print("="*60)
    print("""
💡 提示:
   • 启动 Web 界面: python visualization/web_interface.py
   • 访问地址: http://localhost:5000
    """)


if __name__ == "__main__":
    main()
