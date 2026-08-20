import { Drawer, Tag, Space, Badge, Typography, Tabs, List } from 'antd';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { DatabaseOutlined, InfoCircleOutlined, ClusterOutlined, BranchesOutlined, BuildOutlined, AimOutlined } from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { ManagedEntity } from './types';
import { TYPE_COLORS, TYPE_LABELS, SOURCE_LABELS } from './types';
import { AttributeCard, AttributeCategoryPanel, AttributeSourceTab } from './AttributeCard';

const { Text, Paragraph } = Typography;

interface EntityDetailDrawerProps {
  open: boolean;
  entity: ManagedEntity | null;
  onClose: () => void;
}

export function EntityDetailDrawer({ open, entity, onClose }: EntityDetailDrawerProps) {
  const { t, instance } = useI18n('business');
  if (!entity) return null;

  return (
    <Drawer
      title={
        <Space>
          <DatabaseOutlined />
          <span>{t('实体详情')}</span>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={720}
    >
      <Card size="small" style={{ marginBottom: 16 }} title={t('基本信息')}>
        <Descriptions column={1}>
          <Descriptions.Item label={t('实体ID')}>
            <Text code copyable style={{ fontSize: 12 }}>{entity.entity_id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label={t('实体名称')}>{entity.name}</Descriptions.Item>
          {entity.name_en && (
            <Descriptions.Item label={t('英文名称')}>{entity.name_en}</Descriptions.Item>
          )}
          <Descriptions.Item label={t('所属对象类型')}>
            <Space>
              <Tag color={TYPE_COLORS[entity.type] || TYPE_COLORS.default}>
                {TYPE_LABELS[entity.type] || entity.type}
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {t('（该实体是 {{type}} 对象类型的一个实例）', { type: TYPE_LABELS[entity.type] || entity.type })}
              </Text>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label={t('数据来源')}>
            <Tag>{SOURCE_LABELS[entity.source_type || ''] || entity.source_type}</Tag>
          </Descriptions.Item>
          {entity.confidence !== undefined && (
            <Descriptions.Item label={t('抽取置信度')}>
              <Badge
                color={entity.confidence > 0.8 ? 'green' : entity.confidence > 0.5 ? 'orange' : 'red'}
                text={`${(entity.confidence * 100).toFixed(1)}%`}
              />
            </Descriptions.Item>
          )}
          {entity.source_doc && (
            <Descriptions.Item label={t('来源文档')}>
              <Text code style={{ fontSize: 11 }}>{entity.source_doc}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Tabs items={[
        {
          key: 'by-category',
          label: <span><ClusterOutlined style={{ marginRight: 4 }} />{t('按类别 ({{count}})', { count: entity.attributes.length })}</span>,
          children: <AttributeCategoryPanel attributes={entity.attributes} />,
        },
        {
          key: 'all-attrs',
          label: <span><BranchesOutlined style={{ marginRight: 4 }} />{t('全部属性')}</span>,
          children: <div>{entity.attributes.map(attr => {
            return <AttributeCard key={attr.name} attr={attr} />;
          })}</div>,
        },
        {
          key: 'structured',
          label: <span><BuildOutlined style={{ marginRight: 4 }} />{t('结构化')}<Badge count={entity.attributes.filter(a => a.source === 'structured').length} style={{ marginLeft: 4 }} color="blue" /></span>,
          children: <AttributeSourceTab attributes={entity.attributes} source="structured" label={t('结构化')} />,
        },
        {
          key: 'unstructured',
          label: <span><DatabaseOutlined style={{ marginRight: 4 }} />{t('非结构化/向量')}<Badge count={entity.attributes.filter(a => a.source === 'unstructured').length} style={{ marginLeft: 4 }} color="orange" /></span>,
          children: <AttributeSourceTab attributes={entity.attributes} source="unstructured" label={t('非结构化')} />,
        },
        {
          key: 'computed',
          label: <span><AimOutlined style={{ marginRight: 4 }} />{t('计算/推理')}<Badge count={entity.attributes.filter(a => a.source === 'computed' || a.source === 'inferred').length} style={{ marginLeft: 4 }} color="green" /></span>,
          children: <AttributeSourceTab attributes={entity.attributes} source="computed" label={t('计算/推理')} />,
        },
      ]} />

      <Card size="small" style={{ marginTop: 16 }} title={<Space><InfoCircleOutlined /><span>{t('对象与实体关系说明')}</span></Space>}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          <Text strong>{t('对象（Object Type）')}</Text>{t('是本体中定义的类型，如 OrganizationUnit、Location 等。')}
          <Text strong>{t('实体（Entity）')}</Text>{t('是对象类型的实例，通过')}<Text strong>{t('LLM 结构化抽取')}</Text>{t('从原始数据中提取。')}
        </Paragraph>
        <List size="small">
          <List.Item><Tag color="blue">{t('基础属性')}</Tag><Text type="secondary">{t('实体的基本描述信息，如名称、位置、状态等')}</Text></List.Item>
          <List.Item><Tag color="cyan">{t('统计属性')}</Tag><Text type="secondary">{t('通过计算或评估得出的量化指标，如能力指数、士气等')}</Text></List.Item>
          <List.Item><Tag color="purple">{t('能力属性')}</Tag><Text type="secondary">{t('实体具备的能力特征，如射程、穿甲能力等')}</Text></List.Item>
          <List.Item><Tag color="orange">{t('向量存储')}</Tag><Text type="secondary">{t('非结构化文本的向量表示，用于语义检索和RAG')}</Text></List.Item>
        </List>
      </Card>
    </Drawer>
  );
}
