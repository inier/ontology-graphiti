from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from pydantic import BaseModel, Field
from typing import List, Optional
from ..services import BusinessService

router = APIRouter(prefix="/api", tags=["business"])
service = BusinessService()


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
    related_objects: List[str] = Field(default_factory=list)
    llm_description: str = ""
    flow_nodes: List[FlowNodeSchema] = Field(default_factory=list)
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""
    schema_type_id: Optional[str] = None


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
    schema_type_id: Optional[str] = None


class RuleCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = Field(default_factory=list)
    llm_description: str = ""
    rule_conditions: List[RuleConditionSchema] = Field(default_factory=list)
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""
    schema_type_id: Optional[str] = None


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
    schema_type_id: Optional[str] = None


class LogicCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = Field(default_factory=list)
    llm_description: str = ""
    logic_type: str = "filter"
    logic_expression: str = ""
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""
    schema_type_id: Optional[str] = None


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
    schema_type_id: Optional[str] = None


class IndicatorCreate(BaseModel):
    name: str
    display_name: str = ""
    description: str = ""
    related_objects: List[str] = Field(default_factory=list)
    llm_description: str = ""
    indicator_type: str = "metric"
    calculation_formula: str = ""
    unit: str = ""
    yaml_definition: str = ""
    ontology_id: str = ""
    version_id: str = ""
    schema_type_id: Optional[str] = None


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
    schema_type_id: Optional[str] = None


# ===== Business Processes =====
@router.get("/business-processes")
async def list_processes(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        return service.list_processes(ontology_id=ontology_id, version_id=version_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/business-processes/{process_id}")
async def get_process(process_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.get_process(process_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Process not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-processes")
async def create_process(data: ProcessCreate,
    user=Depends(get_current_user)):
    try:
        return service.create_process(data.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/business-processes/{process_id}")
async def update_process(process_id: str, data: ProcessUpdate,
    user=Depends(get_current_user)):
    try:
        result = service.update_process(process_id, data.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Process not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/business-processes/{process_id}")
async def delete_process(process_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.delete_process(process_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Process not found"))
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Business Rules =====
@router.get("/business-rules")
async def list_rules(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        return service.list_rules(ontology_id=ontology_id, version_id=version_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/business-rules/{rule_id}")
async def get_rule(rule_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.get_rule(rule_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Rule not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-rules")
async def create_rule(data: RuleCreate,
    user=Depends(get_current_user)):
    try:
        return service.create_rule(data.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/business-rules/{rule_id}")
async def update_rule(rule_id: str, data: RuleUpdate,
    user=Depends(get_current_user)):
    try:
        result = service.update_rule(rule_id, data.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Rule not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/business-rules/{rule_id}")
async def delete_rule(rule_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.delete_rule(rule_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Rule not found"))
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Business Logics =====
@router.get("/business-logics")
async def list_logics(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        return service.list_logics(ontology_id=ontology_id, version_id=version_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/business-logics/{logic_id}")
async def get_logic(logic_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.get_logic(logic_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Logic not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-logics")
async def create_logic(data: LogicCreate,
    user=Depends(get_current_user)):
    try:
        return service.create_logic(data.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/business-logics/{logic_id}")
async def update_logic(logic_id: str, data: LogicUpdate,
    user=Depends(get_current_user)):
    try:
        result = service.update_logic(logic_id, data.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Logic not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/business-logics/{logic_id}")
async def delete_logic(logic_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.delete_logic(logic_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Logic not found"))
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Business Indicators =====
@router.get("/business-indicators")
async def list_indicators(
    ontology_id: Optional[str] = Query(None),
    version_id: Optional[str] = Query(None),
    user=Depends(get_current_user)):
    try:
        return service.list_indicators(ontology_id=ontology_id, version_id=version_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/business-indicators/{indicator_id}")
async def get_indicator(indicator_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.get_indicator(indicator_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Indicator not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/business-indicators")
async def create_indicator(data: IndicatorCreate,
    user=Depends(get_current_user)):
    try:
        return service.create_indicator(data.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/business-indicators/{indicator_id}")
async def update_indicator(indicator_id: str, data: IndicatorUpdate,
    user=Depends(get_current_user)):
    try:
        result = service.update_indicator(indicator_id, data.model_dump(exclude_none=True))
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Indicator not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/business-indicators/{indicator_id}")
async def delete_indicator(indicator_id: str,
    user=Depends(get_current_user)):
    try:
        result = service.delete_indicator(indicator_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message", "Indicator not found"))
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== Type Definition Query Endpoints =====
@router.get("/process-type-definitions")
async def list_process_type_definitions(
    ontology_id: str = Query(..., description="本体 ID"),
    user=Depends(get_current_user),
):
    """列出业务过程类型定义（供下拉选择）"""
    try:
        from odap.biz.core.ontology.ontology_api.services import OntologyService
        ontology_service = OntologyService()
        result = ontology_service.list_process_types(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rule-type-definitions")
async def list_rule_type_definitions(
    ontology_id: str = Query(..., description="本体 ID"),
    user=Depends(get_current_user),
):
    """列出规则类型定义（供下拉选择）"""
    try:
        from odap.biz.core.ontology.ontology_api.services import OntologyService
        ontology_service = OntologyService()
        result = ontology_service.list_rule_types(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/function-type-definitions")
async def list_function_type_definitions(
    ontology_id: str = Query(..., description="本体 ID"),
    user=Depends(get_current_user),
):
    """列出逻辑函数类型定义（供下拉选择）"""
    try:
        from odap.biz.core.ontology.ontology_api.services import OntologyService
        ontology_service = OntologyService()
        result = ontology_service.list_function_types(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicator-type-definitions")
async def list_indicator_type_definitions(
    ontology_id: str = Query(..., description="本体 ID"),
    user=Depends(get_current_user),
):
    """列出指标类型定义（供下拉选择）"""
    try:
        from odap.biz.core.ontology.ontology_api.services import OntologyService
        ontology_service = OntologyService()
        result = ontology_service.list_indicator_types(ontology_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=400, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
