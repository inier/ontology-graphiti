/**
 * USL 本体管理 API
 * 对接后端 /api/semantic-assets/pipeline/usl-ontologies 与 /api/ontologies
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const PIPELINE_PREFIX = `${API_BASE}/api/semantic-assets/pipeline`;
const ONTOLOGY_PREFIX = `${API_BASE}/api/ontologies`;

export interface UslOntologyTypeCounts {
  object_types: number;
  link_types: number;
  action_types: number;
  process_types: number;
  rule_types: number;
  [key: string]: number;
}

export interface UslOntology {
  ontology_id: string;
  name: string;
  domain_code: string;
  domain_display_name: string;
  domain_description?: string;
  display_label: string;
  workspace_id?: string;
  created_at?: string;
  type_counts?: UslOntologyTypeCounts;
}

export interface UslOntologyListResult {
  status: string;
  items: UslOntology[];
  total: number;
  domains: Array<{
    id?: string;
    code: string;
    display_name: string;
    description?: string;
    [key: string]: unknown;
  }>;
}

/** 列出 USL 系统本体（管理界面数据源） */
export async function listUslOntologies(
  workspaceId?: string,
): Promise<UslOntologyListResult> {
  const q = workspaceId
    ? `?workspace_id=${encodeURIComponent(workspaceId)}`
    : '';
  return fetchJson(`${PIPELINE_PREFIX}/usl-ontologies${q}`);
}

/** 删除本体（管理界面删除 USL 本体） */
export async function deleteOntology(ontologyId: string): Promise<{
  status?: string;
  deleted?: boolean;
}> {
  return fetchJson(`${ONTOLOGY_PREFIX}/${encodeURIComponent(ontologyId)}`, {
    method: 'DELETE',
  });
}
