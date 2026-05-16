import { useState, useEffect } from 'react';
import {
  Card, Button, Input, Table, Tag, Space, Drawer, Descriptions,
  Empty, message, Tabs, Statistic, Row, Col, Tooltip, Badge,
  Collapse, Typography, List,
} from 'antd';
import {
  SearchOutlined, EyeOutlined, DatabaseOutlined,
  FieldStringOutlined, NumberOutlined, CalendarOutlined,
  TagOutlined, BranchesOutlined, FileTextOutlined,
  BuildOutlined, InfoCircleOutlined,
  ClusterOutlined, AimOutlined,
} from '@ant-design/icons';
import { api } from '../../shared/services/api';
import { useScenario, useWorkspace } from '../../shared/components/AppLayout';

const { Text, Paragraph } = Typography;
const { Panel } = Collapse;

// ───────────────────────────────────────────────
// 属性语义定义 - 基于 OntologyEntity 四层属性结构
// ───────────────────────────────────────────────

interface AttributeSemantic {
  description: string;
  category: 'basic' | 'statistical' | 'capability' | 'constraint' | 'meta' | 'vector';
  dataOrigin: 'structured' | 'unstructured' | 'computed' | 'inferred';
}

/** 属性语义映射表 - 根据后端 OntologyEntity 结构定义 */
const ATTRIBUTE_SEMANTICS: Record<string, AttributeSemantic> = {
  // 基础属性 (basic_properties)
  side: { description: '所属阵营/方', category: 'basic', dataOrigin: 'structured' },
  location: { description: '当前位置', category: 'basic', dataOrigin: 'structured' },
  status: { description: '当前状态', category: 'basic', dataOrigin: 'structured' },
  unit_type: { description: '单位类型', category: 'basic', dataOrigin: 'structured' },
  equipment: { description: '装备配置', category: 'basic', dataOrigin: 'structured' },
  time_period: { description: '时间段', category: 'basic', dataOrigin: 'structured' },
  weather: { description: '天气条件', category: 'basic', dataOrigin: 'structured' },
  terrain: { description: '地形类型', category: 'basic', dataOrigin: 'structured' },
  name_en: { description: '英文名称', category: 'basic', dataOrigin: 'structured' },

  // 统计属性 (statistical_properties)
  combat_power: { description: '战斗力指数 (0-1)', category: 'statistical', dataOrigin: 'computed' },
  morale: { description: '士气指数 (0-1)', category: 'statistical', dataOrigin: 'computed' },
  supply_level: { description: '补给水平 (0-1)', category: 'statistical', dataOrigin: 'computed' },
  casualty_rate: { description: '伤亡率', category: 'statistical', dataOrigin: 'computed' },

  // 能力属性 (capabilities)
  fire_range_km: { description: '火力射程(公里)', category: 'capability', dataOrigin: 'structured' },
  armor_penetration: { description: '穿甲能力', category: 'capability', dataOrigin: 'structured' },
  air_defense: { description: '防空能力', category: 'capability', dataOrigin: 'structured' },

  // 向量/非结构化属性
  embedding: { description: '文本向量嵌入', category: 'vector', dataOrigin: 'unstructured' },
  vector_id: { description: '向量存储标识', category: 'vector', dataOrigin: 'unstructured' },
  content_vector: { description: '内容向量表示', category: 'vector', dataOrigin: 'unstructured' },
  text_embedding: { description: '文本语义向量', category: 'vector', dataOrigin: 'unstructured' },

  // 元信息
  source_doc_id: { description: '来源文档ID', category: 'meta', dataOrigin: 'structured' },
  created_at: { description: '创建时间', category: 'meta', dataOrigin: 'structured' },
  updated_at: { description: '更新时间', category: 'meta', dataOrigin: 'structured' },
  scenario_id: { description: '所属场景', category: 'meta', dataOrigin: 'structured' },
  workspace_id: { description: '所属工作空间', category: 'meta', dataOrigin: 'structured' },
  confidence: { description: '抽取置信度', category: 'meta', dataOrigin: 'inferred' },
};

