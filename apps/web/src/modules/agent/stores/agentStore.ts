import { create } from 'zustand';
import { agentApi, type DispatchResult, type TaskStatusResult, type DecisionChainDetail, type DecisionListResult } from '../services/agentApi';

interface AgentState {
  tasks: TaskStatusResult[];
  decisions: DecisionListResult;
  currentChain: DecisionChainDetail | null;
  lastDispatch: DispatchResult | null;
  loading: boolean;
  error: string | null;

  dispatch: (intent: string, context?: Record<string, unknown>, workspaceId?: string) => Promise<void>;
  getTaskStatus: (taskId: string) => Promise<void>;
  getDecisionChain: (decisionId: string) => Promise<void>;
  loadDecisions: (workspaceId?: string, page?: number, pageSize?: number) => Promise<void>;
  clearError: () => void;
}

export const useAgentStore = create<AgentState>((set) => ({
  tasks: [],
  decisions: { decisions: [], total: 0, page: 1, page_size: 10 },
  currentChain: null,
  lastDispatch: null,
  loading: false,
  error: null,

  dispatch: async (intent, context, workspaceId) => {
    set({ loading: true, error: null });
    try {
      const result = await agentApi.dispatch(intent, context, workspaceId);
      set({ lastDispatch: result, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  getTaskStatus: async (taskId) => {
    set({ loading: true, error: null });
    try {
      const result = await agentApi.getTaskStatus(taskId);
      set((state) => ({
        tasks: [...state.tasks.filter((t) => t.task_id !== taskId), result],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  getDecisionChain: async (decisionId) => {
    set({ loading: true, error: null });
    try {
      const result = await agentApi.getDecisionChainDetail(decisionId);
      set({ currentChain: result, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  loadDecisions: async (workspaceId, page, pageSize) => {
    set({ loading: true, error: null });
    try {
      const result = await agentApi.listDecisions(workspaceId, page, pageSize);
      set({ decisions: result, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
