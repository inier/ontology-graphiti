/**
 * ConflictResolver 类型定义
 * 对应后端 /api/ontology/conflict/* 接口契约
 */

export type ConflictStrategy = 'first_wins' | 'last_wins' | 'llm_judge' | 'manual';

export type ConflictStatus = 'pending' | 'resolved' | 'awaiting_human';

export type ConflictType = 'value_mismatch' | string;

export interface SourceEntityField {
  id: string;
  type: string;
  fields: Record<string, unknown>;
}

export interface ConflictSource {
  source_id: string;
  entities: SourceEntityField[];
}

export interface ConflictCandidate {
  source_id: string;
  value: unknown;
  confidence: number;
  observed_at: string;
}

export interface ChosenCandidate {
  source_id: string;
  value: unknown;
  confidence: number;
}

export interface ConflictRecord {
  id: string;
  entity_id: string;
  entity_type: string;
  field_name: string;
  conflict_type: ConflictType;
  candidates: ConflictCandidate[];
  status: ConflictStatus;
  strategy: ConflictStrategy | null;
  chosen: ChosenCandidate | null;
  detected_at: string;
  rationale?: string | null;
}

export interface DetectConflictsRequest {
  sources: ConflictSource[];
}

export interface DetectConflictsResponse {
  conflicts: ConflictRecord[];
  count: number;
}

export interface ResolveConflictRequest {
  conflict: ConflictRecord;
  strategy: ConflictStrategy;
  context?: Record<string, unknown>;
}

export interface ResolveConflictResponse {
  conflict_id: string;
  status: ConflictStatus;
  chosen: ChosenCandidate | null;
  rationale: string | null;
  strategy_used: ConflictStrategy;
  duration_ms: number;
}

export interface ListConflictsResponse {
  conflicts: ConflictRecord[];
  count: number;
  status: ConflictStatus;
}

export const STRATEGY_OPTIONS: { value: ConflictStrategy; label: string; description: string }[] = [
  { value: 'first_wins', label: 'First-Wins（首个源胜出）', description: '使用 candidates[0]' },
  { value: 'last_wins', label: 'Last-Wins（最后源胜出）', description: '使用 candidates[-1]' },
  { value: 'llm_judge', label: 'LLM Judge（模型判断）', description: '调用 LLM 仲裁' },
  { value: 'manual', label: 'Manual（人工）', description: '标记为 awaiting_human' },
];
