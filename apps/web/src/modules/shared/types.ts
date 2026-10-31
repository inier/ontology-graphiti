/**
 * 场景（Scenario）—— 对齐后端 `ScenarioResponse`
 * （apps/api/odap/biz/platform/workspace/api/schemas.py:231）。
 *
 * 必需字段与后端逐项一致，缺字段会让 App / 场景列表只能靠 `as` 断言通过。
 */
export interface Scenario {
  scenario_id: string;
  name: string;
  description: string;
  workspace_id: string;
  status: string;
  tags?: string[];
  ontology_id?: string;
  ontology_ids?: string[];
  current_ontology_version?: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
  entity_count?: number;
  doc_count?: number;
  event_count?: number;
}

export interface Entity {
  id: string;
  name: string;
  /** 可选展示名（部分接口返回 name_en / display_name） */
  display_name?: string;
  type: string;
  properties?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TimelineEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  description: string;
  participants: string[];
  location?: string;
}

export interface Version {
  version_id: string;
  scenario_id: string;
  description: string;
  created_at: string;
  created_by: string;
  metadata?: Record<string, unknown>;
}

export interface DiffResult {
  added: Array<{
    type: string;
    id: string;
    name: string;
  }>;
  removed: Array<{
    type: string;
    id: string;
    name: string;
  }>;
  modified: Array<{
    type: string;
    id: string;
    name: string;
    changes: Record<string, unknown>;
  }>;
}

export interface Stats {
  total_scenarios: number;
  total_entities: number;
  total_events: number;
  total_versions: number;
  recent_activities: Array<{
    type: string;
    timestamp: string;
    description: string;
  }>;
  pipeline?: {
    ingest_count: number;
    error_count: number;
    version_count: number;
    latest_version: string;
  };
  scenarios?: number;
  ws_clients?: number;
}

export interface MapUnit {
  id: string;
  name: string;
  side: 'blue' | 'red' | 'neutral';
  position: [number, number];
  type: string;
  status: string;
}