export type ServiceCategory =
  | 'llm'
  | 'graph_db'
  | 'object_storage'
  | 'search'
  | 'policy_engine'
  | 'cache'
  | 'auth'
  | 'mcp'
  | 'crawl'
  | 'oauth'
  | 'general';

export type ConfigValueType =
  | 'string'
  | 'integer'
  | 'float'
  | 'boolean'
  | 'url'
  | 'password';

export type ConnectionStatus =
  | 'unknown'
  | 'connected'
  | 'disconnected'
  | 'not_configured';

export interface ConfigItem {
  key: string;
  display_value?: string;
  value_type: ConfigValueType;
  label: string;
  description: string;
  is_sensitive: boolean;
  is_required: boolean;
  default_value?: string;
  choices: string[];
  min_val?: number;
  max_val?: number;
  sort_order: number;
  group: string;
  has_value: boolean;
}

export interface ServiceConfig {
  category: ServiceCategory;
  label: string;
  description: string;
  icon: string;
  items: ConfigItem[];
  connection_status: ConnectionStatus;
  last_tested_at?: string;
  last_error?: string;
}

export interface ConfigValidationResult {
  category: ServiceCategory;
  success: boolean;
  message: string;
  response_time_ms: number;
  tested_at: string;
}

export interface UpdateConfigRequest {
  items: Array<{ key: string; value: string }>;
  test_connection: boolean;
}

export interface UpdateConfigResponse {
  status: string;
  saved_count: number;
  revision_number: number;
  validation_results: ConfigValidationResult[];
  message?: string;
}

export interface ConfigChange {
  key: string;
  old_value?: string;
  new_value?: string;
  is_sensitive: boolean;
}

export interface ConfigRevision {
  id: string;
  revision_number: number;
  operator_id: string;
  operator_name: string;
  changed_at: string;
  changes: ConfigChange[];
}
