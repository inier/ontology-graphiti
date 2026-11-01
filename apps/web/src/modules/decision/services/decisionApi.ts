/**
 * 决策主线 API 封装（ADR-101）
 *
 * 契约：docs/superpowers/specs/2026-10-24-decision-mainline/api-spec.yaml
 * - `workspace_id` 一律不传：后端从 JWT 声明解析（ADR-076 §7 信任模型）
 * - 断言：本文件内不得出现 `workspace_id` 入参
 */
import type {
  CausalLinkType,
  DecisionChain,
  DecisionExecuteResult,
  DecisionGateResult,
  DecisionImpact,
  DecisionLedgerPage,
  DecisionOutcome,
  DecisionRecord,
  PendingQueuePage,
} from '../types';
import { decisionRequest } from './decisionRequest';

const URL_PREFIX = '/api/decisions';

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
  entry_source?: string;
}

/** POST /api/decisions — 决策落库（新记录 status 恒为 pending） */
export async function recordDecision(
  payload: DecisionRecordCreatePayload,
): Promise<DecisionRecord> {
  return decisionRequest<DecisionRecord>(URL_PREFIX, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/** GET /api/decisions — 决策台账（分页 + 筛选 + 排序） */
export async function listDecisionLedger(params: URLSearchParams): Promise<DecisionLedgerPage> {
  return decisionRequest<DecisionLedgerPage>(`${URL_PREFIX}?${params.toString()}`);
}

/** GET /api/decisions/pending — 待决策队列（待办域三分组，服务端二分） */
export async function listPendingDecisions(params: URLSearchParams): Promise<PendingQueuePage> {
  return decisionRequest<PendingQueuePage>(`${URL_PREFIX}/pending?${params.toString()}`);
}

/** POST /api/decisions/{id}/resolve — 裁决（approve → decided / reject → rejected） */
export async function resolveDecision(
  decisionId: string,
  payload: { action: 'approve' | 'reject'; reason?: string },
): Promise<DecisionRecord> {
  return decisionRequest<DecisionRecord>(
    `${URL_PREFIX}/${encodeURIComponent(decisionId)}/resolve`,
    { method: 'POST', body: JSON.stringify(payload) },
  );
}

/** POST /api/decisions/{id}/execute — 发起执行（允许 decided / failed，幂等） */
export async function executeDecision(decisionId: string): Promise<DecisionExecuteResult> {
  return decisionRequest<DecisionExecuteResult>(
    `${URL_PREFIX}/${encodeURIComponent(decisionId)}/execute`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

/** POST /api/decisions/batch-resolve — 批量裁决（≤50，逐条独立结果） */
export async function batchResolveDecisions(payload: {
  decision_ids: string[];
  action: 'approve' | 'reject';
  reason?: string;
}): Promise<{
  succeeded: number;
  failed: number;
  results: Array<{
    decision_id: string;
    ok: boolean;
    status?: string | null;
    error?: { code: string; message: string; handler_name?: string | null } | null;
  }>;
}> {
  return decisionRequest(`${URL_PREFIX}/batch-resolve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/** GET /api/decisions/{id}/chain — 因果链追溯（本期行为不变） */
export async function getDecisionChain(decisionId: string): Promise<DecisionChain> {
  return decisionRequest<DecisionChain>(
    `${URL_PREFIX}/${encodeURIComponent(decisionId)}/chain`,
  );
}

/** GET /api/decisions/similar — 先例搜索（本期行为不变） */
export async function findSimilarDecisions(
  context: string,
  topK = 5,
): Promise<DecisionRecord[]> {
  const qs = new URLSearchParams({ context, top_k: String(topK) });
  return decisionRequest<DecisionRecord[]>(`${URL_PREFIX}/similar?${qs.toString()}`);
}

/** GET /api/decisions/{id}/impact — 影响分析（本期行为不变） */
export async function analyzeDecisionImpact(decisionId: string): Promise<DecisionImpact> {
  return decisionRequest<DecisionImpact>(
    `${URL_PREFIX}/${encodeURIComponent(decisionId)}/impact`,
  );
}

/** POST /api/decisions/{id}/causal-links — 显式建立因果边 */
export async function addCausalLink(
  decisionId: string,
  toDecisionId: string,
  linkType: CausalLinkType,
): Promise<{ success: boolean }> {
  return decisionRequest(`${URL_PREFIX}/${encodeURIComponent(decisionId)}/causal-links`, {
    method: 'POST',
    body: JSON.stringify({ to_decision_id: toDecisionId, link_type: linkType }),
  });
}

/** POST /api/decisions/check-rules — 落库前规则门禁 */
export async function checkDecisionRules(payload: {
  action: string;
  resource: Record<string, unknown>;
  environment?: Record<string, unknown>;
}): Promise<DecisionGateResult> {
  return decisionRequest(`${URL_PREFIX}/check-rules`, {
    method: 'POST',
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
  return decisionRequest<DecisionRecord>(
    `${URL_PREFIX}/${encodeURIComponent(decisionId)}/outcome`,
    {
      method: 'PATCH',
      body: JSON.stringify({
        outcome,
        outcome_details: outcomeDetails,
        feedback_summary: feedbackSummary,
      }),
    },
  );
}
