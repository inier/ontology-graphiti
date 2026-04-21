export interface Scenario {
  scenario_id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at?: string;
  doc_count?: number;
  event_count?: number;
  entity_count?: number;
}

export interface Entity {
  entity_id: string;
  entity_type: string;
  name: string;
  name_en?: string;
  basic_properties: Record<string, unknown>;
  statistical_properties?: Record<string, unknown>;
  capabilities?: Record<string, unknown>;
}

export interface Relation {
  relation_id: string;
  relation_type: string;
  source_entity: string;
  target_entity: string;
  properties?: Record<string, unknown>;
  temporal?: {
    start_time: string;
    end_time?: string;
    is_current: boolean;
  };
}

export interface TimelineEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  location?: string;
  coordinates?: number[];
  participants: string[];
  description: string;
  outcome?: Record<string, unknown>;
  phase?: string;
}

export interface Version {
  version_id: string;
  parent_version?: string | null;
  commit_message: string;
  created_at: string;
  schema_version: string;
  doc_id?: string;
  doc_type?: string;
  entity_count?: number;
  relation_count?: number;
  event_count?: number;
}

export interface DiffResult {
  version_a: string;
  version_b: string;
  added: Record<string, unknown>[];
  removed: Record<string, unknown>[];
  modified: Record<string, { old: unknown; new: unknown }>[];
}

export interface PipelineStats {
  ingest_count: number;
  error_count: number;
  version_count: number;
  latest_version: string;
}

export interface Stats {
  pipeline: PipelineStats;
  scenarios: number;
  ws_clients: number;
}
