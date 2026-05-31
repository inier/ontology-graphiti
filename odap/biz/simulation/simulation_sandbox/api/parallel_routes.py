from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from ..impl.parallel_runner import get_parallel_runner

router = APIRouter(prefix="/api/simulation", tags=["simulation-parallel"])

parallel_runner = get_parallel_runner()


@router.post("/parallel")
async def run_parallel(body: Dict[str, Any] = None):
    try:
        scenarios = (body or {}).get("scenarios", [])
        result = await parallel_runner.run_parallel(scenarios)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/what-if")
async def run_what_if(body: Dict[str, Any] = None):
    try:
        data = body or {}
        base_scenario = data.get("base_scenario", {})
        param_variations = data.get("param_variations", [])
        result = await parallel_runner.run_what_if(base_scenario, param_variations)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison")
async def get_comparison(ids: str = ""):
    try:
        run_ids = [i.strip() for i in ids.split(",") if i.strip()]
        if not run_ids:
            raise HTTPException(status_code=400, detail="ids parameter required")
        result = parallel_runner.compare_by_ids(run_ids)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", ""))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
