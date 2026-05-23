from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional

from ..models import QueryRequest, QueryResult
from ..query_service import QueryService

router = APIRouter(prefix="/api/data-warehouse", tags=["data-warehouse"])

_service: Optional[QueryService] = None


def _get_service() -> QueryService:
    global _service
    if _service is None:
        import os
        data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ontology', 'mock_data')
        _service = QueryService(data_dir=data_dir)
    return _service


@router.post("/query", response_model=QueryResult)
async def execute_query(request: QueryRequest):
    service = _get_service()
    result = service.execute(request)
    if result.error:
        raise HTTPException(status_code=400, detail=result.error)
    return result


@router.get("/tables")
async def list_tables():
    service = _get_service()
    return {"tables": service.list_tables()}


@router.get("/tables/{table_name}/schema")
async def get_table_schema(table_name: str):
    service = _get_service()
    schema = service.get_table_schema(table_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return {"table": table_name, "schema": schema}


@router.get("/tables/{table_name}/data")
async def get_table_data(table_name: str, limit: int = 100, offset: int = 0):
    service = _get_service()
    records = service.warehouse.get_table(table_name)
    if records is None:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    return {
        "table": table_name,
        "total": len(records),
        "data": records[offset:offset + limit],
    }


@router.post("/snapshots")
async def create_snapshot(name: str, description: str = ""):
    service = _get_service()
    snapshot = service.create_snapshot(name, description)
    return {"snapshot_id": snapshot.snapshot_id, "name": snapshot.name}


@router.get("/snapshots")
async def list_snapshots():
    service = _get_service()
    return {"snapshots": service.list_snapshots()}


@router.post("/snapshots/{snapshot_id}/restore")
async def restore_snapshot(snapshot_id: str):
    service = _get_service()
    success = service.restore_snapshot(snapshot_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
    return {"message": "Snapshot restored"}


@router.get("/history")
async def get_query_history(limit: int = 50):
    service = _get_service()
    return {"history": service.get_query_history(limit)}
