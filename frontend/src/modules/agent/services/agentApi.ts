import type { Agent, AgentFormData, AgentRefOption } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE || '';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('token');
  const authHeaders: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) authHeaders['Authorization'] = `Bearer ${token}`;
  const mergedOptions: RequestInit = { ...options, headers: { ...authHeaders, ...(options?.headers as Record<string, string>) } };
  const res = await fetch(url, mergedOptions);
  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const agentApi = {
  listAgents: (params?: { workspaceId?: string; roleId?: string }): Promise<Agent[]> => {
    const qs = new URLSearchParams();
    if (params?.roleId) qs.set('role_id', params.roleId);
    if (params?.workspaceId) qs.set('workspace_id', params.workspaceId);
    const query = qs.toString();
    return fetchJson<Agent[]>(`${API_BASE}/api/agents${query ? `?${query}` : ''}`);
  },

  listAgentsByRole: (roleId: string, workspaceId?: string): Promise<Agent[]> => {
    const qs = new URLSearchParams({ role_id: roleId });
    if (workspaceId) qs.set('workspace_id', workspaceId);
    return fetchJson<Agent[]>(`${API_BASE}/api/agents?${qs.toString()}`);
  },

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

  deleteAgent: (id: string): Promise<void> => {
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return fetch(`${API_BASE}/api/agents/${id}`, { method: 'DELETE', headers }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    });
  },

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
