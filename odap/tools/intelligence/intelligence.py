"""
情报技能模块
实现领域情报收集和分析功能

Category: intelligence

迁移状态：
- SensorSearchSkill: 已迁移到 BaseSkill（新方式）
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
# SensorSearchSkill（新方式：BaseSkill）
# ============================================================

class SensorSearchInput(SkillInput):
    """传感器搜索输入"""
    area: Optional[str] = Field(default=None, description="搜索区域（如 'B'、'A'）")


class SensorSearchSkill(BaseSkill):
    """
    搜索指定区域的传感器系统

    使用图谱管理器查询 ToolSystem 实体，过滤出类型为「传感器」的装备。
    """

    metadata = SkillMetadata(
        name="search_sensor",
        description="搜索指定区域的传感器",
        category="intelligence",
        danger_level="low",
        requires_opa_check=False,
        input_schema=SensorSearchInput,
        version="2.0.0",
    )
    input_schema = SensorSearchInput

    def execute(self, input_data: SensorSearchInput) -> SkillOutput:
        area = input_data.area
        weapons = manager.query_entities(entity_type="ToolSystem", area=area)
        sensors = [w for w in weapons if w["properties"].get("type") == "传感器"]

        return SkillOutput(
            success=True,
            data={
                "sensors": sensors,
                "count": len(sensors),
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

        # 尝试从图谱统计数据中生成动态推荐
        recommendations = []
        recommendations_source = "dynamic"

        try:
            entity_types = stats.get("entity_types", {})
            total_entities = stats.get("total_entities", 0)

            if total_entities == 0:
                recommendations.append("当前图谱无数据，建议先摄入数据构建知识图谱")
            else:
                # 基于实体类型分布生成推荐
                for entity_type, count in entity_types.items():
                    if entity_type == "ToolSystem" and count > 0:
                        recommendations.append(f"检测到 {count} 个工具系统实体，建议关注其部署态势")
                    elif entity_type == "Sensor" and count > 0:
                        recommendations.append(f"检测到 {count} 个传感器实体，建议加强传感器活动监控")
                    elif entity_type == "Threat" and count > 0:
                        recommendations.append(f"检测到 {count} 个威胁实体，建议立即评估威胁等级")

                if not recommendations:
                    recommendations.append("图谱数据正常，暂无特别建议")

        except Exception:
            # 降级：使用默认推荐
            recommendations_source = "default"
            recommendations = [
                "加强对B区的侦察",
                "注意对手传感器活动",
                "准备应对可能的交锋",
            ]

        analysis = {
            "total_entities": stats.get("total_entities", 0),
            "entity_types": stats.get("entity_types", {}),
            "domain_status": "活跃",
            "recommendations": recommendations,
            "recommendations_source": recommendations_source,
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

_sensor_skill = SensorSearchSkill()
_domain_skill = AnalyzeDomainSkill()


# ============================================================
# 旧式裸函数（向后兼容，委托给 BaseSkill 实现）
# ============================================================

def search_sensor(area=None):
    """
    搜索指定区域的传感器（旧式接口）

    Args:
        area: 区域名称

    Returns:
        传感器列表
    """
    result = _sensor_skill.run({"area": area})
    if result.success:
        return result.data.get("sensors", [])
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
    name="search_sensor",
    description="搜索指定区域的传感器",
    handler=search_sensor,
    category="intelligence",
)

register_skill(
    name="analyze_domain",
    description="分析领域态势",
    handler=analyze_domain,
    category="intelligence",
)

# 用真正的 BaseSkill 实例覆盖 LegacySkillAdapter
get_registry().register(_sensor_skill)
get_registry().register(_domain_skill)
