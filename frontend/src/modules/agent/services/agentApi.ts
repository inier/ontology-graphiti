import type { Agent, AgentFormData, AgentRefOption } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const agentApi = {
  listAgents: (): Promise<Agent[]> =>
    fetchJson<Agent[]>(`${API_BASE}/api/agents`),

  listAgentsByRole: (roleId: string): Promise<Agent[]> =>
    fetchJson<Agent[]>(`${API_BASE}/api/agents?role_id=${roleId}`),

  getAgent: (id: string): Promise<Agent> =>
    fetchJson<Agent>(`${API_BASE}/api/agents/${id}`),

  createAgent: (data: AgentFormData): Promise<Agent> =>
    fetchJson<Agent>(`${API_BASE}/api/agents`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateAgent: (id: string, data: AgentFormData): Promise<Agent> =>
    fetchJson<Agent>(`${API_BASE}/api/agents/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteAgent: (id: string): Promise<void> =>
    fetch(`${API_BASE}/api/agents/${id}`, { method: 'DELETE' }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    }),

  // 关联选项查询
  getEntityOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agents/ref-options?type=entity`),

  getBusinessLogicOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agents/ref-options?type=business_logic`),

  getIndicatorOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agents/ref-options?type=indicator`),

  getSkillOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agents/ref-options?type=skill`),

  getKnowledgeBaseOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agents/ref-options?type=knowledge_base`),

  getRoleOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agents/ref-options?type=role`),
};
