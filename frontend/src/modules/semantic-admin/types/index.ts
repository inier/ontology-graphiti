// ===== USL (Universal Semantic Language) 领域类型 =====
// 严格对应后端 Pydantic 字段名，所有枚举与后端契约对齐
// 权威来源：design/04-iter3-quality-approval-design.html §② G1.3 合法集

/** 语义类型枚举：对应 USL term.semantic_type 字段（中文 6 值，与质量闸 G1.3 一致） */
export type SemanticType =
  | '对象类型'
  | '关系类型'
  | '属性'
  | '动作类型'
  | '过程类型'
  | '规则类型';

/** 层级关系类型：is_a(继承) / part_of(组成) */
export type HierarchyRelType = 'is_a' | 'part_of';

/** 属性数据类型：用于 UslPropertySpec.data_type */
export type PropertyDataType =
  | 'string'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'datetime'
  | 'json'
  | 'text';

/** 分页响应泛型：与后端 PagedResponse 一致 */
export interface PagedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ========== 6 大 USL 核心实体 ==========

/** 语义域 (UslDomain) */
export interface UslDomain {
  /** 唯一标识码（英文短横线，如 sanguo_common） */
  code: string;
  /** 显示中文名（如 三国通用语域） */
  display_name: string;
  /** 域描述 */
  description?: string;
  /** 英文→中文映射 JSON，Key 为英文 PascalCase */
  en_mapping?: Record<string, string>;
  /** 术语总数（聚合字段，list 时后端计算） */
  term_count?: number;
  created_at?: string;
  updated_at?: string;
}

/** 创建/更新语义域请求 */
export interface DomainPayload {
  code: string;
  display_name: string;
  description?: string;
  en_mapping?: Record<string, string>;
}

/** 规范术语 (UslTerm) */
export interface UslTerm {
  id?: string;
  /** 所属域 ID（外键 usl_domains.id，非 code） */
  domain_id: string;
  /** 规范中文词 */
  canonical: string;
  /** 语义分类 */
  semantic_type: SemanticType;
  /** 同义词簇 */
  synonyms?: string[];
  /** 近义词 */
  near_synonyms?: string[];
  /** 别名 */
  aliases?: string[];
  /** 是否停用（Stoplist 开关） */
  stoplist_flag?: boolean;
  /** 术语定义 */
  definition?: string;
  created_at?: string;
  updated_at?: string;
}

/** 创建/更新术语请求 */
export interface TermPayload {
  domain_id: string;
  canonical: string;
  semantic_type: SemanticType;
  synonyms?: string[];
  near_synonyms?: string[];
  aliases?: string[];
  stoplist_flag?: boolean;
  definition?: string;
}

/** 层级结构节点 (UslHierarchy) */
export interface UslHierarchy {
  id?: string;
  domain_id: string;
  /** 关系类型：is_a 泛化 / part_of 组成 */
  rel_type: HierarchyRelType;
  /** 父术语 canonical */
  parent_term: string;
  /** 子术语 canonical */
  child_term: string;
  /** 置信度 0-1 */
  confidence?: number;
  /** 来源说明 */
  provenance?: string;
  created_at?: string;
}

/** 属性规范 (UslPropertySpec) */
export interface UslPropertySpec {
  id?: string;
  domain_id: string;
  /** 所属术语 canonical */
  for_term: string;
  /** 属性名 */
  prop_name: string;
  /** 数据类型 */
  data_type: PropertyDataType;
  /** 度量单位（可选） */
  unit?: string;
  /** 是否必填 */
  required?: boolean;
  /** 描述 */
  description?: string;
  created_at?: string;
}

/** 不相交约束对 (UslDisjointPair) */
export interface UslDisjointPair {
  id?: string;
  domain_id: string;
  /** 术语 A canonical */
  term_a: string;
  /** 术语 B canonical（不能同时 is_a A 和 B） */
  term_b: string;
  /** 不相交理由 */
  reason?: string;
  created_at?: string;
}

/** 关系基数约束 (UslCardinality) */
export interface UslCardinality {
  id?: string;
  domain_id: string;
  /** 关系名 canonical（link_type 术语） */
  rel_name: string;
  /** 定义域术语（源端） */
  domain_term: string;
  /** 值域术语（目标端） */
  range_term: string;
  /** 最小基数，默认 0 */
  min_card?: number;
  /** 最大基数，-1 表示无限，默认 -1 */
  max_card?: number;
  /** 描述 */
  description?: string;
  created_at?: string;
}

