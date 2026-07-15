export interface Scenario {
  scenario_id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, any>;
  entity_count?: number;
  doc_count?: number;
}

export interface Entity {
  id: string;
  name: string;
  type: string;
  properties?: Record<string, any>;
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
  metadata?: Record<string, any>;
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
    changes: Record<string, any>;
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