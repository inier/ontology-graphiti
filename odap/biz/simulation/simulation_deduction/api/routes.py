from fastapi import APIRouter, HTTPException
from typing import List

from .schemas import (
    CreateScenarioRequest, AddChainRequest, UpdateConditionRequest,
    SimulateChainRequest, CompareChainsRequest, ListScenariosRequest,
)
from ..services.deduction_service import DeductionService

router = APIRouter(prefix="/api/simulation/deduction", tags=["simulation-deduction"])
service = DeductionService()


@router.post("/scenarios")
async def create_scenario(request: CreateScenarioRequest):
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
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios")
async def list_scenarios(page: int = 1, page_size: int = 20,
                          status: str = None, name: str = None,
                          target_object_type: str = None):
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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    try:
        result = service.get_scenario(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    try:
        result = service.delete_scenario(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/conditions")
async def load_ontology_conditions(scenario_id: str):
    try:
        result = service.load_ontology_conditions(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}/conditions/{condition_id}")
async def update_condition(scenario_id: str, condition_id: str,
                            request: UpdateConditionRequest):
    try:
        result = service.update_condition(scenario_id, condition_id, request.value)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/chains")
async def add_execution_chain(scenario_id: str, request: AddChainRequest):
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
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/scenarios/{scenario_id}/chains/{chain_id}")
async def delete_chain(scenario_id: str, chain_id: str):
    try:
        result = service.delete_chain(scenario_id, chain_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/scenarios/{scenario_id}/chains/{chain_id}")
async def update_chain(scenario_id: str, chain_id: str, request: AddChainRequest):
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
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/chains/{chain_id}/simulate")
async def simulate_chain(scenario_id: str, chain_id: str):
    try:
        result = service.simulate_chain(scenario_id, chain_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/simulate-all")
async def simulate_all_chains(scenario_id: str):
    try:
        result = service.simulate_all_chains(scenario_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenarios/{scenario_id}/compare")
async def compare_chains(scenario_id: str, request: CompareChainsRequest):
    try:
        result = service.compare_chains(scenario_id, request.chain_ids)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
