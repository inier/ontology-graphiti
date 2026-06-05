"""
图谱操作工具集

为 Agent 提供知识图谱的查询、分析、搜索等功能。
"""

from typing import Dict, Any, List, Optional
from odap.infra.graph import GraphManager
from odap.tools import register_skill


import logging

logger = logging.getLogger(__name__)
# 初始化图谱管理器
graph_manager = GraphManager()


def query_entities(entity_type: str = None, area: str = None, limit: int = 100) -> List[Dict]:
    """
    查询图谱中的实体
    
    Args:
        entity_type: 实体类型（如 WeaponSystem, Entity, Organization 等）
        area: 区域过滤
        limit: 返回数量限制
        
    Returns:
        实体列表
    """
    try:
        if entity_type:
            entities = graph_manager.query_entities(entity_type=entity_type, area=area)
        else:
            # 获取所有实体
            entities = graph_manager.get_all_entities()
        
        return entities[:limit] if limit else entities
    except Exception as e:
        logger.warning("silent except caught in {exc} (line 35)", exc_info=True)
        return [{"error": str(e)}]


def query_relations(source_id: str = None, relation_type: str = None, 
                   target_id: str = None, limit: int = 100) -> List[Dict]:
    """
    查询实体间的关系
    
    Args:
        source_id: 源实体ID
        relation_type: 关系类型
        target_id: 目标实体ID
        limit: 返回数量限制
        
    Returns:
        关系列表
    """
    try:
        if source_id:
            relations = graph_manager.get_entity_relations(source_id)
        else:
            relations = graph_manager.get_all_relations()
        
        # 过滤
        if relation_type:
            relations = [r for r in relations if r.get("type") == relation_type]
        if target_id:
            relations = [r for r in relations if r.get("target") == target_id]
            
        return relations[:limit] if limit else relations
    except Exception as e:
        logger.warning("silent except caught in {exc} (line 66)", exc_info=True)
        return [{"error": str(e)}]


def analyze_graph() -> Dict[str, Any]:
    """
    分析图谱结构和统计信息
    
    Returns:
        图谱分析报告
    """
    try:
        stats = graph_manager.get_graph_statistics()
        
        # 获取实体类型分布
        entity_types = {}
        entities = graph_manager.get_all_entities()
        for entity in entities:
            etype = entity.get("type", "unknown")
            entity_types[etype] = entity_types.get(etype, 0) + 1
        
        # 获取关系类型分布
        relation_types = {}
        relations = graph_manager.get_all_relations()
        for relation in relations:
            rtype = relation.get("type", "unknown")
            relation_types[rtype] = relation_types.get(rtype, 0) + 1
        
        return {
            "total_entities": len(entities),
            "total_relations": len(relations),
            "entity_types": entity_types,
            "relation_types": relation_types,
            "density": len(relations) / max(len(entities), 1),
            "statistics": stats,
        }
    except Exception as e:
        logger.warning("silent except caught in {exc} (line 102)", exc_info=True)
        return {"error": str(e)}


def search_graph(keyword: str, search_type: str = "all") -> List[Dict]:
    """
    搜索图谱中的内容
    
    Args:
        keyword: 搜索关键词
        search_type: 搜索类型 (entity/relation/all)
        
    Returns:
        搜索结果
    """
    try:
        results = []
        
        if search_type in ["entity", "all"]:
            entities = graph_manager.search_entities(keyword)
            results.extend([{"type": "entity", "data": e} for e in entities])
        
        if search_type in ["relation", "all"]:
            relations = graph_manager.search_relations(keyword)
            results.extend([{"type": "relation", "data": r} for r in relations])
        
        return results
    except Exception as e:
        logger.warning("silent except caught in {exc} (line 129)", exc_info=True)
        return [{"error": str(e)}]


def get_entity_details(entity_id: str) -> Dict[str, Any]:
    """
    获取实体详细信息
    
    Args:
        entity_id: 实体ID
        
    Returns:
        实体详情
    """
    try:
        entity = graph_manager.get_entity(entity_id)
        if not entity:
            return {"error": f"实体不存在: {entity_id}"}
        
        # 获取相关关系
        relations = graph_manager.get_entity_relations(entity_id)
        
        return {
            "entity": entity,
            "relations": relations,
            "relation_count": len(relations),
        }
    except Exception as e:
        logger.warning("silent except caught in {exc} (line 156)", exc_info=True)
        return {"error": str(e)}


# ============================================================
# 注册技能到 SKILL_CATALOG
# ============================================================

register_skill(
    name="query_entities",
    description="查询图谱中的实体，支持按类型和区域过滤",
    handler=query_entities,
    category="graph",
)

register_skill(
    name="query_relations",
    description="查询实体间的关系，支持按类型过滤",
    handler=query_relations,
    category="graph",
)

register_skill(
    name="analyze_graph",
    description="分析图谱结构和统计信息",
    handler=analyze_graph,
    category="analysis",
)

register_skill(
    name="search_graph",
    description="搜索图谱中的实体和关系",
    handler=search_graph,
    category="graph",
)

register_skill(
    name="get_entity_details",
    description="获取实体的详细信息和关联关系",
    handler=get_entity_details,
    category="graph",
)
