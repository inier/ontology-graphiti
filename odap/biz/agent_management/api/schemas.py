from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    display_name: str = Field(..., min_length=1, max_length=50)
    avatar: str = ""
    description: str = ""
    main_object: str = ""
    related_objects: List[str] = []
    related_processes: List[str] = []
    related_rules: List[str] = []
    related_business_logic: List[str] = []
    related_indicators: List[str] = []
    related_skills: List[str] = []
    related_knowledge_bases: List[str] = []
    allowed_roles: List[str] = []


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


class Agent(BaseModel):
    agent_id: str
    name: str
    display_name: str
    avatar: str
    description: str
    main_object: str
    related_objects: List[str]
    related_processes: List[str]
    related_rules: List[str]
    related_business_logic: List[str]
    related_indicators: List[str]
    related_skills: List[str]
    related_knowledge_bases: List[str]
    allowed_roles: List[str]
    created_by: str
    created_at: str
    updated_at: str
