/**
 * 结构化批量导入（Batch Import）API 客户端。
 *
 * 真实契约（后端 `odap/biz/core/ontology/design/ingestion/api/routes.py`）：
 *   POST /api/ontology/ingestion/batch
 *        BatchImportRequest{entity_type_id, data, format, workspace_id}
 *        → BatchImportResponse{status, success_count, fail_count, errors[], format, entity_type_id, workspace_id}
 *   数据源类型列表：GET /api/ontology/oms/object-types（返回数组，字段为 type_id / property_type）
 *
 * 历史实现打的是 `/api/ingest/batch?scenario_id=...`：
 *   - 该路径不存在（`/api/ingest` 下只有 /unified 与 /source-types）；
 *   - 还把 scenario_id 当作 entity_type_id 传，语义完全错位。
 * 因此把契约收在这里，组件不再自己拼 URL。
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BATCH_URL = `${API_BASE}/api/ontology/ingestion/batch`;
const OBJECT_TYPES_URL = `${API_BASE}/api/ontology/oms/object-types`;

export interface BatchImportError {
  row?: number;
  index?: number;
  error: string;
}

export interface BatchImportResult {
  status: string;
  success_count: number;
  fail_count: number;
  errors: BatchImportError[];
  format: string;
  entity_type_id: string;
  workspace_id: string;
}

export interface ObjectTypeOption {
  type_id: string;
  name: string;
  property_count: number;
}

/**
 * 批量导入。`data` 为文件原文：后端对 CSV 走 `csv.DictReader(StringIO(data))`，
 * 对 JSON 允许字符串（内部 `json.loads`），因此两种格式都直接传文本即可。
 */
export function batchImport(payload: {
  entityTypeId: string;
  data: string;
  format: 'csv' | 'json';
  workspaceId?: string;
}): Promise<BatchImportResult> {
  return fetchJson<BatchImportResult>(BATCH_URL, {
    method: 'POST',
    body: JSON.stringify({
      entity_type_id: payload.entityTypeId,
      data: payload.data,
      format: payload.format,
      workspace_id: payload.workspaceId || 'default',
    }),
  });
}

export async function listObjectTypeOptions(): Promise<ObjectTypeOption[]> {
  const raw = await fetchJson<
    Array<{ type_id: string; name: string; properties?: Array<unknown> }>
  >(OBJECT_TYPES_URL);
  if (!Array.isArray(raw)) return [];
  return raw.map((o) => ({
    type_id: o.type_id,
    name: o.name,
    property_count: (o.properties ?? []).length,
  }));
}
