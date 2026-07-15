import { describe, it, expect, vi, beforeEach } from 'vitest';
import { agentApi } from './agentApi';
import type { DispatchResult, TaskStatusResult, DecisionChainResult, DecisionDetail, DecisionListResult } from './agentApi';

const API_BASE = 'http://localhost:8000';

function mockFetchResponse<T>(data: T, status = 200) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response);
}

function mockFetchError(status: number, statusText: string) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve({ detail: statusText }),
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', 'test-jwt-token');
});

// ─── Agent CRUD ────────────────────────────────────────────────

describe('agentApi - Agent CRUD', () => {
  it('listAgents calls correct endpoint without params', async () => {
    const mockData = [{ id: '1', name: 'Agent 1' }];
    mockFetchResponse(mockData);

    const result = await agentApi.listAgents();
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent-management`,
      expect.any(Object),
    );
    expect(result).toEqual(mockData);
  });

  it('listAgents passes workspace_id and role_id as query params', async () => {
    mockFetchResponse([]);

    await agentApi.listAgents({ workspaceId: 'ws-1', roleId: 'role-1' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/agent-management?'),
      expect.any(Object),
    );
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('role_id=role-1');
    expect(calledUrl).toContain('workspace_id=ws-1');
  });

  it('listAgentsByRole calls endpoint with role_id query', async () => {
    mockFetchResponse([]);

    await agentApi.listAgentsByRole('role-1', 'ws-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/agent-management?');
    expect(calledUrl).toContain('role_id=role-1');
    expect(calledUrl).toContain('workspace_id=ws-1');
  });

  it('getAgent calls correct endpoint with id', async () => {
    const mockAgent = { id: 'agent-1', name: 'Test Agent' };
    mockFetchResponse(mockAgent);

    const result = await agentApi.getAgent('agent-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent-management/agent-1`,
      expect.any(Object),
    );
    expect(result).toEqual(mockAgent);
  });

  it('createAgent sends POST with correct body', async () => {
    const formData = { name: 'New Agent', display_name: 'New', workspace_id: 'ws-1' };
    const mockResponse = { id: 'agent-new', ...formData };
    mockFetchResponse(mockResponse);

    const result = await agentApi.createAgent(formData as any);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent-management`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(formData),
      }),
    );
    expect(result).toEqual(mockResponse);
  });

  it('updateAgent sends PUT with correct body', async () => {
    const formData = { name: 'Updated Agent', display_name: 'Updated', workspace_id: 'ws-1' };
    const mockResponse = { id: 'agent-1', ...formData };
    mockFetchResponse(mockResponse);

    const result = await agentApi.updateAgent('agent-1', formData as any);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent-management/agent-1`,
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify(formData),
      }),
    );
    expect(result).toEqual(mockResponse);
  });

  it('deleteAgent sends DELETE request', async () => {
    mockFetchResponse({ status: 'ok' });

    await agentApi.deleteAgent('agent-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent-management/agent-1`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Ref Options ───────────────────────────────────────────────

describe('agentApi - Ref Options', () => {
  const refTypes = [
    { method: 'getEntityOptions', type: 'entity' },
    { method: 'getBusinessLogicOptions', type: 'business_logic' },
    { method: 'getIndicatorOptions', type: 'indicator' },
    { method: 'getSkillOptions', type: 'skill' },
    { method: 'getKnowledgeBaseOptions', type: 'knowledge_base' },
    { method: 'getRoleOptions', type: 'role' },
  ] as const;

  refTypes.forEach(({ method, type }) => {
    it(`${method} calls ref-options with type=${type}`, async () => {
      const mockOptions = [{ id: '1', name: `Option ${type}` }];
      mockFetchResponse(mockOptions);

      const result = await agentApi[method]();
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining(`/api/agent-management/ref-options?type=${type}`),
        expect.any(Object),
      );
      expect(result).toEqual(mockOptions);
    });
  });
});

// ─── Agent Dispatch & Tasks ────────────────────────────────────

describe('agentApi - Dispatch & Tasks', () => {
  it('dispatch sends POST with intent and context', async () => {
    const mockResult: DispatchResult = {
      task_id: 'task-1',
      assigned_agent: 'agent-1',
      confidence: 0.95,
      routing_source: 'auto',
      plan: [],
      status: 'dispatched',
    };
    mockFetchResponse(mockResult);

    const result = await agentApi.dispatch('test intent', { key: 'value' }, 'ws-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/dispatch`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ intent: 'test intent', context: { key: 'value' }, workspace_id: 'ws-1' }),
      }),
    );
    expect(result.task_id).toBe('task-1');
    expect(result.confidence).toBe(0.95);
  });

  it('dispatch sends empty context when not provided', async () => {
    mockFetchResponse({ task_id: 't1', assigned_agent: 'a1', confidence: 0.5, routing_source: 'auto', plan: [], status: 'ok' });

    await agentApi.dispatch('hello');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/dispatch`,
      expect.objectContaining({
        body: JSON.stringify({ intent: 'hello', context: {}, workspace_id: undefined }),
      }),
    );
  });

  it('getTaskStatus calls correct endpoint', async () => {
    const mockStatus: TaskStatusResult = {
      task_id: 'task-1',
      status: 'completed',
      phases_completed: ['analysis', 'decision'],
      final_decision: { action: 'approve' },
    };
    mockFetchResponse(mockStatus);

    const result = await agentApi.getTaskStatus('task-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/tasks/task-1`,
      expect.any(Object),
    );
    expect(result.status).toBe('completed');
    expect(result.phases_completed).toHaveLength(2);
  });

  it('getDecisionChain calls correct endpoint', async () => {
    const mockChain: DecisionChainResult = {
      task_id: 'task-1',
      chain: [{ step: 1 }],
      final_decision: { action: 'approve' },
    };
    mockFetchResponse(mockChain);

    const result = await agentApi.getDecisionChain('task-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/tasks/task-1/chain`,
      expect.any(Object),
    );
    expect(result.chain).toHaveLength(1);
  });
});

