import type { Agent, AgentFormData, AgentRefOption } from '../types';
import { fetchJson, apiClient } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

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

  deleteAgent: (id: string): Promise<void> =>
    apiClient.delete(`${API_BASE}/api/agent-management/${id}`),

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

  dispatch: (intent: string, context?: Record<string, unknown>, workspaceId?: string): Promise<DispatchResult> =>
    fetchJson<DispatchResult>(`${API_BASE}/api/agent/dispatch`, {
      method: 'POST',
      body: JSON.stringify({ intent, context: context || {}, workspace_id: workspaceId }),
    }),

  getTaskStatus: (taskId: string): Promise<TaskStatusResult> =>
    fetchJson<TaskStatusResult>(`${API_BASE}/api/agent/tasks/${taskId}`),

  getDecisionChain: (taskId: string): Promise<DecisionChainResult> =>
    fetchJson<DecisionChainResult>(`${API_BASE}/api/agent/tasks/${taskId}/chain`),

  configureSwarm: (agentRoles?: Record<string, unknown>, routingRules?: unknown[]): Promise<unknown> =>
    fetchJson(`${API_BASE}/api/agent/swarm/configure`, {
      method: 'POST',
      body: JSON.stringify({ agent_roles: agentRoles, routing_rules: routingRules }),
    }),

  getDecision: (decisionId: string): Promise<DecisionDetail> =>
    fetchJson<DecisionDetail>(`${API_BASE}/api/agent/decisions/${decisionId}`),

  getDecisionChainDetail: (decisionId: string): Promise<DecisionChainDetail> =>
    fetchJson<DecisionChainDetail>(`${API_BASE}/api/agent/decisions/${decisionId}/chain`),

  listDecisions: (workspaceId?: string, page?: number, pageSize?: number): Promise<DecisionListResult> => {
    const qs = new URLSearchParams();
    if (workspaceId) qs.set('workspace_id', workspaceId);
    if (page) qs.set('page', String(page));
    if (pageSize) qs.set('page_size', String(pageSize));
    const query = qs.toString();
    return fetchJson<DecisionListResult>(`${API_BASE}/api/agent/decisions${query ? `?${query}` : ''}`);
  },
};

export interface DispatchResult {
  task_id: string;
  assigned_agent: string;
  confidence: number;
  routing_source: string;
  plan: Record<string, unknown>[];
  status: string;
}

export interface TaskStatusResult {
  task_id: string;
  status: string;
  phases_completed: string[];
  mission?: string;
  final_decision?: Record<string, unknown>;
  execution_time_ms?: number;
  error_message?: string;
}

export interface DecisionChainResult {
  task_id: string;
  chain: Record<string, unknown>[];
  final_decision?: Record<string, unknown>;
}

export interface DecisionDetail {
  decision_id: string;
  task_id: string;
  reasoning: string;
  evidence: Record<string, unknown>[];
  workspace_id?: string;
  steps_count: number;
  created_at: string;
  updated_at: string;
}

export interface DecisionChainDetail {
  decision_id: string;
  task_id: string;
  steps: DecisionStep[];
  reasoning: string;
  evidence: Record<string, unknown>[];
}

export interface DecisionStep {
  step_id: string;
  phase: string;
  description: string;
  evidence: Record<string, unknown>[];
  timestamp: string;
}

export interface DecisionListResult {
  decisions: DecisionDetail[];
  total: number;
  page: number;
  page_size: number;
}
