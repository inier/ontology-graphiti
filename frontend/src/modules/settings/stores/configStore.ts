import { create } from 'zustand';
import { configApi } from '../services/configApi';
import type {
  ServiceConfig,
  ConfigValidationResult,
  UpdateConfigRequest,
} from '../types';

interface ConfigState {
  categories: ServiceConfig[];
  loading: boolean;
  error: string | null;
  validationResults: ConfigValidationResult[];
  historyDrawerOpen: boolean;

  fetchConfigs: () => Promise<void>;
  updateConfig: (
    data: UpdateConfigRequest,
  ) => Promise<ConfigValidationResult[] | null>;
  testConnection: (
    data: UpdateConfigRequest,
  ) => Promise<ConfigValidationResult[] | null>;
  toggleHistoryDrawer: (open?: boolean) => void;
  clearError: () => void;
}

export const useConfigStore = create<ConfigState>((set, get) => ({
  categories: [],
  loading: false,
  error: null,
  validationResults: [],
  historyDrawerOpen: false,

  fetchConfigs: async () => {
    set({ loading: true, error: null });
    try {
      const data = await configApi.getConfigs();
      set({ categories: data.categories || [], loading: false });
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateConfig: async (data) => {
    set({ loading: true, error: null });
    try {
      const result = await configApi.updateConfigs(data);
      const validationResults = result.validation_results || [];
      set({ validationResults, loading: false });
      // Refresh configs after successful update
      await get().fetchConfigs();
      return validationResults;
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  testConnection: async (data) => {
    set({ loading: true, error: null });
    try {
      const result = await configApi.testConnection(data);
      const validationResults = result.validation_results || [];
      set({ validationResults, loading: false });
      // Refresh configs to update connection status
      await get().fetchConfigs();
      return validationResults;
    } catch (e: unknown) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  toggleHistoryDrawer: (open) => {
    set({ historyDrawerOpen: open ?? !get().historyDrawerOpen });
  },

  clearError: () => set({ error: null }),
}));
