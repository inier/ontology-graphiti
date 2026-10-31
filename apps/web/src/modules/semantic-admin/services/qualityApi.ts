import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type { QualityReport } from '../types';

const URL_PREFIX = `${API_BASE}/api/semantic-admin`;

function buildQuery(params: Record<string, unknown>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : '';
}

export async function getQualityReport(
  candidateId: string,
  force: boolean = false,
): Promise<QualityReport> {
  try {
    return await fetchJson<QualityReport>(
      `${URL_PREFIX}/quality-gate/reports/${encodeURIComponent(candidateId)}${buildQuery({ force })}`,
    );
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to get quality report: ${msg}`);
  }
}

export async function batchEvaluateReports(
  candidate_ids: string[],
  sync: boolean = true,
  actor_id: string = '',
): Promise<unknown> {
  try {
    return await fetchJson<unknown>(`${URL_PREFIX}/quality-gate/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidate_ids, sync, actor_id }),
    });
  } catch (e) {
    const errMessage = e instanceof Error ? e.message : String(e);
    const msg = e instanceof Error ? errMessage : String(e);
    throw new Error(`Failed to batch evaluate reports: ${msg}`);
  }
}
