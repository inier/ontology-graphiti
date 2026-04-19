"""区块链模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from enum import Enum


class BlockStatus(str, Enum):
    """区块状态"""
    PENDING = "pending"
    VALIDATED = "validated"
    INVALID = "invalid"
    COMMITTED = "committed"


class ChainStatus(str, Enum):
    """链状态"""
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class Block(BaseModel):
    """区块"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chain_id: str
    previous_hash: str
    current_hash: str
    timestamp: datetime = Field(default_factory=datetime.now)
    log_count: int = 0
    logs: List[str] = Field(default_factory=list)  # 日志ID列表
    status: BlockStatus = BlockStatus.PENDING
    validation_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class BlockChain(BaseModel):
    """区块链"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    status: ChainStatus = ChainStatus.ACTIVE
    block_count: int = 0
    last_block_id: Optional[str] = None
    last_block_hash: Optional[str] = None
    validation_enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
