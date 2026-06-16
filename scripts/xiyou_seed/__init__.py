"""
西游记种子数据包

包含西游记领域的基础数据：
- FACTIONS: 四大势力
- CHARACTERS: 主要人物
- LOCATIONS: 重要地点
- EVENTS: 八十一难（精选）
- TREASURES: 法宝
- SPELLS: 法术
- RELATIONSHIPS: 人物关系
"""

from .factions import FACTIONS
from .characters import CHARACTERS
from .locations import LOCATIONS
from .events import EVENTS
from .treasures import TREASURES
from .spells import SPELLS
from .relationships import RELATIONSHIPS

__all__ = [
    "FACTIONS", "CHARACTERS", "LOCATIONS", "EVENTS",
    "TREASURES", "SPELLS", "RELATIONSHIPS",
]
