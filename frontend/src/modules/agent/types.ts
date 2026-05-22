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
  created_by: string;
  created_at: string;
  updated_at: string;
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
}

export interface AgentRefOption {
  id: string;
  name: string;
  type: 'entity' | 'process' | 'rule' | 'business_logic' | 'indicator' | 'skill' | 'knowledge_base' | 'role';
}
