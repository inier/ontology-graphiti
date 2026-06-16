"""
三国演义领域技能包

注册三国专属 skills 到平台 skill 体系：
- sanguo_timeline: 时间线推演（按年份查询事件）
- sanguo_faction_analysis: 势力分析
- sanguo_character_query: 人物查询
- sanguo_event_query: 事件查询

这些 skill 通过平台 API 查询本体数据，不直接访问数据库。
"""

import json
import logging
from typing import Dict, Any, List, Optional

from odap.tools import register_skill

logger = logging.getLogger(__name__)


def _get_model_storage():
    """获取本体模型存储"""
    try:
        from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import SQLiteModelStorage
        return SQLiteModelStorage()
    except Exception as e:
        logger.warning(f"Sanguo skill: model storage init failed: {e}")
        return None


def _find_type_id(storage, type_name: str) -> Optional[str]:
    """查找实体类型 ID"""
    try:
        types = storage.list_entity_types()
        for t in types:
            if t.get("name") == type_name:
                return t.get("type_id")
    except Exception:
        pass
    return None


def sanguo_timeline(start_year: int = 184, end_year: int = 280,
                    workspace_id: str = "default") -> Dict[str, Any]:
    """三国时间线推演：按年份范围查询事件

    Args:
        start_year: 起始年份（默认184年黄巾起义）
        end_year: 结束年份（默认280年西晋灭吴）
        workspace_id: 工作空间ID

    Returns:
        按年份分组的事件列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    event_type_id = _find_type_id(storage, "SanguoEvent")
    if not event_type_id:
        return {"status": "error", "message": "未找到SanguoEvent实体类型，请先运行build_sanguo_ontology.py"}

    try:
        instances = storage.list_instances(type_id=event_type_id, workspace_id=workspace_id, page_size=200)
        if not instances:
            # 尝试 default workspace
            instances = storage.list_instances(type_id=event_type_id, workspace_id="default", page_size=200)

        timeline = {}
        for inst in instances:
            props = inst.get("properties", {})
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except Exception:
                    continue

            year = props.get("year")
            if year is None:
                continue
            year = int(year)
            if start_year <= year <= end_year:
                if year not in timeline:
                    timeline[year] = []
                timeline[year].append({
                    "name": props.get("name", ""),
                    "category": props.get("category", ""),
                    "location": props.get("location", ""),
                    "description": props.get("description", ""),
                })

        # 按年份排序
        sorted_timeline = dict(sorted(timeline.items()))
        total_events = sum(len(v) for v in sorted_timeline.values())

        return {
            "status": "success",
            "timeline": sorted_timeline,
            "total_events": total_events,
            "year_range": f"{start_year}-{end_year}",
        }
    except Exception as e:
        logger.error(f"sanguo_timeline error: {e}")
        return {"status": "error", "message": str(e)}


def sanguo_faction_analysis(faction_name: str = None,
                            workspace_id: str = "default") -> Dict[str, Any]:
    """三国势力分析：查询势力及其人物

    Args:
        faction_name: 势力名称过滤（魏/蜀/吴/群雄/晋）
        workspace_id: 工作空间ID

    Returns:
        势力信息及关联人物
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    try:
        # 查势力
        faction_type_id = _find_type_id(storage, "SanguoFaction")
        factions = []
        if faction_type_id:
            faction_insts = storage.list_instances(type_id=faction_type_id, workspace_id=workspace_id, page_size=100)
            if not faction_insts:
                faction_insts = storage.list_instances(type_id=faction_type_id, workspace_id="default", page_size=100)
            for inst in faction_insts:
                props = inst.get("properties", {})
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        continue
                if faction_name and faction_name not in props.get("name", ""):
                    continue
                factions.append(props)

        # 查人物
        char_type_id = _find_type_id(storage, "SanguoCharacter")
        characters = []
        if char_type_id:
            char_insts = storage.list_instances(type_id=char_type_id, workspace_id=workspace_id, page_size=200)
            if not char_insts:
                char_insts = storage.list_instances(type_id=char_type_id, workspace_id="default", page_size=200)
            for inst in char_insts:
                props = inst.get("properties", {})
                if isinstance(props, str):
                    try:
                        props = json.loads(props)
                    except Exception:
                        continue
                characters.append(props)

        # 按势力分组
        faction_members = {}
        for f in factions:
            fid = f.get("faction_id", f.get("name", ""))
            faction_members[fid] = {"faction": f, "members": []}

        for c in characters:
            faction = c.get("faction", "unknown")
            if faction not in faction_members:
                faction_members[faction] = {"faction": {"name": faction}, "members": []}
            faction_members[faction]["members"].append({
                "name": c.get("name", ""),
                "role": c.get("role", ""),
                "title": c.get("title", ""),
            })

        return {
            "status": "success",
            "factions": faction_members,
            "total_factions": len(faction_members),
            "total_characters": len(characters),
        }
    except Exception as e:
        logger.error(f"sanguo_faction_analysis error: {e}")
        return {"status": "error", "message": str(e)}


