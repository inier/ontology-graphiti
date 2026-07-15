export interface ResolvedNames {
  workspace_name: string;
  role_names: Record<string, string>;
  object_names: Record<string, string>;
  process_names: Record<string, string>;
  rule_names: Record<string, string>;
  logic_names: Record<string, string>;
  indicator_names: Record<string, string>;
  skill_names: Record<string, string>;
  knowledge_base_names: Record<string, string>;
}

export interface Agent {
  agent_id: string;
  name: string;
  display_name: string;
  avatar: string;
  description: string;
  main_object: string;
  related_objects: string[];
  related_processes: string[];
  related_rules: string[];
  related_business_logic: string[];
  related_indicators: string[];
  related_skills: string[];
  related_knowledge_bases: string[];
  allowed_roles: string[];
  workspace_id?: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  resolved_names?: ResolvedNames;
  /** @deprecated 使用 resolved_names 替代 */
  ref_labels?: Record<string, string>;
}

export interface AgentFormData {
  name: string;
  display_name: string;
  avatar: string;
  description: string;
  main_object: string;
  related_objects: string[];
  related_processes: string[];
  related_rules: string[];
  related_business_logic: string[];
  related_indicators: string[];
  related_skills: string[];
  related_knowledge_bases: string[];
  allowed_roles: string[];
  workspace_id?: string;
}

export interface AgentRefOption {
  id: string;
  name: string;
  type: 'entity' | 'process' | 'rule' | 'business_logic' | 'indicator' | 'skill' | 'knowledge_base' | 'role';
}
