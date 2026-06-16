import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useWorkspaceStore } from './workspaceStore';

vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: vi.fn(),
}));

import { fetchJson } from '@/modules/shared/services/apiClient';

const mockWorkspace = {
  workspace_id: 'ws-1',
  name: 'Test Workspace',
  description: 'A test workspace',
  isolation_level: 'STANDARD' as const,
  type: 'default',
  status: 'active',
  owner: 'admin',
  member_count: 1,
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
};

const mockScenario = {
  scenario_id: 'sc-1',
  name: 'Test Scenario',
  description: 'A test scenario',
  workspace_id: 'ws-1',
  status: 'active',
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-01T00:00:00',
};

describe('workspaceStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useWorkspaceStore.setState({
      workspaces: [],
      currentWorkspace: null,
      scenarios: [],
      loading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('has correct default values', () => {
      const state = useWorkspaceStore.getState();
      expect(state.workspaces).toEqual([]);
      expect(state.currentWorkspace).toBeNull();
      expect(state.scenarios).toEqual([]);
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('loadWorkspaces', () => {
    it('loads workspaces successfully', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue({ workspaces: [mockWorkspace] });
      await useWorkspaceStore.getState().loadWorkspaces();
      expect(useWorkspaceStore.getState().workspaces).toHaveLength(1);
      expect(useWorkspaceStore.getState().workspaces[0].workspace_id).toBe('ws-1');
      expect(useWorkspaceStore.getState().loading).toBe(false);
    });

    it('handles missing workspaces array gracefully', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue({});
      await useWorkspaceStore.getState().loadWorkspaces();
      expect(useWorkspaceStore.getState().workspaces).toEqual([]);
    });

    it('handles loadWorkspaces error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Load failed'));
      await useWorkspaceStore.getState().loadWorkspaces();
      expect(useWorkspaceStore.getState().error).toBe('Load failed');
      expect(useWorkspaceStore.getState().loading).toBe(false);
    });
  });

  describe('createWorkspace', () => {
    it('creates a workspace and adds to list', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(mockWorkspace);
      await useWorkspaceStore.getState().createWorkspace({ name: 'Test Workspace' });
      expect(useWorkspaceStore.getState().workspaces).toHaveLength(1);
      expect(useWorkspaceStore.getState().workspaces[0].name).toBe('Test Workspace');
      expect(useWorkspaceStore.getState().loading).toBe(false);
    });

    it('handles createWorkspace error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Create failed'));
      await useWorkspaceStore.getState().createWorkspace({ name: 'Bad' });
      expect(useWorkspaceStore.getState().error).toBe('Create failed');
      expect(useWorkspaceStore.getState().loading).toBe(false);
    });
  });

  describe('updateWorkspace', () => {
    it('updates workspace in list and currentWorkspace', async () => {
      useWorkspaceStore.setState({
        workspaces: [mockWorkspace],
        currentWorkspace: mockWorkspace,
      });
      const updated = { ...mockWorkspace, name: 'Updated' };
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(updated);
      await useWorkspaceStore.getState().updateWorkspace('ws-1', { name: 'Updated' });
      expect(useWorkspaceStore.getState().workspaces[0].name).toBe('Updated');
      expect(useWorkspaceStore.getState().currentWorkspace?.name).toBe('Updated');
    });

    it('does not update currentWorkspace if different workspace', async () => {
      useWorkspaceStore.setState({
        workspaces: [mockWorkspace],
        currentWorkspace: { ...mockWorkspace, workspace_id: 'ws-2' },
      });
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue({ ...mockWorkspace, name: 'Updated' });
      await useWorkspaceStore.getState().updateWorkspace('ws-1', { name: 'Updated' });
      expect(useWorkspaceStore.getState().currentWorkspace?.name).toBe('Test Workspace');
    });

    it('handles updateWorkspace error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Update failed'));
      await useWorkspaceStore.getState().updateWorkspace('ws-1', { name: 'Bad' });
      expect(useWorkspaceStore.getState().error).toBe('Update failed');
    });
  });

  describe('deleteWorkspace', () => {
    it('deletes workspace from list', async () => {
      useWorkspaceStore.setState({ workspaces: [mockWorkspace] });
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
      await useWorkspaceStore.getState().deleteWorkspace('ws-1');
      expect(useWorkspaceStore.getState().workspaces).toHaveLength(0);
    });

    it('clears currentWorkspace if it is the deleted one', async () => {
      useWorkspaceStore.setState({
        workspaces: [mockWorkspace],
        currentWorkspace: mockWorkspace,
      });
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
      await useWorkspaceStore.getState().deleteWorkspace('ws-1');
      expect(useWorkspaceStore.getState().currentWorkspace).toBeNull();
    });

    it('keeps currentWorkspace if different from deleted', async () => {
      const otherWs = { ...mockWorkspace, workspace_id: 'ws-2' };
      useWorkspaceStore.setState({
        workspaces: [mockWorkspace, otherWs],
        currentWorkspace: otherWs,
      });
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
      await useWorkspaceStore.getState().deleteWorkspace('ws-1');
      expect(useWorkspaceStore.getState().currentWorkspace?.workspace_id).toBe('ws-2');
    });

    it('handles deleteWorkspace error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Delete failed'));
      await useWorkspaceStore.getState().deleteWorkspace('ws-1');
      expect(useWorkspaceStore.getState().error).toBe('Delete failed');
    });
  });

  describe('setCurrentWorkspace', () => {
    it('sets current workspace', () => {
      useWorkspaceStore.getState().setCurrentWorkspace(mockWorkspace);
      expect(useWorkspaceStore.getState().currentWorkspace).toEqual(mockWorkspace);
    });

    it('clears current workspace with null', () => {
      useWorkspaceStore.setState({ currentWorkspace: mockWorkspace });
      useWorkspaceStore.getState().setCurrentWorkspace(null);
      expect(useWorkspaceStore.getState().currentWorkspace).toBeNull();
    });
  });

  describe('exportWorkspace', () => {
    it('exports workspace data', async () => {
      const exportData = { workspace_id: 'ws-1', data: {} };
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(exportData);
      const result = await useWorkspaceStore.getState().exportWorkspace('ws-1');
      expect(result).toEqual(exportData);
    });

    it('returns null on export error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Export failed'));
      const result = await useWorkspaceStore.getState().exportWorkspace('ws-1');
      expect(result).toBeNull();
      expect(useWorkspaceStore.getState().error).toBe('Export failed');
    });
  });

  describe('importWorkspace', () => {
    it('imports workspace and adds to list', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(mockWorkspace);
      await useWorkspaceStore.getState().importWorkspace({ name: 'Imported' });
      expect(useWorkspaceStore.getState().workspaces).toHaveLength(1);
      expect(useWorkspaceStore.getState().loading).toBe(false);
    });

    it('handles importWorkspace error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Import failed'));
      await useWorkspaceStore.getState().importWorkspace({});
      expect(useWorkspaceStore.getState().error).toBe('Import failed');
    });
  });

  describe('loadScenarios', () => {
    it('loads scenarios for a workspace', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue({ scenarios: [mockScenario] });
      await useWorkspaceStore.getState().loadScenarios('ws-1');
      expect(useWorkspaceStore.getState().scenarios).toHaveLength(1);
      expect(useWorkspaceStore.getState().scenarios[0].scenario_id).toBe('sc-1');
    });

    it('handles loadScenarios error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Scenarios failed'));
      await useWorkspaceStore.getState().loadScenarios('ws-1');
      expect(useWorkspaceStore.getState().error).toBe('Scenarios failed');
    });
  });

  describe('createScenario', () => {
    it('creates a scenario and adds to list', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(mockScenario);
      await useWorkspaceStore.getState().createScenario('ws-1', { name: 'Test Scenario' });
      expect(useWorkspaceStore.getState().scenarios).toHaveLength(1);
    });

    it('handles createScenario error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Create scenario failed'));
      await useWorkspaceStore.getState().createScenario('ws-1', { name: 'Bad' });
      expect(useWorkspaceStore.getState().error).toBe('Create scenario failed');
    });
  });

  describe('activateScenario', () => {
    it('activates a scenario', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
      await useWorkspaceStore.getState().activateScenario('ws-1', 'sc-1');
      expect(fetchJson).toHaveBeenCalled();
    });

    it('handles activateScenario error', async () => {
      (fetchJson as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Activate failed'));
      await useWorkspaceStore.getState().activateScenario('ws-1', 'sc-1');
      expect(useWorkspaceStore.getState().error).toBe('Activate failed');
    });
  });

  describe('clearError', () => {
    it('clears error state', () => {
      useWorkspaceStore.setState({ error: 'Some error' });
      useWorkspaceStore.getState().clearError();
      expect(useWorkspaceStore.getState().error).toBeNull();
    });
  });
});
