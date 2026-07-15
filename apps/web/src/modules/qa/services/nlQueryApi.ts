/**
 * NL 本体查询服务 - API 调用层
 * 对接后端 /api/qa/* 路由
 */
import { apiClient } from '@/modules/shared/services/apiClient';

// ── 类型定义 ──────────────────────────────────────────────────────

export type QueryIntent =
  | 'keyword_lookup'
  | 'semantic_search'
  | 'graph_traverse'
  | 'complex_analysis'
  | 'temporal_query'
  | 'action';

export type RetrievalPillar = 'bm25' | 'vector' | 'graph';
export type FusionStrategy = 'weighted' | 'rrf' | 'cascade';
export type QueryMode = 'auto' | 'keyword' | 'semantic' | 'graph';

export interface QueryUnderstanding {
  original_query: string;
  intent: QueryIntent;
  extracted_entities: string[];
  rewritten_queries: string[];
  confidence: number;
  needs_clarification: boolean;
  clarification_reason?: string;
}

export interface SubQuery {
  pillar: RetrievalPillar;
  query: string;
  params: Record<string, unknown>;
  mode?: string;
}

export interface QueryPlan {
  plan_id: string;
  pillars: RetrievalPillar[];
  sub_queries: SubQuery[];
  fusion_strategy: FusionStrategy;
  top_k: number;
}

export interface RetrievalResult {
  doc_id: string;
  content: string;
  score: number;
  pillar: RetrievalPillar;
  source: string;
  metadata: Record<string, unknown>;
  entities: string[];
  relations: string[];
}

export interface SourceReference {
  doc_id: string;
  content: string;
  score: number;
  pillar: RetrievalPillar;
  source: string;
  entity_id?: string;
}

export interface QueryRequest {
  query: string;
  workspace_id?: string;
  scenario_id?: string;
  user_id?: string;
  mode?: QueryMode;
  top_k?: number;
}

export interface QueryResponse {
  query_id: string;
  answer: string;
  sources: SourceReference[];
  understanding?: QueryUnderstanding;
  plan?: QueryPlan;
  pillar_contributions: Record<string, number>;
  total_time_ms: number;
  metadata: Record<string, unknown>;
}

export interface NLSearchResponse {
  results: RetrievalResult[];
  pillar_scores: Record<string, number>;
  total: number;
  metadata: Record<string, unknown>;
}

export interface NLExplainResponse {
  original_query: string;
  understanding: QueryUnderstanding;
  plan: QueryPlan;
  explanation: string;
}

export interface PillarStatus {
  name: RetrievalPillar;
  description: string;
  status: 'available' | 'unavailable';
}

export interface PillarStatusResponse {
  pillars: PillarStatus[];
  index_info: Record<string, unknown>;
}

export interface AuditRecord {
  query_id: string;
  timestamp: string;
  user_id: string;
  workspace_id: string;
  scenario_id?: string;
  original_query: string;
  intent: string;
  extracted_entities: string[];
  rewritten_queries: string[];
  query_plan: Record<string, unknown>;
  selected_pillars: string[];
  pillar_results_count: Record<string, number>;
  cypher_generated?: string;
  execution_time_ms: Record<string, number>;
  total_results_before_fusion: number;
  total_results_after_fusion: number;
  rerank_model?: string;
  response_length: number;
  source_count: number;
  llm_model: string;
  total_time_ms: number;
}

export interface AuditListResponse {
  records: AuditRecord[];
  total: number;
}

export interface AuditStatsResponse {
  total_queries: number;
  avg_time_ms: number;
  pillar_usage: Record<string, number>;
}

export interface EvalResponse {
  dataset_name: string;
  total_cases: number;
  retrieval_metrics: Record<string, number>;
  qa_metrics: Record<string, number>;
  latency_p50_ms: number;
  latency_p95_ms: number;
  pillar_usage: Record<string, number>;
}

// ── API 调用 ──────────────────────────────────────────────────────

/** 完整查询（五阶段管线） */
export async function nlQuery(request: QueryRequest): Promise<QueryResponse> {
  return apiClient.post('/api/qa/query', request);
}

/** 纯检索（不生成回答） */
export async function nlSearch(request: QueryRequest): Promise<NLSearchResponse> {
  return apiClient.post('/api/qa/search', request);
}

/** 查询计划预览 */
export async function nlPlan(request: QueryRequest): Promise<Record<string, unknown>> {
  return apiClient.post('/api/qa/plan', request);
}

/** 查询解释 */
export async function nlExplain(request: QueryRequest): Promise<NLExplainResponse> {
  return apiClient.post('/api/qa/explain', request);
}

/** 三支柱状态 */
export async function getPillarStatus(): Promise<PillarStatusResponse> {
  return apiClient.get('/api/qa/retrieval/pillars');
}

/** 审计详情 */
export async function getAuditDetail(queryId: string): Promise<{ record: AuditRecord }> {
  return apiClient.get(`/api/qa/audit/${queryId}`);
}

/** 审计列表 */
export async function listAuditRecords(params?: {
  workspace_id?: string;
  user_id?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditListResponse> {
  const query = new URLSearchParams();
  if (params?.workspace_id) query.set('workspace_id', params.workspace_id);
  if (params?.user_id) query.set('user_id', params.user_id);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  return apiClient.get(`/api/qa/audit${qs ? `?${qs}` : ''}`);
}

/** 审计统计 */
export async function getAuditStats(workspaceId?: string): Promise<AuditStatsResponse> {
  const qs = workspaceId ? `?workspace_id=${workspaceId}` : '';
  return apiClient.get(`/api/qa/audit/stats${qs}`);
}

/** 运行评估 */
export async function runEvaluation(): Promise<EvalResponse> {
  return apiClient.post('/api/qa/evaluate');
}
