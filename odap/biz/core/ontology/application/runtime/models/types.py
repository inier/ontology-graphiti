from enum import Enum


class FunctionType(str, Enum):
    TRANSFORM = "transform"
    AGGREGATE = "aggregate"
    PREDICT = "predict"
    ACTION = "action"
    CODE = "code"
    QUERY = "query"


class FunctionStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


class AggregateWindow(str, Enum):
    RAW = "raw"
    HOUR_1 = "1h"
    HOUR_6 = "6h"
    DAY_1 = "1d"
    DAY_7 = "7d"
    DAY_30 = "30d"


class AggregateMethod(str, Enum):
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    AVG = "avg"
    COUNT = "count"
    FIRST = "first"
    LAST = "last"
    DISTINCT_COUNT = "distinct_count"


class TriggerType(str, Enum):
    STATE_DRIVEN = "state_driven"
    EVENT_DRIVEN = "event_driven"
    SCHEDULE_DRIVEN = "schedule_driven"
    RELATION_PROPAGATED = "relation_propagated"
