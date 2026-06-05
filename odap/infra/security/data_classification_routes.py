from fastapi import APIRouter, Depends
from odap.infra.security.jwt_auth import get_current_user

from .data_classification import (
    DataClassification,
    CLASSIFICATION_LABELS,
    CLASSIFICATION_HIERARCHY,
    can_access,
)
from pydantic import BaseModel


router = APIRouter(prefix="/api/security", tags=["security"])


class CheckAccessRequest(BaseModel):
    user_clearance: str
    data_classification: str


@router.get("/classification-levels")
async def get_classification_levels(user=Depends(get_current_user)):
    levels = []
    for cls_level in DataClassification:
        levels.append({
            "code": cls_level.value,
            "label": CLASSIFICATION_LABELS[cls_level],
            "hierarchy": CLASSIFICATION_HIERARCHY[cls_level],
        })
    return {"levels": levels}


@router.post("/check-access")
async def check_access(request: CheckAccessRequest,
    user=Depends(get_current_user)):
    try:
        user_cls = DataClassification(request.user_clearance)
        data_cls = DataClassification(request.data_classification)
        allowed = can_access(user_cls, data_cls)
        return {
            "allowed": allowed,
            "user_clearance": user_cls.value,
            "data_classification": data_cls.value,
            "user_level": CLASSIFICATION_HIERARCHY[user_cls],
            "data_level": CLASSIFICATION_HIERARCHY[data_cls],
        }
    except ValueError:
        return {
            "allowed": False,
            "error": "Invalid classification level",
            "user_clearance": request.user_clearance,
            "data_classification": request.data_classification,
        }
