import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useSimulationStore } from './simulationStore';

vi.mock('../services/simulationApi', () => ({
  simulationApi: {
    listSandboxes: vi.fn(),
    createSandbox: vi.fn(),
    getSandboxStatus: vi.fn(),
    runSimulation: vi.fn(),
    destroySandbox: vi.fn(),
    exportResults: vi.fn(),
    runParallel: vi.fn(),
    runWhatIf: vi.fn(),
    listTimelines: vi.fn(),
    createTimeline: vi.fn(),
    controlClock: vi.fn(),
    listTemplates: vi.fn(),
    createTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
    generateEventSequence: vi.fn(),
    injectEvent: vi.fn(),
  },
}));

import { simulationApi } from '../services/simulationApi';

const mockSandbox = {
  sandbox_id: 'sb-1',
  status: 'ready',
  isolation_level: 'STANDARD',
  created_at: '2026-01-01T00:00:00',
};

const mockSandboxStatus = {
  sandbox_id: 'sb-1',
  status: 'ready',
  isolation_level: 'STANDARD',
  created_at: '2026-01-01T00:00:00',
  config: {},
};

const mockSimulationResult = {
  status: 'completed',
  sandbox_id: 'sb-1',
  recommendation: 'Proceed',
  confidence: 0.9,
};

const mockTimeline = {
  timeline_id: 'tl-1',
  clock_state: 'running',
  simulation_speed: 1,
  current_time: '2026-01-01T00:00:00',
  events_injected: 0,
};

const mockTemplate = {
  template_id: 'tpl-1',
  name: 'Test Template',
  description: 'A test template',
  category: 'general',
  event_types: ['event'],
  default_count: 1,
};

const mockEventSequence = {
  sequence_id: 'seq-1',
  template_id: 'tpl-1',
  workspace_id: 'ws-1',
  total_events: 3,
  events: [],
  entity_types_used: [],
};

