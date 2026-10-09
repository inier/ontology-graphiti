import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/semantic-admin/gaps`;

export interface GapItem {
  id: string;
  expression: string;
  scope_key: string;
  heat: number;
  status: 'open' | 'promoted' | 'adopted' | 'rejected';
  source_counts_json: Record<string, number>;
  sources_json: Array<{
    source: string; ref?: string; at: string; detail?: string;
    attribution?: { layer: string; target_kind?: string; target_ref?: string };
  }>;
  attribution_counts_json?: Record<string, number>;
  first_seen: string;
  last_seen: string;
  promoted_candidate_id?: string | null;
  resolved_term_id?: string | null;
  dismiss_reason?: string | null;
}

export interface GapStats {
  total: number;
  by_status: Record<string, number>;
  by_source: Record<string, number>;
  by_layer?: Record<string, number>;
  emit_failures: number;
  top_heat: GapItem[];
  adoption_rate: number | null;
}

// ── 缺口回归集与配对回放（ADR-088 子项目 B） ────────────────────────────

const REG_BASE = `${API_BASE}/api/semantic-admin/gap-regression`;

export interface RegressionSet {
  id: string;
  name: string;
  scope_key: string;
  cases_json: Array<{ query: string; expression: string; gap_id: string; source: string }>;
  case_count: number;
  model_id: string;
  created_at: string;
}

export interface ReplayReport {
  id: string;
  set_id: string;
  model_id: string;
  prompt_version: string;
  verdict: 'pass' | 'fail' | 'error';
  fixed_count: number;
  regressed_count: number;
  unchanged_count: number;
  rounds_json: Array<{ query: string; before_answered: boolean; after_answered: boolean }>;
  cost_json: Record<string, unknown>;
  error_detail?: string | null;
  model_mismatch?: boolean;
  warning?: string;
  created_at: string;
}

export const gapRegressionApi = {
  build: (body: { status?: string; workspace_id?: string; domain_id?: string;
                  min_heat?: number } = {}) =>
    fetchJson<{ set_id: string; case_count: number }>(`${REG_BASE}/sets/build`,
      { method: 'POST', body: JSON.stringify(body) }),
  replay: (setId: string) =>
    fetchJson<{ status: string; report: ReplayReport }>(
      `${REG_BASE}/sets/${setId}/replay`, { method: 'POST' }),
  listReports: (setId?: string) => {
    const qs = setId ? `?set_id=${encodeURIComponent(setId)}` : '';
    return fetchJson<{ items: ReplayReport[]; total: number }>(
      `${REG_BASE}/reports${qs}`);
  },
};

export const gapApi = {
  list: (params: { status?: string; source?: string; workspace_id?: string;
                   page?: number; page_size?: number } = {}) => {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)]),
    ).toString();
    return fetchJson<{ items: GapItem[]; total: number }>(`${BASE}/?${qs}`);
  },
  get: (id: string) => fetchJson<GapItem>(`${BASE}/${id}`),
  promote: (id: string, body: { domain_id?: string; workspace_id?: string } = {}) =>
    fetchJson<{ candidate_id: string }>(`${BASE}/${id}/promote`,
      { method: 'POST', body: JSON.stringify(body) }),
  dismiss: (id: string, reason: string) =>
    fetchJson<{ status: string }>(`${BASE}/${id}/dismiss`,
      { method: 'POST', body: JSON.stringify({ reason }) }),
  resolveCheck: (id: string) =>
    fetchJson<{ resolvable: boolean; via: string; detail: string }>(
      `${BASE}/${id}/resolve-check`),
  stats: () => fetchJson<GapStats>(`${BASE}/stats`),
};
