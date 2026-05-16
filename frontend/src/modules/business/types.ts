export interface BusinessProcess {
  process_id: string;
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  flow_nodes: FlowNode[];
  status: 'draft' | 'published' | 'deprecated';
  created_by: string;
  created_at: string;
  updated_at: string;
  yaml_definition?: string;
}

export interface FlowNode {
  node_id: string;
  name: string;
  order: number;
  type: 'start' | 'task' | 'decision' | 'end';
  description?: string;
}

export interface BusinessProcessFormData {
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  flow_nodes: FlowNode[];
  yaml_definition?: string;
}

// 业务规则
export interface BusinessRule {
  rule_id: string;
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  rule_conditions: RuleCondition[];
  status: 'draft' | 'published' | 'deprecated';
  created_by: string;
  created_at: string;
  updated_at: string;
  yaml_definition?: string;
}

export interface RuleCondition {
  condition_id: string;
  trigger_event: string;
  requirement: string;
  order: number;
}

export interface BusinessRuleFormData {
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  rule_conditions: RuleCondition[];
  yaml_definition?: string;
}

// 业务逻辑
export interface BusinessLogic {
  logic_id: string;
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  logic_type: 'filter' | 'transform' | 'validate' | 'compute';
  logic_expression: string;
  status: 'draft' | 'published' | 'deprecated';
  created_by: string;
  created_at: string;
  updated_at: string;
  yaml_definition?: string;
}

export interface BusinessLogicFormData {
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  logic_type: 'filter' | 'transform' | 'validate' | 'compute';
  logic_expression: string;
  yaml_definition?: string;
}

// 业务指标
export interface BusinessIndicator {
  indicator_id: string;
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  indicator_type: 'kpi' | 'metric' | 'dimension';
  calculation_formula: string;
  unit: string;
  status: 'draft' | 'published' | 'deprecated';
  created_by: string;
  created_at: string;
  updated_at: string;
  yaml_definition?: string;
}

export interface BusinessIndicatorFormData {
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  indicator_type: 'kpi' | 'metric' | 'dimension';
  calculation_formula: string;
  unit: string;
  yaml_definition?: string;
}

// 通用业务实体类型
export type BusinessEntityType = 'process' | 'rule' | 'logic' | 'indicator';

export interface BusinessEntity {
  id: string;
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  entity_type: BusinessEntityType;
  status: 'draft' | 'published' | 'deprecated';
  created_by: string;
  created_at: string;
  updated_at: string;
  yaml_definition?: string;
  // 扩展字段
  flow_nodes?: FlowNode[];
  rule_conditions?: RuleCondition[];
  logic_type?: string;
  logic_expression?: string;
  indicator_type?: string;
  calculation_formula?: string;
  unit?: string;
}

export interface BusinessEntityFormData {
  name: string;
  display_name: string;
  description: string;
  related_objects: string[];
  llm_description: string;
  yaml_definition?: string;
  // 扩展字段
  flow_nodes?: FlowNode[];
  rule_conditions?: RuleCondition[];
  logic_type?: string;
  logic_expression?: string;
  indicator_type?: string;
  calculation_formula?: string;
  unit?: string;
}
