from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ActionRequestStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ActionRequest(BaseModel):
    action_type_id: str
    target_object_id: str
    target_object_type: str
    parameters: Dict[str, Any] = {}
    requested_by: str = "system"
    reason: str = ""
    agent_id: Optional[str] = None


class ActionRecord(BaseModel):
    action_record_id: str
    action_type_id: str
    target_object_id: str
    target_object_type: str
    parameters: Dict[str, Any] = {}
    status: ActionRequestStatus = ActionRequestStatus.PENDING
    requested_by: str = "system"
    reason: str = ""
    agent_id: Optional[str] = None
    opa_decision: Optional[Dict[str, Any]] = None
    validation_result: Optional[Dict[str, Any]] = None
    execution_result: Optional[Dict[str, Any]] = None
    writeback_result: Optional[Dict[str, Any]] = None
    created_at: str = ""
    updated_at: str = ""


class ActionApproval(BaseModel):
    action_record_id: str
    approved: bool
    approver: str = ""
    comment: str = ""


class ActionExecutionResult(BaseModel):
    success: bool
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    writeback_status: Optional[str] = None
