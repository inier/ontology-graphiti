from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from ..storage.sqlite_storage import BusinessStorage

router = APIRouter(prefix="/api/business", tags=["business"])
storage = BusinessStorage()


class FlowNodeSchema(BaseModel):
    node_id: str = ""
    name: str = ""
    order: int = 0
    type: str = "task"
    description: str = ""


class RuleConditionSchema(BaseModel):
    condition_id: str = ""
    trigger_event: str = ""
    requirement: str = ""
    order: int = 0


class ProcessCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = []
    llm_description: str = ""
    flow_nodes: List[FlowNodeSchema] = []
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""


class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    related_objects: Optional[List[str]] = None
    llm_description: Optional[str] = None
    flow_nodes: Optional[List[FlowNodeSchema]] = None
    status: Optional[str] = None
    yaml_definition: Optional[str] = None
    ontology_id: Optional[str] = None
    version_id: Optional[str] = None


class RuleCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = []
    llm_description: str = ""
    rule_conditions: List[RuleConditionSchema] = []
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    related_objects: Optional[List[str]] = None
    llm_description: Optional[str] = None
    rule_conditions: Optional[List[RuleConditionSchema]] = None
    status: Optional[str] = None
    yaml_definition: Optional[str] = None
    ontology_id: Optional[str] = None
    version_id: Optional[str] = None


class LogicCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = []
    llm_description: str = ""
    logic_type: str = "filter"
    logic_expression: str = ""
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""


class LogicUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    related_objects: Optional[List[str]] = None
    llm_description: Optional[str] = None
    logic_type: Optional[str] = None
    logic_expression: Optional[str] = None
    status: Optional[str] = None
    yaml_definition: Optional[str] = None
    ontology_id: Optional[str] = None
    version_id: Optional[str] = None


class IndicatorCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = []
    llm_description: str = ""
    indicator_type: str = "metric"
    calculation_formula: str = ""
    unit: str = ""
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""


class IndicatorUpdate(BaseModel):
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    related_objects: Optional[List[str]] = None
    llm_description: Optional[str] = None
    indicator_type: Optional[str] = None
    calculation_formula: Optional[str] = None
    unit: Optional[str] = None
    status: Optional[str] = None
    yaml_definition: Optional[str] = None
    ontology_id: Optional[str] = None
    version_id: Optional[str] = None


# ===== Business Processes =====
@router.get("/business-processes")
async def list_processes(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
):
    return storage.list_processes(ontology_id=ontology_id, version_id=version_id)


@router.get("/business-processes/{process_id}")
async def get_process(process_id: str):
    result = storage.get_process(process_id)
    if not result:
        raise HTTPException(status_code=404, detail="Process not found")
    return result


@router.post("/business-processes")
async def create_process(data: ProcessCreate):
    return storage.create_process(data.model_dump())


@router.put("/business-processes/{process_id}")
async def update_process(process_id: str, data: ProcessUpdate):
    result = storage.update_process(process_id, data.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Process not found")
    return result


@router.delete("/business-processes/{process_id}")
async def delete_process(process_id: str):
    if not storage.delete_process(process_id):
        raise HTTPException(status_code=404, detail="Process not found")
    return {"status": "deleted"}


# ===== Business Rules =====
@router.get("/business-rules")
async def list_rules(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
):
    return storage.list_rules(ontology_id=ontology_id, version_id=version_id)


@router.get("/business-rules/{rule_id}")
async def get_rule(rule_id: str):
    result = storage.get_rule(rule_id)
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.post("/business-rules")
async def create_rule(data: RuleCreate):
    return storage.create_rule(data.model_dump())


@router.put("/business-rules/{rule_id}")
async def update_rule(rule_id: str, data: RuleUpdate):
    result = storage.update_rule(rule_id, data.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete("/business-rules/{rule_id}")
async def delete_rule(rule_id: str):
    if not storage.delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}


# ===== Business Logics =====
@router.get("/business-logics")
async def list_logics(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
):
    return storage.list_logics(ontology_id=ontology_id, version_id=version_id)


@router.get("/business-logics/{logic_id}")
async def get_logic(logic_id: str):
    result = storage.get_logic(logic_id)
    if not result:
        raise HTTPException(status_code=404, detail="Logic not found")
    return result


@router.post("/business-logics")
async def create_logic(data: LogicCreate):
    return storage.create_logic(data.model_dump())


@router.put("/business-logics/{logic_id}")
async def update_logic(logic_id: str, data: LogicUpdate):
    result = storage.update_logic(logic_id, data.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Logic not found")
    return result


@router.delete("/business-logics/{logic_id}")
async def delete_logic(logic_id: str):
    if not storage.delete_logic(logic_id):
        raise HTTPException(status_code=404, detail="Logic not found")
    return {"status": "deleted"}


# ===== Business Indicators =====
@router.get("/business-indicators")
async def list_indicators(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
):
    return storage.list_indicators(ontology_id=ontology_id, version_id=version_id)


@router.get("/business-indicators/{indicator_id}")
async def get_indicator(indicator_id: str):
    result = storage.get_indicator(indicator_id)
    if not result:
        raise HTTPException(status_code=404, detail="Indicator not found")
    return result


@router.post("/business-indicators")
async def create_indicator(data: IndicatorCreate):
    return storage.create_indicator(data.model_dump())


@router.put("/business-indicators/{indicator_id}")
async def update_indicator(indicator_id: str, data: IndicatorUpdate):
    result = storage.update_indicator(indicator_id, data.model_dump(exclude_none=True))
    if not result:
        raise HTTPException(status_code=404, detail="Indicator not found")
    return result


@router.delete("/business-indicators/{indicator_id}")
async def delete_indicator(indicator_id: str):
    if not storage.delete_indicator(indicator_id):
        raise HTTPException(status_code=404, detail="Indicator not found")
    return {"status": "deleted"}
