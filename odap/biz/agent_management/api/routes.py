from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from .schemas import Agent, AgentCreate, AgentUpdate
from ..storage.sqlite_agent_storage import SQLiteAgentStorage

router = APIRouter(prefix="/api/agents", tags=["agents"])

storage = SQLiteAgentStorage()


@router.get("", response_model=List[Agent])
async def list_agents(role_id: Optional[str] = Query(None, description="按角色ID过滤")):
    return storage.list_agents(role_id=role_id)


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
