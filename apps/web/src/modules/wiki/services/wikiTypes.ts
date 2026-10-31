/**
 * LLM Wiki 模块类型契约（对应 SPEC §5 API 与 §6 表结构）
 *
 * 这些类型是前后端共享契约的前端侧实现；字段名与 openapi-v2.yaml 保持一致（snake_case）。
 */

export type WikiEntryStatus = 'draft' | 'review' | 'published' | 'superseded' | 'archived';

export interface WikiEntry {
  id: string;
  title: string;
  status: WikiEntryStatus;
  owner_id: string;
  version: string;
  source_ref: string | null;
  superseded_by: string | null;
  content_hash: string;
  last_verified: string;
  tags: string[];
  concept_refs: string[];
  workspace_id: string;
  created_at: string;
  updated_at: string;
}

export interface WikiEntryList {
  data: WikiEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface WikiVersion {
  id: string;
  entry_id: string;
  version: string;
  content: string;
  content_hash: string;
  author_id: string;
  change_note: string;
  created_at: string;
}

export interface WikiVersionList {
  data: WikiVersion[];
  total: number;
}

/** 引用类型（SPEC §6 wiki_citations.kind） */
export type CitationKind = 'doc' | 'tbox_node' | 'metric' | 'graph_edge' | 'opa_decision';

export interface CitationRef {
  kind: CitationKind;
  ref: string;
  label: string;
}

/** 引用关系图（AC-06：必须返回 outgoing[] 与 incoming[]） */
export interface ReferenceGraph {
  entry_id: string;
  outgoing: CitationRef[];
  incoming: CitationRef[];
}

/** 去重候选（AC-14） */
export interface DedupeCandidate {
  left_id: string;
  right_id: string;
  left_title: string;
  right_title: string;
  similarity: number;
  reason: string;
  content_hash: string;
  conflicting_fields: string[];
}

export interface DedupeCandidateList {
  data: DedupeCandidate[];
  total: number;
}

/** 列表查询参数 */
export interface WikiListQuery {
  status?: WikiEntryStatus | 'all';
  owner?: string;
  tag?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}

/** 合并动作请求（AC-07：只置 superseded，禁止物理删除） */
export interface WikiMergeRequest {
  keep_id: string;
  discard_id: string;
  /** 冲突字段的取值决策：字段名 → 采用哪一侧 */
  field_choices: Record<string, 'left' | 'right'>;
  note: string;
}
