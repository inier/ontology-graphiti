import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type {
  ServiceConfig,
  ServiceCategory,
  ConfigValidationResult,
  UpdateConfigRequest,
  UpdateConfigResponse,
  ConfigRevision,
} from '../types';

const BASE = `${API_BASE}/api/config`;

export const configApi = {
  getConfigs: (): Promise<{ categories: ServiceConfig[] }> =>
    fetchJson<{ categories: ServiceConfig[] }>(`${BASE}`),

  getConfigsByCategory: (category: ServiceCategory): Promise<ServiceConfig> =>
    fetchJson<ServiceConfig>(`${BASE}/${category}`),

  updateConfigs: (data: UpdateConfigRequest): Promise<UpdateConfigResponse> =>
    fetchJson<UpdateConfigResponse>(`${BASE}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  testConnection: (
    data: UpdateConfigRequest,
  ): Promise<{ validation_results: ConfigValidationResult[] }> =>
    fetchJson<{ validation_results: ConfigValidationResult[] }>(`${BASE}/test`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getConfigHistory: (params?: {
    page?: number;
    page_size?: number;
  }): Promise<{ revisions: ConfigRevision[]; total: number }> => {
    const query = new URLSearchParams();
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    const qs = query.toString();
    return fetchJson<{ revisions: ConfigRevision[]; total: number }>(
      `${BASE}/history${qs ? `?${qs}` : ''}`,
    );
  },

  rollbackConfig: (
    revisionNumber: number,
  ): Promise<UpdateConfigResponse> =>
    fetchJson<UpdateConfigResponse>(`${BASE}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ revision_number: revisionNumber }),
    }),

  exportConfigs: (): Promise<{ items: Array<{ key: string; value: string }> }> =>
    fetchJson<{ items: Array<{ key: string; value: string }> }>(`${BASE}/export`),

  importConfigs: (
    items: Array<{ key: string; value: string }>,
  ): Promise<UpdateConfigResponse> =>
    fetchJson<UpdateConfigResponse>(`${BASE}/import`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  getConfigStatus: (): Promise<
    Array<{ category: ServiceCategory; status: string; last_tested_at?: string }>
  > =>
    fetchJson<
      Array<{ category: ServiceCategory; status: string; last_tested_at?: string }>
    >(`${BASE}/status`),
};
