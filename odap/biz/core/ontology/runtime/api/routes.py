from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from .schemas import (
    CreateFunctionRequest, UpdateFunctionRequest, ExecuteFunctionRequest,
    CreateContractRequest, UpdateContractRequest,
    ComputeImpactRequest, RecordMutationRequest,
    CreateAggregateRequest, ComputeAggregateRequest,
    CaptureSnapshotRequest, CompareSnapshotsRequest,
    CreateTriggerRequest, EvaluateTriggersRequest, ExecuteTriggerRequest,
)
from ..services import get_runtime_service

router = APIRouter(prefix="/api/ontology/runtime", tags=["ontology-runtime"])


# ── Function ──

@router.post("/functions", response_model=dict)
async def create_function(request: CreateFunctionRequest):
    try:
        service = get_runtime_service()
        result = service.register_function(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/functions", response_model=dict)
async def list_functions(
    function_type: Optional[str] = Query(None),
    target_object_type: Optional[str] = Query(None),
):
    try:
        service = get_runtime_service()
        return service.list_functions(function_type=function_type, target_object_type=target_object_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/functions/{function_id}", response_model=dict)
async def get_function(function_id: str):
    try:
        service = get_runtime_service()
        result = service.get_function(function_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/functions/{function_id}", response_model=dict)
async def update_function(function_id: str, request: UpdateFunctionRequest):
    try:
        service = get_runtime_service()
        result = service.update_function(function_id, request.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/functions/{function_id}/execute", response_model=dict)
async def execute_function(function_id: str, request: ExecuteFunctionRequest):
    try:
        service = get_runtime_service()
        return service.execute_function(function_id, request.context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/functions/{function_id}", response_model=dict)
async def delete_function(function_id: str):
    try:
        service = get_runtime_service()
        result = service.delete_function(function_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ActionContract ──

@router.post("/contracts", response_model=dict)
async def create_contract(request: CreateContractRequest):
    try:
        service = get_runtime_service()
        result = service.create_contract(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts", response_model=dict)
async def list_contracts():
    try:
        service = get_runtime_service()
        return service.list_contracts()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/{contract_id}", response_model=dict)
async def get_contract(contract_id: str):
    try:
        service = get_runtime_service()
        result = service.get_contract(contract_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/contracts/by-action/{action_type_id}", response_model=dict)
async def get_contract_by_action(action_type_id: str):
    try:
        service = get_runtime_service()
        result = service.get_contract_by_action(action_type_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/contracts/{contract_id}/verify", response_model=dict)
async def verify_contract(contract_id: str):
    try:
        service = get_runtime_service()
        return service.verify_contract(contract_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/contracts/{contract_id}", response_model=dict)
async def update_contract(contract_id: str, request: UpdateContractRequest):
    try:
        service = get_runtime_service()
        result = service.update_contract(contract_id, request.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contracts/{contract_id}", response_model=dict)
async def delete_contract(contract_id: str):
    try:
        service = get_runtime_service()
        result = service.delete_contract(contract_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── StatePropagation ──

@router.post("/propagation/build", response_model=dict)
async def build_propagation_graph():
    try:
        service = get_runtime_service()
        return service.build_propagation_graph()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/propagation/impact", response_model=dict)
async def compute_impact(request: ComputeImpactRequest):
    try:
        service = get_runtime_service()
        return service.compute_impact(request.graph_id, request.action_type_id, request.target_object_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/propagation/graphs/{graph_id}", response_model=dict)
async def get_propagation_graph(graph_id: str):
    try:
        service = get_runtime_service()
        result = service.get_propagation_graph(graph_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mutations", response_model=dict)
async def record_mutation(request: RecordMutationRequest):
    try:
        service = get_runtime_service()
        return service.record_mutation(request.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mutations", response_model=dict)
async def query_mutations(
    target_object_id: Optional[str] = Query(None),
    action_type_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    try:
        service = get_runtime_service()
        return service.query_mutations(target_object_id=target_object_id, action_type_id=action_type_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Aggregate ──

@router.post("/aggregates", response_model=dict)
async def create_aggregate(request: CreateAggregateRequest):
    try:
        service = get_runtime_service()
        result = service.register_aggregate(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aggregates", response_model=dict)
async def list_aggregates(target_object_type: Optional[str] = Query(None)):
    try:
        service = get_runtime_service()
        return service.list_aggregates(target_object_type=target_object_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/aggregates/{agg_id}", response_model=dict)
async def get_aggregate(agg_id: str):
    try:
        service = get_runtime_service()
        result = service.get_aggregate(agg_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aggregates/{agg_id}/compute", response_model=dict)
async def compute_aggregate(agg_id: str, request: ComputeAggregateRequest):
    try:
        service = get_runtime_service()
        return service.compute_aggregate(agg_id, request.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/aggregates/{agg_id}", response_model=dict)
async def delete_aggregate(agg_id: str):
    try:
        service = get_runtime_service()
        result = service.delete_aggregate(agg_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── WorldState ──

@router.post("/snapshots", response_model=dict)
async def capture_snapshot(request: CaptureSnapshotRequest):
    try:
        service = get_runtime_service()
        return service.capture_snapshot(request.name, scenario_id=request.scenario_id, is_baseline=request.is_baseline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots", response_model=dict)
async def list_snapshots(scenario_id: Optional[str] = Query(None)):
    try:
        service = get_runtime_service()
        return service.list_snapshots(scenario_id=scenario_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots/{snapshot_id}", response_model=dict)
async def get_snapshot(snapshot_id: str):
    try:
        service = get_runtime_service()
        result = service.get_snapshot(snapshot_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/snapshots/compare", response_model=dict)
async def compare_snapshots(request: CompareSnapshotsRequest):
    try:
        service = get_runtime_service()
        return service.compare_snapshots(request.snapshot_id_a, request.snapshot_id_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/snapshots/{snapshot_id}", response_model=dict)
async def delete_snapshot(snapshot_id: str):
    try:
        service = get_runtime_service()
        result = service.delete_snapshot(snapshot_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── ActionTrigger ──

@router.post("/triggers", response_model=dict)
async def create_trigger(request: CreateTriggerRequest):
    try:
        service = get_runtime_service()
        result = service.register_trigger(request.model_dump())
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/triggers", response_model=dict)
async def list_triggers(
    target_object_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
):
    try:
        service = get_runtime_service()
        return service.list_triggers(target_object_type=target_object_type, is_active=is_active)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/triggers/{trigger_id}", response_model=dict)
async def get_trigger(trigger_id: str):
    try:
        service = get_runtime_service()
        result = service.get_trigger(trigger_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/triggers/{trigger_id}", response_model=dict)
async def delete_trigger(trigger_id: str):
    try:
        service = get_runtime_service()
        result = service.delete_trigger(trigger_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triggers/evaluate", response_model=dict)
async def evaluate_triggers(request: EvaluateTriggersRequest):
    try:
        service = get_runtime_service()
        return service.evaluate_triggers(request.object_type, request.object_id, request.state_changes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triggers/{trigger_id}/execute", response_model=dict)
async def execute_trigger(trigger_id: str, request: ExecuteTriggerRequest):
    try:
        service = get_runtime_service()
        return service.execute_trigger(trigger_id, request.triggered_by)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/triggers/executions", response_model=dict)
async def get_trigger_executions(
    trigger_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    try:
        service = get_runtime_service()
        return service.get_trigger_history(trigger_id=trigger_id, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
