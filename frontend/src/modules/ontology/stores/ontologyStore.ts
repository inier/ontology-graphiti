import { create } from 'zustand';
import { ontologyApi } from '../services/ontologyApi';
import type { EntityType, InstanceData, OntologyDocument } from '../services/ontologyApi';

// ─── TypeScript Interfaces for the new ontology redesign ────────────

export interface Ontology {
  ontology_id: string;
  name: string;
  description: string;
  status: string;
  workspace_id?: string;
  scenario_id?: string;
  current_version?: string;
  created_at: string;
  updated_at: string;
}

export interface ObjectTypeDefinition {
  type_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  properties?: Record<string, unknown>[];
  constraints?: Record<string, unknown>;
  classification_level?: string;
  created_at: string;
  updated_at: string;
}

export interface LinkTypeDefinition {
  link_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  source_type?: string;
  target_type?: string;
  cardinality?: string;
  link_type?: string;
  is_bidirectional?: boolean;
  reverse_name?: string;
  properties?: Record<string, unknown>[];
  created_at: string;
  updated_at?: string;
}

export interface ActionTypeDefinition {
  action_type_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  properties?: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
}

export interface ProcessTypeDefinition {
  process_type_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  steps?: Record<string, unknown>[];
  properties?: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
}

export interface RuleTypeDefinition {
  rule_type_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  condition?: string;
  action?: string;
  properties?: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
}

export interface FunctionTypeDefinition {
  function_type_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  parameters?: Record<string, unknown>[];
  return_type?: string;
  properties?: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
}

export interface IndicatorTypeDefinition {
  indicator_type_id: string;
  ontology_id: string;
  name: string;
  display_name?: string;
  description?: string;
  formula?: string;
  unit?: string;
  properties?: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
}

export interface SchemaVersion {
  version_id: string;
  ontology_id: string;
  version_number: number;
  changelog: string;
  status: string;
  created_at: string;
  created_by?: string;
}

// ─── Store State Interface ─────────────────────────────────────────

interface OntologyState {
  // Legacy state (backward compatibility)
  entityTypes: EntityType[];
  selectedTypeId: string | null;
  instances: InstanceData[];
  instancesTotal: number;
  document: OntologyDocument | null;
  loading: boolean;
  error: string | null;

  // Ontology selection state
  ontologies: Ontology[];
  currentOntology: Ontology | null;

  // Type definition state
  objectTypes: ObjectTypeDefinition[];
  linkTypes: LinkTypeDefinition[];
  actionTypes: ActionTypeDefinition[];
  processTypes: ProcessTypeDefinition[];
  ruleTypes: RuleTypeDefinition[];
  functionTypes: FunctionTypeDefinition[];
  indicatorTypes: IndicatorTypeDefinition[];

  // Schema version state
  schemaVersions: SchemaVersion[];
  currentVersionId: string | null;

  // Graph data
  graphData: Record<string, unknown> | null;

  // ─── Legacy actions (backward compatibility) ───────────────────

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
  clearCurrentOntology: () => void;

  // ─── Ontology CRUD actions ─────────────────────────────────────

  loadOntologies: (workspaceId?: string) => Promise<void>;
  selectOntology: (ontologyId: string) => Promise<void>;
  createOntology: (data: { name: string; description?: string; workspace_id?: string; scenario_id?: string }) => Promise<void>;

  // ─── Object Type actions ───────────────────────────────────────

  loadObjectTypes: () => Promise<void>;
  createObjectType: (data: unknown) => Promise<void>;
  updateObjectType: (typeId: string, data: unknown) => Promise<void>;
  deleteObjectType: (typeId: string) => Promise<void>;

  // ─── Link Type actions ─────────────────────────────────────────

  loadLinkTypes: () => Promise<void>;
  createLinkType: (data: unknown) => Promise<void>;
  updateLinkType: (linkId: string, data: unknown) => Promise<void>;
  deleteLinkType: (linkId: string) => Promise<void>;

  // ─── Action Type actions ───────────────────────────────────────

  loadActionTypes: () => Promise<void>;
  createActionType: (data: unknown) => Promise<void>;
  updateActionType: (actionTypeId: string, data: unknown) => Promise<void>;
  deleteActionType: (actionTypeId: string) => Promise<void>;

  // ─── Process Type actions ──────────────────────────────────────

  loadProcessTypes: () => Promise<void>;
  createProcessType: (data: unknown) => Promise<void>;
  updateProcessType: (typeId: string, data: unknown) => Promise<void>;
  deleteProcessType: (typeId: string) => Promise<void>;

  // ─── Rule Type actions ─────────────────────────────────────────

  loadRuleTypes: () => Promise<void>;
  createRuleType: (data: unknown) => Promise<void>;
  updateRuleType: (typeId: string, data: unknown) => Promise<void>;
  deleteRuleType: (typeId: string) => Promise<void>;

  // ─── Function Type actions ─────────────────────────────────────

  loadFunctionTypes: () => Promise<void>;
  createFunctionType: (data: unknown) => Promise<void>;
  updateFunctionType: (typeId: string, data: unknown) => Promise<void>;
  deleteFunctionType: (typeId: string) => Promise<void>;

