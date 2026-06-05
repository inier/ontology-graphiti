export interface AttributeSemantic {
  description: string;
  category: 'basic' | 'statistical' | 'capability' | 'constraint' | 'meta' | 'vector';
  dataOrigin: 'structured' | 'unstructured' | 'computed' | 'inferred';
}

export interface EntityAttribute {
  name: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'vector' | 'json' | 'array';
  value: any;
  source: 'structured' | 'unstructured' | 'computed' | 'inferred';
  semantic: AttributeSemantic;
  vector_id?: string;
  isNested?: boolean;
  children?: EntityAttribute[];
}

export interface ManagedEntity {
  entity_id: string;
  name: string;
  type: string;
  name_en?: string;
  attributes: EntityAttribute[];
  relation_count: number;
  created_at: string;
  updated_at: string;
  source_doc?: string;
  source_type?: string;
  confidence?: number;
  basic_properties?: Record<string, any>;
  statistical_properties?: Record<string, any>;
  capabilities?: Record<string, any>;
  constraints?: any[];
}

export interface ExtractionSource {
  doc_id: string;
  doc_type: string;
  source_type: string;
  title: string;
  description: string;
  collected_at: string;
  confidence: number;
  url?: string;
}

export interface ObjectType {
  type_id: string;
  name: string;
  display_name: string;
  description: string;
  properties: Array<{ name: string; property_type: string; required: boolean }>;
  links: Array<{ name: string; source_type: string; target_type: string }>;
  actions: string[];
  is_active: boolean;
  icon: string;
  color: string;
}

export const ATTRIBUTE_SEMANTICS: Record<string, AttributeSemantic> = {
  side: { description: '所属阵营/方', category: 'basic', dataOrigin: 'structured' },
  location: { description: '当前位置', category: 'basic', dataOrigin: 'structured' },
  status: { description: '当前状态', category: 'basic', dataOrigin: 'structured' },
  unit_type: { description: '单位类型', category: 'basic', dataOrigin: 'structured' },
  equipment: { description: '装备配置', category: 'basic', dataOrigin: 'structured' },
  time_period: { description: '时间段', category: 'basic', dataOrigin: 'structured' },
  weather: { description: '天气条件', category: 'basic', dataOrigin: 'structured' },
  terrain: { description: '地形类型', category: 'basic', dataOrigin: 'structured' },
  name_en: { description: '英文名称', category: 'basic', dataOrigin: 'structured' },
  combat_power: { description: '战斗力指数 (0-1)', category: 'statistical', dataOrigin: 'computed' },
  morale: { description: '士气指数 (0-1)', category: 'statistical', dataOrigin: 'computed' },
  supply_level: { description: '补给水平 (0-1)', category: 'statistical', dataOrigin: 'computed' },
  casualty_rate: { description: '伤亡率', category: 'statistical', dataOrigin: 'computed' },
  fire_range_km: { description: '火力射程(公里)', category: 'capability', dataOrigin: 'structured' },
  armor_penetration: { description: '穿甲能力', category: 'capability', dataOrigin: 'structured' },
  air_defense: { description: '防空能力', category: 'capability', dataOrigin: 'structured' },
  embedding: { description: '文本向量嵌入', category: 'vector', dataOrigin: 'unstructured' },
  vector_id: { description: '向量存储标识', category: 'vector', dataOrigin: 'unstructured' },
  content_vector: { description: '内容向量表示', category: 'vector', dataOrigin: 'unstructured' },
  text_embedding: { description: '文本语义向量', category: 'vector', dataOrigin: 'unstructured' },
  source_doc_id: { description: '来源文档ID', category: 'meta', dataOrigin: 'structured' },
  created_at: { description: '创建时间', category: 'meta', dataOrigin: 'structured' },
  updated_at: { description: '更新时间', category: 'meta', dataOrigin: 'structured' },
  scenario_id: { description: '所属场景', category: 'meta', dataOrigin: 'structured' },
  workspace_id: { description: '所属工作空间', category: 'meta', dataOrigin: 'structured' },
  confidence: { description: '抽取置信度', category: 'meta', dataOrigin: 'inferred' },
};

export const TYPE_COLORS: Record<string, string> = {
  Unit: 'red',
  Equipment: 'orange',
  Location: 'green',
  Person: 'purple',
  Organization: 'cyan',
  EventNode: 'magenta',
  Event: 'volcano',
  Document: 'geekblue',
  EntityType: 'blue',
  Relation: 'lime',
  default: 'default',
};

