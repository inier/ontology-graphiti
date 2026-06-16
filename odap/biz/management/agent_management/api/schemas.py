from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=50)
    avatar: str = ""
    description: str = ""
    main_object: str = ""
    related_objects: List[str] = Field(default_factory=list)
    related_processes: List[str] = Field(default_factory=list)
    related_rules: List[str] = Field(default_factory=list)
    related_business_logic: List[str] = Field(default_factory=list)
    related_indicators: List[str] = Field(default_factory=list)
    related_skills: List[str] = Field(default_factory=list)
    related_knowledge_bases: List[str] = Field(default_factory=list)
    allowed_roles: List[str] = Field(default_factory=list)
    workspace_id: str = ""


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    display_name: Optional[str] = Field(None, min_length=1, max_length=50)
    avatar: Optional[str] = None
    description: Optional[str] = None
    main_object: Optional[str] = None
    related_objects: Optional[List[str]] = None
    related_processes: Optional[List[str]] = None
    related_rules: Optional[List[str]] = None
    related_business_logic: Optional[List[str]] = None
    related_indicators: Optional[List[str]] = None
    related_skills: Optional[List[str]] = None
    related_knowledge_bases: Optional[List[str]] = None
    allowed_roles: Optional[List[str]] = None
    workspace_id: Optional[str] = None


class ResolvedNames(BaseModel):
    """ID→名称的解析映射，写入时同步生成，查询时直接返回"""
    workspace_name: str = ""
    role_names: Dict[str, str] = Field(default_factory=dict)
    object_names: Dict[str, str] = Field(default_factory=dict)
    process_names: Dict[str, str] = Field(default_factory=dict)
    rule_names: Dict[str, str] = Field(default_factory=dict)
    logic_names: Dict[str, str] = Field(default_factory=dict)
    indicator_names: Dict[str, str] = Field(default_factory=dict)
    skill_names: Dict[str, str] = Field(default_factory=dict)
    knowledge_base_names: Dict[str, str] = Field(default_factory=dict)


class Agent(BaseModel):
    agent_id: str
    name: str
    display_name: str
    avatar: str
    description: str
    main_object: str
    related_objects: List[str] = Field(default_factory=list)
    related_processes: List[str] = Field(default_factory=list)
    related_rules: List[str] = Field(default_factory=list)
    related_business_logic: List[str] = Field(default_factory=list)
    related_indicators: List[str] = Field(default_factory=list)
    related_skills: List[str] = Field(default_factory=list)
    related_knowledge_bases: List[str] = Field(default_factory=list)
    allowed_roles: List[str] = Field(default_factory=list)
    workspace_id: str = ""
    created_by: str
    created_at: str
    updated_at: str
    resolved_names: ResolvedNames = Field(default_factory=ResolvedNames)