describe('simulationStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSimulationStore.setState({
      activeTab: 'sandbox',
      sandboxes: [],
      selectedSandboxId: null,
      sandboxStatus: null,
      simulationResult: null,
      parallelResult: null,
      whatIfResult: null,
      timelines: [],
      selectedTimelineId: null,
      templates: [],
      eventSequence: null,
      loading: false,
      error: null,
    });
  });

  describe('initial state', () => {
    it('has correct default values', () => {
      const state = useSimulationStore.getState();
      expect(state.activeTab).toBe('sandbox');
      expect(state.sandboxes).toEqual([]);
      expect(state.selectedSandboxId).toBeNull();
      expect(state.sandboxStatus).toBeNull();
      expect(state.simulationResult).toBeNull();
      expect(state.parallelResult).toBeNull();
      expect(state.whatIfResult).toBeNull();
      expect(state.timelines).toEqual([]);
      expect(state.selectedTimelineId).toBeNull();
      expect(state.templates).toEqual([]);
      expect(state.eventSequence).toBeNull();
      expect(state.loading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('setActiveTab', () => {
    it('sets active tab', () => {
      useSimulationStore.getState().setActiveTab('timeline');
      expect(useSimulationStore.getState().activeTab).toBe('timeline');
    });
  });

  describe('fetchSandboxes', () => {
    it('fetches sandboxes successfully', async () => {
      (simulationApi.listSandboxes as ReturnType<typeof vi.fn>).mockResolvedValue({ sandboxes: [mockSandbox] });
      await useSimulationStore.getState().fetchSandboxes('ws-1');
      expect(simulationApi.listSandboxes).toHaveBeenCalledWith('ws-1');
      expect(useSimulationStore.getState().sandboxes).toHaveLength(1);
    });

    it('handles fetchSandboxes error', async () => {
      (simulationApi.listSandboxes as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Fetch failed'));
      await useSimulationStore.getState().fetchSandboxes();
      expect(useSimulationStore.getState().error).toBe('Fetch failed');
    });
  });

  describe('createSandbox', () => {
    it('creates sandbox and refreshes list', async () => {
      (simulationApi.createSandbox as ReturnType<typeof vi.fn>).mockResolvedValue(mockSandbox);
      (simulationApi.listSandboxes as ReturnType<typeof vi.fn>).mockResolvedValue({ sandboxes: [mockSandbox] });
      const result = await useSimulationStore.getState().createSandbox({ name: 'Test' });
      expect(result).toBe('sb-1');
      expect(useSimulationStore.getState().sandboxes).toHaveLength(1);
      expect(useSimulationStore.getState().loading).toBe(false);
    });

    it('returns null on create error', async () => {
      (simulationApi.createSandbox as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Create failed'));
      const result = await useSimulationStore.getState().createSandbox({});
      expect(result).toBeNull();
      expect(useSimulationStore.getState().error).toBe('Create failed');
    });
  });

  describe('selectSandbox', () => {
    it('selects sandbox and fetches status', async () => {
      (simulationApi.getSandboxStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockSandboxStatus);
      await useSimulationStore.getState().selectSandbox('sb-1');
      expect(useSimulationStore.getState().selectedSandboxId).toBe('sb-1');
      expect(useSimulationStore.getState().sandboxStatus).toEqual(mockSandboxStatus);
      expect(useSimulationStore.getState().loading).toBe(false);
    });

    it('handles selectSandbox error', async () => {
      (simulationApi.getSandboxStatus as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Status failed'));
      await useSimulationStore.getState().selectSandbox('sb-1');
      expect(useSimulationStore.getState().error).toBe('Status failed');
    });
  });

  describe('runSimulation', () => {
    it('runs simulation when sandbox is selected', async () => {
      useSimulationStore.setState({ selectedSandboxId: 'sb-1' });
      (simulationApi.runSimulation as ReturnType<typeof vi.fn>).mockResolvedValue(mockSimulationResult);
      (simulationApi.getSandboxStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockSandboxStatus);
      await useSimulationStore.getState().runSimulation({ scenario: 'test' });
      expect(simulationApi.runSimulation).toHaveBeenCalledWith('sb-1', { scenario: 'test' });
      expect(useSimulationStore.getState().simulationResult).toEqual(mockSimulationResult);
    });

    it('does nothing when no sandbox is selected', async () => {
      useSimulationStore.setState({ selectedSandboxId: null });
      await useSimulationStore.getState().runSimulation({});
      expect(simulationApi.runSimulation).not.toHaveBeenCalled();
    });

    it('handles runSimulation error', async () => {
      useSimulationStore.setState({ selectedSandboxId: 'sb-1' });
      (simulationApi.runSimulation as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Run failed'));
      await useSimulationStore.getState().runSimulation({});
      expect(useSimulationStore.getState().error).toBe('Run failed');
    });
  });

  describe('destroySandbox', () => {
    it('destroys sandbox and clears related state if selected', async () => {
      useSimulationStore.setState({
        selectedSandboxId: 'sb-1',
        sandboxStatus: mockSandboxStatus,
        simulationResult: mockSimulationResult,
      });
      (simulationApi.destroySandbox as ReturnType<typeof vi.fn>).mockResolvedValue({});
      (simulationApi.listSandboxes as ReturnType<typeof vi.fn>).mockResolvedValue({ sandboxes: [] });
      await useSimulationStore.getState().destroySandbox('sb-1');
      expect(useSimulationStore.getState().selectedSandboxId).toBeNull();
      expect(useSimulationStore.getState().sandboxStatus).toBeNull();
      expect(useSimulationStore.getState().simulationResult).toBeNull();
    });

    it('keeps state if destroyed sandbox is not the selected one', async () => {
      useSimulationStore.setState({
        selectedSandboxId: 'sb-2',
        sandboxStatus: mockSandboxStatus,
      });
      (simulationApi.destroySandbox as ReturnType<typeof vi.fn>).mockResolvedValue({});
      (simulationApi.listSandboxes as ReturnType<typeof vi.fn>).mockResolvedValue({ sandboxes: [] });
      await useSimulationStore.getState().destroySandbox('sb-1');
      expect(useSimulationStore.getState().selectedSandboxId).toBe('sb-2');
    });
  });

  describe('runParallel', () => {
    it('runs parallel simulation', async () => {
      const mockParallelResult = {
        run_id: 'pr-1',
        status: 'completed',
        total_scenarios: 2,
        results: [],
        best_scenario_id: null,
        comparison: {},
      };
      (simulationApi.runParallel as ReturnType<typeof vi.fn>).mockResolvedValue(mockParallelResult);
      await useSimulationStore.getState().runParallel([{ scenario: 'a' }, { scenario: 'b' }]);
      expect(useSimulationStore.getState().parallelResult).toEqual(mockParallelResult);
    });

    it('handles runParallel error', async () => {
      (simulationApi.runParallel as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Parallel failed'));
      await useSimulationStore.getState().runParallel([]);
      expect(useSimulationStore.getState().error).toBe('Parallel failed');
    });
  });

  describe('runWhatIf', () => {
    it('runs what-if analysis', async () => {
      const mockWhatIfResult = {
        run_id: 'wi-1',
        status: 'completed',
        total_variations: 2,
        results: [],
        sensitivity_analysis: {},
      };
      (simulationApi.runWhatIf as ReturnType<typeof vi.fn>).mockResolvedValue(mockWhatIfResult);
      await useSimulationStore.getState().runWhatIf({ base: true }, [{ param: 1 }]);
      expect(useSimulationStore.getState().whatIfResult).toEqual(mockWhatIfResult);
    });
  });

  describe('fetchTimelines', () => {
    it('fetches timelines', async () => {
      (simulationApi.listTimelines as ReturnType<typeof vi.fn>).mockResolvedValue({ timelines: [mockTimeline] });
      await useSimulationStore.getState().fetchTimelines();
      expect(useSimulationStore.getState().timelines).toHaveLength(1);
    });

    it('handles fetchTimelines error', async () => {
      (simulationApi.listTimelines as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Timeline failed'));
      await useSimulationStore.getState().fetchTimelines();
      expect(useSimulationStore.getState().error).toBe('Timeline failed');
    });
  });

  describe('createTimeline', () => {
    it('creates timeline and refreshes list', async () => {
      (simulationApi.createTimeline as ReturnType<typeof vi.fn>).mockResolvedValue(mockTimeline);
      (simulationApi.listTimelines as ReturnType<typeof vi.fn>).mockResolvedValue({ timelines: [mockTimeline] });
      const result = await useSimulationStore.getState().createTimeline({ name: 'Test' });
      expect(result).toBe('tl-1');
    });

    it('returns null on create error', async () => {
      (simulationApi.createTimeline as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Create timeline failed'));
      const result = await useSimulationStore.getState().createTimeline({});
      expect(result).toBeNull();
    });
  });

  describe('fetchTemplates', () => {
    it('fetches templates with category', async () => {
      (simulationApi.listTemplates as ReturnType<typeof vi.fn>).mockResolvedValue({ templates: [mockTemplate] });
      await useSimulationStore.getState().fetchTemplates('general');
      expect(simulationApi.listTemplates).toHaveBeenCalledWith('general');
      expect(useSimulationStore.getState().templates).toHaveLength(1);
    });
  });

  describe('generateEventSequence', () => {
    it('generates event sequence', async () => {
      (simulationApi.generateEventSequence as ReturnType<typeof vi.fn>).mockResolvedValue(mockEventSequence);
      await useSimulationStore.getState().generateEventSequence({ template_id: 'tpl-1' });
      expect(useSimulationStore.getState().eventSequence).toEqual(mockEventSequence);
    });

    it('handles generateEventSequence error', async () => {
      (simulationApi.generateEventSequence as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Generate failed'));
      await useSimulationStore.getState().generateEventSequence({});
      expect(useSimulationStore.getState().error).toBe('Generate failed');
    });
  });

  describe('clearError', () => {
    it('clears error state', () => {
      useSimulationStore.setState({ error: 'Some error' });
      useSimulationStore.getState().clearError();
      expect(useSimulationStore.getState().error).toBeNull();
    });
  });
});
