import { apiClient } from '../../shared/services/apiClient';

export interface TemporalAskRequest {
  question: string;
  valid_time?: string;
  workspace_id?: string;
  scenario_id?: string;
}

export interface TemporalAskResponse {
  status: string;
  question: string;
  answer: string;
  valid_time?: string;
  time_type?: string;
  entity_count: number;
}

export interface ChartRequest {
  chart_type: string;
  data: Record<string, unknown>;
  title?: string;
  render_mode?: string;
  options?: Record<string, unknown>;
}

export interface ChartResponse {
  status: string;
  chart_type: string;
  render_mode: string;
  title: string;
  spec: Record<string, unknown>;
}

export async function askTemporalQuestion(request: TemporalAskRequest): Promise<TemporalAskResponse> {
  return apiClient.post('/api/qa/ask/temporal', request);
}

export async function renderChart(request: ChartRequest): Promise<ChartResponse> {
  return apiClient.post('/api/qa/chart', request);
}
