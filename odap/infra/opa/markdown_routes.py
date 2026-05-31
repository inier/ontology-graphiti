from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from odap.infra.opa.opa_service import MarkdownPolicyService, ABACService

router = APIRouter(prefix="/api/policy/markdown", tags=["policy-markdown"])

markdown_service = MarkdownPolicyService()
abac_service = ABACService()


class MarkdownPolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    markdown_content: str = Field(..., min_length=1)
    category: str = "custom"


class MarkdownPolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    markdown_content: Optional[str] = None
    category: Optional[str] = None


class ABACCheckRequest(BaseModel):
    subject: Dict[str, Any]
    action: Dict[str, Any]
    resource: Dict[str, Any]
    environment: Optional[Dict[str, Any]] = None


@router.post("")
async def create_markdown_policy(data: MarkdownPolicyCreate):
    try:
        compile_result = markdown_service.compile_markdown_policy(data.markdown_content)
        if compile_result.get("status") == "error":
            return {
                "policy_id": f"policy-{uuid.uuid4().hex[:8]}",
                "name": data.name,
                "description": data.description,
                "category": data.category,
                "markdown_content": data.markdown_content,
                "compile_status": "failed",
                "compile_errors": compile_result.get("errors", []),
                "created_at": datetime.now().isoformat(),
            }

        policy_id = f"policy-{uuid.uuid4().hex[:8]}"
        version_result = markdown_service.version_storage.save_version(
            policy_id=policy_id,
            rego_text=compile_result["rego_text"],
            markdown_text=data.markdown_content,
            version=1,
        )

        return {
            "policy_id": policy_id,
            "name": data.name,
            "description": data.description,
            "category": data.category,
            "markdown_content": data.markdown_content,
            "rego_text": compile_result["rego_text"],
            "compile_status": "success",
            "version": 1,
            "created_at": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{policy_id}")
async def get_markdown_policy(policy_id: str):
    try:
        latest = markdown_service.version_storage.get_latest_version(policy_id)
        if not latest:
            raise HTTPException(status_code=404, detail="策略不存在")
        return latest
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{policy_id}")
async def update_markdown_policy(policy_id: str, data: MarkdownPolicyUpdate):
    try:
        latest = markdown_service.version_storage.get_latest_version(policy_id)
        if not latest:
            raise HTTPException(status_code=404, detail="策略不存在")

        new_markdown = data.markdown_content if data.markdown_content is not None else latest["markdown_text"]
        result = markdown_service.hot_update_markdown_policy(policy_id, new_markdown)

        if result.get("status") == "error":
            return {
                "policy_id": policy_id,
                "compile_status": "failed",
                "errors": result.get("errors", []),
                "message": result.get("message", ""),
            }

        return {
            "policy_id": policy_id,
            "compile_status": "success",
            "version": result.get("version"),
            "rego_text": result.get("rego_text"),
            "updated_at": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{policy_id}/compile")
async def compile_markdown_policy(policy_id: str):
    try:
        latest = markdown_service.version_storage.get_latest_version(policy_id)
        if not latest:
            raise HTTPException(status_code=404, detail="策略不存在")

        result = markdown_service.compile_markdown_policy(latest["markdown_text"])
        return {
            "policy_id": policy_id,
            "compile_status": result.get("status"),
            "rego_text": result.get("rego_text", ""),
            "errors": result.get("errors", []),
            "rules": result.get("rules", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{policy_id}/status")
async def get_policy_compile_status(policy_id: str):
    try:
        latest = markdown_service.version_storage.get_latest_version(policy_id)
        if not latest:
            raise HTTPException(status_code=404, detail="策略不存在")

        from odap.infra.opa.markdown_compiler import MarkdownCompiler
        compiler = MarkdownCompiler()
        validation = compiler.validate(latest["rego_text"])

        return {
            "policy_id": policy_id,
            "version": latest["version"],
            "compile_status": "success" if validation["valid"] else "failed",
            "validation": validation,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{policy_id}/versions")
async def get_policy_versions(policy_id: str):
    try:
        versions = markdown_service.version_storage.list_versions(policy_id)
        return {
            "policy_id": policy_id,
            "versions": versions,
            "total": len(versions),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/abac/check")
async def check_abac_permission(data: ABACCheckRequest):
    try:
        result = abac_service.check_permission_abac(
            subject=data.subject,
            action=data.action,
            resource=data.resource,
            env=data.environment,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
