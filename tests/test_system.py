"""
系统测试用例
"""

import sys
import os

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import skills
from core.orchestrator import SelfCorrectingOrchestrator
from core.graph_manager import BattlefieldGraphManager
from core.opa_manager import OPAManager

# 测试技能注册
def test_skill_registration():
    """
    测试技能注册
    """
    print("=== 测试技能注册 ===")
    assert len(skills.SKILL_CATALOG) > 0, "技能注册失败"
    print(f"技能注册成功，共注册了 {len(skills.SKILL_CATALOG)} 个技能")
    print(f"技能列表: {list(skills.SKILL_CATALOG.keys())}")
    return True

# 测试图谱管理器
def test_graph_manager():
    """
    测试图谱管理器
    """
    print("\n=== 测试图谱管理器 ===")
    manager = BattlefieldGraphManager()
    stats = manager.get_graph_statistics()
    assert stats["total_entities"] > 0, "图谱构建失败"
    print(f"图谱构建成功，节点数: {stats['total_entities']}")
    print(f"实体类型统计: {stats['entity_types']}")
    
    # 测试查询功能
    locations = manager.query_entities(entity_type="Location", area="B")
    assert len(locations) > 0, "查询功能失败"
    print(f"B区地理位置查询成功，找到 {len(locations)} 个位置")
    
    return True

# 测试OPA管理器
def test_opa_manager():
    """
    测试OPA管理器
    """
    print("\n=== 测试OPA管理器 ===")
    opa_manager = OPAManager()
    
    # 测试飞行员权限
    pilot_view = opa_manager.check_permission(
        "pilot",
        "view_intelligence",
        {"id": "WEAPON_Bl_1", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    assert pilot_view, "飞行员查看情报权限测试失败"
    print("飞行员查看情报权限测试成功")
    
    # 测试飞行员攻击权限（应该被拒绝）
    pilot_attack = opa_manager.check_permission(
        "pilot",
        "attack",
        {"id": "WEAPON_Bl_1", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    assert not pilot_attack, "飞行员攻击权限测试失败"
    print("飞行员攻击权限测试成功（被正确拒绝）")
    
    # 测试指挥官攻击雷达权限
    commander_attack_radar = opa_manager.check_permission(
        "commander",
        "attack",
        {"id": "WEAPON_Bl_1", "type": "WeaponSystem", "properties": {"type": "雷达"}}
    )
    assert commander_attack_radar, "指挥官攻击雷达权限测试失败"
    print("指挥官攻击雷达权限测试成功")
    
    # 测试指挥官攻击医院权限（应该被拒绝）
    commander_attack_hospital = opa_manager.check_permission(
        "commander",
        "attack",
        {"id": "CIV_A_1", "type": "CivilianInfrastructure", "properties": {"type": "医院"}}
    )
    assert not commander_attack_hospital, "指挥官攻击医院权限测试失败"
    print("指挥官攻击医院权限测试成功（被正确拒绝）")
    
    return True

# 测试编排器
def test_orchestrator():
    """
    测试编排器
    """
    print("\n=== 测试编排器 ===")
    
    # 测试飞行员角色
    pilot = SelfCorrectingOrchestrator(user_role="pilot")
    
    # 测试搜索雷达
    result = pilot.run("帮我看看 B 区有没有雷达")
    assert len(result) > 0, "搜索雷达功能测试失败"
    print("搜索雷达功能测试成功")
    
    # 测试飞行员攻击（应该被拒绝）
    result = pilot.run("攻击 WEAPON_Bl_1")
    assert result["status"] == "denied", "飞行员攻击测试失败"
    print("飞行员攻击测试成功（被正确拒绝）")
    
    # 测试指挥官角色
    commander = SelfCorrectingOrchestrator(user_role="commander")
    
    # 测试指挥官攻击雷达
    result = commander.run("我是指挥官，攻击 WEAPON_Bl_1")
    assert result["status"] == "success", "指挥官攻击雷达测试失败"
    print("指挥官攻击雷达测试成功")
    
    # 测试指挥官攻击医院（应该被拒绝）
    result = commander.run("攻击 CIV_A_1")
    assert result["status"] == "denied", "指挥官攻击医院测试失败"
    print("指挥官攻击医院测试成功（被正确拒绝）")
    
    # 测试分析战场态势
    result = commander.run("分析当前战场态势")
    assert "total_entities" in result, "分析战场态势测试失败"
    print("分析战场态势测试成功")
    
    return True

# 运行所有测试
def run_all_tests():
    """
    运行所有测试
    """
    print("开始运行系统测试...")
    
    tests = [
        test_skill_registration,
        test_graph_manager,
        test_opa_manager,
        test_orchestrator
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"测试 {test.__name__} 失败: {e}")
            failed += 1
    
    print(f"\n测试结果: 成功 {passed}, 失败 {failed}")
    
    if failed == 0:
        print("🎉 所有测试通过！")
    else:
        print("❌ 有测试失败，请检查代码")
    
    return failed == 0

if __name__ == "__main__":
    run_all_tests()