/** SemanticType 全中文枚举，Tag 显示直接用 value，Label 表保留用于 OptionList 生成 */
export const SEMANTIC_TYPE_LABEL: Record<SemanticType, string> = {
  '对象类型': '对象类型',
  '关系类型': '关系类型',
  '属性': '属性',
  '动作类型': '动作类型',
  '过程类型': '过程类型',
  '规则类型': '规则类型',
};

/** SemanticType → AntD Tag color 映射（中文 key） */
export const SEMANTIC_TYPE_COLOR: Record<SemanticType, string> = {
  '对象类型': 'blue',
  '关系类型': 'green',
  '属性': 'purple',
  '动作类型': 'orange',
  '过程类型': 'cyan',
  '规则类型': 'magenta',
};

/** 属性数据类型下拉选项 */
export const PROPERTY_DATA_TYPE_OPTIONS: Array<{
  label: string;
  value: PropertyDataType;
}> = [
  { label: '字符串', value: 'string' },
  { label: '整数', value: 'integer' },
  { label: '浮点', value: 'float' },
  { label: '布尔', value: 'boolean' },
  { label: '日期时间', value: 'datetime' },
  { label: 'JSON', value: 'json' },
  { label: '长文本', value: 'text' },
];

/** 层级关系类型选项 */
export const HIERARCHY_REL_OPTIONS: Array<{
  label: string;
  value: HierarchyRelType;
}> = [
  { label: 'is_a (继承/泛化)', value: 'is_a' },
  { label: 'part_of (组成/部分)', value: 'part_of' },
];

export type CandidateStatus =
  | 'DRAFT'
  | 'L1_DONE'
  | 'L2_DONE'
  | 'L3_DONE'
  | 'L4_DONE'
  | 'L5_DONE'
  | 'PENDING_REVIEW'
  | 'AUDITOR_APPROVED'
  | 'ADMIN_PENDING'
  | 'APPROVED'
  | 'REVIEWER_REJECTED'
  | 'ADMIN_REJECTED'
  | 'WRITTEN_BACK'
  | 'STOPLISTED';

export const CANDIDATE_STATUS_LABEL: Record<CandidateStatus, string> = {
  DRAFT: '草稿',
  L1_DONE: '分词完成',
  L2_DONE: '归一化完成',
  L3_DONE: '概念抽取完成',
  L4_DONE: '关系抽取完成',
  L5_DONE: '模式挖掘完成',
  PENDING_REVIEW: '待审核',
  AUDITOR_APPROVED: '审核员已通过',
  ADMIN_PENDING: '管理员待审批',
  APPROVED: '已通过',
  REVIEWER_REJECTED: '审核员驳回',
  ADMIN_REJECTED: '管理员驳回',
  WRITTEN_BACK: '已回写',
  STOPLISTED: '已停用',
};

export const CANDIDATE_STATUS_COLOR: Record<CandidateStatus, string> = {
  DRAFT: 'default',
  L1_DONE: 'cyan',
  L2_DONE: 'cyan',
  L3_DONE: 'cyan',
  L4_DONE: 'cyan',
  L5_DONE: 'cyan',
  PENDING_REVIEW: 'orange',
  AUDITOR_APPROVED: 'blue',
  ADMIN_PENDING: 'geekblue',
  APPROVED: 'green',
  REVIEWER_REJECTED: 'red',
  ADMIN_REJECTED: 'magenta',
  WRITTEN_BACK: 'lime',
  STOPLISTED: 'gold',
};

/** Graphiti 双写回状态（candidate.provenance.graphiti_writeback） */
export interface GraphitiWritebackStatus {
  /** 写入结果：ok / error / skipped */
  status: 'ok' | 'error' | 'skipped';
  /** 写入方法：object / link / action / process / rule */
  method?: 'object' | 'link' | 'action' | 'process' | 'rule';
  /** 是否新建 */
  created_new?: boolean;
  /** 是否幂等跳过 */
  skipped?: boolean;
  /** 是否覆盖更新 */
  overwrote_existing?: boolean;
  /** 写入失败时：失败步骤或消息 */
  step?: string;
  message?: string;
  reason?: string;
  /** Graphiti 类型 ID */
  type_id?: string;
  /** 原始 payload（可选） */
  payload?: Record<string, any>;
}

