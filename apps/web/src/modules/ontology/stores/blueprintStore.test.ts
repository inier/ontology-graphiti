import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useBlueprintStore } from './blueprintStore';

vi.mock('../services/blueprintApi', () => ({
  blueprintApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    addNode: vi.fn(),
    updateNode: vi.fn(),
    removeNode: vi.fn(),
    addEdge: vi.fn(),
    removeEdge: vi.fn(),
    batchUpdatePositions: vi.fn(),
    autoLayout: vi.fn(),
    validate: vi.fn(),
    publish: vi.fn(),
    fork: vi.fn(),
    export: vi.fn(),
    import: vi.fn(),
  },
}));

import { blueprintApi } from '../services/blueprintApi';

const mockBlueprint = {
  blueprint_id: 'bp-test1',
  name: 'Test Blueprint',
  description: '',
  scenario_id: null,
  version: 1,
  nodes: [],
  edges: [],
  layout: {},
  is_published: false,
  parent_version_id: null,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
  metadata: {},
};

describe('blueprintStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useBlueprintStore.setState({
      blueprints: [],
      currentBlueprint: null,
      isLoading: false,
      error: null,
      selectedNodeIds: [],
    });
  });

  describe('loadBlueprints', () => {
    it('loads blueprints successfully', async () => {
      (blueprintApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
        status: 'success',
        blueprints: [mockBlueprint],
      });
      await useBlueprintStore.getState().loadBlueprints();
      expect(useBlueprintStore.getState().blueprints).toHaveLength(1);
    });

    it('handles load error', async () => {
      (blueprintApi.list as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));
      await useBlueprintStore.getState().loadBlueprints();
      expect(useBlueprintStore.getState().error).toBe('Network error');
    });
  });

  describe('loadBlueprint', () => {
    it('loads a single blueprint', async () => {
      (blueprintApi.get as ReturnType<typeof vi.fn>).mockResolvedValue(mockBlueprint);
      await useBlueprintStore.getState().loadBlueprint('bp-test1');
      expect(useBlueprintStore.getState().currentBlueprint?.blueprint_id).toBe('bp-test1');
    });
  });

  describe('createBlueprint', () => {
    it('creates a blueprint and adds to list', async () => {
      (blueprintApi.create as ReturnType<typeof vi.fn>).mockResolvedValue(mockBlueprint);
      const result = await useBlueprintStore.getState().createBlueprint('Test');
      expect(result.blueprint_id).toBe('bp-test1');
      expect(useBlueprintStore.getState().blueprints).toHaveLength(1);
    });
  });

  describe('addNode', () => {
    it('adds a node to current blueprint', async () => {
      useBlueprintStore.setState({ currentBlueprint: { ...mockBlueprint } });
      (blueprintApi.addNode as ReturnType<typeof vi.fn>).mockResolvedValue({ node_id: 'node-1' });
      await useBlueprintStore.getState().addNode('data_source', 'Source', { x: 100, y: 100 });
      expect(useBlueprintStore.getState().currentBlueprint?.nodes).toHaveLength(1);
      expect(useBlueprintStore.getState().currentBlueprint?.nodes[0].node_id).toBe('node-1');
    });
  });

  describe('updateNodePosition', () => {
    it('updates node position locally', () => {
      useBlueprintStore.setState({
        currentBlueprint: {
          ...mockBlueprint,
          nodes: [{ node_id: 'node-1', node_type: 'data_source', name: 'Source', position: { x: 0, y: 0 }, config: {} }],
        },
      });
      useBlueprintStore.getState().updateNodePosition('node-1', { x: 200, y: 300 });
      expect(useBlueprintStore.getState().currentBlueprint?.nodes[0].position).toEqual({ x: 200, y: 300 });
    });
  });

  describe('removeNode', () => {
    it('removes node and its connected edges', async () => {
      useBlueprintStore.setState({
        currentBlueprint: {
          ...mockBlueprint,
          nodes: [{ node_id: 'node-1', node_type: 'data_source', name: 'Source', position: { x: 0, y: 0 }, config: {} }],
          edges: [{ edge_id: 'edge-1', source: 'node-1', target: 'node-2', edge_type: 'data_flow', label: '' }],
        },
      });
      (blueprintApi.removeNode as ReturnType<typeof vi.fn>).mockResolvedValue({});
      await useBlueprintStore.getState().removeNode('node-1');
      expect(useBlueprintStore.getState().currentBlueprint?.nodes).toHaveLength(0);
      expect(useBlueprintStore.getState().currentBlueprint?.edges).toHaveLength(0);
    });
  });

  describe('addEdge', () => {
    it('adds an edge to current blueprint', async () => {
      useBlueprintStore.setState({ currentBlueprint: { ...mockBlueprint } });
      (blueprintApi.addEdge as ReturnType<typeof vi.fn>).mockResolvedValue({ edge_id: 'edge-1' });
      await useBlueprintStore.getState().addEdge('node-1', 'node-2', 'data_flow');
      expect(useBlueprintStore.getState().currentBlueprint?.edges).toHaveLength(1);
    });
  });

  describe('validate', () => {
    it('validates current blueprint', async () => {
      useBlueprintStore.setState({ currentBlueprint: { ...mockBlueprint } });
      (blueprintApi.validate as ReturnType<typeof vi.fn>).mockResolvedValue({
        status: 'success', is_valid: true, errors: [], warnings: [],
      });
      const result = await useBlueprintStore.getState().validate();
      expect(result.is_valid).toBe(true);
    });
  });

  describe('publish', () => {
    it('publishes current blueprint', async () => {
      useBlueprintStore.setState({ currentBlueprint: { ...mockBlueprint, is_published: false } });
      (blueprintApi.publish as ReturnType<typeof vi.fn>).mockResolvedValue({ status: 'success' });
      await useBlueprintStore.getState().publish();
      expect(useBlueprintStore.getState().currentBlueprint?.is_published).toBe(true);
    });
  });

  describe('autoLayout', () => {
    it('calls autoLayout and reloads blueprint', async () => {
      const bpWithNodes = {
        ...mockBlueprint,
        nodes: [{ node_id: 'n1', node_type: 'data_source', name: 'S', position: { x: 0, y: 0 }, config: {} }],
      };
      useBlueprintStore.setState({ currentBlueprint: bpWithNodes });
      (blueprintApi.autoLayout as ReturnType<typeof vi.fn>).mockResolvedValue({ status: 'success' });
      (blueprintApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...bpWithNodes,
        nodes: [{ ...bpWithNodes.nodes[0], position: { x: 250, y: 100 } }],
      });
      await useBlueprintStore.getState().autoLayout('TB');
      expect(blueprintApi.autoLayout).toHaveBeenCalledWith('bp-test1', 'TB');
    });
  });
});
