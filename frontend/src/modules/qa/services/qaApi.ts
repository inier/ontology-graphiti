import { API_BASE } from '../../../config';

const QA_BASE = `${API_BASE}/api/qa`;

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
  const response = await fetch(`${QA_BASE}/ask/temporal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`时序问答请求失败: ${response.status}`);
  }
  return response.json();
}

export async function renderChart(request: ChartRequest): Promise<ChartResponse> {
  const response = await fetch(`${QA_BASE}/chart`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(`图表渲染请求失败: ${response.status}`);
  }
  return response.json();
}
