from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from .schemas import Agent, AgentCreate, AgentUpdate
from ..storage.sqlite_agent_storage import SQLiteAgentStorage

router = APIRouter(prefix="/api/agents", tags=["agents"])

storage = SQLiteAgentStorage()


@router.get("", response_model=List[Agent])
async def list_agents(role_id: Optional[str] = Query(None, description="按角色ID过滤")):
    return storage.list_agents(role_id=role_id)


@router.get("/ref-options")
async def get_ref_options(type: str = Query(..., description="引用类型")):
    options = []
    if type == "entity":
        try:
            from odap.biz.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
            oms = SQLiteOMSStorage()
            for obj in oms.list_object_types():
                options.append({"value": obj.get("type_id", ""), "label": obj.get("display_name") or obj.get("name", "")})
        except Exception:
            pass
    elif type == "business_logic":
        try:
            from odap.biz.business.storage.sqlite_storage import SQLiteBusinessStorage
            biz = SQLiteBusinessStorage()
            for item in biz.list_logics():
                options.append({"value": item.get("logic_id", ""), "label": item.get("display_name") or item.get("name", "")})
        except Exception:
            pass
    elif type == "indicator":
        try:
            from odap.biz.business.storage.sqlite_storage import SQLiteBusinessStorage
            biz = SQLiteBusinessStorage()
            for item in biz.list_indicators():
                options.append({"value": item.get("indicator_id", ""), "label": item.get("display_name") or item.get("name", "")})
        except Exception:
            pass
    elif type == "skill":
        try:
            from odap.biz.skill_system.impl.manager import SkillManager
            mgr = SkillManager()
            for s in mgr.list_skills():
                options.append({"value": s.id, "label": s.name})
        except Exception:
            pass
    elif type == "knowledge_base":
        try:
            from odap.biz.knowledge_base.storage.sqlite_kb_storage import SQLiteKBStorage
            kb = SQLiteKBStorage()
            for item in kb.list_knowledge_bases():
                options.append({"value": item.get("kb_id", ""), "label": item.get("name", "")})
        except Exception:
            pass
    elif type == "role":
        try:
            from odap.biz.roles.storage.sqlite_role_storage import SQLiteRoleStorage
            role_store = SQLiteRoleStorage()
            for r in role_store.list_roles():
                options.append({"value": r.get("id", ""), "label": r.get("name", "")})
        except Exception:
            pass
    return {"options": options}


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    agent = storage.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return agent


@router.post("", response_model=Agent)
async def create_agent(agent: AgentCreate):
    data = agent.model_dump()
    return storage.create_agent(data)


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, agent: AgentUpdate):
    data = agent.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="无更新数据")
    updated = storage.update_agent(agent_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return updated


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    success = storage.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="智能体不存在")
    return {"message": "智能体删除成功"}