def sanguo_character_query(name: str = None, faction: str = None, role: str = None,
                           workspace_id: str = "default") -> Dict[str, Any]:
    """三国人物查询

    Args:
        name: 人物名称（模糊匹配）
        faction: 势力过滤
        role: 角色过滤（君主/武将/谋士/诸侯）
        workspace_id: 工作空间ID

    Returns:
        匹配的人物列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    char_type_id = _find_type_id(storage, "SanguoCharacter")
    if not char_type_id:
        return {"status": "error", "message": "未找到SanguoCharacter实体类型"}

    try:
        instances = storage.list_instances(type_id=char_type_id, workspace_id=workspace_id, page_size=200)
        if not instances:
            instances = storage.list_instances(type_id=char_type_id, workspace_id="default", page_size=200)

        results = []
        for inst in instances:
            props = inst.get("properties", {})
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except Exception:
                    continue

            # 过滤
            if name and name not in props.get("name", ""):
                continue
            if faction and faction not in props.get("faction", ""):
                continue
            if role and role != props.get("role", ""):
                continue

            results.append(props)

        return {
            "status": "success",
            "characters": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"sanguo_character_query error: {e}")
        return {"status": "error", "message": str(e)}


def sanguo_event_query(name: str = None, year: int = None, category: str = None,
                       workspace_id: str = "default") -> Dict[str, Any]:
    """三国事件查询

    Args:
        name: 事件名称（模糊匹配）
        year: 年份过滤
        category: 类别过滤（战役/政治/计谋/联盟）
        workspace_id: 工作空间ID

    Returns:
        匹配的事件列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    event_type_id = _find_type_id(storage, "SanguoEvent")
    if not event_type_id:
        return {"status": "error", "message": "未找到SanguoEvent实体类型"}

    try:
        instances = storage.list_instances(type_id=event_type_id, workspace_id=workspace_id, page_size=200)
        if not instances:
            instances = storage.list_instances(type_id=event_type_id, workspace_id="default", page_size=200)

        results = []
        for inst in instances:
            props = inst.get("properties", {})
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except Exception:
                    continue

            if name and name not in props.get("name", ""):
                continue
            if year is not None and int(props.get("year", 0)) != year:
                continue
            if category and category != props.get("category", ""):
                continue

            results.append(props)

        return {
            "status": "success",
            "events": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"sanguo_event_query error: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================
# 注册到平台 skill 体系
# ============================================================

register_skill(
    name="sanguo_timeline",
    description="三国时间线推演：按年份范围查询事件，支持动态推演历史进程",
    handler=sanguo_timeline,
    category="ontology",
)

register_skill(
    name="sanguo_faction_analysis",
    description="三国势力分析：查询各势力信息及其关联人物",
    handler=sanguo_faction_analysis,
    category="analysis",
)

register_skill(
    name="sanguo_character_query",
    description="三国人物查询：按名称、势力、角色过滤查询人物",
    handler=sanguo_character_query,
    category="ontology",
)

register_skill(
    name="sanguo_event_query",
    description="三国事件查询：按名称、年份、类别过滤查询事件",
    handler=sanguo_event_query,
    category="ontology",
)

logger.info("三国演义技能包注册完成: sanguo_timeline, sanguo_faction_analysis, sanguo_character_query, sanguo_event_query")
