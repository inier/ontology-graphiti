/**
 * 决策主线类型定义（ADR-091 / ADR-076）
 * 唯一依据：docs/superpowers/specs/2026-10-24-decision-mainline/api-spec.yaml
 * 字段名逐字对齐契约，不自行改名（`available_operations` 不是 `available_actions`）。
 */

/** 执行结果五态（ADR-076 §3，本期零变更） */
export type DecisionOutcome =
  | 'success'
  | 'partial_success'
  | 'failure'
  | 'pending'
  | 'rejected';

/** 决策流程状态六值 —— 服务端产生，客户端不可写。注意：**不含** `partial_success` */
export type DecisionStatus =
  | 'pending'
  | 'decided'
  | 'executing'
  | 'executed'
  | 'failed'
  | 'rejected';

/** 入口来源七值（api-spec `DecisionEntrySource`） */
export type DecisionEntrySource =
  | 'manual'
  | 'pipeline'
  | 'recommendation'
  | 'qa'
  | 'agent'
  | 'import'
  | 'legacy';

/** 队列 SLA 三档（服务端派生，前端只渲染不自算） */
export type DecisionSlaState = 'ok' | 'warning' | 'breached';

/** 队列操作集（注意与 `RecommendedAction` 区分：这是用户可做的动作） */
export type DecisionOperation = 'approve' | 'reject' | 'execute' | 'retry';

/** 队列分组（服务端二分，前端不反推） */
export type DecisionQueueGroup = 'to_resolve' | 'to_execute';

export type CausalLinkType = 'CAUSED_BY' | 'INFLUENCED_BY' | 'PRECEDENT_FOR';

/** 可执行载荷（`execute` 缺省取此值） */
export interface RecommendedAction {
  action_type_id: string;
  target_object_id: string;
  target_object_type: string;
  parameters?: Record<string, unknown>;
}

/** 裁决留痕 —— 独立字段，不塞 `outcome_details`（后者会被 pipeline 回填覆写） */
export interface Resolution {
  action: 'approve' | 'reject';
  actor_type: 'user' | 'system';
  by?: string | null;
  at: string;
  reason?: string | null;
}

export interface ReasoningStep {
  step_id: string;
  phase: 'observe' | 'orient' | 'decide' | 'act';
  description?: string;
  evidence?: Array<Record<string, unknown>>;
  timestamp: string;
}

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
  /** 流程状态（服务端产生）。历史数据由 `status_assumed=true` 标记 */
  status: DecisionStatus;
  /** true = 迁移时为存量数据推定的状态，不是真实流程状态；这类记录不进队列 */
  status_assumed?: boolean;
  entry_source: DecisionEntrySource;
  recommended_action?: RecommendedAction | null;
  resolution?: Resolution | null;
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

/** 台账分页（api-spec `DecisionLedgerPage`） */
export interface DecisionLedgerPage {
  items: DecisionRecord[];
  total: number;
  total_is_estimate: boolean;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** 队列条目（api-spec `PendingDecisionItem`） */
export interface PendingDecisionItem {
  decision: DecisionRecord;
  group: DecisionQueueGroup;
  /** 自 `created_at` 起算（不是 updated_at）。**服务 `to_resolve` 档** */
  waited_minutes: number;
  /**
   * 自 `resolution.at`（裁决时刻）起算，**服务 `to_execute` 档**；非该档时为 `null`。
   * 与 `waited_minutes` 差一整个待裁定周期，两者不可互相顶替。
   */
  decided_waited_minutes: number | null;
  /** 计时基准按 `group` 取，与对应的 `*_waited_minutes` 必须一致 */
  sla_state: DecisionSlaState;
  /** 该记录当前可执行的操作，由状态机单点派生；为空时**不渲染按钮组** */
  available_operations: DecisionOperation[];
  executable: boolean;
}

export interface PendingQueueCounts {
  to_resolve: number;
  to_execute: number;
  sla_warning: number;
  sla_breached: number;
}

export interface PendingQueuePage {
  items: PendingDecisionItem[];
  total: number;
  counts: PendingQueueCounts;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface DecisionExecuteResult {
  decision: DecisionRecord;
  action_record?: Record<string, unknown> | null;
  decision_status: DecisionStatus;
  decision_outcome: DecisionOutcome;
  idempotent_replay: boolean;
}

/** 台账筛选条件（与 URL query 同构） */
export interface DecisionFilters {
  /** 结果：6 个派生态选项（界面归 5 类标签） */
  results: string[];
  entrySource?: DecisionEntrySource;
  /** 置信度区间 */
  confidenceBand: 'all' | 'low' | 'medium' | 'high';
  q?: string;
  createdFrom?: string;
  createdTo?: string;
}

/** 结果筛选选项（6 个派生态，见 uiux §4.3） */
export const RESULT_FILTER_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'pending', label: '待裁定' },
  { value: 'decided', label: '待执行确认' },
  { value: 'executed', label: '执行成功' },
  { value: 'partial_success', label: '部分成功' },
  { value: 'failed', label: '执行失败' },
  { value: 'rejected', label: '已驳回' },
];

/** 入口来源七值展示名（uiux §4.4） */
export const ENTRY_SOURCE_OPTIONS: Array<{ value: DecisionEntrySource; label: string }> = [
  { value: 'qa', label: '问答' },
  { value: 'agent', label: 'Agent 决策链' },
  { value: 'pipeline', label: '流水线' },
  { value: 'recommendation', label: '推荐采纳' },
  { value: 'manual', label: '手工录入' },
  { value: 'import', label: '批量导入' },
  { value: 'legacy', label: '来源未标注' },
];

/** 仅保留 label：色系由 `DecisionStatusTag` 走 token，不再用 antd 预设色名 */
export const OUTCOME_META: Record<DecisionOutcome, { label: string }> = {
  success: { label: '成功' },
  partial_success: { label: '部分成功' },
  failure: { label: '失败' },
  pending: { label: '待定' },
  rejected: { label: '已拒绝' },
};

export const CAUSAL_LINK_OPTIONS: Array<{ value: CausalLinkType; label: string }> = [
  { value: 'CAUSED_BY', label: '直接导致（CAUSED_BY）' },
  { value: 'INFLUENCED_BY', label: '弱影响（INFLUENCED_BY）' },
  { value: 'PRECEDENT_FOR', label: '先例引用（PRECEDENT_FOR）' },
];
