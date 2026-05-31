import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

export interface SandboxInfo {
  sandbox_id: string;
  status: string;
  isolation_level?: string;
  created_at?: string;
  workspace_id?: string;
}

export interface SandboxStatus {
  sandbox_id: string;
  status: string;
  isolation_level: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  config: Record<string, unknown>;
}

export interface SimulationResult {
  status: string;
  sandbox_id: string;
  scenario_id?: string;
  baseline_metrics?: Record<string, unknown>;
  projected_metrics?: Record<string, unknown>[];
  metric_changes?: Array<{
    metric_name: string;
    before: unknown;
    after: unknown;
    delta: number | null;
  }>;
  risk_assessment?: Record<string, unknown>;
  recommendation?: string;
  confidence?: number;
  elapsed_seconds?: number;
  message?: string;
}

export interface ParallelResult {
  run_id: string;
  status: string;
  total_scenarios: number;
  results: Array<Record<string, unknown>>;
  best_scenario_id: string | null;
  comparison: Record<string, unknown>;
}

export interface WhatIfResult {
  run_id: string;
  status: string;
  total_variations: number;
  results: Array<Record<string, unknown>>;
  sensitivity_analysis: Record<string, unknown>;
}

export interface EventSequence {
  sequence_id: string;
  template_id: string;
  workspace_id: string;
  total_events: number;
  events: Array<Record<string, unknown>>;
  entity_types_used: string[];
}

export interface TimelineInfo {
  timeline_id: string;
  clock_state: string;
  simulation_speed: number;
  current_time: string;
  events_injected: number;
  queued_events?: number;
  events?: Array<Record<string, unknown>>;
}

export interface TemplateInfo {
  template_id: string;
  name: string;
  description: string;
  category: string;
  event_types: string[];
  default_count: number;
}

export const simulationApi = {
  createSandbox: (config: Record<string, unknown> = {}): Promise<SandboxInfo> =>
    fetchJson<SandboxInfo>(`${API_BASE}/api/simulation/sandbox`, {
      method: 'POST',
      body: JSON.stringify(config),
    }),

  runSimulation: (sandboxId: string, params: Record<string, unknown> = {}): Promise<SimulationResult> =>
    fetchJson<SimulationResult>(`${API_BASE}/api/simulation/sandbox/${sandboxId}/run`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  getSandboxStatus: (sandboxId: string): Promise<SandboxStatus> =>
    fetchJson<SandboxStatus>(`${API_BASE}/api/simulation/sandbox/${sandboxId}/status`),

  getSandboxResults: (sandboxId: string): Promise<SimulationResult> =>
    fetchJson<SimulationResult>(`${API_BASE}/api/simulation/sandbox/${sandboxId}/results`),

  destroySandbox: (sandboxId: string): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/simulation/sandbox/${sandboxId}`, { method: 'DELETE' }),

  exportResults: (sandboxId: string, approvedBy: string = ''): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/simulation/sandbox/${sandboxId}/export`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    }),

  listSandboxes: (workspaceId?: string): Promise<{ sandboxes: SandboxInfo[] }> =>
    fetchJson(`${API_BASE}/api/simulation/sandbox${workspaceId ? `?workspace_id=${workspaceId}` : ''}`),

  runParallel: (scenarios: Array<Record<string, unknown>>): Promise<ParallelResult> =>
    fetchJson<ParallelResult>(`${API_BASE}/api/simulation/parallel`, {
      method: 'POST',
      body: JSON.stringify({ scenarios }),
    }),

  runWhatIf: (
    baseScenario: Record<string, unknown>,
    paramVariations: Array<Record<string, unknown>>,
  ): Promise<WhatIfResult> =>
    fetchJson<WhatIfResult>(`${API_BASE}/api/simulation/what-if`, {
      method: 'POST',
      body: JSON.stringify({ base_scenario: baseScenario, param_variations: paramVariations }),
    }),

  getComparison: (ids: string[]): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/simulation/comparison?ids=${ids.join(',')}`),

  generateEventSequence: (params: Record<string, unknown> = {}): Promise<EventSequence> =>
    fetchJson<EventSequence>(`${API_BASE}/api/event-simulator/generate`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  injectEvent: (params: Record<string, unknown> = {}): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/event-simulator/inject`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  createTimeline: (params: Record<string, unknown> = {}): Promise<TimelineInfo> =>
    fetchJson<TimelineInfo>(`${API_BASE}/api/event-simulator/timeline`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  getTimeline: (timelineId: string): Promise<TimelineInfo> =>
    fetchJson<TimelineInfo>(`${API_BASE}/api/event-simulator/timeline/${timelineId}`),

  controlClock: (params: Record<string, unknown>): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/event-simulator/clock/control`, {
      method: 'POST',
      body: JSON.stringify(params),
    }),

  listTemplates: (category?: string): Promise<{ templates: TemplateInfo[] }> =>
    fetchJson(`${API_BASE}/api/event-simulator/templates${category ? `?category=${category}` : ''}`),

  getTemplate: (templateId: string): Promise<TemplateInfo> =>
    fetchJson<TemplateInfo>(`${API_BASE}/api/event-simulator/templates/${templateId}`),

  createTemplate: (data: Record<string, unknown>): Promise<TemplateInfo> =>
    fetchJson<TemplateInfo>(`${API_BASE}/api/event-simulator/templates`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  deleteTemplate: (templateId: string): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/event-simulator/templates/${templateId}`, { method: 'DELETE' }),

  listTimelines: (): Promise<{ timelines: TimelineInfo[] }> =>
    fetchJson(`${API_BASE}/api/event-simulator/timelines`),

  injectTimelineEvent: (timelineId: string, event: Record<string, unknown>, targetTime?: string): Promise<Record<string, unknown>> =>
    fetchJson(`${API_BASE}/api/event-simulator/timeline/${timelineId}/events`, {
      method: 'POST',
      body: JSON.stringify({ event, target_time: targetTime }),
    }),
};
