from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import uuid


class FeedbackType(str, Enum):
    ACTION_RESULT = "action_result"
    DECISION_FEEDBACK = "decision_feedback"
    OUTCOME_DEVIATION = "outcome_deviation"
    LESSON_LEARNED = "lesson_learned"


class FeedbackSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Feedback(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    feedback_type: FeedbackType
    source_id: str
    severity: FeedbackSeverity = FeedbackSeverity.INFO
    title: str = ""
    description: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    deviation_score: float = 0.0
    deviation_factors: List[str] = Field(default_factory=list)
    root_causes: List[str] = Field(default_factory=list)
    lesson_learned: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class FeedbackQuery(BaseModel):
    source_id: Optional[str] = None
    feedback_type: Optional[FeedbackType] = None
    severity: Optional[FeedbackSeverity] = None
    limit: int = 50
