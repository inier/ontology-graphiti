import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from odap.infra.security.jwt_auth import get_current_user
from typing import List, Optional, Dict, Any

from .schemas import Agent, AgentCreate, AgentUpdate
from ..services.agent_service import get_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent-management", tags=["agent-management"])

agent_service = get_agent_service()


@router.get("", response_model=List[Agent])
async def list_agents(
    role_id: Optional[str] = Query(None, description="按角色ID过滤"),
    workspace_id: Optional[str] = Query(None, description="按工作空间ID过滤"),
    user=Depends(get_current_user),
):
    try:
        return agent_service.list_agents(role_id=role_id, workspace_id=workspace_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ref-options")
async def get_ref_options(type: str = Query(..., description="引用类型"),
    user=Depends(get_current_user)):
    options = []
    if type == "entity":
        try:
            from odap.biz.core.ontology.application.oms.services import get_oms_service
            oms = get_oms_service()
            for obj in oms.list_object_types():
                options.append({"value": obj.get("type_id", ""), "label": obj.get("display_name") or obj.get("name", "")})
        except HTTPException:
            raise
        except Exception:
            pass
    elif type == "business_logic":
        try:
            from odap.biz.management.business.services import get_business_service
            biz = get_business_service()
            for item in biz.list_logics():
                options.append({"value": item.get("logic_id", ""), "label": item.get("display_name") or item.get("name", "")})
        except HTTPException:
            raise
        except Exception:
            pass
    elif type == "indicator":
        try:
            from odap.biz.management.business.services import get_business_service
            biz = get_business_service()
            for item in biz.list_indicators():
                options.append({"value": item.get("indicator_id", ""), "label": item.get("display_name") or item.get("name", "")})
        except HTTPException:
            raise
        except Exception:
            pass
    elif type == "skill":
        try:
            from odap.biz.platform.skill_system.services.skill_service import SkillService
            svc = SkillService()
            result = svc.list_skills()
            for s in result.get("skills", []):
                options.append({"value": s.get("skill_id", ""), "label": s.get("name", "")})
        except HTTPException:
            raise
        except Exception:
            pass
    elif type == "knowledge_base":
        try:
            from odap.biz.data.knowledge_base.services import get_kb_service
            kb = get_kb_service()
            for item in kb.list_knowledge_bases():
                options.append({"value": item.get("kb_id", ""), "label": item.get("name", "")})
        except HTTPException:
            raise
        except Exception:
            pass
    elif type == "role":
        try:
            from odap.biz.platform.roles.services import get_role_service
            role_svc = get_role_service()
            result = role_svc.list_roles()
            for r in result.get("roles", []):
                options.append({"value": r.get("id", ""), "label": r.get("name", "")})
        except HTTPException:
            raise
        except Exception:
            pass
    return {"options": options}


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str,
    user=Depends(get_current_user)):
    try:
        result = agent_service.get_agent(agent_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Agent)
async def create_agent(agent: AgentCreate,
    user=Depends(get_current_user)):
    try:
        data = agent.model_dump()
        result = agent_service.create_agent(data)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, agent: AgentUpdate,
    user=Depends(get_current_user)):
    try:
        data = agent.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="无更新数据")
        result = agent_service.update_agent(agent_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str,
    user=Depends(get_current_user)):
    try:
        result = agent_service.delete_agent(agent_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
