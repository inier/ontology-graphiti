/**
 * 语义资产统一编排 Pipeline API（对接后端 /api/semantic-assets/pipeline/*）
 * 一条 Pipeline 完成：结构化数据引入 / 非结构化文档抽取 → 候选归集 → 提交审核
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const URL_PREFIX = `${API_BASE}/api/semantic-assets/pipeline`;

export interface AssetSourceTypes {
  structured: string[];
  unstructured: string[];
}

export interface AssetTemplate {
  name: string;
  template_path?: string;
  description?: string;
  type?: string;
  tags?: string[];
  language?: string;
  [key: string]: unknown;
}

export interface AssetOntology {
  ontology_id?: string;
  id?: string;
  name?: string;
  display_name?: string;
  workspace_id?: string;
  [key: string]: unknown;
}

export interface AssetPipelineOptions {
  status: string;
  source_types: AssetSourceTypes;
  templates: AssetTemplate[];
  ontologies: AssetOntology[];
}

export interface AssetCandidate {
  id?: string;
  run_id?: string;
  pipeline_run_id?: string;
  canonical: string;
  semantic_type?: string;
  definition?: string;
  synonyms?: string[];
  confidence?: number;
  origin?: string;
  status?: string;
  [key: string]: unknown;
}

export interface AssetPipelineRunRequest {
  source_type: string;
  ontology_id?: string;
  extraction_mode?: 'constrained' | 'exploratory';
  template_ref?: string;
  payload: Record<string, unknown>;
  scenario_id?: string;
  workspace_id?: string;
}

export interface AssetPipelineRunResult {
  status: string;
  pipeline_run_id?: string;
  source_kind?: string;
  source_type?: string;
  candidate_count: number;
  candidates: AssetCandidate[];
  session_id?: string;
  template_used?: string;
  degradation_flags?: string[];
  ingest?: Record<string, unknown>;
  message?: string;
}

export async function getAssetPipelineOptions(
  ontologyId?: string,
): Promise<AssetPipelineOptions> {
  const q = ontologyId ? `?ontology_id=${encodeURIComponent(ontologyId)}` : '';
  return fetchJson(`${URL_PREFIX}/options${q}`);
}

export async function runAssetPipeline(
  payload: AssetPipelineRunRequest,
): Promise<AssetPipelineRunResult> {
  return fetchJson(`${URL_PREFIX}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function getAssetPipelineRun(
  pipelineRunId: string,
): Promise<{ status: string; pipeline_run_id: string; total: number; candidates: AssetCandidate[] }> {
  return fetchJson(`${URL_PREFIX}/${encodeURIComponent(pipelineRunId)}`);
}

export async function submitAssetPipeline(
  pipelineRunId: string,
): Promise<{ status: string; pipeline_run_id: string; submitted: number; skipped: number }> {
  return fetchJson(`${URL_PREFIX}/${encodeURIComponent(pipelineRunId)}/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ pipeline_run_id: pipelineRunId }),
  });
}
