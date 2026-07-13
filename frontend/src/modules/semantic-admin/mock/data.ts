/**
 * Semantic Admin Suite 前端 6 类 Mock 数据场景库。
 * 覆盖：TIER_A / TIER_B / TIER_C / TIER_D / 空数据集 / 异常边界（null 分数、负分、除零分母）
 *
 * 用法：
 *   import { mockQualityReport_TIER_A, mockEmptyDashboard, mockAbnormalScore }
 *     from '@/modules/semantic-admin/mock/data';
 *
 * 严格对齐 types/index.ts 里的接口：QualityReport / Candidate / ApprovalTask / DashboardResponse。
 */

import type {
  Candidate,
  CandidateStatus,
  QualityReport,
  DashboardResponse,
  ApprovalTask,
  SubMetricsGroup,
  QualityTier,
} from '../types';

// ============================================================
// Helpers
// ============================================================

const ZERO_TIME = '2025-03-18T10:00:00.000Z';

function buildSubmetrics(
  tier: QualityTier,
  opts?: { gate1Avg?: number; gate2Avg?: number; gate3Avg?: number },
): SubMetricsGroup {
  const g1 = opts?.gate1Avg ?? (tier === 'VERY_HIGH' ? 0.98 : tier === 'HIGH' ? 0.92 : tier === 'MEDIUM' ? 0.77 : tier === 'LOW' ? 0.60 : 0.31);
  const g2 = opts?.gate2Avg ?? (tier === 'VERY_HIGH' ? 1.0 : tier === 'HIGH' ? 0.94 : tier === 'MEDIUM' ? 0.8 : tier === 'LOW' ? 0.62 : 0.34);
  const g3 = opts?.gate3Avg ?? (tier === 'VERY_HIGH' ? 0.96 : tier === 'HIGH' ? 0.88 : tier === 'MEDIUM' ? 0.73 : tier === 'LOW' ? 0.60 : 0.30);
  return {
    gate1: [
      { submetric: 'g1_name_valid', score: g1, rule_name: 'semadm_g1_1', reason: `canonical 符合规范 → ${(g1 * 100).toFixed(0)}%` },
      { submetric: 'g1_en_mapping_valid', score: Math.min(1, g1 + 0.02), rule_name: 'semadm_g1_2', reason: 'en PascalCase 合法' },
      { submetric: 'g1_semantic_type_valid', score: 1.0, rule_name: 'semadm_g1_3', reason: 'semantic_type ∈ 合法枚举' },
      { submetric: 'g1_synonyms_size_valid', score: Math.min(1, g1 + 0.01), rule_name: 'semadm_g1_4', reason: '同义词 ∈ [0,30]' },
      { submetric: 'g1_synonyms_dedup_ratio', score: g1, rule_name: 'semadm_g1_5', reason: `去重率 = ${g1.toFixed(3)}` },
      { submetric: 'g1_circular_inclusion_free', score: 1.0, rule_name: 'semadm_g1_6', reason: 'canonical 与同义词互不包含' },
      { submetric: 'g1_usl_duplicate_check', score: Math.max(0, g1 - 0.05), rule_name: 'semadm_g1_7', reason: tier === 'VERY_LOW' ? 'USL 未命中（新增候选）' : '已去重比对 USL' },
    ],
    gate2: [
      { submetric: 'g2_usl_disjointness', score: g2, rule_name: 'semadm_g2_1', reason: 'disjoint pair 未命中' },
      { submetric: 'g2_cardinality_constraint', score: Math.min(1, g2 + 0.02), rule_name: 'semadm_g2_2', reason: '占位（L5 基数归纳待接入）' },
      { submetric: 'g2_isa_acyclic', score: 1.0, rule_name: 'semadm_g2_3', reason: '占位（L3 拓扑待接入）' },
      { submetric: 'g2_llm_semantic_judge', score: g2, rule_name: 'semadm_g2_4', reason: 'feature flag=false，LLM Judge 关闭' },
    ],
    gate3: [
      { submetric: 'g3_property_density', score: g3, rule_name: 'semadm_g3_1', reason: `属性密度估计 s=${g3.toFixed(3)}` },
      { submetric: 'g3_term_frequency_coverage', score: Math.min(1, g3 + 0.03), rule_name: 'semadm_g3_2', reason: `doc_hits 归一化=${g3.toFixed(2)}` },
      { submetric: 'g3_synonym_richness', score: g3, rule_name: 'semadm_g3_3', reason: `同义词丰富度=${g3.toFixed(2)}` },
      { submetric: 'g3_usl_alignment_novelty', score: Math.max(0, 1 - g3), rule_name: 'semadm_g3_4', reason: `新颖度=${(1 - g3).toFixed(2)}` },
      { submetric: 'g3_hierarchy_contrib', score: Math.min(1, g3 + 0.04), rule_name: 'semadm_g3_5', reason: `层级贡献度=${g3.toFixed(2)}` },
    ],
  };
}