  // ─── Indicator Type actions ────────────────────────────────────

  loadIndicatorTypes: () => Promise<void>;
  createIndicatorType: (data: unknown) => Promise<void>;
  updateIndicatorType: (typeId: string, data: unknown) => Promise<void>;
  deleteIndicatorType: (typeId: string) => Promise<void>;

  // ─── Schema Version actions ────────────────────────────────────

  loadSchemaVersions: () => Promise<void>;
  commitVersion: (changelog: string) => Promise<void>;

  // ─── Graph actions ─────────────────────────────────────────────

  loadGraph: () => Promise<void>;
}

// ─── Helper: get current ontology ID ───────────────────────────────

function requireCurrentOntology(currentOntology: Ontology | null): string {
  if (!currentOntology) {
    throw new Error('No ontology selected');
  }
  return currentOntology.ontology_id;
}

// ─── Store Implementation ──────────────────────────────────────────

export const useOntologyStore = create<OntologyState>((set, get) => ({
  // Legacy state
  entityTypes: [],
  selectedTypeId: null,
  instances: [],
  instancesTotal: 0,
  document: null,
  loading: false,
  error: null,

  // Ontology selection state
  ontologies: [],
  currentOntology: null,

  // Type definition state
  objectTypes: [],
  linkTypes: [],
  actionTypes: [],
  processTypes: [],
  ruleTypes: [],
  functionTypes: [],
  indicatorTypes: [],

  // Schema version state
  schemaVersions: [],
  currentVersionId: null,

  // Graph data
  graphData: null,

  // ═══════════════════════════════════════════════════════════════
  // Legacy actions (backward compatibility)
  // ═══════════════════════════════════════════════════════════════

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
  clearCurrentOntology: () => set({
    currentOntology: null,
    objectTypes: [],
    linkTypes: [],
    actionTypes: [],
    processTypes: [],
    ruleTypes: [],
    functionTypes: [],
    indicatorTypes: [],
    schemaVersions: [],
    currentVersionId: null,
    graphData: null,
  }),

  // ═══════════════════════════════════════════════════════════════
  // Ontology CRUD actions
  // ═══════════════════════════════════════════════════════════════

  loadOntologies: async (workspaceId) => {
    set({ loading: true, error: null });
    try {
      const result = await ontologyApi.ontologies.list(workspaceId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.ontologies as Ontology[] || [];
      set({ ontologies: list, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  selectOntology: async (ontologyId) => {
    set({ loading: true, error: null });
    try {
      const result = await ontologyApi.ontologies.get(ontologyId);
      const ontology = result as Ontology;
      set({ currentOntology: ontology });

      // Load all type definitions for the selected ontology in parallel
      await Promise.all([
        get().loadObjectTypes(),
        get().loadLinkTypes(),
        get().loadActionTypes(),
        get().loadProcessTypes(),
        get().loadRuleTypes(),
        get().loadFunctionTypes(),
        get().loadIndicatorTypes(),
        get().loadSchemaVersions(),
      ]);

      set({ loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  createOntology: async (data) => {
    set({ loading: true, error: null });
    try {
      const result = await ontologyApi.ontologies.create(data);
      const newOntology = result as Ontology;
      set((state) => ({
        ontologies: [...state.ontologies, newOntology],
        currentOntology: newOntology,
        // Reset type definitions for the new ontology
        objectTypes: [],
        linkTypes: [],
        actionTypes: [],
        processTypes: [],
        ruleTypes: [],
        functionTypes: [],
        indicatorTypes: [],
        schemaVersions: [],
        currentVersionId: null,
        graphData: null,
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Object Type actions
  // ═══════════════════════════════════════════════════════════════

  loadObjectTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.objectTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.object_types as ObjectTypeDefinition[] || [];
      set({ objectTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createObjectType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.objectTypeDefinitions.create(ontologyId, data);
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
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.objectTypeDefinitions.update(ontologyId, typeId, data);
      const updated = result as ObjectTypeDefinition;
      set((state) => ({
        objectTypes: state.objectTypes.map((t) =>
          t.type_id === typeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteObjectType: async (typeId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.objectTypeDefinitions.delete(ontologyId, typeId);
      set((state) => ({
        objectTypes: state.objectTypes.filter((t) => t.type_id !== typeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Link Type actions
  // ═══════════════════════════════════════════════════════════════

  loadLinkTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.linkTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.link_types as LinkTypeDefinition[] || [];
      set({ linkTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createLinkType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.linkTypeDefinitions.create(ontologyId, data);
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
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.linkTypeDefinitions.update(ontologyId, linkId, data);
      const updated = result as LinkTypeDefinition;
      set((state) => ({
        linkTypes: state.linkTypes.map((t) =>
          t.link_id === linkId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteLinkType: async (linkId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.linkTypeDefinitions.delete(ontologyId, linkId);
      set((state) => ({
        linkTypes: state.linkTypes.filter((t) => t.link_id !== linkId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Action Type actions
  // ═══════════════════════════════════════════════════════════════

  loadActionTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.actionTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.action_types as ActionTypeDefinition[] || [];
      set({ actionTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createActionType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.actionTypeDefinitions.create(ontologyId, data);
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
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.actionTypeDefinitions.update(ontologyId, actionTypeId, data);
      const updated = result as ActionTypeDefinition;
      set((state) => ({
        actionTypes: state.actionTypes.map((t) =>
          t.action_type_id === actionTypeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteActionType: async (actionTypeId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.actionTypeDefinitions.delete(ontologyId, actionTypeId);
      set((state) => ({
        actionTypes: state.actionTypes.filter((t) => t.action_type_id !== actionTypeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Process Type actions
  // ═══════════════════════════════════════════════════════════════

  loadProcessTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.processTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.process_types as ProcessTypeDefinition[] || [];
      set({ processTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createProcessType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.processTypeDefinitions.create(ontologyId, data);
      const newType = result as ProcessTypeDefinition;
      set((state) => ({
        processTypes: [...state.processTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateProcessType: async (typeId, data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.processTypeDefinitions.update(ontologyId, typeId, data);
      const updated = result as ProcessTypeDefinition;
      set((state) => ({
        processTypes: state.processTypes.map((t) =>
          t.process_type_id === typeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteProcessType: async (typeId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.processTypeDefinitions.delete(ontologyId, typeId);
      set((state) => ({
        processTypes: state.processTypes.filter((t) => t.process_type_id !== typeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Rule Type actions
  // ═══════════════════════════════════════════════════════════════

  loadRuleTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.ruleTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.rule_types as RuleTypeDefinition[] || [];
      set({ ruleTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createRuleType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.ruleTypeDefinitions.create(ontologyId, data);
      const newType = result as RuleTypeDefinition;
      set((state) => ({
        ruleTypes: [...state.ruleTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateRuleType: async (typeId, data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.ruleTypeDefinitions.update(ontologyId, typeId, data);
      const updated = result as RuleTypeDefinition;
      set((state) => ({
        ruleTypes: state.ruleTypes.map((t) =>
          t.rule_type_id === typeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteRuleType: async (typeId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.ruleTypeDefinitions.delete(ontologyId, typeId);
      set((state) => ({
        ruleTypes: state.ruleTypes.filter((t) => t.rule_type_id !== typeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Function Type actions
  // ═══════════════════════════════════════════════════════════════

  loadFunctionTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.functionTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.function_types as FunctionTypeDefinition[] || [];
      set({ functionTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createFunctionType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.functionTypeDefinitions.create(ontologyId, data);
      const newType = result as FunctionTypeDefinition;
      set((state) => ({
        functionTypes: [...state.functionTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateFunctionType: async (typeId, data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.functionTypeDefinitions.update(ontologyId, typeId, data);
      const updated = result as FunctionTypeDefinition;
      set((state) => ({
        functionTypes: state.functionTypes.map((t) =>
          t.function_type_id === typeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteFunctionType: async (typeId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.functionTypeDefinitions.delete(ontologyId, typeId);
      set((state) => ({
        functionTypes: state.functionTypes.filter((t) => t.function_type_id !== typeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Indicator Type actions
  // ═══════════════════════════════════════════════════════════════

  loadIndicatorTypes: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.indicatorTypeDefinitions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.indicator_types as IndicatorTypeDefinition[] || [];
      set({ indicatorTypes: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  createIndicatorType: async (data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.indicatorTypeDefinitions.create(ontologyId, data);
      const newType = result as IndicatorTypeDefinition;
      set((state) => ({
        indicatorTypes: [...state.indicatorTypes, newType],
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  updateIndicatorType: async (typeId, data) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.indicatorTypeDefinitions.update(ontologyId, typeId, data);
      const updated = result as IndicatorTypeDefinition;
      set((state) => ({
        indicatorTypes: state.indicatorTypes.map((t) =>
          t.indicator_type_id === typeId ? updated : t
        ),
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  deleteIndicatorType: async (typeId) => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      await ontologyApi.indicatorTypeDefinitions.delete(ontologyId, typeId);
      set((state) => ({
        indicatorTypes: state.indicatorTypes.filter((t) => t.indicator_type_id !== typeId),
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Schema Version actions
  // ═══════════════════════════════════════════════════════════════

  loadSchemaVersions: async () => {
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.schemaVersions.list(ontologyId);
      const list = Array.isArray(result) ? result : (result as Record<string, unknown>)?.versions as SchemaVersion[] || [];
      set({ schemaVersions: list });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  commitVersion: async (changelog) => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.schemaVersions.commit(ontologyId, changelog);
      const newVersion = result as SchemaVersion;
      set((state) => ({
        schemaVersions: [newVersion, ...state.schemaVersions],
        currentVersionId: newVersion.version_id,
        loading: false,
      }));
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // Graph actions
  // ═══════════════════════════════════════════════════════════════

  loadGraph: async () => {
    set({ loading: true, error: null });
    try {
      const ontologyId = requireCurrentOntology(get().currentOntology);
      const result = await ontologyApi.graph.get(ontologyId);
      set({ graphData: result as Record<string, unknown>, loading: false });
    } catch (e) {
      set({ error: (e as Error).message, loading: false });
    }
  },
}));
