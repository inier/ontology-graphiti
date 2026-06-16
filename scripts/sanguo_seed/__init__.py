"""三国演义种子数据模块 — 导出所有数据和辅助函数"""

from .factions import FACTIONS, get_faction
from .characters import CHARACTERS, get_character, get_character_by_name, search_characters
from .locations import LOCATIONS, get_location
from .events import EVENTS, get_event, get_events_in_range
from .relationships import RELATIONSHIPS, get_relationships_of
from .time_anchors import TIME_ANCHORS, get_time_anchor, get_time_anchor_by_year

__all__ = [
    # 势力
    "FACTIONS",
    "get_faction",
    # 人物
    "CHARACTERS",
    "get_character",
    "get_character_by_name",
    "search_characters",
    # 地点
    "LOCATIONS",
    "get_location",
    # 事件
    "EVENTS",
    "get_event",
    "get_events_in_range",
    # 关系
    "RELATIONSHIPS",
    "get_relationships_of",
    # 时间锚点
    "TIME_ANCHORS",
    "get_time_anchor",
    "get_time_anchor_by_year",
]
