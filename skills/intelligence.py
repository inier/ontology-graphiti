"""
情报技能模块
实现战场情报收集和分析功能
"""

import sys
import os

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import register_skill
from core.graph_manager import BattlefieldGraphManager

# 初始化图谱管理器
manager = BattlefieldGraphManager()

# 搜索雷达
def search_radar(area=None):
    """
    搜索指定区域的雷达
    
    Args:
        area: 区域名称
        
    Returns:
        雷达列表
    """
    # 查询武器系统，过滤出雷达类型
    weapons = manager.query_entities(entity_type="WeaponSystem", area=area)
    radars = [weapon for weapon in weapons if weapon["properties"].get("type") == "雷达"]
    
    return radars

# 分析战场态势
def analyze_battlefield():
    """
    分析战场态势
    
    Returns:
        战场态势分析结果
    """
    # 获取图谱统计信息
    stats = manager.get_graph_statistics()
    
    # 分析结果
    analysis = {
        "total_entities": stats["node_count"],
        "entity_types": stats["type_count"],
        "battlefield_status": "活跃",
        "recommendations": [
            "加强对B区的侦察",
            "注意敌方雷达活动",
            "准备应对可能的攻击"
        ]
    }
    
    return analysis

# 注册技能
register_skill(
    name="search_radar",
    description="搜索指定区域的雷达",
    handler=search_radar
)

register_skill(
    name="analyze_battlefield",
    description="分析战场态势",
    handler=analyze_battlefield
)