"""语义类型定义 — SemanticType 枚举。

供 L1 Design 层的 Property 和 EntityType 使用，实现跨本体语义对齐。
"""

from enum import Enum


class SemanticType(str, Enum):
    """属性语义类型。

    用于标注 Property 在业务域中的角色，使系统能理解属性的语义含义。
    - IDENTIFIER: 主键/唯一标识（如 id, uuid, code）
    - MEASURE: 度量值/数值指标（如 price, age, score）
    - DIMENSION: 维度/分类字段（如 category, status, type）
    - TEMPORAL: 时间属性（如 created_at, valid_time）
    - GEOSPATIAL: 地理属性（如 latitude, location）
    - TEXT: 自由文本（如 description, content）
    - REFERENCE: 外键引用（如 parent_id, owner_id）
    - ORDINAL: 序数/排序字段（如 priority, rank）
    """

    IDENTIFIER = "identifier"
    MEASURE = "measure"
    DIMENSION = "dimension"
    TEMPORAL = "temporal"
    GEOSPATIAL = "geospatial"
    TEXT = "text"
    REFERENCE = "reference"
    ORDINAL = "ordinal"


class DomainCategory(str, Enum):
    """领域分类（预定义）。"""

    MILITARY = "military"
    ECONOMY = "economy"
    POPULATION = "population"
    LOGISTICS = "logistics"
    INTELLIGENCE = "intelligence"
    MEDICAL = "medical"
    GOVERNANCE = "governance"
    TECHNOLOGY = "technology"
    CUSTOM = "custom"


__all__ = ["SemanticType", "DomainCategory"]
