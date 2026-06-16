import { useState, useEffect } from 'react';
import { Collapse, Tag, Spin, Empty, Typography, Card, Space, Badge, Table } from 'antd';
import { DatabaseOutlined, ApartmentOutlined, TeamOutlined, SafetyOutlined, CodeOutlined, FileTextOutlined, ProfileOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';

const { Text, Paragraph } = Typography;

interface SchemaData {
  version: string;
  last_updated: string;
  entity_types: Record<string, EntityTypeDef>;
  roles: Record<string, RoleDef>;
  domain_config: {
    factions?: any[];
    areas?: any[];
    random_events?: string[];
  };
  ontology_document_schema?: Record<string, DataClassSchema>;
  business_processes?: any[];
  business_rules?: any[];
  business_logics?: any[];
  business_indicators?: any[];
}

interface EntityTypeDef {
  properties: Record<string, string>;
  relationships: Record<string, string>;
}

interface RoleDef {
  permissions: string[];
  restrictions: string[];
}

interface DataClassSchema {
  fields: Record<string, FieldDef>;
  doc?: string;
  [key: string]: any;
}

interface FieldDef {
  type: string;
  default?: string | null;
  default_factory?: string | null;
}

const TYPE_COLORS: Record<string, string> = {
  Location: 'orange',
  OrganizationUnit: 'blue',
  ToolSystem: 'magenta',
  PublicAsset: 'green',
  IncidentEvent: 'red',
  Mission: 'purple',
  Faction: 'cyan',
};

const TYPE_LABELS: Record<string, string> = {
  Location: '地理位置',
  OrganizationUnit: '组织单元',
  ToolSystem: '工具系统',
  PublicAsset: '公共资产',
  IncidentEvent: '领域事件',
  Mission: '任务',
  Faction: '交战方',
};

const SCHEMA_COLORS: Record<string, string> = {
  OntologyDocument: '#1890ff',
  OntologyEntity: '#13c2c2',
  OntologyRelation: '#722ed1',
  OntologyEvent: '#f5222d',
  OntologyAction: '#fa8c16',
  OntologyRule: '#52c41a',
  OntologyConstraint: '#eb2f96',
  DataSource: '#2f54eb',
  DocumentMeta: '#faad14',
  TemporalInfo: '#a0d911',
  VersionRef: '#9254de',
};

const SCHEMA_LABELS: Record<string, string> = {
  OntologyDocument: '本体文档',
  OntologyEntity: '实体',
  OntologyRelation: '关系',
  OntologyEvent: '事件',
  OntologyAction: '行动',
  OntologyRule: '规则',
  OntologyConstraint: '约束',
  DataSource: '数据来源',
  DocumentMeta: '文档元数据',
  TemporalInfo: '时序信息',
  VersionRef: '版本引用',
};

const FIELD_TYPE_LABELS: Record<string, string> = {
  'str': '字符串',
  'int': '整数',
  'float': '浮点数',
  'bool': '布尔',
  'Dict': '字典',
  'List': '列表',
  'Optional': '可选',
};

function simplifyTypeName(typeStr: string): string {
  if (typeStr.startsWith('typing.Optional')) {
    const inner = typeStr.replace('typing.Optional[', '').replace(']', '');
    return `可选 ${simplifyTypeName(inner)}`;
  }
  if (typeStr.startsWith('typing.List')) {
    const inner = typeStr.replace('typing.List[', '').replace(']', '');
    return `列表<${simplifyTypeName(inner)}>`;
  }
  if (typeStr.startsWith('Dict')) return '字典';
  if (typeStr === 'str') return '字符串';
  if (typeStr === 'float') return '浮点数';
  if (typeStr === 'bool') return '布尔';
  if (typeStr === 'int') return '整数';
  return typeStr;
}

function renderEntityTypeSchema(name: string, def: EntityTypeDef) {
  return (
    <Card
      size="small"
      style={{ marginBottom: 8, borderLeft: `3px solid ${TYPE_COLORS[name] === 'orange' ? '#fa8c16' : TYPE_COLORS[name] === 'blue' ? '#1890ff' : TYPE_COLORS[name] === 'magenta' ? '#eb2f96' : TYPE_COLORS[name] === 'green' ? '#52c41a' : TYPE_COLORS[name] === 'red' ? '#f5222d' : TYPE_COLORS[name] === 'purple' ? '#722ed1' : TYPE_COLORS[name] === 'cyan' ? '#13c2c2' : '#d9d9d9'}` }}
    >
      <div style={{ marginBottom: 8 }}>
        <Space>
          <Tag color={TYPE_COLORS[name] || 'default'}>{name}</Tag>
          <Text type="secondary">{TYPE_LABELS[name] || name}</Text>
        </Space>
      </div>
      <Collapse
        size="small"
        defaultActiveKey={['props', 'rels']}
        items={[
          {
            key: 'props',
            label: <Text strong style={{ fontSize: 13 }}>属性 ({Object.keys(def.properties).length})</Text>,
            children: (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(def.properties).map(([prop, type]) => (
                  <Tag key={prop} style={{ margin: 0 }}>
                    {prop}: <Text style={{ fontSize: 11, color: '#999' }}>{type}</Text>
                  </Tag>
                ))}
              </div>
            ),
          },
          {
            key: 'rels',
            label: <Text strong style={{ fontSize: 13 }}>关系 ({Object.keys(def.relationships).length})</Text>,
            children: (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(def.relationships).map(([rel, target]) => (
                  <Tag key={rel} color="blue" style={{ margin: 0 }}>
                    {rel} → <Text style={{ fontSize: 11 }}>{target}</Text>
                  </Tag>
                ))}
              </div>
            ),
          },
        ]}
      />
    </Card>
  );
}