/** 获取属性语义 */
function getAttributeSemantic(name: string): AttributeSemantic {
  // 精确匹配
  if (ATTRIBUTE_SEMANTICS[name]) {
    return ATTRIBUTE_SEMANTICS[name];
  }
  // 模糊匹配
  for (const [key, semantic] of Object.entries(ATTRIBUTE_SEMANTICS)) {
    if (name.toLowerCase().includes(key.toLowerCase()) || key.toLowerCase().includes(name.toLowerCase())) {
      return semantic;
    }
  }
  // 默认语义推断
  let category: AttributeSemantic['category'] = 'basic';
  let dataOrigin: AttributeSemantic['dataOrigin'] = 'structured';

  if (name.includes('vector') || name.includes('embedding') || name.includes('embedding')) {
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

  return {
    description: name,
    category,
    dataOrigin,
  };
}

// ───────────────────────────────────────────────
// 类型定义
// ───────────────────────────────────────────────

interface EntityAttribute {
  name: string;
  type: 'string' | 'number' | 'date' | 'boolean' | 'vector' | 'json' | 'array';
  value: any;
  source: 'structured' | 'unstructured' | 'computed' | 'inferred';
  semantic: AttributeSemantic;
  vector_id?: string;
  isNested?: boolean;
  children?: EntityAttribute[];
}

interface ManagedEntity {
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
  // 四层属性结构（来自 OntologyEntity）
  basic_properties?: Record<string, any>;
  statistical_properties?: Record<string, any>;
  capabilities?: Record<string, any>;
  constraints?: any[];
}

interface ExtractionSource {
  doc_id: string;
  doc_type: string;
  source_type: string;
  title: string;
  description: string;
  collected_at: string;
  confidence: number;
  url?: string;
}

// ───────────────────────────────────────────────
// 常量
// ───────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
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

const TYPE_LABELS: Record<string, string> = {
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

const CATEGORY_COLORS: Record<string, string> = {
  basic: 'blue',
  statistical: 'cyan',
  capability: 'purple',
  constraint: 'red',
  meta: 'default',
  vector: 'orange',
};

const CATEGORY_LABELS: Record<string, string> = {
  basic: '基础属性',
  statistical: '统计属性',
  capability: '能力属性',
  constraint: '约束条件',
  meta: '元信息',
  vector: '向量存储',
};

const SOURCE_COLORS: Record<string, string> = {
  structured: 'blue',
  unstructured: 'orange',
  computed: 'green',
  inferred: 'purple',
};

const SOURCE_LABELS: Record<string, string> = {
  structured: '结构化',
  unstructured: '非结构化',
  computed: '计算得出',
  inferred: '推理得出',
};

const ATTR_ICONS: Record<string, React.ReactNode> = {
  string: <FieldStringOutlined />,
  number: <NumberOutlined />,
  date: <CalendarOutlined />,
  boolean: <TagOutlined />,
  vector: <DatabaseOutlined />,
  json: <BranchesOutlined />,
  array: <ClusterOutlined />,
};

// ───────────────────────────────────────────────
// 属性解析工具函数
// ───────────────────────────────────────────────

function detectValueType(value: any): EntityAttribute['type'] {
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

function parsePropertiesToAttributes(
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

    // 检测向量存储
    let source: EntityAttribute['source'] = semantic.dataOrigin;
    let vectorId: string | undefined;

    if (key.includes('vector') || key.includes('embedding')) {
      source = 'unstructured';
      vectorId = typeof val === 'string' ? val.substring(0, 24) : undefined;
    }

    if (attrType === 'json' && val !== null && typeof val === 'object' && !Array.isArray(val)) {
      // 嵌套对象 - 创建父属性 + 子属性
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

// ───────────────────────────────────────────────
// 主组件
// ───────────────────────────────────────────────

export function ObjectManagement() {
  const { currentScenario } = useScenario();
  const { currentWorkspace } = useWorkspace();
  const [entities, setEntities] = useState<ManagedEntity[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [sourceFilter, setSourceFilter] = useState<string>('all');
  const [detailOpen, setDetailOpen] = useState(false);
  const [viewingEntity, setViewingEntity] = useState<ManagedEntity | null>(null);
  const [extractionSources, setExtractionSources] = useState<ExtractionSource[]>([]);
  const [stats, setStats] = useState({
    total: 0,
    types: 0,
    structured: 0,
    unstructured: 0,
    computed: 0,
    inferred: 0,
    byCategory: {} as Record<string, number>,
  });

  useEffect(() => {
    if (currentScenario) {
      loadEntities();
      loadExtractionSources();
    }
  }, [currentScenario]);

  /** 加载实体列表 */
  const loadEntities = async () => {
    if (!currentScenario) return;
    setLoading(true);
    try {
      // 优先使用新版 queryEntities API（需要 workspace_id）
      let result: { entities: Array<{ entity_id: string; name: string; type: string; properties: Record<string, unknown> }>; total: number } | null = null;
      try {
        result = await api.queryEntities({}, currentWorkspace || undefined);
      } catch (e) {
        console.warn('queryEntities 失败，尝试 getEntities', e);
      }

      // 如果新版 API 失败或无数据，回退到旧版 getEntities
      let rawEntities: Array<{ entity_id: string; name: string; type: string; properties: Record<string, unknown> }> = [];
      if (result && result.entities && result.entities.length > 0) {
        rawEntities = result.entities;
      } else {
        try {
          const oldResult = await api.getEntities(currentScenario);
          rawEntities = oldResult.map((e: any) => ({
            entity_id: e.id || e.entity_id,
            name: e.name,
            type: e.type || e.entity_type,
            properties: e.properties || {
              basic: e.basic_properties,
              statistical: e.statistical_properties,
              capabilities: e.capabilities,
            },
          }));
        } catch (e2) {
          console.warn('getEntities 也失败', e2);
        }
      }

      // 2. 获取本体文档以补充详细信息
      let ontologyDocs: Record<string, any>[] = [];
      try {
        ontologyDocs = await api.getOntologyDocuments(currentScenario, 50);
      } catch (e) {
        console.warn('获取本体文档失败', e);
      }

      // 构建文档查找表
      const docMap = new Map<string, any>();
      ontologyDocs.forEach((doc: any) => {
        if (doc.doc_id) docMap.set(doc.doc_id, doc);
        if (doc.entities) {
          doc.entities.forEach((e: any) => {
            if (e.entity_id) docMap.set(e.entity_id, { ...e, _doc: doc });
          });
        }
      });

      const mapped: ManagedEntity[] = rawEntities
        .filter((e: any) => {
          // 对象管理页面完全隐藏所有审计相关实体，只保留业务实体
          const entityType = e.type || e.entity_type;
          const entityId = e.entity_id || e.id;
          const isAuditEntity = 
            entityType?.startsWith('Audit') || 
            entityId?.startsWith('audit_') ||
            entityId?.startsWith('user_') ||
            entityId?.startsWith('resource_') ||
            entityId?.startsWith('service_');
          return !isAuditEntity;
        })
        .map((e: any) => {
        const attrs: EntityAttribute[] = [];

        if (e.properties) {
          if (e.properties.basic && typeof e.properties.basic === 'object') {
            attrs.push(...parsePropertiesToAttributes(e.properties.basic));
          }
          if (e.properties.statistical && typeof e.properties.statistical === 'object') {
            attrs.push(...parsePropertiesToAttributes(e.properties.statistical));
          }
          if (e.properties.capabilities && typeof e.properties.capabilities === 'object') {
            attrs.push(...parsePropertiesToAttributes(e.properties.capabilities));
          }
          if (!e.properties.basic && !e.properties.statistical && !e.properties.capabilities) {
            attrs.push(...parsePropertiesToAttributes(e.properties));
          }
        }

        if (e.basic_properties && typeof e.basic_properties === 'object') {
          const bp = e.basic_properties;
          if (bp.properties && typeof bp.properties === 'object') {
            const existingKeys = new Set(attrs.map(a => a.name));
            for (const [key, val] of Object.entries(bp.properties)) {
              if (!existingKeys.has(key) && key !== 'workspace_id' && key !== 'source_type' && key !== 'scenario_id' && key !== 'ingest_id' && key !== 'original_entity_id') {
                const semantic = getAttributeSemantic(key);
                attrs.push({
                  name: key,
                  type: detectValueType(val),
                  value: val,
                  source: semantic.dataOrigin,
                  semantic,
                });
              }
            }
          }
        }

        const originalEntity = docMap.get(e.entity_id);
        const doc = originalEntity?._doc;

        return {
          entity_id: e.entity_id || e.id,
          name: e.name,
          type: e.type || e.entity_type || 'Unknown',
          name_en: originalEntity?.name_en || e.name_en,
          attributes: attrs,
          relation_count: e.relation_count || 0,
          created_at: doc?.source?.collected_at || new Date().toISOString(),
          updated_at: new Date().toISOString(),
          source_doc: doc?.doc_id,
          source_type: e.properties?.source_type || e.basic_properties?.properties?.source_type || doc?.source?.type || 'random',
          confidence: doc?.source?.confidence || originalEntity?.confidence,
          basic_properties: originalEntity?.basic_properties || e.properties?.basic,
          statistical_properties: originalEntity?.statistical_properties || e.properties?.statistical,
          capabilities: originalEntity?.capabilities || e.properties?.capabilities,
          constraints: originalEntity?.constraints,
        };
      });

      setEntities(mapped);

      // 统计
      const typeSet = new Set(mapped.map(e => e.type));
      const categoryCount: Record<string, number> = {};
      let structuredCount = 0;
      let unstructuredCount = 0;
      let computedCount = 0;
      let inferredCount = 0;

      mapped.forEach(e => {
        e.attributes.forEach(a => {
          categoryCount[a.semantic.category] = (categoryCount[a.semantic.category] || 0) + 1;
          if (a.source === 'structured') structuredCount++;
          if (a.source === 'unstructured') unstructuredCount++;
          if (a.source === 'computed') computedCount++;
          if (a.source === 'inferred') inferredCount++;
        });
      });

      setStats({
        total: mapped.length,
        types: typeSet.size,
        structured: structuredCount,
        unstructured: unstructuredCount,
        computed: computedCount,
        inferred: inferredCount,
        byCategory: categoryCount,
      });
    } catch (e) {
      message.error('加载实体列表失败');
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  /** 加载抽取来源信息 */
  const loadExtractionSources = async () => {
    if (!currentScenario) return;
    try {
      const docs = await api.getOntologyDocuments(currentScenario, 20);
      const sources: ExtractionSource[] = docs.map((doc: any) => ({
        doc_id: doc.doc_id || doc.id,
        doc_type: doc.doc_type || 'unknown',
        source_type: doc.source?.type || 'unknown',
        title: doc.meta?.title || '未命名',
        description: doc.meta?.description || '',
        collected_at: doc.source?.collected_at || '',
        confidence: doc.source?.confidence || 1.0,
        url: doc.source?.url,
      }));
      setExtractionSources(sources);
    } catch (e) {
      console.warn('加载抽取来源失败', e);
    }
  };

  const handleView = (entity: ManagedEntity) => {
    setViewingEntity(entity);
    setDetailOpen(true);
  };

  const entityTypes = Array.from(new Set(entities.map(e => e.type)));

  const filteredEntities = entities.filter(e => {
    const matchSearch = !searchText ||
      e.name.toLowerCase().includes(searchText.toLowerCase()) ||
      e.type.toLowerCase().includes(searchText.toLowerCase()) ||
      e.attributes.some(a => a.name.toLowerCase().includes(searchText.toLowerCase())) ||
      e.attributes.some(a => a.semantic.description.includes(searchText));
    const matchType = typeFilter === 'all' || e.type === typeFilter;
    const matchSource = sourceFilter === 'all' || e.source_type === sourceFilter;
    return matchSearch && matchType && matchSource;
  });

  // ─── 表格列定义 ───
  const columns = [
    {
      title: '实体ID',
      dataIndex: 'entity_id',
      width: 160,
      render: (id: string) => (
        <Text code copyable style={{ fontSize: 12 }}>{id}</Text>
      ),
    },
    {
      title: '实体名称',
      dataIndex: 'name',
      render: (name: string, record: ManagedEntity) => (
        <div>
          <div style={{ fontWeight: 600 }}>{name}</div>
          {record.name_en && (
            <div style={{ fontSize: 12, color: '#8c8c8c' }}>{record.name_en}</div>
          )}
        </div>
      ),
    },
    {
      title: '所属对象类型',
      dataIndex: 'type',
      width: 140,
      render: (type: string) => (
        <Tooltip title={`对象类型: ${TYPE_LABELS[type] || type} — 该实体是此对象类型的一个实例`}>
          <Tag color={TYPE_COLORS[type] || TYPE_COLORS.default} style={{ fontSize: 13, padding: '2px 8px' }}>
            {TYPE_LABELS[type] || type}
          </Tag>
        </Tooltip>
      ),
    },
    {
      title: '属性分布',
      dataIndex: 'attributes',
      width: 200,
      render: (attrs: EntityAttribute[]) => {
        const byCategory: Record<string, number> = {};
        attrs.forEach(a => {
          byCategory[a.semantic.category] = (byCategory[a.semantic.category] || 0) + 1;
        });
        return (
          <Space size={4} wrap>
            {Object.entries(byCategory).map(([cat, count]) => (
              <Tooltip key={cat} title={`${CATEGORY_LABELS[cat] || cat}: ${count}个`}>
                <Tag color={CATEGORY_COLORS[cat] || 'default'} style={{ fontSize: 11 }}>
                  {CATEGORY_LABELS[cat]?.charAt(0) || cat.charAt(0)}{count}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        );
      },
    },
    {
      title: '数据来源',
      dataIndex: 'source_type',
      width: 120,
      render: (sourceType: string, record: ManagedEntity) => (
        <Space direction="vertical" size={2}>
          <Tag color="default" style={{ fontSize: 11 }}>
            {sourceType === 'random' ? '随机生成' :
             sourceType === 'random_gen' ? '随机生成' :
             sourceType === 'news_ingest' ? '新闻采集' :
             sourceType === 'manual' ? '手动录入' :
             sourceType === 'simulation' ? '模拟推演' :
             sourceType}
          </Tag>
          {record.confidence !== undefined && (
            <Tooltip title={`抽取置信度: ${(record.confidence * 100).toFixed(0)}%`}>
              <Badge
                color={record.confidence > 0.8 ? 'green' : record.confidence > 0.5 ? 'orange' : 'red'}
                text={`${(record.confidence * 100).toFixed(0)}%`}
              />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      width: 80,
      fixed: 'right' as const,
      render: (_: unknown, record: ManagedEntity) => (
        <Button
          type="text"
          icon={<EyeOutlined />}
          onClick={() => handleView(record)}
          title="查看详情"
        />
      ),
    },
  ];

  // ─── 渲染属性卡片 ───
  const renderAttributeCard = (attr: EntityAttribute) => {
    const isVector = attr.type === 'vector' || attr.semantic.category === 'vector';
    const isNested = attr.isNested && attr.children && attr.children.length > 0;

    return (
      <Card
        key={attr.name}
        size="small"
        style={{ marginBottom: 8 }}
        title={
          <Space wrap>
            {ATTR_ICONS[attr.type]}
            <span style={{ fontWeight: 600 }}>{attr.name}</span>
            <Tooltip title={attr.semantic.description}>
              <Tag color={CATEGORY_COLORS[attr.semantic.category]}>
                {CATEGORY_LABELS[attr.semantic.category]}
              </Tag>
            </Tooltip>
            <Tag color={SOURCE_COLORS[attr.source]}>
              {SOURCE_LABELS[attr.source]}
            </Tag>
            <Tag style={{ fontSize: 11 }}>{attr.type}</Tag>
          </Space>
        }
      >
        <div style={{ fontFamily: 'monospace', fontSize: 13, wordBreak: 'break-all' }}>
          {/* 属性语义说明 */}
          <div style={{ marginBottom: 8, padding: '4px 8px', background: '#f6ffed', borderRadius: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <InfoCircleOutlined style={{ marginRight: 4 }} />
              {attr.semantic.description}
            </Text>
          </div>

          {isVector ? (
            <div>
              <div style={{ color: '#8c8c8c', marginBottom: 4 }}>
                <DatabaseOutlined style={{ marginRight: 4 }} />
                向量存储标识:
              </div>
              <Text code copyable style={{ fontSize: 12 }}>
                {attr.vector_id || String(attr.value)}
              </Text>
              <div style={{ marginTop: 8, color: '#fa8c16', fontSize: 12 }}>
                此属性来自非结构化数据的向量化表示，用于语义检索和RAG查询
              </div>
            </div>
          ) : attr.type === 'json' ? (
            <div>
              {isNested ? (
                <Collapse ghost size="small">
                  <Panel header={`展开 ${attr.children?.length || 0} 个子属性`} key="1">
                    {attr.children?.map(child => renderAttributeCard(child))}
                  </Panel>
                </Collapse>
              ) : (
                <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                  {JSON.stringify(attr.value, null, 2)}
                </pre>
              )}
            </div>
          ) : attr.type === 'array' ? (
            <div>
              <Text type="secondary">数组 ({(attr.value as any[]).length} 项)</Text>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                {JSON.stringify(attr.value, null, 2)}
              </pre>
            </div>
          ) : attr.type === 'boolean' ? (
            <Tag color={attr.value ? 'green' : 'red'}>
              {attr.value ? '是' : '否'}
            </Tag>
          ) : (
            <Text>{String(attr.value)}</Text>
          )}
        </div>
      </Card>
    );
  };

  // ─── 按类别分组的属性视图 ───
  const renderAttributesByCategory = (entity: ManagedEntity) => {
    const grouped: Record<string, EntityAttribute[]> = {};
    entity.attributes.forEach(attr => {
      const cat = attr.semantic.category;
      if (!grouped[cat]) grouped[cat] = [];
      grouped[cat].push(attr);
    });

    return (
      <Collapse defaultActiveKey={Object.keys(grouped)}>
        {Object.entries(grouped).map(([category, attrs]) => (
          <Panel
            key={category}
            header={
              <Space>
                <Tag color={CATEGORY_COLORS[category]}>
                  {CATEGORY_LABELS[category]}
                </Tag>
                <Text type="secondary">{attrs.length} 个属性</Text>
              </Space>
            }
          >
            {attrs.map(attr => renderAttributeCard(attr))}
          </Panel>
        ))}
      </Collapse>
    );
  };

  return (
    <div>
      {/* ─── 统计卡片 ─── */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card>
            <Statistic title="实体总数" value={stats.total} prefix={<AimOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="对象类型数" value={stats.types} prefix={<TagOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="结构化属性"
              value={stats.structured}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="非结构化"
              value={stats.unstructured}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="计算属性"
              value={stats.computed}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="推理属性"
              value={stats.inferred}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* ─── 对象类型分布 ─── */}
      {entityTypes.length > 0 && (
        <Card
          title={
            <Space>
              <ClusterOutlined />
              <span>对象类型分布</span>
              <Tooltip title="对象类型是本体中定义的类型，每个对象类型下可有多个实体实例">
                <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
              </Tooltip>
            </Space>
          }
          style={{ marginBottom: 16 }}
          size="small"
        >
          <Space size={8} wrap>
            {entityTypes.map(type => {
              const count = entities.filter(e => e.type === type).length;
              return (
                <Tag
                  key={type}
                  color={TYPE_COLORS[type] || 'default'}
                  style={{ fontSize: 13, padding: '4px 12px', cursor: 'pointer' }}
                  onClick={() => setTypeFilter(typeFilter === type ? 'all' : type)}
                >
                  {TYPE_LABELS[type] || type}: {count}个实体
                </Tag>
              );
            })}
          </Space>
        </Card>
      )}

      {/* ─── 抽取来源概览 ─── */}
      {extractionSources.length > 0 && (
        <Card
          title={
            <Space>
              <FileTextOutlined />
              <span>抽取来源</span>
            </Space>
          }
          style={{ marginBottom: 16 }}
          size="small"
        >
          <Space size={8} wrap>
            {extractionSources.map(src => (
              <Tooltip
                key={src.doc_id}
                title={
                  <div>
                    <div>{src.title}</div>
                    <div style={{ fontSize: 11, color: '#bfbfbf' }}>
                      {src.description?.substring(0, 100)}
                    </div>
                    <div>置信度: {(src.confidence * 100).toFixed(0)}%</div>
                  </div>
                }
              >
                <Tag color="blue" style={{ cursor: 'pointer' }}>
                  <FileTextOutlined style={{ marginRight: 4 }} />
                  {src.title?.substring(0, 15) || src.doc_id}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        </Card>
      )}

      {/* ─── 实体列表 ─── */}
      <Card
        title={
          <Space>
            <DatabaseOutlined />
            <span>对象管理（实体清单）</span>
            <Tooltip title={
              <div>
                <div><b>对象与实体的关系：</b></div>
                <div>• <b>对象（Object Type）</b>：本体中定义的类型，如 MilitaryUnit、Location、Equipment 等</div>
                <div>• <b>实体（Entity）</b>：对象类型的实例，是从数据源中抽取的具体数据记录</div>
                <div>• 例如：MilitaryUnit 是一个对象类型，RedForce 是该类型的一个实体实例</div>
                <div style={{ marginTop: 4 }}>每个实体包含属性（结构化字段、指标、向量存储ID等），来源于数据摄入和LLM抽取</div>
              </div>
            }>
              <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
            </Tooltip>
          </Space>
        }
        extra={
          <Space>
            <Input.Search
              placeholder="搜索实体、属性或语义..."
              value={searchText}
              onChange={e => setSearchText(e.target.value)}
              style={{ width: 280 }}
              allowClear
              prefix={<SearchOutlined />}
            />
          </Space>
        }
      >
        {/* 类型过滤 */}
        <div style={{ marginBottom: 12 }}>
          <Text type="secondary" style={{ marginRight: 8 }}>类型过滤:</Text>
          <Space size={8} wrap>
            <Tag
              color={typeFilter === 'all' ? 'blue' : 'default'}
              style={{ cursor: 'pointer' }}
              onClick={() => setTypeFilter('all')}
            >
              全部
            </Tag>
            {entityTypes.map(type => (
              <Tag
                key={type}
                color={typeFilter === type ? 'blue' : (TYPE_COLORS[type] || 'default')}
                style={{ cursor: 'pointer' }}
                onClick={() => setTypeFilter(type)}
              >
                {TYPE_LABELS[type] || type}
              </Tag>
            ))}
          </Space>
        </div>

        {/* 数据来源过滤 */}
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ marginRight: 8 }}>来源过滤:</Text>
          <Space size={8} wrap>
            {['all', 'random', 'news_ingest', 'manual', 'simulation'].map(src => (
              <Tag
                key={src}
                color={sourceFilter === src ? 'blue' : 'default'}
                style={{ cursor: 'pointer' }}
                onClick={() => setSourceFilter(src)}
              >
                {src === 'all' ? '全部' :
                 src === 'random' ? '随机生成' :
                 src === 'news_ingest' ? '新闻采集' :
                 src === 'manual' ? '手动录入' :
                 src === 'simulation' ? '模拟推演' : src}
              </Tag>
            ))}
          </Space>
        </div>

        {filteredEntities.length === 0 ? (
          <Empty description={currentScenario ? '暂无实体数据' : '请先选择场景'} />
        ) : (
          <Table
            dataSource={filteredEntities}
            columns={columns}
            rowKey="entity_id"
            loading={loading}
            pagination={{ pageSize: 10 }}
            scroll={{ x: 1000 }}
          />
        )}
      </Card>

      {/* ─── 详情抽屉 ─── */}
      <Drawer
        title={
          <Space>
            <DatabaseOutlined />
            <span>实体详情</span>
          </Space>
        }
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        width={720}
      >
        {viewingEntity && (
          <div>
            {/* 基本信息 */}
            <Card size="small" style={{ marginBottom: 16 }} title="基本信息">
              <Descriptions column={1} bordered size="small">
                <Descriptions.Item label="实体ID">
                  <Text code copyable style={{ fontSize: 12 }}>
                    {viewingEntity.entity_id}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="实体名称">{viewingEntity.name}</Descriptions.Item>
                {viewingEntity.name_en && (
                  <Descriptions.Item label="英文名称">{viewingEntity.name_en}</Descriptions.Item>
                )}
                <Descriptions.Item label="所属对象类型">
                  <Space>
                    <Tag color={TYPE_COLORS[viewingEntity.type] || TYPE_COLORS.default}>
                      {TYPE_LABELS[viewingEntity.type] || viewingEntity.type}
                    </Tag>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      （该实体是 {TYPE_LABELS[viewingEntity.type] || viewingEntity.type} 对象类型的一个实例）
                    </Text>
                  </Space>
                </Descriptions.Item>
                <Descriptions.Item label="数据来源">
                  <Tag>
                    {viewingEntity.source_type === 'random' ? '随机生成' :
                     viewingEntity.source_type === 'random_gen' ? '随机生成' :
                     viewingEntity.source_type === 'news_ingest' ? '新闻采集' :
                     viewingEntity.source_type === 'manual' ? '手动录入' :
                     viewingEntity.source_type === 'simulation' ? '模拟推演' :
                     viewingEntity.source_type}
                  </Tag>
                </Descriptions.Item>
                {viewingEntity.confidence !== undefined && (
                  <Descriptions.Item label="抽取置信度">
                    <Badge
                      color={viewingEntity.confidence > 0.8 ? 'green' : viewingEntity.confidence > 0.5 ? 'orange' : 'red'}
                      text={`${(viewingEntity.confidence * 100).toFixed(1)}%`}
                    />
                  </Descriptions.Item>
                )}
                {viewingEntity.source_doc && (
                  <Descriptions.Item label="来源文档">
                    <Text code style={{ fontSize: 11 }}>{viewingEntity.source_doc}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>

            {/* 属性详情 - 按类别分组 */}
            <Tabs
              items={[
                {
                  key: 'by-category',
                  label: (
                    <span>
                      <ClusterOutlined style={{ marginRight: 4 }} />
                      按类别 ({viewingEntity.attributes.length})
                    </span>
                  ),
                  children: renderAttributesByCategory(viewingEntity),
                },
                {
                  key: 'all-attrs',
                  label: (
                    <span>
                      <BranchesOutlined style={{ marginRight: 4 }} />
                      全部属性
                    </span>
                  ),
                  children: (
                    <div>
                      {viewingEntity.attributes.map(attr => renderAttributeCard(attr))}
                    </div>
                  ),
                },
                {
                  key: 'structured',
                  label: (
                    <span>
                      <BuildOutlined style={{ marginRight: 4 }} />
                      结构化
                      <Badge
                        count={viewingEntity.attributes.filter(a => a.source === 'structured').length}
                        style={{ marginLeft: 4 }}
                        color="blue"
                      />
                    </span>
                  ),
                  children: (
                    <div>
                      {viewingEntity.attributes
                        .filter(a => a.source === 'structured')
                        .map(attr => renderAttributeCard(attr))}
                      {viewingEntity.attributes.filter(a => a.source === 'structured').length === 0 && (
                        <Empty description="暂无结构化属性" />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'unstructured',
                  label: (
                    <span>
                      <DatabaseOutlined style={{ marginRight: 4 }} />
                      非结构化/向量
                      <Badge
                        count={viewingEntity.attributes.filter(a => a.source === 'unstructured').length}
                        style={{ marginLeft: 4 }}
                        color="orange"
                      />
                    </span>
                  ),
                  children: (
                    <div>
                      {viewingEntity.attributes
                        .filter(a => a.source === 'unstructured')
                        .map(attr => renderAttributeCard(attr))}
                      {viewingEntity.attributes.filter(a => a.source === 'unstructured').length === 0 && (
                        <Empty description="暂无非结构化属性" />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'computed',
                  label: (
                    <span>
                      <AimOutlined style={{ marginRight: 4 }} />
                      计算/推理
                      <Badge
                        count={viewingEntity.attributes.filter(a => a.source === 'computed' || a.source === 'inferred').length}
                        style={{ marginLeft: 4 }}
                        color="green"
                      />
                    </span>
                  ),
                  children: (
                    <div>
                      {viewingEntity.attributes
                        .filter(a => a.source === 'computed' || a.source === 'inferred')
                        .map(attr => renderAttributeCard(attr))}
                      {viewingEntity.attributes.filter(a => a.source === 'computed' || a.source === 'inferred').length === 0 && (
                        <Empty description="暂无计算/推理属性" />
                      )}
                    </div>
                  ),
                },
              ]}
            />

            {/* 抽取语义说明 */}
            <Card
              size="small"
              style={{ marginTop: 16 }}
              title={
                <Space>
                  <InfoCircleOutlined />
                  <span>对象与实体关系说明</span>
                </Space>
              }
            >
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                <Text strong>对象（Object Type）</Text>是本体中定义的类型，如 MilitaryUnit、Location 等。
                <Text strong>实体（Entity）</Text>是对象类型的实例，通过 <Text strong>LLM 结构化抽取</Text> 从原始数据中提取。
              </Paragraph>
              <List size="small">
                <List.Item>
                  <Tag color="blue">基础属性</Tag>
                  <Text type="secondary">实体的基本描述信息，如名称、位置、状态等</Text>
                </List.Item>
                <List.Item>
                  <Tag color="cyan">统计属性</Tag>
                  <Text type="secondary">通过计算或评估得出的量化指标，如战斗力、士气等</Text>
                </List.Item>
                <List.Item>
                  <Tag color="purple">能力属性</Tag>
                  <Text type="secondary">实体具备的能力特征，如射程、穿甲能力等</Text>
                </List.Item>
                <List.Item>
                  <Tag color="orange">向量存储</Tag>
                  <Text type="secondary">非结构化文本的向量表示，用于语义检索和RAG</Text>
                </List.Item>
              </List>
            </Card>
          </div>
        )}
      </Drawer>
    </div>
  );
}
