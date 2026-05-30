import type { Agent, AgentFormData, AgentRefOption } from '../types';
import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

export const agentApi = {
  listAgents: (params?: { workspaceId?: string; roleId?: string }): Promise<Agent[]> => {
    const qs = new URLSearchParams();
    if (params?.roleId) qs.set('role_id', params.roleId);
    if (params?.workspaceId) qs.set('workspace_id', params.workspaceId);
    const query = qs.toString();
    return fetchJson<Agent[]>(`${API_BASE}/api/agent-management${query ? `?${query}` : ''}`);
  },

  listAgentsByRole: (roleId: string, workspaceId?: string): Promise<Agent[]> => {
    const qs = new URLSearchParams({ role_id: roleId });
    if (workspaceId) qs.set('workspace_id', workspaceId);
    return fetchJson<Agent[]>(`${API_BASE}/api/agent-management?${qs.toString()}`);
  },

  getAgent: (id: string): Promise<Agent> =>
    fetchJson<Agent>(`${API_BASE}/api/agent-management/${id}`),

  createAgent: (data: AgentFormData): Promise<Agent> =>
    fetchJson<Agent>(`${API_BASE}/api/agent-management`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateAgent: (id: string, data: AgentFormData): Promise<Agent> =>
    fetchJson<Agent>(`${API_BASE}/api/agent-management/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  deleteAgent: (id: string): Promise<void> => {
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return fetch(`${API_BASE}/api/agent-management/${id}`, { method: 'DELETE', headers }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
    });
  },

  getEntityOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agent-management/ref-options?type=entity`),

  getBusinessLogicOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agent-management/ref-options?type=business_logic`),

  getIndicatorOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agent-management/ref-options?type=indicator`),

  getSkillOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agent-management/ref-options?type=skill`),

  getKnowledgeBaseOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agent-management/ref-options?type=knowledge_base`),

  getRoleOptions: (): Promise<AgentRefOption[]> =>
    fetchJson<AgentRefOption[]>(`${API_BASE}/api/agent-management/ref-options?type=role`),
};
