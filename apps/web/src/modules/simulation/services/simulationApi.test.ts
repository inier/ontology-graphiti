import { describe, it, expect, vi, beforeEach } from 'vitest';
import { simulationApi } from './simulationApi';
import type {
  SandboxInfo,
  SandboxStatus,
  SimulationResult,
  ParallelResult,
  WhatIfResult,
  EventSequence,
  TimelineInfo,
  TemplateInfo,
} from './simulationApi';

const API_BASE = 'http://localhost:8000';

function mockFetchResponse<T>(data: T, status = 200) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response);
}

function mockFetchError(status: number, statusText: string) {
  (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve({ detail: statusText }),
  } as Response);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.setItem('token', 'test-jwt-token');
});

// ─── Sandbox CRUD ──────────────────────────────────────────────

describe('simulationApi - Sandbox CRUD', () => {
  const mockSandboxInfo: SandboxInfo = {
    sandbox_id: 'sb-1',
    status: 'created',
    isolation_level: 'strict',
    created_at: '2026-01-01',
    workspace_id: 'ws-1',
  };

  it('createSandbox sends POST with config', async () => {
    const config = { workspace_id: 'ws-1', isolation_level: 'strict' };
    mockFetchResponse(mockSandboxInfo);

    const result = await simulationApi.createSandbox(config);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(config),
      }),
    );
    expect(result.sandbox_id).toBe('sb-1');
  });

  it('createSandbox sends empty config by default', async () => {
    mockFetchResponse(mockSandboxInfo);

    await simulationApi.createSandbox();
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({}),
      }),
    );
  });

  it('runSimulation sends POST with params', async () => {
    const mockResult: SimulationResult = {
      status: 'completed',
      sandbox_id: 'sb-1',
      confidence: 0.85,
      elapsed_seconds: 12,
    };
    mockFetchResponse(mockResult);

    const result = await simulationApi.runSimulation('sb-1', { scenario: 'test' });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1/run`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ scenario: 'test' }),
      }),
    );
    expect(result.status).toBe('completed');
    expect(result.confidence).toBe(0.85);
  });

  it('runSimulation sends empty params by default', async () => {
    mockFetchResponse({ status: 'completed', sandbox_id: 'sb-1' });

    await simulationApi.runSimulation('sb-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1/run`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({}),
      }),
    );
  });

  it('getSandboxStatus calls GET endpoint', async () => {
    const mockStatus: SandboxStatus = {
      sandbox_id: 'sb-1',
      status: 'running',
      isolation_level: 'strict',
      created_at: '2026-01-01',
      config: {},
    };
    mockFetchResponse(mockStatus);

    const result = await simulationApi.getSandboxStatus('sb-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1/status`,
      expect.any(Object),
    );
    expect(result.status).toBe('running');
  });

  it('getSandboxResults calls GET endpoint', async () => {
    const mockResult: SimulationResult = {
      status: 'completed',
      sandbox_id: 'sb-1',
      recommendation: 'Approve',
    };
    mockFetchResponse(mockResult);

    const result = await simulationApi.getSandboxResults('sb-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1/results`,
      expect.any(Object),
    );
    expect(result.recommendation).toBe('Approve');
  });

  it('destroySandbox sends DELETE request', async () => {
    mockFetchResponse({ status: 'destroyed' });

    await simulationApi.destroySandbox('sb-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it('exportResults sends POST with approved_by', async () => {
    mockFetchResponse({ exported: true });

    await simulationApi.exportResults('sb-1', 'admin');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1/export`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ approved_by: 'admin' }),
      }),
    );
  });

  it('exportResults defaults approved_by to empty string', async () => {
    mockFetchResponse({ exported: true });

    await simulationApi.exportResults('sb-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/sandbox/sb-1/export`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ approved_by: '' }),
      }),
    );
  });

  it('listSandboxes calls GET without params', async () => {
    mockFetchResponse({ sandboxes: [mockSandboxInfo] });

    const result = await simulationApi.listSandboxes();
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toBe(`${API_BASE}/api/simulation/sandbox`);
    expect(result.sandboxes).toHaveLength(1);
  });

  it('listSandboxes passes workspace_id as query param', async () => {
    mockFetchResponse({ sandboxes: [] });

    await simulationApi.listSandboxes('ws-1');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('workspace_id=ws-1');
  });
});

