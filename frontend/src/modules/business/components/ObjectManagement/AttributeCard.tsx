import { Card, Tag, Space, Tooltip, Typography, Collapse, Empty } from 'antd';
import {
  FieldStringOutlined, NumberOutlined, CalendarOutlined,
  TagOutlined, BranchesOutlined, ClusterOutlined, InfoCircleOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import type { EntityAttribute } from './types';
import { CATEGORY_COLORS, CATEGORY_LABELS, SOURCE_COLORS, SOURCE_LABELS } from './types';

const { Text } = Typography;


const ATTR_ICONS: Record<string, React.ReactNode> = {
  string: <FieldStringOutlined />,
  number: <NumberOutlined />,
  date: <CalendarOutlined />,
  boolean: <TagOutlined />,
  vector: <DatabaseOutlined />,
  json: <BranchesOutlined />,
  array: <ClusterOutlined />,
};

interface AttributeCardProps {
  attr: EntityAttribute;
}

export function AttributeCard({ attr }: AttributeCardProps) {
  const isVector = attr.type === 'vector' || attr.semantic.category === 'vector';
  const isNested = attr.isNested && attr.children && attr.children.length > 0;

  return (
    <Card
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
              <Collapse variant="ghost" size="small" items={[
                { key: '1', label: `展开 ${attr.children?.length || 0} 个子属性`, children: attr.children?.map(child => <AttributeCard key={child.name} attr={child} />) },
              ]} />
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
}

interface AttributeCategoryPanelProps {
  attributes: EntityAttribute[];
}

export function AttributeCategoryPanel({ attributes }: AttributeCategoryPanelProps) {
  const grouped: Record<string, EntityAttribute[]> = {};
  attributes.forEach(attr => {
    const cat = attr.semantic.category;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(attr);
  });

  return (
    <Collapse defaultActiveKey={Object.keys(grouped)} items={
      Object.entries(grouped).map(([category, attrs]) => ({
        key: category,
        label: (
          <Space>
            <Tag color={CATEGORY_COLORS[category]}>
              {CATEGORY_LABELS[category]}
            </Tag>
            <Text type="secondary">{attrs.length} 个属性</Text>
          </Space>
        ),
        children: attrs.map(attr => <AttributeCard key={attr.name} attr={attr} />),
      }))
    } />
  );
}

interface AttributeSourceTabProps {
  attributes: EntityAttribute[];
  source: 'structured' | 'unstructured' | 'computed' | 'inferred';
  label: string;
}

export function AttributeSourceTab({ attributes, source }: AttributeSourceTabProps) {
  const filtered = attributes.filter(a => {
    if (source === 'computed') return a.source === 'computed' || a.source === 'inferred';
    return a.source === source;
  });

  if (filtered.length === 0) {
    return <Empty description={`暂无${SOURCE_LABELS[source]}属性`} />;
  }

  return (
    <div>
      {filtered.map(attr => <AttributeCard key={attr.name} attr={attr} />)}
    </div>
  );
}
