import { create } from 'zustand';
import { registryApi } from '../services/registryApi';
import type {
  ObjectTypeDefinition,
  LinkTypeDefinition,
  ActionTypeDefinition,
} from './ontologyStore';

// ─── Consistency validation result ──────────────────────────────────

export interface ConsistencyResult {
  valid: boolean;
  issues: string[];
  warnings: string[];
}

// ─── Store State Interface ──────────────────────────────────────────

interface RegistryState {
  currentOntologyId: string | null;
  objectTypes: ObjectTypeDefinition[];
  linkTypes: LinkTypeDefinition[];
  actionTypes: ActionTypeDefinition[];
  consistencyResult: ConsistencyResult | null;
  loading: boolean;
  error: string | null;

  // ─── Actions ────────────────────────────────────────────────────

  selectOntology: (ontologyId: string) => Promise<void>;
  loadObjectTypes: () => Promise<void>;
  loadLinkTypes: () => Promise<void>;
  loadActionTypes: () => Promise<void>;
  createObjectType: (data: unknown) => Promise<void>;
  updateObjectType: (typeId: string, data: unknown) => Promise<void>;
  deleteObjectType: (typeId: string) => Promise<void>;
  createActionType: (data: unknown) => Promise<void>;
  updateActionType: (actionTypeId: string, data: unknown) => Promise<void>;
  deleteActionType: (actionTypeId: string) => Promise<void>;
  createLinkType: (data: unknown) => Promise<void>;
  updateLinkType: (linkId: string, data: unknown) => Promise<void>;
  deleteLinkType: (linkId: string) => Promise<void>;
  commitVersion: (changelog: string) => Promise<void>;
  validateConsistency: () => Promise<void>;
  clearCurrentOntology: () => void;
}

// ─── Helper ─────────────────────────────────────────────────────────

function requireOntologyId(id: string | null): string {
  if (!id) {
    throw new Error('No ontology selected');
  }
  return id;
}

// ─── Store Implementation ───────────────────────────────────────────

export const useRegistryStore = create<RegistryState>((set, get) => ({
  currentOntologyId: null,
  objectTypes: [],
  linkTypes: [],
  actionTypes: [],
  consistencyResult: null,
  loading: false,
  error: null,

  // ─── Select ontology & load all types ───────────────────────────

  selectOntology: async (ontologyId) => {
    set({ loading: true, error: null, currentOntologyId: ontologyId });
    try {
      await Promise.all([
        get().loadObjectTypes(),
        get().loadLinkTypes(),
        get().loadActionTypes(),
      ]);
      set({ loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  // ─── Object Type ────────────────────────────────────────────────

  loadObjectTypes: async () => {
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.objectTypes.list(ontologyId);
      const list = Array.isArray(result)
        ? result
        : ((result as Record<string, unknown>)?.object_types as ObjectTypeDefinition[]) ?? [];
      set({ objectTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createObjectType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.objectTypes.create(ontologyId, data);
      const newType = result as ObjectTypeDefinition;
      set((state) => ({
        objectTypes: [...state.objectTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateObjectType: async (typeId, data) => {
    set({ loading: true, error: null });
    try {
      const result = await registryApi.objectTypes.update(typeId, data);
      const updated = result as ObjectTypeDefinition;
      set((state) => ({
        objectTypes: state.objectTypes.map((t) =>
          t.type_id === typeId ? updated : t,
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteObjectType: async (typeId) => {
    try {
      await registryApi.objectTypes.delete(typeId);
      set((state) => ({
        objectTypes: state.objectTypes.filter((t) => t.type_id !== typeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ─── Action Type ────────────────────────────────────────────────

  loadActionTypes: async () => {
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.actionTypes.list(ontologyId);
      const list = Array.isArray(result)
        ? result
        : ((result as Record<string, unknown>)?.action_types as ActionTypeDefinition[]) ?? [];
      set({ actionTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createActionType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.actionTypes.create(ontologyId, data);
      const newType = result as ActionTypeDefinition;
      set((state) => ({
        actionTypes: [...state.actionTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateActionType: async (actionTypeId, data) => {
    set({ loading: true, error: null });
    try {
      const result = await registryApi.actionTypes.update(actionTypeId, data);
      const updated = result as ActionTypeDefinition;
      set((state) => ({
        actionTypes: state.actionTypes.map((t) =>
          t.action_type_id === actionTypeId ? updated : t,
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteActionType: async (actionTypeId) => {
    try {
      await registryApi.actionTypes.delete(actionTypeId);
      set((state) => ({
        actionTypes: state.actionTypes.filter((t) => t.action_type_id !== actionTypeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ─── Link Type ──────────────────────────────────────────────────

  loadLinkTypes: async () => {
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.linkTypes.list(ontologyId);
      const list = Array.isArray(result)
        ? result
        : ((result as Record<string, unknown>)?.link_types as LinkTypeDefinition[]) ?? [];
      set({ linkTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createLinkType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.linkTypes.create(ontologyId, data);
      const newType = result as LinkTypeDefinition;
      set((state) => ({
        linkTypes: [...state.linkTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateLinkType: async (linkId, data) => {
    set({ loading: true, error: null });
    try {
      const result = await registryApi.linkTypes.update(linkId, data);
      const updated = result as LinkTypeDefinition;
      set((state) => ({
        linkTypes: state.linkTypes.map((t) =>
          t.link_id === linkId ? updated : t,
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteLinkType: async (linkId) => {
    try {
      await registryApi.linkTypes.delete(linkId);
      set((state) => ({
        linkTypes: state.linkTypes.filter((t) => t.link_id !== linkId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ─── Version & Consistency ──────────────────────────────────────

  commitVersion: async (changelog) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      await registryApi.commitVersion(ontologyId, changelog);
      set({ loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  validateConsistency: async () => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.validateConsistency(ontologyId);
      set({
        consistencyResult: result as ConsistencyResult,
        loading: false,
      });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  // ─── Reset ──────────────────────────────────────────────────────

  clearCurrentOntology: () =>
    set({
      currentOntologyId: null,
      objectTypes: [],
      linkTypes: [],
      actionTypes: [],
      consistencyResult: null,
      loading: false,
      error: null,
    }),
}));
