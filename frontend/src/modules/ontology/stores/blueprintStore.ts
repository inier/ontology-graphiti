import { create } from 'zustand';
import { blueprintApi } from '../services/blueprintApi';
import type { Blueprint, BlueprintNode, BlueprintEdge, BlueprintListItem } from '../services/blueprintApi';

interface BlueprintState {
  blueprints: BlueprintListItem[];
  currentBlueprint: Blueprint | null;
  isLoading: boolean;
  error: string | null;
  selectedNodeIds: string[];

  loadBlueprints: (scenarioId?: string) => Promise<void>;
  loadBlueprint: (blueprintId: string) => Promise<void>;
  createBlueprint: (name: string, description?: string, scenarioId?: string) => Promise<Blueprint>;
  deleteBlueprint: (blueprintId: string) => Promise<void>;
  addNode: (nodeType: string, name: string, position?: { x: number; y: number }) => Promise<void>;
  updateNodePosition: (nodeId: string, position: { x: number; y: number }) => void;
  batchUpdatePositions: () => Promise<void>;
  removeNode: (nodeId: string) => Promise<void>;
  addEdge: (source: string, target: string, edgeType?: string) => Promise<void>;
  removeEdge: (edgeId: string) => Promise<void>;
  setSelectedNodeIds: (ids: string[]) => void;
  validate: () => Promise<{ is_valid: boolean; errors: string[]; warnings: string[] }>;
  publish: () => Promise<void>;
  autoLayout: (direction?: string) => Promise<void>;
  clearError: () => void;
}

export const useBlueprintStore = create<BlueprintState>((set, get) => ({
  blueprints: [],
  currentBlueprint: null,
  isLoading: false,
  error: null,
  selectedNodeIds: [],

  loadBlueprints: async (scenarioId) => {
    set({ isLoading: true, error: null });
    try {
      const result = await blueprintApi.list(scenarioId) as unknown as { blueprints?: BlueprintListItem[] };
      const list = Array.isArray(result) ? result : (result.blueprints || []);
      set({ blueprints: list, isLoading: false });
    } catch (e) {
      set({ error: (e as Error).message, isLoading: false });
    }
  },

  loadBlueprint: async (blueprintId) => {
    set({ isLoading: true, error: null });
    try {
      const result = await blueprintApi.get(blueprintId);
      set({ currentBlueprint: result, isLoading: false });
    } catch (e) {
      set({ error: (e as Error).message, isLoading: false });
    }
  },

  createBlueprint: async (name, description, scenarioId) => {
    set({ isLoading: true, error: null });
    try {
      const result = await blueprintApi.create({ name, description, scenario_id: scenarioId });
      const bp = result as unknown as Blueprint;
      set((state) => ({ blueprints: [...state.blueprints, bp], currentBlueprint: bp, isLoading: false }));
      return bp;
    } catch (e) {
      set({ error: (e as Error).message, isLoading: false });
      throw e;
    }
  },

  deleteBlueprint: async (blueprintId) => {
    try {
      await blueprintApi.delete(blueprintId);
      set((state) => ({
        blueprints: state.blueprints.filter(b => b.blueprint_id !== blueprintId),
        currentBlueprint: state.currentBlueprint?.blueprint_id === blueprintId ? null : state.currentBlueprint,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  addNode: async (nodeType, name, position) => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    try {
      const result = await blueprintApi.addNode(bp.blueprint_id, { node_type: nodeType, name, position });
      const newNode: BlueprintNode = {
        node_id: result.node_id,
        node_type: nodeType,
        name,
        position: position || { x: 0, y: 0 },
        config: {},
      };
      set((state) => ({
        currentBlueprint: state.currentBlueprint
          ? { ...state.currentBlueprint, nodes: [...state.currentBlueprint.nodes, newNode] }
          : null,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  updateNodePosition: (nodeId, position) => {
    set((state) => {
      if (!state.currentBlueprint) return state;
      const nodes = state.currentBlueprint.nodes.map(n =>
        n.node_id === nodeId ? { ...n, position } : n
      );
      return { currentBlueprint: { ...state.currentBlueprint, nodes } };
    });
  },

  batchUpdatePositions: async () => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    const positions: Record<string, { x: number; y: number }> = {};
    bp.nodes.forEach(n => { positions[n.node_id] = n.position; });
    try {
      await blueprintApi.batchUpdatePositions(bp.blueprint_id, positions);
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  removeNode: async (nodeId) => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    try {
      await blueprintApi.removeNode(bp.blueprint_id, nodeId);
      set((state) => {
        if (!state.currentBlueprint) return state;
        return {
          currentBlueprint: {
            ...state.currentBlueprint,
            nodes: state.currentBlueprint.nodes.filter(n => n.node_id !== nodeId),
            edges: state.currentBlueprint.edges.filter(e => e.source !== nodeId && e.target !== nodeId),
          },
        };
      });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  addEdge: async (source, target, edgeType) => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    try {
      const result = await blueprintApi.addEdge(bp.blueprint_id, {
        source,
        target,
        edge_type: edgeType || 'data_flow',
      });
      const newEdge: BlueprintEdge = {
        edge_id: result.edge_id,
        source,
        target,
        edge_type: edgeType || 'data_flow',
        label: '',
      };
      set((state) => ({
        currentBlueprint: state.currentBlueprint
          ? { ...state.currentBlueprint, edges: [...state.currentBlueprint.edges, newEdge] }
          : null,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  removeEdge: async (edgeId) => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    try {
      await blueprintApi.removeEdge(bp.blueprint_id, edgeId);
      set((state) => {
        if (!state.currentBlueprint) return state;
        return {
          currentBlueprint: {
            ...state.currentBlueprint,
            edges: state.currentBlueprint.edges.filter(e => e.edge_id !== edgeId),
          },
        };
      });
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  setSelectedNodeIds: (ids) => set({ selectedNodeIds: ids }),

  validate: async () => {
    const bp = get().currentBlueprint;
    if (!bp) return { is_valid: false, errors: ['No blueprint loaded'], warnings: [] };
    return await blueprintApi.validate(bp.blueprint_id);
  },

  publish: async () => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    try {
      await blueprintApi.publish(bp.blueprint_id);
      set((state) => ({
        currentBlueprint: state.currentBlueprint
          ? { ...state.currentBlueprint, is_published: true }
          : null,
      }));
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  autoLayout: async (direction) => {
    const bp = get().currentBlueprint;
    if (!bp) return;
    try {
      await blueprintApi.autoLayout(bp.blueprint_id, direction);
      await get().loadBlueprint(bp.blueprint_id);
    } catch (e) {
      set({ error: (e as Error).message });
    }
  },

  clearError: () => set({ error: null }),
}));
