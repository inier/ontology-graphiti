from enum import Enum


class StateType(str, Enum):
    INITIAL = "initial"
    NORMAL = "normal"
    FINAL = "final"
    ERROR = "error"


class TransitionGuard(str, Enum):
    ALWAYS = "always"
    ROLE_BASED = "role_based"
    CONDITION_BASED = "condition_based"
    MANUAL_APPROVAL = "manual_approval"
