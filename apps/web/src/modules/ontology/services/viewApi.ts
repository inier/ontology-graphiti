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
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

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
  /**
   * 后端 `CreateViewRequest.filters` 在**请求边界**做归一（见 view/api/schemas.py
   * `normalize_view_filters`）：接受 `{field: {op: value}}` 或规则数组
   * `[{field, op, value}]`，两者都归一成字典。设计器提交的是数组，故此处放宽类型。
   */
  filters?: Record<string, unknown> | FilterRule[];
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
  /** 视图设计器直接提交字段列表，服务层会折算成 projected_properties */
  fields?: Array<{ field: string; label?: string; visible?: boolean }>;
  filters?: FilterRule[];
  row_limit?: number;
  /** 视图设计器使用的行数上限别名（落到 row_limit） */
  limit?: number;
  sort_order?: Array<Record<string, string>>;
  sorts?: SortRule[];
  enabled?: boolean;
}

/**
 * `update` 直接透传原始视图报文（filters 用 `{field: {op: value}}` 结构），
 * 与视图设计器使用的 `UpdateViewPayload`（filters 为规则数组）区分开。
 */
export interface RawViewPatch {
  name?: string;
  description?: string;
  base_type_id?: string;
  role?: string;
  projected_properties?: string[];
  filters?: Record<string, Record<string, unknown>>;
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

export interface ObjectViewField {
  field: string;
  label?: string;
  visible: boolean;
}

export interface FilterRule { field: string; op: '=' | '!=' | '>' | '<' | 'contains'; value: string; }
export interface SortRule { field: string; direction: 'asc' | 'desc'; }

/**
 * `filters` is re-declared as a structured rule list (the UI edits it field-by-field),
 * so the flat `Record<string, unknown>` from `ObjectView` has to be omitted first.
 */
export interface ExtendedObjectView extends Omit<ObjectView, 'filters'> {
  fields: ObjectViewField[];
  /**
   * 对象类型的**显示名**。后端 `ViewResponse` 只返回 `base_type_id`，没有名称字段，
   * 故此处不填；名称需由调用方用 object-types 解析。切勿把 id 塞进这个字段——
   * 那会让界面把 `ot_xxx` 当类型名展示，且搜索/分组会按 id 命中。
   */
  object_type_name?: string;
  /** 对象类型 id（后端 `base_type_id` 的原值，作为解析失败时的兜底展示） */
  object_type_id?: string;
  filters: FilterRule[];
  sorts: SortRule[];
  limit: number;
  permissions: ViewPermission[];
}

/** 后端支持的过滤算子白名单（与 view 模块 schema 一致）。 */
const FILTER_OPS: ReadonlyArray<FilterRule['op']> = ['=', '!=', '>', '<', 'contains'];

/**
 * 后端 `ViewResponse.filters` 形如 `{ field: { op: value } }`，UI 需要逐条可编辑的 `FilterRule[]`。
 *
 * 历史实现直接把这里写成 `filters: []`，导致**已保存的过滤条件在打开视图时被清空**——
 * 用户改了过滤条件保存，再打开发现没了，属于静默数据丢失。
 * 同时兼容 `{ field: value }` 简写（视为等值），未知算子丢弃（后端对不支持的算子返回 422）。
 */
function toFilterRules(raw: Record<string, unknown> | null | undefined): FilterRule[] {
  if (!raw || typeof raw !== 'object') return [];
  const rules: FilterRule[] = [];
  for (const [field, spec] of Object.entries(raw)) {
    if (spec && typeof spec === 'object' && !Array.isArray(spec)) {
      for (const [op, value] of Object.entries(spec as Record<string, unknown>)) {
        if (!FILTER_OPS.includes(op as FilterRule['op'])) continue;
        rules.push({
          field,
          op: op as FilterRule['op'],
          value: value === null || value === undefined ? '' : String(value),
        });
      }
    } else {
      rules.push({ field, op: '=', value: spec === null || spec === undefined ? '' : String(spec) });
    }
  }
  return rules;
}

/**
 * 后端 `sort_order` 的键是 `property` + `direction`（见 view_query_engine_impl._apply_sort），
 * UI 用 `field` + `direction`。历史实现同样硬编码为 `sorts: []`，排序条件一并丢失。
 */
function toSortRules(raw: Array<Record<string, string>> | null | undefined): SortRule[] {
  if (!Array.isArray(raw)) return [];
  const rules: SortRule[] = [];
  for (const spec of raw) {
    const field = spec?.property || spec?.field;
    if (!field) continue;
    rules.push({
      field,
      direction: (spec?.direction || '').toLowerCase() === 'desc' ? 'desc' : 'asc',
    });
  }
  return rules;
}

/** 后端视图报文 → 设计器可编辑形态（唯一适配入口，避免多处各写一份）。 */
function toExtendedView(v: ObjectView): ExtendedObjectView {
  return {
    ...v,
    fields: (v.projected_properties || []).map((p) => ({ field: p, label: p, visible: true })),
    object_type_id: v.base_type_id,
    filters: toFilterRules(v.filters),
    sorts: toSortRules(v.sort_order),
    limit: v.row_limit,
    permissions: [],
  };
}

export interface ObjectTypeSummary {
  object_type_id: string;
  name: string;
  properties: Array<{ name: string; data_type: string }>;
}

export const viewApi = {
  list: (params?: { base_type?: string; role?: string }) => {
    const qs = new URLSearchParams();
    if (params?.base_type) qs.set('base_type', params.base_type);
    if (params?.role) qs.set('role', params.role);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return fetchJson<{ views: ObjectView[]; count: number }>(`${BASE}${suffix}`);
  },

  listViews: async (params?: { workspace_id?: string }) => {
    const qs = new URLSearchParams();
    if (params?.workspace_id) qs.set('workspace_id', params.workspace_id);
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    const data = await fetchJson<{ views: ObjectView[]; count: number }>(`${BASE}${suffix}`);
    return (data.views || []).map(toExtendedView);
  },

  get: (viewId: string) =>
    fetchJson<ObjectView>(`${BASE}/${encodeURIComponent(viewId)}`),

  getView: async (viewId: string) => {
    const v = await fetchJson<ObjectView>(`${BASE}/${encodeURIComponent(viewId)}`);
    return toExtendedView(v);
  },

  /**
   * 对象类型列表（视图设计器的数据源树）。
   *
   * 两个曾经写错的地方：
   *   1. 路径：真实端点是 `GET /api/ontology/oms/object-types`（oms 路由前缀是
   *      `/api/ontology/oms`）。此前写的 `/api/ontology/object-types` 不存在，恒 404，
   *      导致设计器左侧对象类型树永远为空。
   *   2. 形态：该端点 `response_model=List[ObjectTypeDefinition]`，返回**数组**，
   *      不是 `{object_types: [...]}`；属性类型字段是 `property_type` 而非 `data_type`。
   */
  listObjectTypes: async (): Promise<ObjectTypeSummary[]> => {
    const raw = await fetchJson<
      Array<{ type_id: string; name: string; properties?: Array<{ name: string; property_type?: string }> }>
    >(`${API_BASE}/api/ontology/oms/object-types`);
    if (!Array.isArray(raw)) return [];
    return raw.map((o) => ({
      object_type_id: o.type_id,
      name: o.name,
      properties: (o.properties ?? []).map((p) => ({
        name: p.name,
        data_type: p.property_type ?? 'string',
      })),
    }));
  },

  getMyPermission: async (viewId: string) => {
    try {
      const data = await fetchJson<{ permissions: ViewPermission[]; count: number }>(
        `${BASE}/${encodeURIComponent(viewId)}/permissions`,
      );
      return (data.permissions || [])[0] || null;
    } catch {
      return null;
    }
  },

  create: (payload: CreateViewPayload) =>
    fetchJson<ObjectView>(BASE, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  update: (viewId: string, payload: RawViewPatch) =>
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

  queryView: async (viewId: string, context: Record<string, unknown> = {}) => {
    return fetchJson<QueryViewResult>(`${BASE}/${encodeURIComponent(viewId)}/query`, {
      method: 'POST',
      // 预览需按当前设计（fields/filters/sorts/limit）执行；仅补齐缺失的身份字段
      body: JSON.stringify({ user_id: 'anonymous', ws_id: 'default', role: 'viewer', ...context }),
    });
  },

  updateView: (viewId: string, payload: UpdateViewPayload) =>
    fetchJson<ExtendedObjectView>(`${BASE}/${encodeURIComponent(viewId)}`, {
      method: 'PUT',
      body: JSON.stringify({
        name: payload.name,
        description: payload.description,
        base_type_id: payload.base_type_id,
        role: payload.role,
        enabled: payload.enabled,
        projected_properties: payload.projected_properties ?? payload.fields?.map((f) => f.field),
        filters: payload.filters,
        row_limit: payload.limit ?? payload.row_limit,
        sort_order: payload.sort_order,
      }),
    }),

  exportView: async (viewId: string, format: 'csv' | 'json' = 'csv'): Promise<Blob> => {
    const url = `${BASE}/${encodeURIComponent(viewId)}/export?format=${format}`;
    const token = localStorage.getItem('token') || '';
    const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Export failed: ${res.status}`);
    return res.blob();
  },

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
