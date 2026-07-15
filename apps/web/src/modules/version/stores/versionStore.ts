import { create } from 'zustand';
import { apiClient } from '@/modules/shared/services/apiClient';

const BASE = '/api/ontology/versions';

export interface VersionInfo {
  version_id: string;
  document_id: string;
  version_number: number;
  changelog: string;
  status: 'draft' | 'published' | 'archived';
  created_at: string;
  created_by: string;
  entity_count: number;
  relation_count: number;
}

export interface ComparisonResult {
  added_types: string[];
  removed_types: string[];
  modified_types: Array<{
    type_name: string;
    changes: Array<{ field: string; old_value: unknown; new_value: unknown }>;
  }>;
  added_properties: Array<{ type_name: string; property_name: string }>;
  removed_properties: Array<{ type_name: string; property_name: string }>;
}

interface VersionState {
  versions: VersionInfo[];
  currentVersion: VersionInfo | null;
  comparison: ComparisonResult | null;
  loading: boolean;
  error: string | null;

  loadVersions: (documentId: string) => Promise<void>;
  createVersion: (documentId: string, changelog: string) => Promise<void>;
  rollbackVersion: (documentId: string, versionId: string) => Promise<void>;
  compareVersions: (documentId: string, versionA: string, versionB: string) => Promise<void>;
  temporalQuery: (documentId: string, timestamp: string) => Promise<unknown>;
  clearError: () => void;
}

export const useVersionStore = create<VersionState>((set) => ({
  versions: [],
  currentVersion: null,
  comparison: null,
  loading: false,
  error: null,

  loadVersions: async (documentId) => {
    set({ loading: true, error: null });
    try {
      const data = await apiClient.get<{ versions: VersionInfo[] }>(`${BASE}/${documentId}`);
      set({ versions: data.versions || [], loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createVersion: async (documentId, changelog) => {
    set({ loading: true, error: null });
    try {
      const newVersion = await apiClient.post<VersionInfo>(`${BASE}/${documentId}`, { changelog });
      set((state) => ({
        versions: [newVersion, ...state.versions],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  rollbackVersion: async (documentId, versionId) => {
    set({ loading: true, error: null });
    try {
      await apiClient.post(`${BASE}/${documentId}/rollback`, { version_id: versionId });
      set({ loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  compareVersions: async (documentId, versionA, versionB) => {
    set({ loading: true, error: null });
    try {
      const result = await apiClient.get<ComparisonResult>(
        `${BASE}/${documentId}/compare?version_a=${versionA}&version_b=${versionB}`
      );
      set({ comparison: result, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  temporalQuery: async (documentId, timestamp) => {
    set({ loading: true, error: null });
    try {
      const result = await apiClient.post<unknown>(`${BASE}/${documentId}/temporal`, { timestamp });
      set({ loading: false });
      return result;
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  clearError: () => set({ error: null }),
}));
