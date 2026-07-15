import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type { PagedResponse } from '../types';

export interface QualityReport {
  id: string;
  gate1_score: number;
  gate2_score: number;
  gate3_score: number;
  total_score: number;
  tier: 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW';
  grades?: { A: number; B: number; C: number; D: number };
}

export interface Candidate {
  id: string;
  pipeline_run_id: string;
  domain_id?: string;
  canonical: string;
  semantic_type?: string;
  synonyms: string[];
  aliases: string[];
  near_synonyms: string[];
  definition?: string;
  examples: string[];
  stoplist_flag: boolean;
  confidence: number;
  source_text?: string;
  provenance: Record<string, unknown>;
  status:
    | 'new'
    | 'gated'
    | 'approved'
    | 'rejected'
    | 'written'
    | 'auditor_approved'
    | 'admin_pending'
    | 'written_back'
    | 'stoplisted';
  created_at: string;
  updated_at: string;
  quality_report?: QualityReport;
}

export type CandidateStatus = Candidate['status'];

export interface PipelineRunStats {
  L1_tokens?: number;
  L2_concepts?: number;
  L3_entities?: number;
  L4_relations?: number;
  L5_patterns?: number;
  total_candidates?: number;
  grades?: { A: number; B: number; C: number; D: number };
}

export interface PipelineRun {
  id: string;
  workspace_id: string;
  ontology_id?: string;
  source_type: string;
  source_ref?: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  triggered_by?: string;
  progress: number;
  total_input_chars: number;
  total_output_candidates: number;
  error_message?: string;
  started_at?: string;
  finished_at?: string;
  created_at: string;
  stats?: PipelineRunStats;
}

export type PipelineRunStatus = PipelineRun['status'];

export interface CreatePipelineRunRequest {
  workspace_id: string;
  ontology_id?: string;
  source_type: string;
  source_ref?: string;
  source_text?: string;
  triggered_by?: string;
}

export interface ReviewPayload {
  reviewer: string;
  comment?: string;
  level: 1 | 2;
}

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

export async function listPipelineRuns(params: {
  workspace_id?: string;
  status?: PipelineRunStatus;
  page?: number;
  page_size?: number;
} = {}): Promise<PagedResponse<PipelineRun>> {
  return fetchJson(`${URL_PREFIX}/pipeline/runs${buildQuery({
    workspace_id: params.workspace_id,
    status: params.status,
    page: params.page ?? 1,
    page_size: params.page_size ?? 50,
  })}`);
}

export async function getPipelineRuns(params: {
  workspace_id?: string;
  status?: PipelineRunStatus;
  page?: number;
  page_size?: number;
}): Promise<PagedResponse<PipelineRun>> {
  return listPipelineRuns(params);
}

export async function getPipelineRun(id: string): Promise<PipelineRun> {
  return fetchJson(`${URL_PREFIX}/pipeline/runs/${encodeURIComponent(id)}`);
}

export async function createPipelineRun(payload: CreatePipelineRunRequest): Promise<PipelineRun> {
  return fetchJson(`${URL_PREFIX}/pipeline/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function runPipelineNow(id: string): Promise<PipelineRun> {
  return fetchJson(`${URL_PREFIX}/pipeline/runs/${encodeURIComponent(id)}/run`, {
    method: 'POST',
  });
}

/**
 * AGENTS.md §F C6: 推进 Pipeline Run 单个阶段
 *   POST /api/semantic-admin/pipeline/runs/{id}/advance
 */
export async function advancePipelineRun(id: string, payload: {
  stage?: string;
  actor_id?: string;
} = {}): Promise<PipelineRun> {
  return fetchJson(`${URL_PREFIX}/pipeline/runs/${encodeURIComponent(id)}/advance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/**
 * AGENTS.md §F C6: 一键推进 Pipeline Run 全部 6 层阶段
 *   POST /api/semantic-admin/pipeline/runs/{id}/execute-all
 */
export async function executeAllPipelineStages(id: string, payload: {
  actor_id?: string;
  force?: boolean;
} = {}): Promise<PipelineRun> {
  return fetchJson(`${URL_PREFIX}/pipeline/runs/${encodeURIComponent(id)}/execute-all`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function listCandidates(params: {
  pipeline_run_id?: string;
  domain_id?: string;
  status?: CandidateStatus;
  semantic_type?: string;
  min_confidence?: number;
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<PagedResponse<Candidate>> {
  return fetchJson(`${URL_PREFIX}/candidates${buildQuery({
    pipeline_run_id: params.pipeline_run_id,
    domain_id: params.domain_id,
    status: params.status,
    semantic_type: params.semantic_type,
    min_confidence: params.min_confidence,
    keyword: params.keyword,
    page: params.page ?? 1,
    page_size: params.page_size ?? 50,
  })}`);
}

export async function getCandidate(id: string): Promise<Candidate> {
  return fetchJson(`${URL_PREFIX}/candidates/${encodeURIComponent(id)}`);
}

export async function approveCandidate(
  id: string,
  payload: ReviewPayload,
): Promise<Candidate> {
  return fetchJson(`${URL_PREFIX}/candidates/${encodeURIComponent(id)}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function rejectCandidate(
  id: string,
  payload: ReviewPayload,
): Promise<Candidate> {
  return fetchJson(`${URL_PREFIX}/candidates/${encodeURIComponent(id)}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteCandidate(id: string): Promise<{ status: string; message: string }> {
  return fetchJson(`${URL_PREFIX}/candidates/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });
}

export interface CandidatePatch {
  term?: string;
  canonical_label?: string;
  term_type?: string;
  synonyms?: string[];
  domain_id?: string;
  definition?: string;
  custom_attributes?: Record<string, any>;
  status?: string;
}

export async function modifyCandidate(
  id: string,
  patch: CandidatePatch,
): Promise<{ candidate_id: string; updated_fields: string[] }> {
  return fetchJson(`${URL_PREFIX}/candidates/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
}

export async function listApprovalTasks(params: Record<string, unknown> = {}): Promise<PagedResponse<unknown>> {
  return fetchJson(`${URL_PREFIX}/approval/tasks${buildQuery(params)}`);
}

export async function listAuditLogs(params: Record<string, unknown> = {}): Promise<PagedResponse<unknown>> {
  return fetchJson(`${URL_PREFIX}/audit/logs${buildQuery(params)}`);
}
