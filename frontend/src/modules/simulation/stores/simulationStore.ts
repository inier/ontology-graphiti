import { create } from 'zustand';
import { simulationApi } from '../services/simulationApi';
import type {
  SandboxInfo,
  SandboxStatus,
  SimulationResult,
  TimelineInfo,
  TemplateInfo,
  EventSequence,
} from '../services/simulationApi';

interface SimulationState {
  activeTab: string;
  sandboxes: SandboxInfo[];
  selectedSandboxId: string | null;
  sandboxStatus: SandboxStatus | null;
  simulationResult: SimulationResult | null;
  parallelResult: Record<string, unknown> | null;
  whatIfResult: Record<string, unknown> | null;
  timelines: TimelineInfo[];
  selectedTimelineId: string | null;
  templates: TemplateInfo[];
  eventSequence: EventSequence | null;
  loading: boolean;
  error: string | null;

  setActiveTab: (tab: string) => void;
  fetchSandboxes: (workspaceId?: string) => Promise<void>;
  createSandbox: (config: Record<string, unknown>) => Promise<string | null>;
  selectSandbox: (sandboxId: string) => Promise<void>;
  runSimulation: (params: Record<string, unknown>) => Promise<void>;
  destroySandbox: (sandboxId: string) => Promise<void>;
  exportResults: (sandboxId: string, approvedBy?: string) => Promise<void>;
  runParallel: (scenarios: Array<Record<string, unknown>>) => Promise<void>;
  runWhatIf: (baseScenario: Record<string, unknown>, paramVariations: Array<Record<string, unknown>>) => Promise<void>;
  fetchTimelines: () => Promise<void>;
  createTimeline: (params: Record<string, unknown>) => Promise<string | null>;
  controlClock: (params: Record<string, unknown>) => Promise<void>;
  fetchTemplates: (category?: string) => Promise<void>;
  createTemplate: (data: Record<string, unknown>) => Promise<void>;
  deleteTemplate: (templateId: string) => Promise<void>;
  generateEventSequence: (params: Record<string, unknown>) => Promise<void>;
  injectEvent: (params: Record<string, unknown>) => Promise<void>;
  clearError: () => void;
}

export const useSimulationStore = create<SimulationState>((set, get) => ({
  activeTab: 'sandbox',
  sandboxes: [],
  selectedSandboxId: null,
  sandboxStatus: null,
  simulationResult: null,
  parallelResult: null,
  whatIfResult: null,
  timelines: [],
  selectedTimelineId: null,
  templates: [],
  eventSequence: null,
  loading: false,
  error: null,

  setActiveTab: (tab) => set({ activeTab: tab }),

  fetchSandboxes: async (workspaceId) => {
    try {
      const data = await simulationApi.listSandboxes(workspaceId);
      set({ sandboxes: data.sandboxes || [] });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  createSandbox: async (config) => {
    set({ loading: true, error: null });
    try {
      const result = await simulationApi.createSandbox(config);
      const data = await simulationApi.listSandboxes();
      set({ sandboxes: data.sandboxes || [], loading: false });
      return result.sandbox_id;
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  selectSandbox: async (sandboxId) => {
    set({ selectedSandboxId: sandboxId, loading: true, error: null });
    try {
      const status = await simulationApi.getSandboxStatus(sandboxId);
      set({ sandboxStatus: status, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  runSimulation: async (params) => {
    const sandboxId = get().selectedSandboxId;
    if (!sandboxId) return;
    set({ loading: true, error: null });
    try {
      const result = await simulationApi.runSimulation(sandboxId, params);
      set({ simulationResult: result, loading: false });
      const status = await simulationApi.getSandboxStatus(sandboxId);
      set({ sandboxStatus: status });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  destroySandbox: async (sandboxId) => {
    set({ loading: true, error: null });
    try {
      await simulationApi.destroySandbox(sandboxId);
      const data = await simulationApi.listSandboxes();
      set({
        sandboxes: data.sandboxes || [],
        selectedSandboxId: get().selectedSandboxId === sandboxId ? null : get().selectedSandboxId,
        sandboxStatus: get().selectedSandboxId === sandboxId ? null : get().sandboxStatus,
        simulationResult: get().selectedSandboxId === sandboxId ? null : get().simulationResult,
        loading: false,
      });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  exportResults: async (sandboxId, approvedBy = '') => {
    set({ loading: true, error: null });
    try {
      await simulationApi.exportResults(sandboxId, approvedBy);
      set({ loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  runParallel: async (scenarios) => {
    set({ loading: true, error: null });
    try {
      const result = await simulationApi.runParallel(scenarios);
      set({ parallelResult: result, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  runWhatIf: async (baseScenario, paramVariations) => {
    set({ loading: true, error: null });
    try {
      const result = await simulationApi.runWhatIf(baseScenario, paramVariations);
      set({ whatIfResult: result, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  fetchTimelines: async () => {
    try {
      const data = await simulationApi.listTimelines();
      set({ timelines: data.timelines || [] });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  createTimeline: async (params) => {
    set({ loading: true, error: null });
    try {
      const result = await simulationApi.createTimeline(params);
      const data = await simulationApi.listTimelines();
      set({ timelines: data.timelines || [], loading: false });
      return result.timeline_id;
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  controlClock: async (params) => {
    set({ loading: true, error: null });
    try {
      await simulationApi.controlClock(params);
      const timelineId = params.timeline_id as string;
      if (timelineId) {
        const data = await simulationApi.listTimelines();
        set({ timelines: data.timelines || [], loading: false });
      } else {
        set({ loading: false });
      }
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  fetchTemplates: async (category) => {
    try {
      const data = await simulationApi.listTemplates(category);
      set({ templates: data.templates || [] });
    } catch (e: unknown) {
      set({ error: (e as Error).message });
    }
  },

  createTemplate: async (data) => {
    set({ loading: true, error: null });
    try {
      await simulationApi.createTemplate(data);
      const result = await simulationApi.listTemplates();
      set({ templates: result.templates || [], loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteTemplate: async (templateId) => {
    set({ loading: true, error: null });
    try {
      await simulationApi.deleteTemplate(templateId);
      const result = await simulationApi.listTemplates();
      set({ templates: result.templates || [], loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  generateEventSequence: async (params) => {
    set({ loading: true, error: null });
    try {
      const result = await simulationApi.generateEventSequence(params);
      set({ eventSequence: result, loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  injectEvent: async (params) => {
    set({ loading: true, error: null });
    try {
      await simulationApi.injectEvent(params);
      set({ loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
