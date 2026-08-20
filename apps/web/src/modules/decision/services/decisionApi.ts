/**
 * 决策智能 API 封装（ADR-076：7 端点）
 * workspace_id 由后端从 JWT 声明解析，前端无需也不应透传
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';
import type {
  CausalLinkType,
  DecisionChain,
  DecisionGateResult,
  DecisionImpact,
  DecisionOutcome,
  DecisionRecord,
} from '../types';

const URL_PREFIX = `${API_BASE}/api/decisions`;

export interface DecisionRecordCreatePayload {
  context_summary: string;
  constraints?: Record<string, unknown>;
  reasoning?: string;
  confidence?: number;
  recommended_option: string;
  alternative_options?: string[];
  decision_method?: string;
  decision_type?: string;
  parent_decision_id?: string;
  precedent_decision_ids?: string[];
}

/** POST /api/decisions — 决策落库 */
export async function recordDecision(
  payload: DecisionRecordCreatePayload,
): Promise<DecisionRecord> {
  return fetchJson(URL_PREFIX, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/** GET /api/decisions/{id}/chain — 因果链追溯 */
export async function getDecisionChain(decisionId: string): Promise<DecisionChain> {
  return fetchJson(`${URL_PREFIX}/${encodeURIComponent(decisionId)}/chain`);
}

/** GET /api/decisions/similar — 先例搜索 */
export async function findSimilarDecisions(
  context: string,
  topK = 5,
): Promise<DecisionRecord[]> {
  const qs = new URLSearchParams({ context, top_k: String(topK) });
  return fetchJson(`${URL_PREFIX}/similar?${qs.toString()}`);
}

/** GET /api/decisions/{id}/impact — 影响分析 */
export async function analyzeDecisionImpact(decisionId: string): Promise<DecisionImpact> {
  return fetchJson(`${URL_PREFIX}/${encodeURIComponent(decisionId)}/impact`);
}

/** POST /api/decisions/{id}/causal-links — 显式建立因果边 */
export async function addCausalLink(
  decisionId: string,
  toDecisionId: string,
  linkType: CausalLinkType,
): Promise<{ success: boolean }> {
  return fetchJson(`${URL_PREFIX}/${encodeURIComponent(decisionId)}/causal-links`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ to_decision_id: toDecisionId, link_type: linkType }),
  });
}

/** POST /api/decisions/check-rules — 落库前规则门禁 */
export async function checkDecisionRules(payload: {
  action: string;
  resource: Record<string, unknown>;
  environment?: Record<string, unknown>;
}): Promise<DecisionGateResult> {
  return fetchJson(`${URL_PREFIX}/check-rules`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/** PATCH /api/decisions/{id}/outcome — 结果回填 */
export async function updateDecisionOutcome(
  decisionId: string,
  outcome: DecisionOutcome,
  outcomeDetails: Record<string, unknown> = {},
  feedbackSummary?: string,
): Promise<DecisionRecord> {
  return fetchJson(`${URL_PREFIX}/${encodeURIComponent(decisionId)}/outcome`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      outcome,
      outcome_details: outcomeDetails,
      feedback_summary: feedbackSummary,
    }),
  });
}
