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
  sources_json: Array<{ source: string; ref?: string; at: string; detail?: string }>;
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
  emit_failures: number;
  top_heat: GapItem[];
  adoption_rate: number | null;
}

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
