from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict, Any

from .schemas import Agent, AgentCreate, AgentUpdate
from ..storage.sqlite_agent_storage import SQLiteAgentStorage

router = APIRouter(prefix="/api/agents", tags=["agents"])

storage = SQLiteAgentStorage()


def _build_ref_labels(agent_data: Dict[str, Any]) -> Dict[str, str]:
    labels: Dict[str, str] = {}
    if not agent_data:
        return labels

    all_ids = set()
    for field in ("related_objects", "related_processes", "related_rules",
                  "related_business_logic", "related_indicators",
                  "related_skills", "related_knowledge_bases"):
        for v in agent_data.get(field, []):
            all_ids.add(v)

    if not all_ids:
        return labels

    try:
        from odap.biz.core.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
        oms = SQLiteOMSStorage()
        for obj in oms.list_object_types():
            tid = obj.get("type_id", "")
            tname = obj.get("name", "")
            tdisplay = obj.get("display_name") or tname
            if tid in all_ids:
                labels[tid] = tdisplay
            if tname in all_ids and tname not in labels:
                labels[tname] = tdisplay
            if tdisplay in all_ids and tdisplay not in labels:
                labels[tdisplay] = tdisplay
    except Exception:
        pass

    try:
        from odap.biz.management.business.storage.sqlite_storage import SQLiteBusinessStorage
        biz = SQLiteBusinessStorage()
        for item in biz.list_processes():
            pid = item.get("process_id", "")
            pname = item.get("name", "")
            pdisplay = item.get("display_name") or pname
            if pid in all_ids:
                labels[pid] = pdisplay
            if pname in all_ids and pname not in labels:
                labels[pname] = pdisplay
        for item in biz.list_rules():
            rid = item.get("rule_id", "")
            rname = item.get("name", "")
            rdisplay = item.get("display_name") or rname
            if rid in all_ids:
                labels[rid] = rdisplay
            if rname in all_ids and rname not in labels:
                labels[rname] = rdisplay
        for item in biz.list_logics():
            lid = item.get("logic_id", "")
            lname = item.get("name", "")
            ldisplay = item.get("display_name") or lname
            if lid in all_ids:
                labels[lid] = ldisplay
            if lname in all_ids and lname not in labels:
                labels[lname] = ldisplay
        for item in biz.list_indicators():
            iid = item.get("indicator_id", "")
            iname = item.get("name", "")
            idisplay = item.get("display_name") or iname
            if iid in all_ids:
                labels[iid] = idisplay
            if iname in all_ids and iname not in labels:
                labels[iname] = idisplay
    except Exception:
        pass

    try:
        from odap.biz.platform.skill_system.impl.skill_manager import SkillManager
        mgr = SkillManager()
        for s in mgr.list_skills():
            sid = s.id
            sname = s.name
            if sid in all_ids:
                labels[sid] = sname
            if sname in all_ids and sname not in labels:
                labels[sname] = sname
    except Exception:
        pass

    try:
        from odap.biz.data.knowledge_base.storage.sqlite_kb_storage import SQLiteKBStorage
        kb = SQLiteKBStorage()
        for item in kb.list_knowledge_bases():
            kid = item.get("kb_id", "")
            kname = item.get("name", "")
            if kid in all_ids:
                labels[kid] = kname
            if kname in all_ids and kname not in labels:
                labels[kname] = kname
    except Exception:
        pass

    return labels


class AgentService:
    def __init__(self):
        self.storage = storage

    def list_agents(self, role_id: Optional[str] = None, workspace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.list_agents(role_id=role_id, workspace_id=workspace_id)

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        agent = self.storage.get_agent(agent_id)
        if not agent:
            return {"status": "error", "message": "智能体不存在"}
        return agent

    def create_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return self.storage.create_agent(data)

    def update_agent(self, agent_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        updated = self.storage.update_agent(agent_id, data)
        if not updated:
            return {"status": "error", "message": "智能体不存在"}
        return updated

    def delete_agent(self, agent_id: str) -> Dict[str, Any]:
        success = self.storage.delete_agent(agent_id)
        if not success:
            return {"status": "error", "message": "智能体不存在"}
        return {"status": "success", "message": "智能体删除成功"}


agent_service = AgentService()


@router.get("", response_model=List[Agent])
async def list_agents(
    role_id: Optional[str] = Query(None, description="按角色ID过滤"),
    workspace_id: Optional[str] = Query(None, description="按工作空间ID过滤"),
):
    try:
        agents = agent_service.list_agents(role_id=role_id, workspace_id=workspace_id)
        for a in agents:
            a["ref_labels"] = _build_ref_labels(a)
        return agents
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ref-options")
async def get_ref_options(type: str = Query(..., description="引用类型")):
    options = []
    if type == "entity":
        try:
            from odap.biz.core.ontology.oms.storage.sqlite_oms_storage import SQLiteOMSStorage
            oms = SQLiteOMSStorage()
            for obj in oms.list_object_types():
                options.append({"value": obj.get("type_id", ""), "label": obj.get("display_name") or obj.get("name", "")})
        except Exception:
            pass
    elif type == "business_logic":
        try:
            from odap.biz.management.business.storage.sqlite_storage import SQLiteBusinessStorage
            biz = SQLiteBusinessStorage()
            for item in biz.list_logics():
                options.append({"value": item.get("logic_id", ""), "label": item.get("display_name") or item.get("name", "")})
        except Exception:
            pass
    elif type == "indicator":
        try:
            from odap.biz.management.business.storage.sqlite_storage import SQLiteBusinessStorage
            biz = SQLiteBusinessStorage()
            for item in biz.list_indicators():
                options.append({"value": item.get("indicator_id", ""), "label": item.get("display_name") or item.get("name", "")})
        except Exception:
            pass
    elif type == "skill":
        try:
            from odap.biz.platform.skill_system.impl.skill_manager import SkillManager
            mgr = SkillManager()
            for s in mgr.list_skills():
                options.append({"value": s.id, "label": s.name})
        except Exception:
            pass
    elif type == "knowledge_base":
        try:
            from odap.biz.data.knowledge_base.storage.sqlite_kb_storage import SQLiteKBStorage
            kb = SQLiteKBStorage()
            for item in kb.list_knowledge_bases():
                options.append({"value": item.get("kb_id", ""), "label": item.get("name", "")})
        except Exception:
            pass
    elif type == "role":
        try:
            from odap.biz.platform.roles.storage.sqlite_role_storage import SQLiteRoleStorage
            role_store = SQLiteRoleStorage()
            for r in role_store.list_roles():
                options.append({"value": r.get("id", ""), "label": r.get("name", "")})
        except Exception:
            pass
    return {"options": options}


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str):
    try:
        result = agent_service.get_agent(agent_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        result["ref_labels"] = _build_ref_labels(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=Agent)
async def create_agent(agent: AgentCreate):
    try:
        data = agent.model_dump()
        result = agent_service.create_agent(data)
        result["ref_labels"] = _build_ref_labels(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, agent: AgentUpdate):
    try:
        data = agent.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="无更新数据")
        result = agent_service.update_agent(agent_id, data)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        result["ref_labels"] = _build_ref_labels(result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    try:
        result = agent_service.delete_agent(agent_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result["message"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
