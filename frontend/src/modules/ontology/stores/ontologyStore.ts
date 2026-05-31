import { create } from 'zustand';
import { ontologyApi } from '../services/ontologyApi';
import type { EntityType, InstanceData, OntologyDocument } from '../services/ontologyApi';

interface OntologyState {
  entityTypes: EntityType[];
  selectedTypeId: string | null;
  instances: InstanceData[];
  instancesTotal: number;
  document: OntologyDocument | null;
  loading: boolean;
  error: string | null;

  loadEntityTypes: (documentId: string) => Promise<void>;
  createEntityType: (documentId: string, data: Omit<EntityType, 'type_id' | 'created_at' | 'updated_at'>) => Promise<void>;
  updateEntityType: (documentId: string, typeId: string, data: Partial<EntityType>) => Promise<void>;
  deleteEntityType: (documentId: string, typeId: string) => Promise<void>;
  setSelectedTypeId: (typeId: string | null) => void;

  loadInstances: (documentId: string, typeId: string, page?: number, pageSize?: number) => Promise<void>;
  createInstance: (documentId: string, typeId: string, data: Record<string, unknown>) => Promise<void>;
  updateInstance: (documentId: string, typeId: string, instanceId: string, data: Record<string, unknown>) => Promise<void>;
  deleteInstance: (documentId: string, typeId: string, instanceId: string) => Promise<void>;
  batchImport: (documentId: string, typeId: string, instances: Record<string, unknown>[]) => Promise<void>;

  loadOntologyDocument: (documentId: string) => Promise<void>;
  exportDocument: (documentId: string, format?: string) => Promise<{ format: string; data: unknown } | null>;
  clearError: () => void;
}

export const useOntologyStore = create<OntologyState>((set, get) => ({
  entityTypes: [],
  selectedTypeId: null,
  instances: [],
  instancesTotal: 0,
  document: null,
  loading: false,
  error: null,

  loadEntityTypes: async (documentId) => {
    set({ loading: true, error: null });
    try {
      const types = await ontologyApi.listEntityTypes(documentId);
      set({ entityTypes: Array.isArray(types) ? types : [], loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createEntityType: async (documentId, data) => {
    set({ loading: true, error: null });
    try {
      const newType = await ontologyApi.createEntityType(documentId, data);
      set((state) => ({
        entityTypes: [...state.entityTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateEntityType: async (documentId, typeId, data) => {
    set({ loading: true, error: null });
    try {
      const updated = await ontologyApi.updateEntityType(documentId, typeId, data);
      set((state) => ({
        entityTypes: state.entityTypes.map((t) =>
          t.type_id === typeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteEntityType: async (documentId, typeId) => {
    try {
      await ontologyApi.deleteEntityType(documentId, typeId);
      set((state) => ({
        entityTypes: state.entityTypes.filter((t) => t.type_id !== typeId),
        selectedTypeId: state.selectedTypeId === typeId ? null : state.selectedTypeId,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  setSelectedTypeId: (typeId) => set({ selectedTypeId: typeId }),

  loadInstances: async (documentId, typeId, page, pageSize) => {
    set({ loading: true, error: null });
    try {
      const result = await ontologyApi.listInstances(documentId, typeId, page, pageSize);
      set({
        instances: result.instances || [],
        instancesTotal: result.total || 0,
        loading: false,
      });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createInstance: async (documentId, typeId, data) => {
    set({ loading: true, error: null });
    try {
      const newInstance = await ontologyApi.createInstance(documentId, typeId, data);
      set((state) => ({
        instances: [...state.instances, newInstance],
        instancesTotal: state.instancesTotal + 1,
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateInstance: async (documentId, typeId, instanceId, data) => {
    set({ loading: true, error: null });
    try {
      const updated = await ontologyApi.updateInstance(documentId, typeId, instanceId, data);
      set((state) => ({
        instances: state.instances.map((i) =>
          i.instance_id === instanceId ? updated : i
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteInstance: async (documentId, typeId, instanceId) => {
    try {
      await ontologyApi.deleteInstance(documentId, typeId, instanceId);
      set((state) => ({
        instances: state.instances.filter((i) => i.instance_id !== instanceId),
        instancesTotal: state.instancesTotal - 1,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  batchImport: async (documentId, typeId, instances) => {
    set({ loading: true, error: null });
    try {
      await ontologyApi.batchImport(documentId, typeId, instances);
      await get().loadInstances(documentId, typeId);
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  loadOntologyDocument: async (documentId) => {
    set({ loading: true, error: null });
    try {
      const doc = await ontologyApi.loadOntologyDocument(documentId);
      set({ document: doc, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  exportDocument: async (documentId, format) => {
    try {
      return await ontologyApi.exportDocument(documentId, format);
    } catch (e) {
      set({ error: (e as Error).message });
      return null;
    }
  },

  clearError: () => set({ error: null }),
}));
