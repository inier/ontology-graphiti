"""
情报技能模块
实现领域情报收集和分析功能

Category: intelligence

迁移状态：
- RadarSearchSkill: 已迁移到 BaseSkill（新方式）
- AnalyzeDomainSkill: 已迁移到 BaseSkill（新方式）
- register_skill() 保留向后兼容
"""

import sys
import os

# 确保当前目录在Python路径中
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, List
from pydantic import Field

from odap.tools.base import (
    BaseSkill,
    SkillInput,
    SkillOutput,
    SkillMetadata,
    get_registry,
)
from odap.tools import register_skill
from odap.infra.graph import GraphManager

# 初始化图谱管理器
manager = GraphManager()


# ============================================================
# RadarSearchSkill（新方式：BaseSkill）
# ============================================================

class RadarSearchInput(SkillInput):
    """雷达搜索输入"""
    area: Optional[str] = Field(default=None, description="搜索区域（如 'B'、'A'）")


class RadarSearchSkill(BaseSkill):
    """
    搜索指定区域的雷达系统

    使用图谱管理器查询 WeaponSystem 实体，过滤出类型为「雷达」的装备。
    """

    metadata = SkillMetadata(
        name="search_radar",
        description="搜索指定区域的雷达",
        category="intelligence",
        danger_level="low",
        requires_opa_check=False,
        input_schema=RadarSearchInput,
        version="2.0.0",
    )
    input_schema = RadarSearchInput

    def execute(self, input_data: RadarSearchInput) -> SkillOutput:
        area = input_data.area
        weapons = manager.query_entities(entity_type="WeaponSystem", area=area)
        radars = [w for w in weapons if w["properties"].get("type") == "雷达"]

        return SkillOutput(
            success=True,
            data={
                "radars": radars,
                "count": len(radars),
                "area": area or "全局",
            },
            execution_time_ms=0,
            skill_name=self.metadata.name,
            request_id=input_data.request_id,
        )


# ============================================================
# AnalyzeDomainSkill（新方式：BaseSkill）
# ============================================================

class AnalyzeDomainSkill(BaseSkill):
    """
    分析当前领域态势

    从图谱获取统计信息，生成结构化态势报告和行动建议。
    """

    metadata = SkillMetadata(
        name="analyze_domain",
        description="分析领域态势",
        category="intelligence",
        danger_level="low",
        requires_opa_check=False,
        version="2.0.0",
    )

    def execute(self, input_data: SkillInput) -> SkillOutput:
        stats = manager.get_graph_statistics()

        analysis = {
            "total_entities": stats.get("total_entities", 0),
            "entity_types": stats.get("entity_types", {}),
            "domain_status": "活跃",
            "recommendations": [
                "加强对B区的侦察",
                "注意敌方雷达活动",
                "准备应对可能的攻击",
            ],
        }

        return SkillOutput(
            success=True,
            data=analysis,
            execution_time_ms=0,
            skill_name=self.metadata.name,
            request_id=input_data.request_id,
        )


# ============================================================
# 创建 BaseSkill 实例
# ============================================================

_radar_skill = RadarSearchSkill()
_domain_skill = AnalyzeDomainSkill()


# ============================================================
# 旧式裸函数（向后兼容，委托给 BaseSkill 实现）
# ============================================================

def search_radar(area=None):
    """
    搜索指定区域的雷达（旧式接口）

    Args:
        area: 区域名称

    Returns:
        雷达列表
    """
    result = _radar_skill.run({"area": area})
    if result.success:
        return result.data.get("radars", [])
    return []


def analyze_domain():
    """
    分析领域态势（旧式接口）

    Returns:
        领域态势分析结果
    """
    result = _domain_skill.run({})
    if result.success:
        return result.data
    return {}


# ============================================================
# 先注册旧式（SKILL_CATALOG），再注册新式（SkillRegistry）覆盖
# 确保 SkillRegistry 中保留 BaseSkill 实例而非 LegacySkillAdapter
# ============================================================

register_skill(
    name="search_radar",
    description="搜索指定区域的雷达",
    handler=search_radar,
    category="intelligence",
)

register_skill(
    name="analyze_domain",
    description="分析领域态势",
    handler=analyze_domain,
    category="intelligence",
)

# 用真正的 BaseSkill 实例覆盖 LegacySkillAdapter
get_registry().register(_radar_skill)
get_registry().register(_domain_skill)
