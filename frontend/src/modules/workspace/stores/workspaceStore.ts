import { create } from 'zustand';
import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

const BASE = `${API_BASE}/api/workspaces`;

export interface WorkspaceDetail {
  workspace_id: string;
  name: string;
  description: string;
  isolation_level: 'LOW' | 'STANDARD' | 'HIGH' | 'STRICT';
  type: string;
  status: string;
  owner: string;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface ScenarioDetail {
  scenario_id: string;
  name: string;
  description: string;
  workspace_id: string;
  ontology_id?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface WorkspaceState {
  workspaces: WorkspaceDetail[];
  currentWorkspace: WorkspaceDetail | null;
  scenarios: ScenarioDetail[];
  loading: boolean;
  error: string | null;

  loadWorkspaces: () => Promise<void>;
  createWorkspace: (data: { name: string; description?: string; isolation_level?: string; owner?: string }) => Promise<void>;
  updateWorkspace: (workspaceId: string, data: Partial<WorkspaceDetail>) => Promise<void>;
  deleteWorkspace: (workspaceId: string) => Promise<void>;
  setCurrentWorkspace: (workspace: WorkspaceDetail | null) => void;

  exportWorkspace: (workspaceId: string) => Promise<unknown>;
  importWorkspace: (data: Record<string, unknown>) => Promise<void>;

  loadScenarios: (workspaceId: string) => Promise<void>;
  createScenario: (workspaceId: string, data: { name: string; description?: string; ontology_id?: string }) => Promise<void>;
  activateScenario: (workspaceId: string, scenarioId: string) => Promise<void>;
  clearError: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set, get) => ({
  workspaces: [],
  currentWorkspace: null,
  scenarios: [],
  loading: false,
  error: null,

  loadWorkspaces: async () => {
    set({ loading: true, error: null });
    try {
      const data = await fetchJson<{ workspaces: WorkspaceDetail[] }>(`${BASE}?page_size=100`);
      set({ workspaces: data.workspaces || [], loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createWorkspace: async (data) => {
    set({ loading: true, error: null });
    try {
      const newWs = await fetchJson<WorkspaceDetail>(BASE, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      set((state) => ({
        workspaces: [...state.workspaces, newWs],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateWorkspace: async (workspaceId, data) => {
    set({ loading: true, error: null });
    try {
      const updated = await fetchJson<WorkspaceDetail>(`${BASE}/${workspaceId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
      set((state) => ({
        workspaces: state.workspaces.map((w) =>
          w.workspace_id === workspaceId ? { ...w, ...updated } : w
        ),
        currentWorkspace: state.currentWorkspace?.workspace_id === workspaceId
          ? { ...state.currentWorkspace, ...updated }
          : state.currentWorkspace,
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteWorkspace: async (workspaceId) => {
    try {
      await fetchJson<void>(`${BASE}/${workspaceId}`, { method: 'DELETE' });
      set((state) => ({
        workspaces: state.workspaces.filter((w) => w.workspace_id !== workspaceId),
        currentWorkspace: state.currentWorkspace?.workspace_id === workspaceId
          ? null
          : state.currentWorkspace,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  setCurrentWorkspace: (workspace) => set({ currentWorkspace: workspace }),

  exportWorkspace: async (workspaceId) => {
    try {
      return await fetchJson<unknown>(`${BASE}/${workspaceId}/export`);
    } catch (e) {
      set({ error: (e as Error).message });
      return null;
    }
  },

  importWorkspace: async (data) => {
    set({ loading: true, error: null });
    try {
      const newWs = await fetchJson<WorkspaceDetail>(`${BASE}/import`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      set((state) => ({
        workspaces: [...state.workspaces, newWs],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  loadScenarios: async (workspaceId) => {
    set({ loading: true, error: null });
    try {
      const data = await fetchJson<{ scenarios: ScenarioDetail[] }>(`${BASE}/${workspaceId}/scenarios`);
      set({ scenarios: data.scenarios || [], loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createScenario: async (workspaceId, data) => {
    set({ loading: true, error: null });
    try {
      const newScenario = await fetchJson<ScenarioDetail>(`${BASE}/${workspaceId}/scenarios`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
      set((state) => ({
        scenarios: [...state.scenarios, newScenario],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  activateScenario: async (workspaceId, scenarioId) => {
    try {
      await fetchJson<void>(`${BASE}/${workspaceId}/scenarios/${scenarioId}/activate`, {
        method: 'POST',
      });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  clearError: () => set({ error: null }),
}));
