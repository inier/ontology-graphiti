"""SHACL/OWL 本体治理 API（ADR-077）。

端点：
- POST /api/ontology/shacl/validate  实例数据 SHACL 合规校验
- GET  /api/ontology/shacl/shapes    生成 SHACL shapes（实时，不持久化）
- GET  /api/ontology/owl/export      导出 OWL/Turtle
- POST /api/ontology/owl/import      导入 OWL → Schema 候选（草稿）

所有端点复用 get_current_user，实体类型定义从 ModelService 读取。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel

from odap.infra.security.jwt_auth import get_current_user

from ..shacl.shape_generator import ShapeGenerator
from ..shacl.validator import SHACLValidator
from ..owl.owl_exporter import OWLExporter
from ..owl.owl_importer import OWLImporter

router = APIRouter(prefix="/api/ontology", tags=["ontology-shacl-owl"])


class SHACLValidateRequest(BaseModel):
    entity_types: List[Dict[str, Any]]
    instances: List[Dict[str, Any]]


class OWLImportRequest(BaseModel):
    owl_turtle: str


def _get_entity_types_from_model(ontology_id: str = "") -> List[Dict[str, Any]]:
    """从 ModelService 读取实体类型定义（供 shape 生成/导出用）"""
    from odap.biz.core.ontology.design.model.services.model_service import ModelService
    service = ModelService()
    result = service.list_entity_types(filters=None, page=1, page_size=1000)
    return result.get("entity_types", []) or []


@router.post("/shacl/validate")
async def shacl_validate(request: SHACLValidateRequest,
    user=Depends(get_current_user)):
    """实例数据 SHACL 合规校验（ADR-077 裁决 3：显式传入实例数据）"""
    try:
        validator = SHACLValidator()
        return validator.validate(request.entity_types, request.instances)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/shacl/shapes")
async def shacl_shapes(ontology_id: str = "",
    user=Depends(get_current_user)):
    """实时生成 SHACL shapes（不持久化，防漂移）"""
    try:
        entity_types = _get_entity_types_from_model(ontology_id)
        shapes_ttl = ShapeGenerator().generate(entity_types)
        return {"entity_types_count": len(entity_types), "shapes_ttl": shapes_ttl}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/owl/export")
async def owl_export(ontology_id: str = "", fmt: str = "turtle",
    user=Depends(get_current_user)):
    """导出 OWL 本体（Turtle/RDFXML）"""
    try:
        entity_types = _get_entity_types_from_model(ontology_id)
        exporter = OWLExporter()
        if fmt == "turtle":
            content = exporter.export_turtle(entity_types)
        elif fmt == "rdfxml":
            content = exporter.export_rdfxml(entity_types)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的格式: {fmt}")
        return {"format": fmt, "entity_types_count": len(entity_types), "content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/owl/import")
async def owl_import(request: OWLImportRequest,
    user=Depends(get_current_user)):
    """导入 OWL → Schema 候选（草稿，经 HITL 确认后写回，裁决 2）"""
    try:
        importer = OWLImporter()
        result = importer.import_schema_candidates(request.owl_turtle)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