function renderDataClassSchema(name: string, schema: DataClassSchema) {
  const color = SCHEMA_COLORS[name] || '#d9d9d9';
  const label = SCHEMA_LABELS[name] || name;
  const fields = schema.fields || {};
  const doc = schema.doc || '';
  const enumKeys = Object.keys(schema).filter(k => k !== 'fields' && k !== 'doc');

  const columns = [
    {
      title: '字段名',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (text: string) => <Text code style={{ fontSize: 12 }}>{text}</Text>,
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      width: 200,
      render: (text: string) => <Tag style={{ fontSize: 11 }}>{simplifyTypeName(text)}</Tag>,
    },
    {
      title: '默认值',
      dataIndex: 'default',
      key: 'default',
      width: 180,
      render: (text: string | null, record: any) => {
        if (record.default_factory) {
          return <Tag color="blue" style={{ fontSize: 11 }}>{record.default_factory}()</Tag>;
        }
        if (text && text !== 'None') {
          return <Tag style={{ fontSize: 11 }}>{text}</Tag>;
        }
        return <Text type="secondary" style={{ fontSize: 11 }}>-</Text>;
      },
    },
  ];

  const dataSource = Object.entries(fields).map(([fname, fdef]) => ({
    key: fname,
    name: fname,
    type: fdef.type,
    default: fdef.default,
    default_factory: fdef.default_factory,
  }));

  return (
    <Card
      size="small"
      style={{ marginBottom: 8, borderLeft: `3px solid ${color}` }}
    >
      <div style={{ marginBottom: 6 }}>
        <Space>
          <Tag color={color}>{name}</Tag>
          <Text strong style={{ fontSize: 13 }}>{label}</Text>
        </Space>
      </div>
      {doc && (
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 6 }}>
          {doc.split('\n')[0]}
        </Paragraph>
      )}
      {enumKeys.length > 0 && (
        <div style={{ marginBottom: 6 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>枚举值:</Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
            {enumKeys.map(ek => {
              const values = schema[ek];
              if (Array.isArray(values)) {
                return values.map((v: string) => (
                  <Tag key={`${ek}-${v}`} color="blue" style={{ fontSize: 11 }}>{v}</Tag>
                ));
              }
              return null;
            })}
          </div>
        </div>
      )}
      <Table
        dataSource={dataSource}
        columns={columns}
        size="small"
        pagination={false}
        bordered
        style={{ fontSize: 12 }}
      />
    </Card>
  );
}

