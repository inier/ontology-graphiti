/**
 * Goal / ChangeProposal API 客户端 (Phase 11 Batch 4 — FR-037)
 *
 * 对应后端 /api/ontology/goals 路由：
 *   POST   /                              创建 Goal
 *   GET    /                              列出 (query: workspace_id, status, page, page_size)
 *   GET    /{goal_id}                     获取详情
 *   PUT    /{goal_id}                     更新
 *   DELETE /{goal_id}                     删除
 *   POST   /{goal_id}/transition          状态机转换
 *   POST   /{goal_id}/propose-change      创建 ChangeProposal + ImpactAnalysis
 *   GET    /{goal_id}/proposals           列出该 Goal 的所有 Proposal
 *   GET    /{goal_id}/lineage             获取 Goal 血缘
 *   POST   /proposals/{proposal_id}/review  审批 Proposal
 */
import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const BASE = `${API_BASE}/api/ontology/goals`;

export type GoalStatus =
  | 'proposed'
  | 'approved'
  | 'rejected'
  | 'in-progress'
  | 'achieved'
  | 'abandoned';

export type ProposalStatus =
  | 'draft'
  | 'submitted'
  | 'under-review'
  | 'approved'
  | 'rejected'
  | 'implemented';

export type ImpactCost = 'low' | 'medium' | 'high';
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

export interface Goal {
  id: string;
  title: string;
  description: string;
  business_objective: string;
  rationale: string | null;
  status: GoalStatus;
  parent_goal_id: string | null;
  workspace_id: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface ChangeProposal {
  id: string;
  goal_id: string;
  title: string;
  description: string;
  changes: Array<Record<string, unknown>>;
  impact_analysis_id: string | null;
  estimated_benefit: string;
  estimated_cost: string | null;
  status: ProposalStatus;
  proposed_by: string;
  created_at: string;
  reviewed_at: string | null;
  reviewer_notes: string | null;
}

export interface ImpactAnalysis {
  id: string;
  proposal_id: string;
  affected_object_types: string[];
  affected_action_types: string[];
  affected_instances_count: number;
  breaking_changes: string[];
  estimated_migration_cost: ImpactCost;
  risk_level: RiskLevel;
  analysis_metadata: Record<string, unknown>;
  created_at: string;
}

export interface CreateGoalPayload {
  title: string;
  description?: string;
  business_objective: string;
  workspace_id: string;
  created_by: string;
  parent_goal_id?: string | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
  auto_rationale?: boolean;
}

export interface UpdateGoalPayload {
  title?: string;
  description?: string;
  business_objective?: string;
  rationale?: string;
  parent_goal_id?: string | null;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface ProposeChangePayload {
  title: string;
  description?: string;
  changes: Array<Record<string, unknown>>;
  proposed_by: string;
  estimated_benefit?: string;
  estimated_cost?: string;
}

export interface ReviewProposalPayload {
  decision: 'approve' | 'reject' | 'submit' | 'review' | 'implement' | string;
  reviewer_notes?: string;
}

export interface GoalLineage {
  goal: Goal | null;
  ancestors: Goal[];
  children: Goal[];
  proposals: ChangeProposal[];
}

export const goalApi = {
  list: (params: { workspace_id: string; status?: string; page?: number; page_size?: number }) => {
    const qs = new URLSearchParams();
    qs.set('workspace_id', params.workspace_id);
    if (params.status) qs.set('status', params.status);
    if (params.page) qs.set('page', String(params.page));
    if (params.page_size) qs.set('page_size', String(params.page_size));
    return fetchJson<{ goals: Goal[]; total: number; page: number; page_size: number; count: number }>(
      `${BASE}?${qs.toString()}`,
    );
  },

  get: (goalId: string) =>
    fetchJson<Goal>(`${BASE}/${encodeURIComponent(goalId)}`),

  create: (payload: CreateGoalPayload) =>
    fetchJson<Goal>(BASE, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  update: (goalId: string, payload: UpdateGoalPayload) =>
    fetchJson<Goal>(`${BASE}/${encodeURIComponent(goalId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  remove: (goalId: string) =>
    fetchJson<{ goal_id: string; deleted: boolean }>(
      `${BASE}/${encodeURIComponent(goalId)}`,
      { method: 'DELETE' },
    ),

  transition: (goalId: string, newStatus: GoalStatus) =>
    fetchJson<Goal>(`${BASE}/${encodeURIComponent(goalId)}/transition`, {
      method: 'POST',
      body: JSON.stringify({ new_status: newStatus }),
    }),

  proposeChange: (goalId: string, payload: ProposeChangePayload) =>
    fetchJson<{ proposal: ChangeProposal; impact: ImpactAnalysis }>(
      `${BASE}/${encodeURIComponent(goalId)}/propose-change`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),

  listProposals: (goalId: string) =>
    fetchJson<{ proposals: ChangeProposal[]; count: number }>(
      `${BASE}/${encodeURIComponent(goalId)}/proposals`,
    ),

  getProposal: (proposalId: string) =>
    fetchJson<ChangeProposal>(
      `${BASE}/proposals/${encodeURIComponent(proposalId)}`,
    ),

  getImpact: (impactId: string) =>
    fetchJson<ImpactAnalysis>(
      `${BASE}/impacts/${encodeURIComponent(impactId)}`,
    ),

  getLineage: (goalId: string) =>
    fetchJson<GoalLineage>(`${BASE}/${encodeURIComponent(goalId)}/lineage`),

  reviewProposal: (proposalId: string, payload: ReviewProposalPayload) =>
    fetchJson<ChangeProposal>(
      `${BASE}/proposals/${encodeURIComponent(proposalId)}/review`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
};
