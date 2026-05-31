import { create } from 'zustand';
import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

const BASE = `${API_BASE}/api/ontology/versions`;

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
  selectedVersionId: string | null;
  comparisonResult: ComparisonResult | null;
  loading: boolean;
  error: string | null;

  loadVersions: (documentId: string) => Promise<void>;
  createVersion: (documentId: string, changelog: string) => Promise<void>;
  rollbackVersion: (documentId: string, versionId: string) => Promise<void>;
  compareVersions: (documentId: string, versionA: string, versionB: string) => Promise<void>;
  temporalQuery: (documentId: string, timestamp: string) => Promise<unknown>;
  setSelectedVersionId: (versionId: string | null) => void;
  clearError: () => void;
}

export const useVersionStore = create<VersionState>((set) => ({
  versions: [],
  selectedVersionId: null,
  comparisonResult: null,
  loading: false,
  error: null,

  loadVersions: async (documentId) => {
    set({ loading: true, error: null });
    try {
      const data = await fetchJson<{ versions: VersionInfo[] }>(`${BASE}/${documentId}`);
      set({ versions: data.versions || [], loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createVersion: async (documentId, changelog) => {
    set({ loading: true, error: null });
    try {
      const newVersion = await fetchJson<VersionInfo>(`${BASE}/${documentId}`, {
        method: 'POST',
        body: JSON.stringify({ changelog }),
      });
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
      await fetchJson<void>(`${BASE}/${documentId}/rollback`, {
        method: 'POST',
        body: JSON.stringify({ version_id: versionId }),
      });
      set({ loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  compareVersions: async (documentId, versionA, versionB) => {
    set({ loading: true, error: null });
    try {
      const result = await fetchJson<ComparisonResult>(
        `${BASE}/${documentId}/compare?version_a=${versionA}&version_b=${versionB}`
      );
      set({ comparisonResult: result, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  temporalQuery: async (documentId, timestamp) => {
    set({ loading: true, error: null });
    try {
      const result = await fetchJson<unknown>(`${BASE}/${documentId}/temporal`, {
        method: 'POST',
        body: JSON.stringify({ timestamp }),
      });
      set({ loading: false });
      return result;
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
      return null;
    }
  },

  setSelectedVersionId: (versionId) => set({ selectedVersionId: versionId }),
  clearError: () => set({ error: null }),
}));
