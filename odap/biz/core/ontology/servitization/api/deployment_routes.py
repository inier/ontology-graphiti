from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .deployment_schemas import DeployRequest
from ..services.deployment_executor import DeploymentExecutor

router = APIRouter(prefix="/api/ontology/servitization/deployments", tags=["deployment-executor"])
executor = DeploymentExecutor.get_instance()


@router.post("", response_model=dict)
async def deploy_service(request: DeployRequest):
    try:
        result = executor.deploy(
            deployment_id=request.deployment_id,
            service_id=request.service_id,
            service_name=request.service_name,
            version=request.version,
            endpoint=request.endpoint,
            config=request.config,
            metadata=request.metadata,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{deployment_id}/stop", response_model=dict)
async def stop_deployment(deployment_id: str):
    try:
        result = executor.stop(deployment_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{deployment_id}/rollback", response_model=dict)
async def rollback_deployment(deployment_id: str):
    try:
        result = executor.rollback(deployment_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{deployment_id}/health", response_model=dict)
async def health_check(deployment_id: str):
    try:
        result = executor.health_check(deployment_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/health-check", response_model=dict)
async def batch_health_check():
    try:
        return executor.batch_health_check()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{deployment_id}", response_model=dict)
async def get_deployment(deployment_id: str):
    try:
        result = executor.get_deployment(deployment_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=dict)
async def list_deployments(status: Optional[str] = Query(None)):
    try:
        return executor.list_deployments(status=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
