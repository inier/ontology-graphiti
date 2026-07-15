"""
西游记领域技能包

注册西游专属 skills 到平台 skill 体系：
- xiyou_timeline: 劫难时间线推演（按难数查询事件）
- xiyou_character_query: 人物查询（按种族/势力/角色过滤）
- xiyou_treasure_query: 法宝查询
- xiyou_spell_query: 法术查询

这些 skill 通过平台 API 查询本体数据，不直接访问数据库。
"""

import json
import logging
from typing import Dict, Any, List, Optional

from odap.tools import register_skill

logger = logging.getLogger(__name__)


def _get_model_storage():
    try:
        from odap.biz.core.ontology.design.model.storage.sqlite_model_storage import SQLiteModelStorage
        return SQLiteModelStorage()
    except Exception as e:
        logger.warning(f"Xiyou skill: model storage init failed: {e}")
        return None


def _find_type_id(storage, type_name: str) -> Optional[str]:
    try:
        types = storage.list_entity_types()
        for t in types:
            if t.get("name") == type_name:
                return t.get("type_id")
    except Exception:
        pass
    return None


def xiyou_timeline(trial_start: int = 1, trial_end: int = 81,
                   workspace_id: str = "default") -> Dict[str, Any]:
    """西游劫难时间线推演：按难数范围查询事件

    Args:
        trial_start: 起始难数（默认1）
        trial_end: 结束难数（默认81）
        workspace_id: 工作空间ID

    Returns:
        按难数分组的事件列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    event_type_id = _find_type_id(storage, "XiyouEvent")
    if not event_type_id:
        return {"status": "error", "message": "未找到XiyouEvent实体类型，请先运行build_xiyou_ontology.py"}

    try:
        instances = storage.list_instances(type_id=event_type_id, workspace_id=workspace_id, page_size=200)
        if not instances:
            instances = storage.list_instances(type_id=event_type_id, workspace_id="default", page_size=200)

        timeline = {}
        for inst in instances:
            props = inst.get("properties", {})
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except Exception:
                    continue

            trial = props.get("trial_number")
            if trial is None:
                continue
            trial = int(trial)
            if trial_start <= trial <= trial_end:
                if trial not in timeline:
                    timeline[trial] = []
                timeline[trial].append({
                    "name": props.get("name", ""),
                    "chapter": props.get("chapter", ""),
                    "category": props.get("category", ""),
                    "location": props.get("location", ""),
                    "description": props.get("description", ""),
                })

        sorted_timeline = dict(sorted(timeline.items()))
        total_events = sum(len(v) for v in sorted_timeline.values())

        return {
            "status": "success",
            "timeline": sorted_timeline,
            "total_events": total_events,
            "trial_range": f"第{trial_start}难-第{trial_end}难",
        }
    except Exception as e:
        logger.error(f"xiyou_timeline error: {e}")
        return {"status": "error", "message": str(e)}


def xiyou_character_query(name: str = None, race: str = None,
                           faction: str = None, role: str = None,
                           workspace_id: str = "default") -> Dict[str, Any]:
    """西游人物查询

    Args:
        name: 人物名称（模糊匹配）
        race: 种族过滤（神仙/妖魔/凡人/菩萨/佛/石猴/猪妖/水怪/龙族/妖族）
        faction: 势力过滤（天庭/佛门/妖界/人间）
        role: 角色过滤（取经人/大徒弟/二徒弟/三徒弟/坐骑）
        workspace_id: 工作空间ID

    Returns:
        匹配的人物列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    char_type_id = _find_type_id(storage, "XiyouCharacter")
    if not char_type_id:
        return {"status": "error", "message": "未找到XiyouCharacter实体类型"}

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

            if name and name not in props.get("name", ""):
                continue
            if race and race not in props.get("race", ""):
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
        logger.error(f"xiyou_character_query error: {e}")
        return {"status": "error", "message": str(e)}


def xiyou_treasure_query(name: str = None, holder: str = None,
                          treasure_type: str = None,
                          workspace_id: str = "default") -> Dict[str, Any]:
    """西游法宝查询

    Args:
        name: 法宝名称（模糊匹配）
        holder: 持有者名称
        treasure_type: 法宝类型（兵器/法宝/法器）
        workspace_id: 工作空间ID

    Returns:
        匹配的法宝列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    treas_type_id = _find_type_id(storage, "XiyouTreasure")
    if not treas_type_id:
        return {"status": "error", "message": "未找到XiyouTreasure实体类型"}

    try:
        instances = storage.list_instances(type_id=treas_type_id, workspace_id=workspace_id, page_size=200)
        if not instances:
            instances = storage.list_instances(type_id=treas_type_id, workspace_id="default", page_size=200)

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
            if holder and holder not in props.get("holder", ""):
                continue
            if treasure_type and treasure_type != props.get("treasure_type", ""):
                continue

            results.append(props)

        return {
            "status": "success",
            "treasures": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"xiyou_treasure_query error: {e}")
        return {"status": "error", "message": str(e)}


def xiyou_spell_query(name: str = None, master: str = None,
                       spell_type: str = None,
                       workspace_id: str = "default") -> Dict[str, Any]:
    """西游法术查询

    Args:
        name: 法术名称（模糊匹配）
        master: 掌握者名称
        spell_type: 法术类型（变化/遁术/神通/法术/咒语）
        workspace_id: 工作空间ID

    Returns:
        匹配的法术列表
    """
    storage = _get_model_storage()
    if not storage:
        return {"status": "error", "message": "模型存储不可用"}

    spell_type_id = _find_type_id(storage, "XiyouSpell")
    if not spell_type_id:
        return {"status": "error", "message": "未找到XiyouSpell实体类型"}

    try:
        instances = storage.list_instances(type_id=spell_type_id, workspace_id=workspace_id, page_size=200)
        if not instances:
            instances = storage.list_instances(type_id=spell_type_id, workspace_id="default", page_size=200)

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
            if master and master not in props.get("master", ""):
                continue
            if spell_type and spell_type != props.get("spell_type", ""):
                continue

            results.append(props)

        return {
            "status": "success",
            "spells": results,
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"xiyou_spell_query error: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================
# 注册到平台 skill 体系
# ============================================================

register_skill(
    name="xiyou_timeline",
    description="西游劫难时间线推演：按难数范围查询八十一难事件，支持动态推演取经进程",
    handler=xiyou_timeline,
    category="ontology",
)

register_skill(
    name="xiyou_character_query",
    description="西游人物查询：按名称、种族、势力、角色过滤查询人物",
    handler=xiyou_character_query,
    category="ontology",
)

register_skill(
    name="xiyou_treasure_query",
    description="西游法宝查询：按名称、持有者、类型过滤查询法宝",
    handler=xiyou_treasure_query,
    category="ontology",
)

register_skill(
    name="xiyou_spell_query",
    description="西游法术查询：按名称、掌握者、类型过滤查询法术",
    handler=xiyou_spell_query,
    category="ontology",
)

logger.info("西游记技能包注册完成: xiyou_timeline, xiyou_character_query, xiyou_treasure_query, xiyou_spell_query")