export const TYPE_LABELS: Record<string, string> = {
  Unit: '作战单元',
  Equipment: '装备',
  Location: '地点',
  Person: '人员',
  Organization: '组织',
  EventNode: '事件节点',
  Event: '事件',
  Document: '文档',
  EntityType: '实体类型',
  Relation: '关系',
};

export const CATEGORY_COLORS: Record<string, string> = {
  basic: 'blue',
  statistical: 'cyan',
  capability: 'purple',
  constraint: 'red',
  meta: 'default',
  vector: 'orange',
};

export const CATEGORY_LABELS: Record<string, string> = {
  basic: '基础属性',
  statistical: '统计属性',
  capability: '能力属性',
  constraint: '约束条件',
  meta: '元信息',
  vector: '向量存储',
};

export const SOURCE_COLORS: Record<string, string> = {
  structured: 'blue',
  unstructured: 'orange',
  computed: 'green',
  inferred: 'purple',
};

export const SOURCE_LABELS: Record<string, string> = {
  structured: '结构化',
  unstructured: '非结构化',
  computed: '计算得出',
  inferred: '推理得出',
};

export const ATTR_ICONS: Record<string, string> = {
  string: 'FieldStringOutlined',
  number: 'NumberOutlined',
  date: 'CalendarOutlined',
  boolean: 'TagOutlined',
  vector: 'DatabaseOutlined',
  json: 'BranchesOutlined',
  array: 'ClusterOutlined',
};

export function getAttributeSemantic(name: string): AttributeSemantic {
  if (ATTRIBUTE_SEMANTICS[name]) {
    return ATTRIBUTE_SEMANTICS[name];
  }
  for (const [key, semantic] of Object.entries(ATTRIBUTE_SEMANTICS)) {
    if (name.toLowerCase().includes(key.toLowerCase()) || key.toLowerCase().includes(name.toLowerCase())) {
      return semantic;
    }
  }
  let category: AttributeSemantic['category'] = 'basic';
  let dataOrigin: AttributeSemantic['dataOrigin'] = 'structured';

  if (name.includes('vector') || name.includes('embedding')) {
    category = 'vector';
    dataOrigin = 'unstructured';
  } else if (name.includes('count') || name.includes('rate') || name.includes('power') || name.includes('level') || name.includes('score')) {
    category = 'statistical';
    dataOrigin = 'computed';
  } else if (name.includes('cap') || name.includes('ability') || name.includes('range') || name.includes('defense')) {
    category = 'capability';
  } else if (name.includes('id') || name.includes('at') || name.includes('time') || name.includes('source')) {
    category = 'meta';
  }

  return { description: name, category, dataOrigin };
}

export function detectValueType(value: any): EntityAttribute['type'] {
  if (value === null || value === undefined) return 'string';
  if (typeof value === 'number') return 'number';
  if (typeof value === 'boolean') return 'boolean';
  if (value instanceof Date) return 'date';
  if (typeof value === 'string') {
    if (/^\d{4}-\d{2}-\d{2}/.test(value)) return 'date';
    if (value.includes('vector') || value.includes('embedding')) return 'vector';
    return 'string';
  }
  if (Array.isArray(value)) return 'array';
  if (typeof value === 'object') return 'json';
  return 'string';
}

export function parsePropertiesToAttributes(
  properties: Record<string, any>,
  parentPrefix: string = ''
): EntityAttribute[] {
  const attrs: EntityAttribute[] = [];
  const META_KEYS = new Set(['workspace_id', 'source_type', 'scenario_id', 'ingest_id', 'original_entity_id']);

  for (const [key, val] of Object.entries(properties)) {
    if (META_KEYS.has(key)) continue;
    const fullName = parentPrefix ? `${parentPrefix}.${key}` : key;
    const semantic = getAttributeSemantic(key);
    const attrType = detectValueType(val);

    let source: EntityAttribute['source'] = semantic.dataOrigin;
    let vectorId: string | undefined;

    if (key.includes('vector') || key.includes('embedding')) {
      source = 'unstructured';
      vectorId = typeof val === 'string' ? val.substring(0, 24) : undefined;
    }

    if (attrType === 'json' && val !== null && typeof val === 'object' && !Array.isArray(val)) {
      attrs.push({
        name: fullName,
        type: 'json',
        value: val,
        source,
        semantic: { ...semantic, description: `${semantic.description} (对象)` },
        isNested: true,
        children: parsePropertiesToAttributes(val, fullName),
      });
    } else {
      attrs.push({
        name: fullName,
        type: attrType,
        value: val,
        source,
        semantic,
        vector_id: vectorId,
      });
    }
  }

  return attrs;
}
