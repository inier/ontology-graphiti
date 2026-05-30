from enum import Enum


class SharedEventType(str, Enum):
    STATE_UPDATE = "state_update"
    TASK_ASSIGNMENT = "task_assignment"
    TASK_COMPLETION = "task_completion"
    CONFLICT_DETECTED = "conflict_detected"
    CONSENSUS_REQUEST = "consensus_request"
    CONSENSUS_REACHED = "consensus_reached"
