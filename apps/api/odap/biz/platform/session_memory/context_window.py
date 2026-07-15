import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"


class ChatMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    role: MessageRole
    content: str
    tokens: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    entities: List[str] = Field(default_factory=list)
    cot_nodes: List[str] = Field(default_factory=list)


class ContextWindow(BaseModel):
    max_tokens: int = 8000
    system_prompt_tokens: int = 0
    messages: List[ChatMessage] = Field(default_factory=list)
    summary: str = ""

    @property
    def used_tokens(self) -> int:
        return sum(m.tokens for m in self.messages)

    @property
    def available_tokens(self) -> int:
        return self.max_tokens - self.system_prompt_tokens - self.used_tokens

    @property
    def usage_ratio(self) -> float:
        if self.max_tokens <= 0:
            return 0.0
        return (self.system_prompt_tokens + self.used_tokens) / self.max_tokens

    def add_message(self, message: ChatMessage) -> bool:
        if message.tokens > self.available_tokens:
            logger.warning(f"ContextWindow: message exceeds available tokens ({message.tokens} > {self.available_tokens})")
            return False
        self.messages.append(message)
        return True

    def remove_oldest(self, count: int = 1) -> List[ChatMessage]:
        removed = self.messages[:count]
        self.messages = self.messages[count:]
        return removed

    def get_recent(self, count: int = 4) -> List[ChatMessage]:
        return self.messages[-count:] if self.messages else []

    def clear(self):
        self.messages = []
        self.summary = ""

    def to_dict(self) -> dict:
        return {
            "max_tokens": self.max_tokens,
            "system_prompt_tokens": self.system_prompt_tokens,
            "used_tokens": self.used_tokens,
            "available_tokens": self.available_tokens,
            "usage_ratio": round(self.usage_ratio, 3),
            "message_count": len(self.messages),
            "summary_length": len(self.summary),
        }
