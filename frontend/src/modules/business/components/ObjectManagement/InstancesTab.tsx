import { Card, Statistic, Row, Col, Tag, Space, Tooltip, Input, Empty, Button } from 'antd';
import { SearchOutlined, EyeOutlined, DatabaseOutlined, ClusterOutlined, AimOutlined, TagOutlined, FileTextOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { Typography } from 'antd';
import type { ManagedEntity, ExtractionSource } from './types';
import { TYPE_COLORS, TYPE_LABELS } from './types';
import { AdvancedTable } from '@/modules/shared';

const { Text } = Typography;

interface InstancesTabProps {
  entities: ManagedEntity[];
  loading: boolean;
  stats: {
    total: number;
    types: number;
    structured: number;
    unstructured: number;
    computed: number;
    inferred: number;
    byCategory: Record<string, number>;
  };
  extractionSources: ExtractionSource[];
  currentScenario: Record<string, unknown>;
  searchText: string;
  onSearchTextChange: (text: string) => void;
  typeFilter: string;
  onTypeFilterChange: (type: string) => void;
  sourceFilter: string;
  onSourceFilterChange: (source: string) => void;
  onViewEntity: (entity: ManagedEntity) => void;
}

export function InstancesTab({
  entities,
  loading,
  stats,
  extractionSources,
  currentScenario,
  searchText,
  onSearchTextChange,
  typeFilter,
  onTypeFilterChange,
  sourceFilter,
  onSourceFilterChange,
  onViewEntity,
}: InstancesTabProps) {
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

  const columns = [
    {
      title: '实体ID', dataIndex: 'entity_id', width: 160,
      render: (id: string) => <Text code copyable style={{ fontSize: 12 }}>{id}</Text>,
    },
    {
      title: '实体名称', dataIndex: 'name',
      render: (name: string, record: ManagedEntity) => (
        <div>
          <div style={{ fontWeight: 600 }}>{name}</div>
          {record.name_en && <div style={{ fontSize: 12, color: '#8c8c8c' }}>{record.name_en}</div>}
        </div>
      ),
    },
    {
      title: '所属对象类型', dataIndex: 'type', width: 140,
      render: (type: string) => (
        <Tooltip title={`对象类型: ${TYPE_LABELS[type] || type}`}>
          <Tag color={TYPE_COLORS[type] || TYPE_COLORS.default} style={{ fontSize: 13, padding: '2px 8px' }}>
            {TYPE_LABELS[type] || type}
          </Tag>
        </Tooltip>
      ),
    },
    {
      title: '数据来源', dataIndex: 'source_type', width: 120,
      render: (sourceType: string) => <Tag color="default" style={{ fontSize: 11 }}>{sourceType || 'unknown'}</Tag>,
    },
    {
      title: '操作', width: 80, fixed: 'right' as const,
      render: (_: unknown, record: ManagedEntity) => (
        <Button type="text" icon={<EyeOutlined />} onClick={() => onViewEntity(record)} title="查看详情" />
      ),
    },
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}><Card><Statistic title="实体总数" value={stats.total} prefix={<AimOutlined />} /></Card></Col>
        <Col span={4}><Card><Statistic title="对象类型数" value={stats.types} prefix={<TagOutlined />} /></Card></Col>
        <Col span={4}><Card><Statistic title="结构化属性" value={stats.structured} styles={{ content: { color: '#1890ff' } }} /></Card></Col>
        <Col span={4}><Card><Statistic title="非结构化" value={stats.unstructured} styles={{ content: { color: '#fa8c16' } }} /></Card></Col>
        <Col span={4}><Card><Statistic title="计算属性" value={stats.computed} styles={{ content: { color: '#52c41a' } }} /></Card></Col>
        <Col span={4}><Card><Statistic title="推理属性" value={stats.inferred} styles={{ content: { color: '#722ed1' } }} /></Card></Col>
      </Row>

      {entityTypes.length > 0 && (
        <Card title={<Space><ClusterOutlined /><span>对象类型分布</span></Space>} style={{ marginBottom: 16 }} size="small">
          <Space size={8} wrap>
            {entityTypes.map(type => {
              const count = entities.filter(e => e.type === type).length;
              return (
                <Tag key={type} color={TYPE_COLORS[type] || 'default'} style={{ fontSize: 13, padding: '4px 12px', cursor: 'pointer' }} onClick={() => onTypeFilterChange(typeFilter === type ? 'all' : type)}>
                  {TYPE_LABELS[type] || type}: {count}个实体
                </Tag>
              );
            })}
          </Space>
        </Card>
      )}

      {extractionSources.length > 0 && (
        <Card title={<Space><FileTextOutlined /><span>抽取来源</span></Space>} style={{ marginBottom: 16 }} size="small">
          <Space size={8} wrap>
            {extractionSources.map(src => (
              <Tooltip key={src.doc_id} title={<div><div>{src.title}</div><div>置信度: {(src.confidence * 100).toFixed(0)}%</div></div>}>
                <Tag color="blue" style={{ cursor: 'pointer' }}>
                  <FileTextOutlined style={{ marginRight: 4 }} />
                  {src.title?.substring(0, 15) || src.doc_id}
                </Tag>
              </Tooltip>
            ))}
          </Space>
        </Card>
      )}

      <Card
        title={<Space><DatabaseOutlined /><span>对象管理（实体清单）</span>
          <Tooltip title="对象是本体中定义的类型，实体是对象类型的实例">
            <InfoCircleOutlined style={{ color: '#8c8c8c' }} />
          </Tooltip>
        </Space>}
        extra={<Input.Search placeholder="搜索实体..." value={searchText} onChange={e => onSearchTextChange(e.target.value)} style={{ width: 280 }} allowClear prefix={<SearchOutlined />} />}
      >
        <div style={{ marginBottom: 12 }} data-tour="obj-mgmt-filter">
          <Text type="secondary" style={{ marginRight: 8 }}>类型过滤:</Text>
          <Space size={8} wrap>
            <Tag color={typeFilter === 'all' ? 'blue' : 'default'} style={{ cursor: 'pointer' }} onClick={() => onTypeFilterChange('all')}>全部</Tag>
            {entityTypes.map(type => (
              <Tag key={type} color={typeFilter === type ? 'blue' : (TYPE_COLORS[type] || 'default')} style={{ cursor: 'pointer' }} onClick={() => onTypeFilterChange(type)}>
                {TYPE_LABELS[type] || type}
              </Tag>
            ))}
          </Space>
        </div>

        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ marginRight: 8 }}>来源过滤:</Text>
          <Space size={8} wrap>
            {['all', 'random', 'news_ingest', 'manual', 'simulation'].map(src => (
              <Tag key={src} color={sourceFilter === src ? 'blue' : 'default'} style={{ cursor: 'pointer' }} onClick={() => onSourceFilterChange(src)}>
                {src === 'all' ? '全部' : src}
              </Tag>
            ))}
          </Space>
        </div>

        {filteredEntities.length === 0 ? (
          <Empty description={currentScenario ? '暂无实体数据' : '请先选择场景'} />
        ) : (
          <AdvancedTable dataSource={filteredEntities} columns={columns} rowKey="entity_id" loading={loading} pagination={{ pageSize: 10 }} scroll={{ x: 1000 }} />
        )}
      </Card>
    </div>
  );
}
