from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import time
import uuid

router = APIRouter(prefix="/api/policies", tags=["policies"])

_policies_store: Dict[str, Dict[str, Any]] = {}


def _init_default_policies():
    if _policies_store:
        return
    defaults = [
        {
            "policy_id": "policy-access-control",
            "name": "访问控制策略",
            "description": "基于角色的访问控制策略，定义不同角色的权限范围",
            "category": "access_control",
            "status": "enabled",
            "version": "1.0.0",
            "markdown_content": "# 访问控制策略\n\n定义系统管理员、项目经理、团队成员和访客的权限。",
            "rego_content": 'package domain\n\ndefault allow = false\n\nallow {\n    input.role == "system_admin"\n}',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "policy_id": "policy-data-privacy",
            "name": "数据隐私策略",
            "description": "数据访问和隐私保护策略",
            "category": "data_privacy",
            "status": "enabled",
            "version": "1.0.0",
            "markdown_content": "# 数据隐私策略\n\n保护敏感数据，限制未授权访问。",
            "rego_content": 'package domain.data_privacy\n\ndefault allow = false\n\nallow {\n    input.clearance_level >= input.resource.clearance_required\n}',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
        {
            "policy_id": "policy-compliance",
            "name": "合规审计策略",
            "description": "操作合规性和审计追踪策略",
            "category": "compliance",
            "status": "enabled",
            "version": "1.0.0",
            "markdown_content": "# 合规审计策略\n\n确保所有操作符合合规要求。",
            "rego_content": 'package domain.compliance\n\ndefault allow = false\n\nallow {\n    input.action == "read"\n}',
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        },
    ]
    for p in defaults:
        _policies_store[p["policy_id"]] = p


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    markdown_content: str = Field(..., min_length=1)
    category: str = "custom"


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1, max_length=500)
    markdown_content: Optional[str] = None
    status: Optional[str] = None


@router.get("")
async def list_policies(
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    _init_default_policies()
    policies = list(_policies_store.values())
    if status:
        policies = [p for p in policies if p["status"] == status]
    if category:
        policies = [p for p in policies if p["category"] == category]
    policies = policies[:limit]
    return {"policies": policies, "total": len(policies)}


@router.post("")
async def create_policy(data: PolicyCreate):
    _init_default_policies()
    policy_id = f"policy-{uuid.uuid4().hex[:8]}"
    rego_content = _markdown_to_rego(data.markdown_content)
    policy = {
        "policy_id": policy_id,
        "name": data.name,
        "description": data.description,
        "category": data.category,
        "status": "enabled",
        "version": "1.0.0",
        "markdown_content": data.markdown_content,
        "rego_content": rego_content,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    _policies_store[policy_id] = policy
    return policy


@router.get("/{policy_id}")
async def get_policy(policy_id: str):
    _init_default_policies()
    policy = _policies_store.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    return policy


@router.put("/{policy_id}")
async def update_policy(policy_id: str, data: PolicyUpdate):
    _init_default_policies()
    policy = _policies_store.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    if data.name is not None:
        policy["name"] = data.name
    if data.description is not None:
        policy["description"] = data.description
    if data.markdown_content is not None:
        policy["markdown_content"] = data.markdown_content
        policy["rego_content"] = _markdown_to_rego(data.markdown_content)
    if data.status is not None:
        policy["status"] = data.status
    version_parts = policy["version"].split(".")
    version_parts[-1] = str(int(version_parts[-1]) + 1)
    policy["version"] = ".".join(version_parts)
    policy["updated_at"] = datetime.utcnow().isoformat()
    return {
        "policy_id": policy_id,
        "name": policy["name"],
        "status": policy["status"],
        "version": policy["version"],
    }


@router.post("/{policy_id}/toggle")
async def toggle_policy_status(policy_id: str, enabled: bool = Query(True)):
    _init_default_policies()
    policy = _policies_store.get(policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="策略不存在")
    policy["status"] = "enabled" if enabled else "disabled"
    policy["updated_at"] = datetime.utcnow().isoformat()
    return {"policy_id": policy_id, "status": policy["status"]}


def _markdown_to_rego(markdown: str) -> str:
    lines = markdown.strip().split("\n")
    package_name = "domain.custom"
    for line in lines:
        if line.startswith("# "):
            pkg = line[2:].strip().lower().replace(" ", "_")
            package_name = f"domain.{pkg}"
            break
    return f"package {package_name}\n\ndefault allow = false\n\nallow {{\n    # TODO: 从Markdown策略生成Rego规则\n    true\n}}"