function renderBusinessSection(title: string, icon: React.ReactNode, items: any[], color: string) {
  if (!items || items.length === 0) return null;
  return {
    key: title,
    label: (
      <Space>
        {icon}
        <Text strong>{title}</Text>
        <Badge count={items.length} style={{ backgroundColor: color }} />
      </Space>
    ),
    children: (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((item: any, idx: number) => (
          <Card key={item.process_id || item.rule_id || item.logic_id || item.indicator_id || idx} size="small" style={{ borderLeft: `3px solid ${color}` }}>
            <Space orientation="vertical" size={2} style={{ width: '100%' }}>
              <Space>
                <Text strong>{item.display_name || item.name}</Text>
                <Tag color={color}>{item.name}</Tag>
              </Space>
              {item.description && <Text type="secondary" style={{ fontSize: 12 }}>{item.description}</Text>}
              {item.llm_description && (
                <Text type="secondary" style={{ fontSize: 12, fontStyle: 'italic' }}>
                  LLM: {item.llm_description.substring(0, 100)}{item.llm_description.length > 100 ? '...' : ''}
                </Text>
              )}
              <Space size={4} wrap>
                {item.related_objects?.map((obj: string) => (
                  <Tag key={obj} style={{ fontSize: 11 }}>{obj}</Tag>
                ))}
                {item.indicator_type && <Tag color="blue" style={{ fontSize: 11 }}>{item.indicator_type}</Tag>}
                {item.logic_type && <Tag color="purple" style={{ fontSize: 11 }}>{item.logic_type}</Tag>}
              </Space>
            </Space>
          </Card>
        ))}
      </div>
    ),
  };
}

