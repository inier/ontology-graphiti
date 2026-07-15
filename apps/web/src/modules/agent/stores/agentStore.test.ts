import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAgentStore } from './agentStore';

vi.mock('../services/agentApi', () => ({
  agentApi: {
    dispatch: vi.fn(),
    getTaskStatus: vi.fn(),
    getDecisionChainDetail: vi.fn(),
    listDecisions: vi.fn(),
  },
}));

import { agentApi } from '../services/agentApi';

const mockDispatchResult = {
  task_id: 'task-1',
  assigned_agent: 'agent-1',
  confidence: 0.95,
  routing_source: 'auto',
  plan: [],
  status: 'dispatched',
};

const mockTaskStatus = {
  task_id: 'task-1',
  status: 'completed',
  phases_completed: ['analysis', 'decision'],
  mission: 'Test mission',
};

const mockDecisionChain = {
  decision_id: 'dec-1',
  task_id: 'task-1',
  steps: [
    { step_id: 's1', phase: 'analysis', description: 'Analyzed', evidence: [], timestamp: '2026-01-01T00:00:00' },
  ],
  reasoning: 'Test reasoning',
  evidence: [],
};

const mockDecisionListResult = {
  decisions: [
    {
      decision_id: 'dec-1',
      task_id: 'task-1',
      reasoning: 'Test',
      evidence: [],
      workspace_id: 'ws-1',
      steps_count: 1,
      created_at: '2026-01-01T00:00:00',
      updated_at: '2026-01-01T00:00:00',
    },
  ],
  total: 1,
  page: 1,
  page_size: 10,
};

describe('agentStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAgentStore.setState({
      tasks: [],
      decisions: { decisions: [], total: 0, page: 1, page_size: 10 },
      currentChain: null,
      lastDispatch: null,
      loading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('has correct default values', () => {
      const state = useAgentStore.getState();
      expect(state.tasks).toEqual([]);
      expect(state.decisions).toEqual({ decisions: [], total: 0, page: 1, page_size: 10 });
      expect(state.currentChain).toBeNull();
      expect(state.lastDispatch).toBeNull();
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('dispatch', () => {
    it('dispatches intent successfully', async () => {
      (agentApi.dispatch as ReturnType<typeof vi.fn>).mockResolvedValue(mockDispatchResult);
      await useAgentStore.getState().dispatch('test intent', { key: 'value' }, 'ws-1');
      expect(agentApi.dispatch).toHaveBeenCalledWith('test intent', { key: 'value' }, 'ws-1');
      expect(useAgentStore.getState().lastDispatch).toEqual(mockDispatchResult);
      expect(useAgentStore.getState().loading).toBe(false);
      expect(useAgentStore.getState().error).toBeNull();
    });

    it('sets loading to true during dispatch', async () => {
      let resolveDispatch: (value: unknown) => void;
      const dispatchPromise = new Promise((resolve) => { resolveDispatch = resolve; });
      (agentApi.dispatch as ReturnType<typeof vi.fn>).mockReturnValue(dispatchPromise);
      const actionPromise = useAgentStore.getState().dispatch('test');
      expect(useAgentStore.getState().loading).toBe(true);
      resolveDispatch!(mockDispatchResult);
      await actionPromise;
      expect(useAgentStore.getState().loading).toBe(false);
    });

    it('handles dispatch error', async () => {
      (agentApi.dispatch as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Dispatch failed'));
      await useAgentStore.getState().dispatch('bad intent');
      expect(useAgentStore.getState().error).toBe('Dispatch failed');
      expect(useAgentStore.getState().loading).toBe(false);
      expect(useAgentStore.getState().lastDispatch).toBeNull();
    });
  });

  describe('getTaskStatus', () => {
    it('fetches task status and adds to tasks list', async () => {
      (agentApi.getTaskStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockTaskStatus);
      await useAgentStore.getState().getTaskStatus('task-1');
      expect(useAgentStore.getState().tasks).toHaveLength(1);
      expect(useAgentStore.getState().tasks[0].task_id).toBe('task-1');
      expect(useAgentStore.getState().loading).toBe(false);
    });

    it('replaces existing task with same task_id', async () => {
      useAgentStore.setState({
        tasks: [{ task_id: 'task-1', status: 'running', phases_completed: [] }],
      });
      (agentApi.getTaskStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockTaskStatus);
      await useAgentStore.getState().getTaskStatus('task-1');
      expect(useAgentStore.getState().tasks).toHaveLength(1);
      expect(useAgentStore.getState().tasks[0].status).toBe('completed');
    });

    it('handles getTaskStatus error', async () => {
      (agentApi.getTaskStatus as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Task not found'));
      await useAgentStore.getState().getTaskStatus('bad-task');
      expect(useAgentStore.getState().error).toBe('Task not found');
      expect(useAgentStore.getState().loading).toBe(false);
    });
  });

  describe('getDecisionChain', () => {
    it('fetches decision chain detail', async () => {
      (agentApi.getDecisionChainDetail as ReturnType<typeof vi.fn>).mockResolvedValue(mockDecisionChain);
      await useAgentStore.getState().getDecisionChain('dec-1');
      expect(useAgentStore.getState().currentChain).toEqual(mockDecisionChain);
      expect(useAgentStore.getState().loading).toBe(false);
    });

    it('handles getDecisionChain error', async () => {
      (agentApi.getDecisionChainDetail as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Chain not found'));
      await useAgentStore.getState().getDecisionChain('bad-dec');
      expect(useAgentStore.getState().error).toBe('Chain not found');
      expect(useAgentStore.getState().loading).toBe(false);
    });
  });

  describe('loadDecisions', () => {
    it('loads decisions with parameters', async () => {
      (agentApi.listDecisions as ReturnType<typeof vi.fn>).mockResolvedValue(mockDecisionListResult);
      await useAgentStore.getState().loadDecisions('ws-1', 1, 10);
      expect(agentApi.listDecisions).toHaveBeenCalledWith('ws-1', 1, 10);
      expect(useAgentStore.getState().decisions).toEqual(mockDecisionListResult);
      expect(useAgentStore.getState().loading).toBe(false);
    });

    it('handles loadDecisions error', async () => {
      (agentApi.listDecisions as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Load failed'));
      await useAgentStore.getState().loadDecisions();
      expect(useAgentStore.getState().error).toBe('Load failed');
      expect(useAgentStore.getState().loading).toBe(false);
    });
  });

  describe('clearError', () => {
    it('clears error state', () => {
      useAgentStore.setState({ error: 'Some error' });
      useAgentStore.getState().clearError();
      expect(useAgentStore.getState().error).toBeNull();
    });
  });
});