// ─── Parallel & What-If ───────────────────────────────────────

describe('simulationApi - Parallel & What-If', () => {
  it('runParallel sends POST with scenarios', async () => {
    const mockResult: ParallelResult = {
      run_id: 'run-1',
      status: 'completed',
      total_scenarios: 2,
      results: [],
      best_scenario_id: 'sc-1',
      comparison: {},
    };
    mockFetchResponse(mockResult);

    const scenarios = [{ name: 'A' }, { name: 'B' }];
    const result = await simulationApi.runParallel(scenarios);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/parallel`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ scenarios }),
      }),
    );
    expect(result.total_scenarios).toBe(2);
    expect(result.best_scenario_id).toBe('sc-1');
  });

  it('runWhatIf sends POST with base_scenario and param_variations', async () => {
    const mockResult: WhatIfResult = {
      run_id: 'run-2',
      status: 'completed',
      total_variations: 3,
      results: [],
      sensitivity_analysis: {},
    };
    mockFetchResponse(mockResult);

    const base = { param1: 10 };
    const variations = [{ param1: 20 }, { param1: 30 }, { param1: 40 }];
    const result = await simulationApi.runWhatIf(base, variations);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/simulation/what-if`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ base_scenario: base, param_variations: variations }),
      }),
    );
    expect(result.total_variations).toBe(3);
  });

  it('getComparison calls GET with ids joined by comma', async () => {
    mockFetchResponse({ comparisons: [] });

    await simulationApi.getComparison(['sb-1', 'sb-2', 'sb-3']);
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('/api/simulation/comparison?ids=sb-1,sb-2,sb-3');
  });
});

// ─── Event Simulator ───────────────────────────────────────────

describe('simulationApi - Event Simulator', () => {
  it('generateEventSequence sends POST with params', async () => {
    const mockSeq: EventSequence = {
      sequence_id: 'seq-1',
      template_id: 'tpl-1',
      workspace_id: 'ws-1',
      total_events: 5,
      events: [],
      entity_types_used: [],
    };
    mockFetchResponse(mockSeq);

    const result = await simulationApi.generateEventSequence({ count: 5 });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/generate`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ count: 5 }),
      }),
    );
    expect(result.sequence_id).toBe('seq-1');
  });

  it('generateEventSequence sends empty params by default', async () => {
    mockFetchResponse({ sequence_id: 'seq-1', template_id: '', workspace_id: '', total_events: 0, events: [], entity_types_used: [] });

    await simulationApi.generateEventSequence();
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/generate`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({}),
      }),
    );
  });

  it('injectEvent sends POST with params', async () => {
    mockFetchResponse({ injected: true });

    await simulationApi.injectEvent({ event_type: 'alert' });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/inject`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ event_type: 'alert' }),
      }),
    );
  });

  it('createTimeline sends POST with params', async () => {
    const mockTimeline: TimelineInfo = {
      timeline_id: 'tl-1',
      clock_state: 'running',
      simulation_speed: 1,
      current_time: '2026-01-01T00:00:00Z',
      events_injected: 0,
    };
    mockFetchResponse(mockTimeline);

    const result = await simulationApi.createTimeline({ speed: 10 });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/timeline`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ speed: 10 }),
      }),
    );
    expect(result.timeline_id).toBe('tl-1');
  });

  it('getTimeline calls GET endpoint', async () => {
    mockFetchResponse({ timeline_id: 'tl-1', clock_state: 'paused', simulation_speed: 1, current_time: '', events_injected: 0 });

    await simulationApi.getTimeline('tl-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/timeline/tl-1`,
      expect.any(Object),
    );
  });

  it('controlClock sends POST with params', async () => {
    mockFetchResponse({ status: 'paused' });

    await simulationApi.controlClock({ action: 'pause' });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/clock/control`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ action: 'pause' }),
      }),
    );
  });
});

// ─── Templates ─────────────────────────────────────────────────

describe('simulationApi - Templates', () => {
  const mockTemplate: TemplateInfo = {
    template_id: 'tpl-1',
    name: 'Alert Template',
    description: 'desc',
    category: 'alert',
    event_types: ['alert'],
    default_count: 5,
  };

  it('listTemplates calls GET without category', async () => {
    mockFetchResponse({ templates: [mockTemplate] });

    const result = await simulationApi.listTemplates();
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toBe(`${API_BASE}/api/event-simulator/templates`);
    expect(result.templates).toHaveLength(1);
  });

  it('listTemplates passes category as query param', async () => {
    mockFetchResponse({ templates: [] });

    await simulationApi.listTemplates('alert');
    const calledUrl = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(calledUrl).toContain('category=alert');
  });

  it('getTemplate calls GET endpoint', async () => {
    mockFetchResponse(mockTemplate);

    const result = await simulationApi.getTemplate('tpl-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/templates/tpl-1`,
      expect.any(Object),
    );
    expect(result.template_id).toBe('tpl-1');
  });

  it('createTemplate sends POST with data', async () => {
    mockFetchResponse(mockTemplate);

    const result = await simulationApi.createTemplate({ name: 'New Template' });
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/templates`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'New Template' }),
      }),
    );
    expect(result.name).toBe('Alert Template');
  });

  it('deleteTemplate sends DELETE request', async () => {
    mockFetchResponse({ status: 'deleted' });

    await simulationApi.deleteTemplate('tpl-1');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/templates/tpl-1`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });
});

