"""
本体管理技能模块
实现本体的查询、导入导出和版本管理功能
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills import register_skill
from ontology.ontology_manager import OntologyManager
from core.graph_manager import BattlefieldGraphManager

ontology_manager = OntologyManager()
graph_manager = BattlefieldGraphManager()

def query_ontology(entity_type=None, area=None, affiliation=None):
    """
    查询本体

    Args:
        entity_type: 实体类型
        area: 区域
        affiliation: 所属方

    Returns:
        查询结果
    """
    results = graph_manager.query_entities(entity_type=entity_type, area=area)

    if affiliation:
        results = [r for r in results if r.get("properties", {}).get("affiliation") == affiliation]

    return {
        "status": "success",
        "total": len(results),
        "results": results
    }

def export_ontology(version=None, description=""):
    """
    导出本体

    Args:
        version: 版本号
        description: 版本描述

    Returns:
        导出结果
    """
    export_file = ontology_manager.export_ontology(version=version, description=description)

    return {
        "status": "success",
        "file": export_file,
        "message": "本体导出成功"
    }

def import_ontology(import_file):
    """
    导入本体

    Args:
        import_file: 导入文件路径

    Returns:
        导入结果
    """
    success = ontology_manager.import_ontology(import_file)

    if success:
        return {
            "status": "success",
            "message": "本体导入成功"
        }
    else:
        return {
            "status": "error",
            "message": f"本体导入失败: {import_file}"
        }

def list_ontology_versions():
    """
    列出本体版本

    Returns:
        版本列表
    """
    versions = ontology_manager.list_versions()

    return {
        "status": "success",
        "versions": versions
    }

def rollback_ontology(version):
    """
    回滚本体版本

    Args:
        version: 版本号

    Returns:
        回滚结果
    """
    success = ontology_manager.rollback_version(version)

    if success:
        return {
            "status": "success",
            "message": f"成功回滚到版本: {version}"
        }
    else:
        return {
            "status": "error",
            "message": f"回滚失败: {version}"
        }

def get_current_ontology():
    """
    获取当前本体

    Returns:
        当前本体
    """
    ontology = ontology_manager.get_current_ontology()

    return {
        "status": "success",
        "ontology": ontology
    }

def update_ontology(entity_types=None, roles=None, battlefield_config=None):
    """
    更新本体

    Args:
        entity_types: 实体类型
        roles: 角色
        battlefield_config: 战场配置

    Returns:
        更新结果
    """
    ontology_manager.update_ontology(
        entity_types=entity_types,
        roles=roles,
        battlefield_config=battlefield_config
    )

    return {
        "status": "success",
        "message": "本体更新成功"
    }

def get_entity_history(entity_id):
    """
    获取实体历史

    Args:
        entity_id: 实体ID

    Returns:
        实体历史
    """
    history = graph_manager.get_entity_history(entity_id)

    return {
        "status": "success",
        "entity_id": entity_id,
        "history": history
    }

def search_ontology_hybrid(query_text, top_k=5):
    """
    混合检索本体

    Args:
        query_text: 查询文本
        top_k: 返回前k个结果

    Returns:
        检索结果
    """
    results = graph_manager.search_hybrid(query_text, top_k=top_k)

    return {
        "status": "success",
        "query": query_text,
        "results": results,
        "total": len(results) if results else 0
    }

register_skill(
    name="query_ontology",
    description="查询本体",
    handler=query_ontology,
    category="ontology")


register_skill(
    name="export_ontology",
    description="导出本体",
    handler=export_ontology,
    category="ontology")


register_skill(
    name="import_ontology",
    description="导入本体",
    handler=import_ontology,
    category="ontology")


register_skill(
    name="list_ontology_versions",
    description="列出本体版本",
    handler=list_ontology_versions,
    category="ontology")


register_skill(
    name="rollback_ontology",
    description="回滚本体版本",
    handler=rollback_ontology,
    category="ontology")


register_skill(
    name="get_current_ontology",
    description="获取当前本体",
    handler=get_current_ontology,
    category="ontology")


register_skill(
    name="update_ontology",
    description="更新本体",
    handler=update_ontology,
    category="ontology")


register_skill(
    name="get_entity_history",
    description="获取实体历史",
    handler=get_entity_history,
    category="ontology")


register_skill(
    name="search_ontology_hybrid",
    description="混合检索本体",
    handler=search_ontology_hybrid,
    category="ontology")