export function OntologySchemaViewer() {
  const [schema, setSchema] = useState<SchemaData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSchema();
  }, []);

  const loadSchema = async () => {
    try {
      setLoading(true);
      const data = await api.getOntologySchema() as unknown as SchemaData;
      setSchema(data);
    } catch (error) {
      console.error('加载本体Schema失败:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Spin spinning description="加载本体定义..." style={{ width: '100%' }}>
        <div style={{ minHeight: 200 }} />
      </Spin>
    );
  }

  if (!schema) {
    return <Empty description="无法加载本体定义" />;
  }

  const entityTypes = schema.entity_types || {};
  const roles = schema.roles || {};
  const domainConfig = schema.domain_config || {};
  const docSchema = schema.ontology_document_schema || {};
  const docTypes = docSchema.DocType || [];

  return (
    <div style={{ padding: '0 4px' }}>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space separator={<Text type="secondary">|</Text>}>
          <Text type="secondary">版本: <Text strong>{schema.version}</Text></Text>
          <Text type="secondary">更新: <Text strong>{schema.last_updated}</Text></Text>
          <Text type="secondary">实体类型: <Text strong>{Object.keys(entityTypes).length}</Text></Text>
          <Text type="secondary">角色: <Text strong>{Object.keys(roles).length}</Text></Text>
        </Space>
      </Card>

      <Collapse
        defaultActiveKey={['doc_schema']}
        style={{ marginBottom: 12 }}
        items={[
          {
            key: 'doc_schema',
            label: (
              <Space>
                <ProfileOutlined />
                <Text strong>OntologyDocument 定义</Text>
                <Badge count={Object.keys(docSchema).filter(k => k !== 'DocType').length} style={{ backgroundColor: '#1890ff' }} />
              </Space>
            ),
            children: (
              <>
                {docTypes.length > 0 && (
                  <Card size="small" style={{ marginBottom: 8, borderLeft: '3px solid #1890ff' }}>
                    <Space>
                      <Text strong>DocType 枚举</Text>
                      <Text type="secondary" style={{ fontSize: 12 }}>文档类型</Text>
                    </Space>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                      {docTypes.map((v: string) => (
                        <Tag key={v} color="blue" style={{ fontSize: 11 }}>{v}</Tag>
                      ))}
                    </div>
                  </Card>
                )}
                {Object.entries(docSchema)
                  .filter(([key]) => key !== 'DocType')
                  .sort(([a], [b]) => {
                    const order = ['OntologyDocument', 'OntologyEntity', 'OntologyRelation', 'OntologyEvent', 'OntologyAction', 'OntologyRule', 'OntologyConstraint', 'DataSource', 'DocumentMeta', 'TemporalInfo', 'VersionRef'];
                    return order.indexOf(a) - order.indexOf(b);
                  })
                  .map(([name, def]) => (
                    <div key={name}>
                      {renderDataClassSchema(name, def as DataClassSchema)}
                    </div>
                  ))}
              </>
            ),
          },
          {
            key: 'entity_types',
            label: (
              <Space>
                <DatabaseOutlined />
                <Text strong>实体类型定义</Text>
                <Badge count={Object.keys(entityTypes).length} style={{ backgroundColor: '#13c2c2' }} />
              </Space>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(entityTypes).map(([name, def]) => (
                  <div key={name}>
                    {renderEntityTypeSchema(name, def as EntityTypeDef)}
                  </div>
                ))}
              </div>
            ),
          },
          {
            key: 'roles',
            label: (
              <Space>
                <TeamOutlined />
                <Text strong>角色定义</Text>
                <Badge count={Object.keys(roles).length} style={{ backgroundColor: '#722ed1' }} />
              </Space>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {Object.entries(roles).map(([name, def]) => (
                  <Card key={name} size="small" style={{ borderLeft: '3px solid #722ed1' }}>
                    <Text strong style={{ fontSize: 14 }}>{name}</Text>
                    <div style={{ marginTop: 6 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>权限:</Text>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
                        {(def as RoleDef).permissions.map((p: string) => (
                          <Tag key={p} color="green" style={{ fontSize: 11 }}>{p}</Tag>
                        ))}
                      </div>
                    </div>
                    <div style={{ marginTop: 6 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>限制:</Text>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
                        {(def as RoleDef).restrictions.map((r: string) => (
                          <Tag key={r} color="red" style={{ fontSize: 11 }}>{r}</Tag>
                        ))}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            ),
          },
          {
            key: 'domain_config',
            label: (
              <Space>
                <SafetyOutlined />
                <Text strong>领域配置</Text>
              </Space>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {domainConfig.factions && domainConfig.factions.length > 0 && (
                  <Card size="small" style={{ borderLeft: '3px solid #fa8c16' }}>
                    <Text strong>交战方 ({domainConfig.factions.length})</Text>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                      {domainConfig.factions.map((f: any) => (
                        <Tag key={f.name} color={f.type === 'coalition' ? 'blue' : f.type === 'nation' ? 'green' : 'orange'}>
                          {f.name} ({f.type})
                        </Tag>
                      ))}
                    </div>
                  </Card>
                )}
                {domainConfig.areas && domainConfig.areas.length > 0 && (
                  <Card size="small" style={{ borderLeft: '3px solid #13c2c2' }}>
                    <Text strong>区域 ({domainConfig.areas.length})</Text>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                      {domainConfig.areas.map((a: any) => (
                        <Tag key={a.id} color="cyan">{a.name}</Tag>
                      ))}
                    </div>
                  </Card>
                )}
                {domainConfig.random_events && domainConfig.random_events.length > 0 && (
                  <Card size="small" style={{ borderLeft: '3px solid #f5222d' }}>
                    <Text strong>随机事件类型 ({domainConfig.random_events.length})</Text>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                      {domainConfig.random_events.map((e: string) => (
                        <Tag key={e} color="volcano" style={{ fontSize: 11 }}>{e}</Tag>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            ),
          },
        ]}
      />

      <Collapse
        defaultActiveKey={[]}
        items={[
          renderBusinessSection('业务过程', <ApartmentOutlined />, schema.business_processes || [], '#1890ff'),
          renderBusinessSection('业务规则', <SafetyOutlined />, schema.business_rules || [], '#fa8c16'),
          renderBusinessSection('业务逻辑', <CodeOutlined />, schema.business_logics || [], '#722ed1'),
          renderBusinessSection('业务指标', <DatabaseOutlined />, schema.business_indicators || [], '#52c41a'),
        ].filter(Boolean) as any}
      />
    </div>
  );
}