// ─── Swarm & Decisions ────────────────────────────────────────

describe('agentApi - Swarm & Decisions', () => {
  it('configureSwarm sends POST with swarm config', async () => {
    const roles = { role1: { capability: 'analysis' } };
    const rules = [{ condition: 'x > 0', target: 'agent-1' }];
    mockFetchResponse({ status: 'configured' });

    await agentApi.configureSwarm(roles, rules);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/swarm/configure`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ agent_roles: roles, routing_rules: rules }),
      }),
    );
  });

  it('getDecision calls correct endpoint', async () => {
    const mockDecision: DecisionDetail = {
      decision_id: 'dec-1',
      task_id: 'task-1',
      reasoning: 'test',
      evidence: [],
      steps_count: 3,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    };
    mockFetchResponse(mockDecision);

    const result = await agentApi.getDecision('dec-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/decisions/dec-1`,
      expect.any(Object),
    );
    expect(result.decision_id).toBe('dec-1');
  });

  it('getDecisionChainDetail calls correct endpoint', async () => {
    mockFetchResponse({ decision_id: 'dec-1', task_id: 'task-1', steps: [], reasoning: '', evidence: [] });

    await agentApi.getDecisionChainDetail('dec-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/agent/decisions/dec-1/chain`,
      expect.any(Object),
    );
  });

  it('listDecisions calls endpoint with query params', async () => {
    const mockList: DecisionListResult = {
      decisions: [],
      total: 0,
      page: 1,
      page_size: 10,
    };
    mockFetchResponse(mockList);

    const result = await agentApi.listDecisions('ws-1', 2, 20);
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/agent/decisions?');
    expect(calledUrl).toContain('workspace_id=ws-1');
    expect(calledUrl).toContain('page=2');
    expect(calledUrl).toContain('page_size=20');
    expect(result.total).toBe(0);
  });

  it('listDecisions works without optional params', async () => {
    mockFetchResponse({ decisions: [], total: 0, page: 1, page_size: 10 });

    await agentApi.listDecisions();
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('?');
  });
});

// ─── Error Handling ────────────────────────────────────────────

describe('agentApi - Error Handling', () => {
  it('throws on HTTP error response', async () => {
    mockFetchError(500, 'Internal Server Error');

    await expect(agentApi.listAgents()).rejects.toThrow('HTTP 500');
  });

  it('throws on 404 error', async () => {
    mockFetchError(404, 'Not Found');

    await expect(agentApi.getAgent('nonexistent')).rejects.toThrow('HTTP 404');
  });

  it('throws on network error', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(agentApi.listAgents()).rejects.toThrow('Failed to fetch');
  });
});

// ─── Auth Headers ──────────────────────────────────────────────

describe('agentApi - Auth Headers', () => {
  it('includes Authorization header when token exists', async () => {
    mockFetchResponse([]);

    await agentApi.listAgents();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
  });

  it('includes Content-Type application/json header', async () => {
    mockFetchResponse([]);

    await agentApi.listAgents();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });
});
