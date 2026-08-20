/**
 * 决策智能类型定义（ADR-076）
 * 与后端 odap.biz.decision.decision_record.models 对齐
 */

export type DecisionOutcome =
  | 'success'
  | 'partial_success'
  | 'failure'
  | 'pending'
  | 'rejected';

export type CausalLinkType = 'CAUSED_BY' | 'INFLUENCED_BY' | 'PRECEDENT_FOR';

export interface DecisionRecord {
  decision_id: string;
  workspace_id: string;
  context_summary: string;
  constraints: Record<string, unknown>;
  reasoning: string;
  reasoning_trace: Array<Record<string, unknown>>;
  confidence: number;
  evidence_episode_ids: string[];
  evidence_entity_ids: string[];
  recommended_option: string;
  alternative_options: string[];
  decision_method: string;
  decision_type: string;
  parent_decision_id?: string | null;
  root_goal_id?: string | null;
  precedent_decision_ids: string[];
  action_record_id?: string | null;
  outcome: DecisionOutcome;
  outcome_details: Record<string, unknown>;
  feedback_summary?: string | null;
  agent_id?: string | null;
  opa_approved?: boolean | null;
  opa_decision?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  valid_at: string;
  invalid_at?: string | null;
}

export interface DecisionChain {
  decision: DecisionRecord;
  evidence_entities: Array<Record<string, unknown>>;
  evidence_episodes: Array<Record<string, unknown>>;
  parent_chain: DecisionRecord[];
  precedents: DecisionRecord[];
  reasoning_trace: Array<Record<string, unknown>>;
}

export interface DecisionImpact {
  decision_id: string;
  derived_decisions: Array<Record<string, unknown>>;
  target_changes: Array<Record<string, unknown>>;
  co_evidence_decisions: Array<Record<string, unknown>>;
  impact_completeness: 'full' | 'degraded_target_resolution' | 'partial';
}

export interface DecisionGateResult {
  approved: boolean;
  gate: string;
  details: Record<string, unknown>;
}

export const OUTCOME_META: Record<DecisionOutcome, { label: string; color: string }> = {
  success: { label: '成功', color: 'green' },
  partial_success: { label: '部分成功', color: 'lime' },
  failure: { label: '失败', color: 'red' },
  pending: { label: '待定', color: 'default' },
  rejected: { label: '已拒绝', color: 'orange' },
};

export const CAUSAL_LINK_OPTIONS: Array<{ value: CausalLinkType; label: string }> = [
  { value: 'CAUSED_BY', label: '直接导致（CAUSED_BY）' },
  { value: 'INFLUENCED_BY', label: '弱影响（INFLUENCED_BY）' },
  { value: 'PRECEDENT_FOR', label: '先例引用（PRECEDENT_FOR）' },
];
