import { create } from 'zustand';
import { registryApi } from '../services/registryApi';
import type {
  CreateActionTypeRequest,
  CreateLinkTypeRequest,
  CreateObjectTypeRequest,
  UpdateActionTypeRequest,
  UpdateLinkTypeRequest,
  UpdateObjectTypeRequest,
} from '../services/registryApi';
import {
  toActionTypeDefinition,
  toConsistencyResult,
  toLinkTypeDefinition,
  toList,
  toObjectTypeDefinition,
} from '../services/registryAdapters';
import type {
  ActionType,
  LinkType,
  ObjectType,
} from '../services/registryApi';
import type {
  ObjectTypeDefinition,
  LinkTypeDefinition,
  ActionTypeDefinition,
} from './ontologyStore';

/** `ontology_id` is injected by the store from `currentOntologyId`, callers never pass it. */
export type NewObjectType = Omit<CreateObjectTypeRequest, 'ontology_id'>;
export type NewActionType = Omit<CreateActionTypeRequest, 'ontology_id'>;
export type NewLinkType = Omit<CreateLinkTypeRequest, 'ontology_id'>;

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
  createObjectType: (data: NewObjectType) => Promise<void>;
  updateObjectType: (typeId: string, data: UpdateObjectTypeRequest) => Promise<void>;
  deleteObjectType: (typeId: string) => Promise<void>;
  createActionType: (data: NewActionType) => Promise<void>;
  updateActionType: (actionTypeId: string, data: UpdateActionTypeRequest) => Promise<void>;
  deleteActionType: (actionTypeId: string) => Promise<void>;
  createLinkType: (data: NewLinkType) => Promise<void>;
  updateLinkType: (linkId: string, data: UpdateLinkTypeRequest) => Promise<void>;
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
      const rows = await registryApi.objectTypes.list(ontologyId);
      set({ objectTypes: toList<ObjectType>(rows).map(toObjectTypeDefinition) });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createObjectType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.objectTypes.create({ ...data, ontology_id: ontologyId });
      const newType = toObjectTypeDefinition(result);
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
      const updated = toObjectTypeDefinition(result);
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
      const rows = await registryApi.actionTypes.list(ontologyId);
      set({ actionTypes: toList<ActionType>(rows).map(toActionTypeDefinition) });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createActionType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.actionTypes.create({ ...data, ontology_id: ontologyId });
      const newType = toActionTypeDefinition(result);
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
      const updated = toActionTypeDefinition(result);
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
      const rows = await registryApi.linkTypes.list(ontologyId);
      set({ linkTypes: toList<LinkType>(rows).map(toLinkTypeDefinition) });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createLinkType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireOntologyId(get().currentOntologyId);
      const result = await registryApi.linkTypes.create({ ...data, ontology_id: ontologyId });
      const newType = toLinkTypeDefinition(result);
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
      const updated = toLinkTypeDefinition(result);
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
      const result = await registryApi.validateIngest(ontologyId);
      set({
        consistencyResult: toConsistencyResult(result),
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