function buildQualityReport(
  candidateId: string,
  tier: QualityTier,
  overrides: Partial<QualityReport> = {},
): QualityReport {
  const totalByTier: Record<QualityTier, number> = {
    VERY_HIGH: 0.96,
    HIGH: 0.92,
    MEDIUM: 0.77,
    LOW: 0.61,
    VERY_LOW: 0.33,
  };
  const total = totalByTier[tier];
  const submetrics = buildSubmetrics(tier);
  const overall: QualityReport['overall'] =
    total >= 0.85 ? 'PASS' : total >= 0.65 ? 'REVIEW' : 'FAIL';
  return {
    report_id: `rep-${candidateId}`,
    candidate_id: candidateId,
    run_id: `run-${candidateId.slice(0, 7)}`,
    generated_at: ZERO_TIME,
    gate1_score: Number((0.35 + (total - 0.6)).toFixed(3)),
    gate2_score: Number((0.40 + (total - 0.6) * 0.95).toFixed(3)),
    gate3_score: Number((0.25 + (total - 0.6) * 0.9).toFixed(3)),
    total_score: total,
    tier,
    submetrics,
    overall,
    recommend_auto_skip: total >= 0.9,
    ...overrides,
  };
}

function buildCandidate(
  id: string,
  canonical: string,
  status: CandidateStatus,
  tier: QualityTier,
  total_score: number,
): Candidate {
  return {
    id,
    term: canonical,
    canonical_label: canonical,
    term_type: '对象类型',
    synonyms: [`${canonical}别名A`, `${canonical}别名B`],
    definition: `${canonical} — 示例术语定义，用于前端 UI 预览。`,
    domain_id: 'domain-finance',
    status,
    quality_tier: tier,
    total_score,
    run_id: 'run-20250318-demo',
    created_at: ZERO_TIME,
    updated_at: ZERO_TIME,
  };
}

function buildTask(
  id: string,
  candidateId: string,
  title: string,
  assigned_role: 'schema_auditor' | 'admin',
  status: CandidateStatus,
): ApprovalTask {
  return {
    task_id: id,
    task_type: 'candidate_review',
    title,
    priority: assigned_role === 'admin' ? 'P0' : 'P1',
    status,
    assigned_role,
    candidate_id: candidateId,
    domain_id: 'domain-finance',
    created_at: ZERO_TIME,
  };
}

function buildDashboard(overrides: Partial<DashboardResponse> = {}): DashboardResponse {
  return {
    range: '30d',
    total_candidates: 128,
    by_status: {
      DRAFT: 10, L1_DONE: 20, L2_DONE: 15, L3_DONE: 10, L4_DONE: 8, L5_DONE: 5,
      PENDING_REVIEW: 22, AUDITOR_APPROVED: 18, ADMIN_PENDING: 10,
      APPROVED: 6, REVIEWER_REJECTED: 2, ADMIN_REJECTED: 1, WRITTEN_BACK: 1, STOPLISTED: 0,
    },
    by_tier: { VERY_HIGH: 6, HIGH: 40, MEDIUM: 50, LOW: 24, VERY_LOW: 8 },
    by_quality_gate: { PASS: 46, REVIEW: 54, FAIL: 28 },
    avg_gate_scores: { gate1_avg: 0.83, gate2_avg: 0.81, gate3_avg: 0.76, total_avg: 0.80 },
    approval_times: {
      l1_avg_secs: 3 * 60, l2_avg_secs: 10 * 60, total_avg_secs: 13 * 60,
      l1_samples: 32, l2_samples: 24, total_samples: 56,
    },
    generated_at: ZERO_TIME,
    ...overrides,
  };
}

// ============================================================
// 场景 1：TIER_A（全 HIGH，可 auto-skip）
// ============================================================
export const mockCandidate_TIER_A: Candidate = buildCandidate(
  'cand-a-0001', '库存周转率', 'PENDING_REVIEW', 'HIGH', 0.92,
);
export const mockQualityReport_TIER_A: QualityReport = buildQualityReport(
  'cand-a-0001', 'HIGH', { total_score: 0.92, tier: 'HIGH', recommend_auto_skip: true },
);

// ============================================================
// 场景 2：TIER_B（MEDIUM，建议 L1 人工复核）
// ============================================================
export const mockCandidate_TIER_B: Candidate = buildCandidate(
  'cand-b-0002', '毛利率', 'AUDITOR_APPROVED', 'MEDIUM', 0.77,
);
export const mockQualityReport_TIER_B: QualityReport = buildQualityReport(
  'cand-b-0002', 'MEDIUM', { total_score: 0.77, tier: 'MEDIUM', overall: 'REVIEW' },
);

// ============================================================
// 场景 3：TIER_C（LOW，建议人工干预）
// ============================================================
export const mockCandidate_TIER_C: Candidate = buildCandidate(
  'cand-c-0003', '现金流量', 'PENDING_REVIEW', 'LOW', 0.61,
);
export const mockQualityReport_TIER_C: QualityReport = buildQualityReport(
  'cand-c-0003', 'LOW', { total_score: 0.61, tier: 'LOW', overall: 'REVIEW' },
);