// ─── Timelines ─────────────────────────────────────────────────

describe('simulationApi - Timelines', () => {
  it('listTimelines calls GET endpoint', async () => {
    mockFetchResponse({ timelines: [] });

    const result = await simulationApi.listTimelines();
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/timelines`,
      expect.any(Object),
    );
    expect(result.timelines).toHaveLength(0);
  });

  it('injectTimelineEvent sends POST with event and target_time', async () => {
    mockFetchResponse({ injected: true });

    const event = { type: 'alert', severity: 'high' };
    await simulationApi.injectTimelineEvent('tl-1', event, '2026-01-01T12:00:00Z');
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/timeline/tl-1/events`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ event, target_time: '2026-01-01T12:00:00Z' }),
      }),
    );
  });

  it('injectTimelineEvent works without target_time', async () => {
    mockFetchResponse({ injected: true });

    const event = { type: 'alert' };
    await simulationApi.injectTimelineEvent('tl-1', event);
    expect(fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/event-simulator/timeline/tl-1/events`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ event, target_time: undefined }),
      }),
    );
  });
});

// ─── Error Handling ────────────────────────────────────────────

describe('simulationApi - Error Handling', () => {
  it('throws on HTTP error response', async () => {
    mockFetchError(500, 'Internal Server Error');

    await expect(simulationApi.getSandboxStatus('sb-1')).rejects.toThrow('HTTP 500');
  });

  it('throws on 404 error', async () => {
    mockFetchError(404, 'Not Found');

    await expect(simulationApi.getSandboxStatus('nonexistent')).rejects.toThrow('HTTP 404');
  });

  it('throws on network error', async () => {
    (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new TypeError('Failed to fetch'));

    await expect(simulationApi.getSandboxStatus('sb-1')).rejects.toThrow('Failed to fetch');
  });
});

// ─── Auth Headers ──────────────────────────────────────────────

describe('simulationApi - Auth Headers', () => {
  it('includes Authorization header when token exists', async () => {
    mockFetchResponse({ sandboxes: [] });

    await simulationApi.listSandboxes();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-jwt-token');
  });

  it('includes Content-Type application/json header', async () => {
    mockFetchResponse({ sandboxes: [] });

    await simulationApi.listSandboxes();
    const callOptions = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][1] as Record<string, unknown>;
    const headers = callOptions.headers as Record<string, string>;
    expect(headers['Content-Type']).toBe('application/json');
  });
});