export interface Candidate {
  id: string;
  term: string;
  canonical_label?: string;
  term_type: string;
  synonyms?: string[];
  definition?: string;
  domain_id?: string;
  status: CandidateStatus;
  quality_tier?: QualityTier;
  total_score?: number;
  run_id?: string;
  provenance?: {
    [k: string]: any;
    /** USL 写回术语 ID */
    writeback_usl_term_id?: string;
    /** Graphiti（Ontology）双写回状态 */
    graphiti_writeback?: GraphitiWritebackStatus;
    /** 若 Graphiti 写入成功，自动创建或关联的 Ontology ID */
    graphiti_ontology_id?: string;
    /** 若 Graphiti 写入成功，写入的 ObjectType/LinkType/ActionType 等 ID */
    graphiti_type_id?: string;
    /** 操作人（admin ID） */
    promoted_by_admin?: string;
  };
  custom_attributes?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export type QualityTier = 'VERY_HIGH' | 'HIGH' | 'MEDIUM' | 'LOW' | 'VERY_LOW';

export const QUALITY_TIER_LABEL: Record<QualityTier, string> = {
  VERY_HIGH: '极高',
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低',
  VERY_LOW: '极低',
};

export const QUALITY_TIER_COLOR: Record<QualityTier, string> = {
  VERY_HIGH: 'green',
  HIGH: 'lime',
  MEDIUM: 'gold',
  LOW: 'orange',
  VERY_LOW: 'red',
};

export interface SubMetric {
  submetric: string;
  score: number;
  reason?: string;
  rule_name?: string;
}

export interface SubMetricsGroup {
  gate1: SubMetric[];
  gate2: SubMetric[];
  gate3: SubMetric[];
}

export interface QualityReport {
  report_id: string;
  candidate_id: string;
  run_id?: string;
  generated_at: string;
  gate1_score: number;
  gate2_score: number;
  gate3_score: number;
  total_score: number;
  tier: QualityTier;
  submetrics: SubMetricsGroup;
  overall: 'PASS' | 'REVIEW' | 'FAIL';
  recommend_auto_skip: boolean;
}

export interface ApprovalTask {
  task_id: string;
  task_type: string;
  title: string;
  priority: 'P0' | 'P1' | 'P2' | 'P3';
  status: CandidateStatus;
  assigned_role: 'schema_auditor' | 'admin';
  assignee_user_id?: string;
  candidate_id: string;
  domain_id?: string;
  created_at: string;
  due_at?: string;
}

export interface ApprovalAuditPayload {
  comment?: string;
  decisions?: Record<string, any>;
}

export interface ApprovalModifyPayload {
  candidate_patch: Record<string, any>;
  editor_comment?: string;
}

export interface ApprovalRejectPayload {
  reason?: string;
  close_task?: boolean;
}

export interface ApprovalFinalApprovePayload {
  comment?: string;
  auto_promote?: boolean;
  writeback_now?: boolean;
}

export interface ApprovalTaskResponse {
  task_id: string;
  candidate_id: string;
  new_status: string;
  message?: string;
  promote_to_usl?: Record<string, any>;
  updated_fields?: string[];
  close_task?: boolean;
}

export interface DashboardViewDailyPoint {
  date: string;
  new: number;
  approved: number;
  rejected: number;
}

export interface DashboardViewAccum {
  date: string;
  total: number;
}

export interface DashboardResponse {
  range: string;
  total_candidates: number;
  by_status: Record<string, number>;
  by_tier: Record<string, number>;
  by_quality_gate: Record<string, number>;
  avg_gate_scores: {
    gate1_avg: number;
    gate2_avg: number;
    gate3_avg: number;
    total_avg: number;
  };
  approval_times: {
    l1_avg_secs: number;
    l2_avg_secs: number;
    total_avg_secs: number;
    l1_samples: number;
    l2_samples: number;
    total_samples: number;
  };
  generated_at?: string;
  days?: number;
  workspace_id?: string;
  domain_id?: string;
  daily_points?: DashboardViewDailyPoint[];
  accumulative_new?: DashboardViewAccum[];
  by_role?: Record<string, number>;
  by_decision?: Record<string, number>;
  by_outcome?: Record<string, number>;
  avg_l1_seconds?: number;
  avg_l2_seconds?: number;
  usl_domains?: number;
  usl_terms?: number;
  usl_edges?: number;
  approved_this_week?: number;
  pipeline_7d_success_rate?: number;
}