// ============================================================
// 场景 4：TIER_D（VERY_LOW，FAIL 级直接驳回）
// ============================================================
export const mockCandidate_TIER_D: Candidate = buildCandidate(
  'cand-d-0004', '随便', 'REVIEWER_REJECTED', 'VERY_LOW', 0.33,
);
export const mockQualityReport_TIER_D: QualityReport = buildQualityReport(
  'cand-d-0004', 'VERY_LOW', { total_score: 0.33, tier: 'VERY_LOW', overall: 'FAIL' },
);

// ============================================================
// 场景 5：空数据集（0 candidates / 0 tasks）
// ============================================================
export const mockEmptyCandidates: Candidate[] = [];
export const mockEmptyApprovalTasks: ApprovalTask[] = [];
export const mockEmptyDashboard: DashboardResponse = buildDashboard({
  total_candidates: 0,
  by_status: {},
  by_tier: {},
  by_quality_gate: {},
  avg_gate_scores: { gate1_avg: 0, gate2_avg: 0, gate3_avg: 0, total_avg: 0 },
  approval_times: { l1_avg_secs: 0, l2_avg_secs: 0, total_avg_secs: 0, l1_samples: 0, l2_samples: 0, total_samples: 0 },
});

// ============================================================
// 场景 6：异常边界 — null 分数 / 负分 / 除零分母模拟
// ============================================================

/** 候选字段 confidence='很高' 非数字 + total_score=null — 后端 _safe_float 兜底 0 */
export const mockCandidate_Abnormal: Candidate = {
  id: 'cand-abn-0999',
  term: '<script>alert(1)</script>',
  canonical_label: 'XSS 注入演示',
  term_type: '对象类型',
  synonyms: [],
  domain_id: 'domain-test',
  status: 'DRAFT',
  total_score: Number.NaN,
  quality_tier: 'VERY_LOW',
  created_at: ZERO_TIME,
  updated_at: ZERO_TIME,
  provenance: { doc_hits: 'foo-bar', l3_children_est: 'not-a-number' },
};

/** QualityReport：total_score=-0.1234（非法负分）— 后端 _mk 应 clamp 0 → 前端 UI 正确展示 0 */
export const mockQualityReport_AbnormalScore: QualityReport = buildQualityReport(
  'cand-abn-0999',
  'VERY_LOW',
  {
    gate1_score: -0.05,
    gate2_score: NaN as unknown as number,
    gate3_score: 1.5,
    total_score: -0.1234,
    tier: 'VERY_LOW',
    overall: 'FAIL',
    recommend_auto_skip: false,
  },
);

// ============================================================
// 混合 Dashboard / 混合列表 & 审批任务（全量预览）
// ============================================================

export const mockCandidates_Batch: Candidate[] = [
  mockCandidate_TIER_A,
  mockCandidate_TIER_B,
  mockCandidate_TIER_C,
  mockCandidate_TIER_D,
];

export const mockApprovalTasks_Batch: ApprovalTask[] = [
  buildTask('tsk-l1-a01', mockCandidate_TIER_A.id, '[L1] 审核：库存周转率', 'schema_auditor', 'PENDING_REVIEW'),
  buildTask('tsk-l1-b02', mockCandidate_TIER_B.id, '[L1] 修改：毛利率同义词', 'schema_auditor', 'AUDITOR_APPROVED'),
  buildTask('tsk-l2-a03', mockCandidate_TIER_A.id, '[L2] 终审：库存周转率 ≥0.90', 'admin', 'ADMIN_PENDING'),
  buildTask('tsk-l2-c04', mockCandidate_TIER_C.id, '[L2] 终审：现金流量（L1 提报需补充说明）', 'admin', 'ADMIN_PENDING'),
  buildTask('tsk-l1-d05', mockCandidate_TIER_D.id, '[L1] 驳回：同义词质量过低', 'schema_auditor', 'REVIEWER_REJECTED'),
];

/** Dashboard：TIER_A~D 各分布 10/30/40/20% */
export const mockDashboard_Normal: DashboardResponse = buildDashboard({
  total_candidates: 500,
  by_tier: { VERY_HIGH: 50, HIGH: 150, MEDIUM: 200, LOW: 80, VERY_LOW: 20 },
});

export default {
  mockCandidate_TIER_A, mockQualityReport_TIER_A,
  mockCandidate_TIER_B, mockQualityReport_TIER_B,
  mockCandidate_TIER_C, mockQualityReport_TIER_C,
  mockCandidate_TIER_D, mockQualityReport_TIER_D,
  mockEmptyCandidates, mockEmptyApprovalTasks, mockEmptyDashboard,
  mockCandidate_Abnormal, mockQualityReport_AbnormalScore,
  mockCandidates_Batch, mockApprovalTasks_Batch, mockDashboard_Normal,
};
