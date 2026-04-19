"""隔离模型"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum


class IsolationLevel(str, Enum):
    """隔离级别"""
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"
    STRICT = "strict"


class ResourceQuota(BaseModel):
    """资源配额"""
    cpu: Optional[str] = None
    memory: Optional[str] = None
    storage: Optional[str] = None
    max_connections: Optional[int] = None
    max_processes: Optional[int] = None
    rate_limit: Optional[Dict[str, Any]] = Field(default_factory=dict)


class NetworkPolicy(BaseModel):
    """网络策略"""
    allowed_ips: List[str] = Field(default_factory=list)
    blocked_ips: List[str] = Field(default_factory=list)
    allowed_ports: List[int] = Field(default_factory=list)
    blocked_ports: List[int] = Field(default_factory=list)
    egress_rules: List[Dict[str, Any]] = Field(default_factory=list)
    ingress_rules: List[Dict[str, Any]] = Field(default_factory=list)
    enable_firewall: bool = True
