/**
 * Object View API 客户端 (Phase 11 Batch 3 — FR-036)
 *
 * 对应后端 /api/ontology/views 路由：
 *   POST   /                            创建视图
 *   GET    /                            列出视图 (query: base_type, role)
 *   GET    /{view_id}                   获取视图
 *   PUT    /{view_id}                   更新视图
 *   DELETE /{view_id}                   删除视图
 *   POST   /{view_id}/query             查询 (body: {user_id, ws_id, role})
 *   POST   /{view_id}/permissions       添加/更新权限
 *   GET    /{view_id}/permissions       列出权限
 *   DELETE /permissions/{perm_id}       删除权限
 */
import { fetchJson } from '../../shared/services/apiClient';
import { API_BASE } from '../../../config';

const BASE = `${API_BASE}/api/ontology/views`;

export interface ObjectView {
  id: string;
  name: string;
  description: string;
  base_type_id: string;
  role: string;
  projected_properties: string[];
  filters: Record<string, unknown>;
  row_limit: number;
  sort_order: Array<Record<string, string>>;
  enabled: boolean;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ViewPermission {
  id: string;
  view_id: string;
  role: string;
  can_export: boolean;
  can_share: boolean;
  redaction_rules: Record<string, unknown>;
  created_at: string;
}

export interface CreateViewPayload {
  name: string;
  base_type_id: string;
  role: string;
  description?: string;
  projected_properties?: string[];
  filters?: Record<string, unknown>;
  row_limit?: number;
  sort_order?: Array<Record<string, string>>;
  enabled?: boolean;
  created_by?: string;
}

export interface UpdateViewPayload {
  name?: string;
  description?: string;
  base_type_id?: string;
  role?: string;
  projected_properties?: string[];
  filters?: Record<string, unknown>;
  row_limit?: number;
  sort_order?: Array<Record<string, string>>;
  enabled?: boolean;
}

export interface AttachPermissionPayload {
  role: string;
  can_export?: boolean;
  can_share?: boolean;
  redaction_rules?: Record<string, unknown>;
}

export interface QueryViewContext {
  user_id?: string;
  ws_id?: string;
  role?: string;
}

export interface QueryViewResult {
  rows: Array<Record<string, unknown>>;
  total_count: number;
  truncated: boolean;
}

export const viewApi = {
  list: (params?: { base_type?: string; role?: string }) => {
    const qs = new URLSearchParams();
    if (params?.base_type) qs.set('base_type', params.base_type);
    if (params?.role) qs.set('role', params.role);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return fetchJson<{ views: ObjectView[]; count: number }>(`${BASE}${suffix}`);
  },

  get: (viewId: string) =>
    fetchJson<ObjectView>(`${BASE}/${encodeURIComponent(viewId)}`),

  create: (payload: CreateViewPayload) =>
    fetchJson<ObjectView>(BASE, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  update: (viewId: string, payload: UpdateViewPayload) =>
    fetchJson<ObjectView>(`${BASE}/${encodeURIComponent(viewId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  remove: (viewId: string) =>
    fetchJson<{ view_id: string; deleted: boolean }>(
      `${BASE}/${encodeURIComponent(viewId)}`,
      { method: 'DELETE' },
    ),

  query: (viewId: string, context: QueryViewContext) =>
    fetchJson<QueryViewResult>(`${BASE}/${encodeURIComponent(viewId)}/query`, {
      method: 'POST',
      body: JSON.stringify(context),
    }),

  listPermissions: (viewId: string) =>
    fetchJson<{ permissions: ViewPermission[]; count: number }>(
      `${BASE}/${encodeURIComponent(viewId)}/permissions`,
    ),

  attachPermission: (viewId: string, payload: AttachPermissionPayload) =>
    fetchJson<ViewPermission>(
      `${BASE}/${encodeURIComponent(viewId)}/permissions`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),

  detachPermission: (permId: string) =>
    fetchJson<{ perm_id: string; deleted: boolean }>(
      `${BASE}/permissions/${encodeURIComponent(permId)}`,
      { method: 'DELETE' },
    ),
};
