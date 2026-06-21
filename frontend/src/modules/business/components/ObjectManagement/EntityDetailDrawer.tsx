import { Drawer, Tag, Space, Badge, Typography, Tabs, List } from 'antd';
import { ProDescriptions as Descriptions } from '@ant-design/pro-components';
import { ProCard as Card } from '@ant-design/pro-components';
import { DatabaseOutlined, InfoCircleOutlined, ClusterOutlined, BranchesOutlined, BuildOutlined, AimOutlined } from '@ant-design/icons';
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
  if (!entity) return null;

  return (
    <Drawer
      title={
        <Space>
          <DatabaseOutlined />
          <span>实体详情</span>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={720}
    >
      <Card size="small" style={{ marginBottom: 16 }} title="基本信息">
        <Descriptions column={1} variant="bordered" size="small">
          <Descriptions.Item label="实体ID">
            <Text code copyable style={{ fontSize: 12 }}>{entity.entity_id}</Text>
          </Descriptions.Item>
          <Descriptions.Item label="实体名称">{entity.name}</Descriptions.Item>
          {entity.name_en && (
            <Descriptions.Item label="英文名称">{entity.name_en}</Descriptions.Item>
          )}
          <Descriptions.Item label="所属对象类型">
            <Space>
              <Tag color={TYPE_COLORS[entity.type] || TYPE_COLORS.default}>
                {TYPE_LABELS[entity.type] || entity.type}
              </Tag>
              <Text type="secondary" style={{ fontSize: 12 }}>
                （该实体是 {TYPE_LABELS[entity.type] || entity.type} 对象类型的一个实例）
              </Text>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label="数据来源">
            <Tag>{SOURCE_LABELS[entity.source_type || ''] || entity.source_type}</Tag>
          </Descriptions.Item>
          {entity.confidence !== undefined && (
            <Descriptions.Item label="抽取置信度">
              <Badge
                color={entity.confidence > 0.8 ? 'green' : entity.confidence > 0.5 ? 'orange' : 'red'}
                text={`${(entity.confidence * 100).toFixed(1)}%`}
              />
            </Descriptions.Item>
          )}
          {entity.source_doc && (
            <Descriptions.Item label="来源文档">
              <Text code style={{ fontSize: 11 }}>{entity.source_doc}</Text>
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Tabs items={[
        {
          key: 'by-category',
          label: <span><ClusterOutlined style={{ marginRight: 4 }} />按类别 ({entity.attributes.length})</span>,
          children: <AttributeCategoryPanel attributes={entity.attributes} />,
        },
        {
          key: 'all-attrs',
          label: <span><BranchesOutlined style={{ marginRight: 4 }} />全部属性</span>,
          children: <div>{entity.attributes.map(attr => {
            return <AttributeCard key={attr.name} attr={attr} />;
          })}</div>,
        },
        {
          key: 'structured',
          label: <span><BuildOutlined style={{ marginRight: 4 }} />结构化<Badge count={entity.attributes.filter(a => a.source === 'structured').length} style={{ marginLeft: 4 }} color="blue" /></span>,
          children: <AttributeSourceTab attributes={entity.attributes} source="structured" label="结构化" />,
        },
        {
          key: 'unstructured',
          label: <span><DatabaseOutlined style={{ marginRight: 4 }} />非结构化/向量<Badge count={entity.attributes.filter(a => a.source === 'unstructured').length} style={{ marginLeft: 4 }} color="orange" /></span>,
          children: <AttributeSourceTab attributes={entity.attributes} source="unstructured" label="非结构化" />,
        },
        {
          key: 'computed',
          label: <span><AimOutlined style={{ marginRight: 4 }} />计算/推理<Badge count={entity.attributes.filter(a => a.source === 'computed' || a.source === 'inferred').length} style={{ marginLeft: 4 }} color="green" /></span>,
          children: <AttributeSourceTab attributes={entity.attributes} source="computed" label="计算/推理" />,
        },
      ]} />

      <Card size="small" style={{ marginTop: 16 }} title={<Space><InfoCircleOutlined /><span>对象与实体关系说明</span></Space>}>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          <Text strong>对象（Object Type）</Text>是本体中定义的类型，如 OrganizationUnit、Location 等。
          <Text strong>实体（Entity）</Text>是对象类型的实例，通过 <Text strong>LLM 结构化抽取</Text> 从原始数据中提取。
        </Paragraph>
        <List size="small">
          <List.Item><Tag color="blue">基础属性</Tag><Text type="secondary">实体的基本描述信息，如名称、位置、状态等</Text></List.Item>
          <List.Item><Tag color="cyan">统计属性</Tag><Text type="secondary">通过计算或评估得出的量化指标，如能力指数、士气等</Text></List.Item>
          <List.Item><Tag color="purple">能力属性</Tag><Text type="secondary">实体具备的能力特征，如射程、穿甲能力等</Text></List.Item>
          <List.Item><Tag color="orange">向量存储</Tag><Text type="secondary">非结构化文本的向量表示，用于语义检索和RAG</Text></List.Item>
        </List>
      </Card>
    </Drawer>
  );
}
