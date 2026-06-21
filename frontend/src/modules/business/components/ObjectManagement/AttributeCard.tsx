import { Tag, Space, Tooltip, Typography, Collapse, Empty } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  FieldStringOutlined, NumberOutlined, CalendarOutlined,
  TagOutlined, BranchesOutlined, ClusterOutlined, InfoCircleOutlined,
  DatabaseOutlined,
} from '@ant-design/icons';
import type { EntityAttribute } from './types';
import { CATEGORY_COLORS, CATEGORY_LABELS, SOURCE_COLORS, SOURCE_LABELS } from './types';
import { useI18n } from '@/modules/shared/hooks/useI18n';

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
  const { t } = useI18n('business');
  const isVector = attr.type === 'vector' || attr.semantic.category === 'vector';
  const isNested = attr.isNested && attr.children && attr.children.length > 0;

  const categoryLabelKey = CATEGORY_LABELS[attr.semantic.category];
  const categoryLabel = categoryLabelKey ? t(categoryLabelKey) : attr.semantic.category;
  const sourceLabelKey = SOURCE_LABELS[attr.source];
  const sourceLabel = sourceLabelKey ? t(sourceLabelKey) : attr.source;

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
              {categoryLabel}
            </Tag>
          </Tooltip>
          <Tag color={SOURCE_COLORS[attr.source]}>
            {sourceLabel}
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
              {t('attributeCard.vectorStorageLabel')}
            </div>
            <Text code copyable style={{ fontSize: 12 }}>
              {attr.vector_id || String(attr.value)}
            </Text>
            <div style={{ marginTop: 8, color: '#fa8c16', fontSize: 12 }}>
              {t('attributeCard.vectorDescription')}
            </div>
          </div>
        ) : attr.type === 'json' ? (
          <div>
            {isNested ? (
              <Collapse variant="ghost" size="small" items={[
                { key: '1', label: t('attributeCard.expandChildren', { count: attr.children?.length || 0 }), children: attr.children?.map(child => <AttributeCard key={child.name} attr={child} />) },
              ]} />
            ) : (
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
                {JSON.stringify(attr.value, null, 2)}
              </pre>
            )}
          </div>
        ) : attr.type === 'array' ? (
          <div>
            <Text type="secondary">{t('attributeCard.arrayItems', { count: (attr.value as any[]).length })}</Text>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: 12 }}>
              {JSON.stringify(attr.value, null, 2)}
            </pre>
          </div>
        ) : attr.type === 'boolean' ? (
          <Tag color={attr.value ? 'green' : 'red'}>
            {attr.value ? t('attributeCard.yes') : t('attributeCard.no')}
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
  const { t } = useI18n('business');
  const grouped: Record<string, EntityAttribute[]> = {};
  attributes.forEach(attr => {
    const cat = attr.semantic.category;
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(attr);
  });

  return (
    <Collapse defaultActiveKey={Object.keys(grouped)} items={
      Object.entries(grouped).map(([category, attrs]) => {
        const categoryLabelKey = CATEGORY_LABELS[category];
        const categoryLabel = categoryLabelKey ? t(categoryLabelKey) : category;
        return {
          key: category,
          label: (
            <Space>
              <Tag color={CATEGORY_COLORS[category]}>
                {categoryLabel}
              </Tag>
              <Text type="secondary">{t('attributeCard.attributeCount', { count: attrs.length })}</Text>
            </Space>
          ),
          children: attrs.map(attr => <AttributeCard key={attr.name} attr={attr} />),
        };
      })
    } />
  );
}

interface AttributeSourceTabProps {
  attributes: EntityAttribute[];
  source: 'structured' | 'unstructured' | 'computed' | 'inferred';
  label: string;
}

export function AttributeSourceTab({ attributes, source, label }: AttributeSourceTabProps) {
  const { t } = useI18n('business');
  const filtered = attributes.filter(a => {
    if (source === 'computed') return a.source === 'computed' || a.source === 'inferred';
    return a.source === source;
  });

  if (filtered.length === 0) {
    return <Empty description={t('attributeCard.emptyAttributes', { label })} />;
  }

  return (
    <div>
      {filtered.map(attr => <AttributeCard key={attr.name} attr={attr} />)}
    </div>
  );
}
