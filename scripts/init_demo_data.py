#!/usr/bin/env python3
"""
初始化演示数据

为 Graphiti 系统创建示例工作空间和实体数据，用于测试和演示。
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from odap.biz.platform.workspace.services.workspace_service import WorkspaceService
from odap.infra.graph import GraphManager


def init_workspaces():
    """初始化示例工作空间"""
    print("=== 初始化示例工作空间 ===")
    
    workspace_service = WorkspaceService()
    
    # 检查是否已有工作空间
    result = workspace_service.list_workspaces()
    existing = result.get("workspaces", [])
    
    if existing:
        print(f"已存在 {len(existing)} 个工作空间，跳过初始化")
        return
    
    # 创建示例工作空间
    workspaces = [
        {
            "name": "东部战区情报分析",
            "description": "东部战区相关的军事情报分析和实体管理",
            "owner": "admin"
        },
        {
            "name": "武器装备库",
            "description": "各类武器装备系统的信息库",
            "owner": "admin"
        },
        {
            "name": "人员组织管理",
            "description": "军事人员和组织架构管理",
            "owner": "admin"
        },
        {
            "name": "地理信息系统",
            "description": "军事地理信息和基础设施管理",
            "owner": "admin"
        }
    ]
    
    for ws_data in workspaces:
        try:
            result = workspace_service.create_workspace(
                name=ws_data["name"],
                description=ws_data["description"],
                owner=ws_data["owner"]
            )
            print(f"✓ 创建工作空间: {ws_data['name']} (ID: {result.get('workspace_id')})")
        except Exception as e:
            print(f"✗ 创建工作空间失败 {ws_data['name']}: {e}")
    
    print()


def init_graph_entities():
    """初始化示例图谱实体"""
    print("=== 初始化示例图谱实体 ===")
    
    graph_manager = GraphManager()
    
    # 检查是否已有实体
    existing = graph_manager.get_all_entities()
    if existing:
        print(f"已存在 {len(existing)} 个实体，跳过初始化")
        return
    
    # 示例实体数据
    entities = [
        # 武器装备
        {"id": "weapon_001", "type": "WeaponSystem", "properties": {"name": "歼-20战斗机", "category": "战斗机", "generation": "第五代", "status": "服役"}},
        {"id": "weapon_002", "type": "WeaponSystem", "properties": {"name": "055型驱逐舰", "category": "驱逐舰", "displacement": "12000吨", "status": "服役"}},
        {"id": "weapon_003", "type": "WeaponSystem", "properties": {"name": "东风-41洲际导弹", "category": "弹道导弹", "range": "12000公里", "status": "服役"}},
        
        # 军事单位
        {"id": "unit_001", "type": "MilitaryUnit", "properties": {"name": "东部战区空军", "level": "战区", "type": "空军", "area": "东部战区"}},
        {"id": "unit_002", "type": "MilitaryUnit", "properties": {"name": "海军南海舰队", "level": "舰队", "type": "海军", "area": "南部战区"}},
        {"id": "unit_003", "type": "MilitaryUnit", "properties": {"name": "火箭军某旅", "level": "旅级", "type": "火箭军", "area": "中部战区"}},
        
        # 人员
        {"id": "person_001", "type": "Person", "properties": {"name": "张三", "rank": "上校", "position": "指挥官", "unit": "unit_001"}},
        {"id": "person_002", "type": "Person", "properties": {"name": "李四", "rank": "中校", "position": "参谋长", "unit": "unit_002"}},
        
        # 地点
        {"id": "loc_001", "type": "Location", "properties": {"name": "北京", "type": "首都", "coordinates": "116.4,39.9"}},
        {"id": "loc_002", "type": "Location", "properties": {"name": "上海", "type": "直辖市", "coordinates": "121.5,31.2"}},
        {"id": "loc_003", "type": "Location", "properties": {"name": "广州", "type": "省会城市", "coordinates": "113.3,23.1"}},
        
        # 基础设施
        {"id": "infra_001", "type": "Infrastructure", "properties": {"name": "某军事基地", "type": "空军基地", "area": "东部战区"}},
        {"id": "infra_002", "type": "Infrastructure", "properties": {"name": "某港口", "type": "军港", "area": "南部战区"}},
    ]
    
    for entity in entities:
        try:
            graph_manager.add_entity(
                entity_id=entity["id"],
                entity_type=entity["type"],
                properties=entity["properties"]
            )
            print(f"✓ 添加实体: {entity['properties']['name']} ({entity['id']})")
        except Exception as e:
            print(f"✗ 添加实体失败 {entity['id']}: {e}")
    
    # 添加关系
    relations = [
        ("unit_001", "weapon_001", "装备", {"quantity": "24架"}),
        ("unit_002", "weapon_002", "装备", {"quantity": "8艘"}),
        ("unit_003", "weapon_003", "装备", {"quantity": "12枚"}),
        ("person_001", "unit_001", "隶属", {"role": "指挥官"}),
        ("person_002", "unit_002", "隶属", {"role": "参谋长"}),
        ("unit_001", "loc_001", "驻扎", {"status": "常驻"}),
        ("unit_002", "loc_003", "驻扎", {"status": "常驻"}),
        ("infra_001", "unit_001", "所属", {"type": "主基地"}),
        ("infra_002", "unit_002", "所属", {"type": "母港"}),
    ]
    
    for source, target, rel_type, props in relations:
        try:
            graph_manager.add_relationship(source, target, rel_type, props)
            print(f"✓ 添加关系: {source} -> {target} ({rel_type})")
        except Exception as e:
            print(f"✗ 添加关系失败 {source} -> {target}: {e}")
    
    print()


def main():
    """主函数"""
    print("=" * 60)
    print("Graphiti 演示数据初始化")
    print("=" * 60)
    print()
    
    try:
        init_workspaces()
        init_graph_entities()
        
        print("=" * 60)
        print("初始化完成！")
        print("=" * 60)
        print()
        print("您现在可以：")
        print("1. 访问 /api/workspace 查看工作空间")
        print("2. 访问 /api/agent/chat 与 Agent 对话")
        print("3. 使用 '查询所有实体' 测试图谱查询")
        print("4. 使用 '列出所有工作空间' 测试工作空间查询")
        
    except Exception as e:
        print(f"初始化失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
