from fastapi import APIRouter, HTTPException, Depends
from odap.infra.security.jwt_auth import get_current_user
from odap.infra.security.audit_helper import audit as _audit_shared
from typing import List

from .schemas import (
    CreateScenarioRequest, AddChainRequest, UpdateConditionRequest,
    SimulateChainRequest, CompareChainsRequest, ListScenariosRequest,
)
from ..services.deduction_service import DeductionService

router = APIRouter(prefix="/api/simulation/deduction", tags=["simulation-deduction"])
service = DeductionService()


def _audit(action: str, user_id: str, result_status: str, result_message: str = "",
           details: dict = None, service: str = "simulation_deduction", workspace_id: str = "default"):
    """审计便捷函数 - 使用共享 helper"""
    _audit_shared(
        action=action,
        user=user_id,
        result_status=result_status,
        result_message=result_message,
        details=details,
        service=service,
        workspace_id=workspace_id,
        resource="simulation_deduction",
    )


@router.post("/scenarios")
async def create_scenario(request: CreateScenarioRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.create_scenario(
            name=request.name,
            description=request.description,
            source_recommendation_id=request.source_recommendation_id,
            source_analysis_id=request.source_analysis_id,
            target_object_id=request.target_object_id,
            target_object_type=request.target_object_type,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        _audit("simulation_deduction_create_scenario", _uid, "success", details={"name": request.name})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_create_scenario_failed", _uid, "failure", str(e), details={"name": request.name})
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios")
async def list_scenarios(page: int = 1, page_size: int = 20,
                          status: str = None, name: str = None,
                          target_object_type: str = None,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        filters = {}
        if status:
            filters["status"] = status
        if name:
            filters["name"] = name
        if target_object_type:
            filters["target_object_type"] = target_object_type
        result = service.list_scenarios(filters=filters, page=page, page_size=page_size)
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_list_scenarios_failed", _uid, "failure", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.get_scenario(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_get_scenario_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.delete_scenario(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        _audit("simulation_deduction_delete_scenario", _uid, "success", details={"scenario_id": scenario_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_delete_scenario_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/conditions")
async def load_ontology_conditions(scenario_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.load_ontology_conditions(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        _audit("simulation_deduction_load_conditions", _uid, "success", details={"scenario_id": scenario_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_load_conditions_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}/conditions/{condition_id}")
async def update_condition(scenario_id: str, condition_id: str,
                            request: UpdateConditionRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.update_condition(scenario_id, condition_id, request.value)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        _audit("simulation_deduction_update_condition", _uid, "success", details={"scenario_id": scenario_id, "condition_id": condition_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_update_condition_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id, "condition_id": condition_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/chains")
async def add_execution_chain(scenario_id: str, request: AddChainRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.add_execution_chain(
            scenario_id=scenario_id,
            name=request.name,
            description=request.description,
            steps=request.steps,
            conditions=request.conditions,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        _audit("simulation_deduction_add_chain", _uid, "success", details={"scenario_id": scenario_id, "name": request.name})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_add_chain_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scenarios/{scenario_id}/chains/{chain_id}")
async def delete_chain(scenario_id: str, chain_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.delete_chain(scenario_id, chain_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        _audit("simulation_deduction_delete_chain", _uid, "success", details={"scenario_id": scenario_id, "chain_id": chain_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_delete_chain_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id, "chain_id": chain_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}/chains/{chain_id}")
async def update_chain(scenario_id: str, chain_id: str, request: AddChainRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.update_chain(
            scenario_id=scenario_id,
            chain_id=chain_id,
            name=request.name,
            description=request.description,
            steps=request.steps,
            conditions=request.conditions,
        )
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        _audit("simulation_deduction_update_chain", _uid, "success", details={"scenario_id": scenario_id, "chain_id": chain_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_update_chain_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id, "chain_id": chain_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/chains/{chain_id}/simulate")
async def simulate_chain(scenario_id: str, chain_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.simulate_chain(scenario_id, chain_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        _audit("simulation_deduction_simulate_chain", _uid, "success", details={"scenario_id": scenario_id, "chain_id": chain_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_simulate_chain_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id, "chain_id": chain_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/simulate-all")
async def simulate_all_chains(scenario_id: str,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.simulate_all_chains(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        _audit("simulation_deduction_simulate_all", _uid, "success", details={"scenario_id": scenario_id})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_simulate_all_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/compare")
async def compare_chains(scenario_id: str, request: CompareChainsRequest,
    user=Depends(get_current_user)):
    _uid = user.get("sub", "anonymous") if isinstance(user, dict) else "anonymous"
    try:
        result = service.compare_chains(scenario_id, request.chain_ids)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        _audit("simulation_deduction_compare_chains", _uid, "success", details={"scenario_id": scenario_id, "chain_ids": request.chain_ids})
        return result
    except HTTPException:
        raise
    except Exception as e:
        _audit("simulation_deduction_compare_chains_failed", _uid, "failure", str(e), details={"scenario_id": scenario_id})
        raise HTTPException(status_code=500, detail=str(e))
