/**
 * USL 本体管理页（/semantic-admin/usl-ontologies）
 *
 * 管理 USL → Graphiti 双写时系统自动生成的本体（name 形如 USL__{code}）。
 * 与「建本体 → 本体设计器」里的手工本体区分开：
 *   - 这里只列出 domain_code 非空（或 name 以 USL__ 开头）的系统本体；
 *   - 展示可读的领域名 + code，而非 USL__{hash}；
 *   - 支持按领域筛选、查看类型分布、删除本体。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Descriptions,
  Drawer,
  Empty,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ApartmentOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons';
import { SemanticAdminTabsContainer } from './SemanticAdminIndex';
import {
  deleteOntology,
  listUslOntologies,
  type UslOntology,
} from '../services/uslOntologyApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;

const TYPE_COUNT_META: Array<{ key: string; label: string; color: string }> = [
  { key: 'object_types', label: '对象类型', color: 'blue' },
  { key: 'link_types', label: '关系类型', color: 'green' },
  { key: 'action_types', label: '动作类型', color: 'orange' },
  { key: 'process_types', label: '过程类型', color: 'cyan' },
  { key: 'rule_types', label: '规则类型', color: 'magenta' },
];

export default function UslOntologyPage() {
  const { message } = App.useApp();
  const { t } = useI18n();

  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslOntology[]>([]);
  const [domains, setDomains] = useState<Array<{ code: string; display_name: string }>>([]);
  const [domainFilter, setDomainFilter] = useState<string | undefined>(undefined);
  const [detail, setDetail] = useState<UslOntology | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listUslOntologies();
      setItems(res.items || []);
      setDomains(
        (res.domains || []).map((d) => ({
          code: String(d.code),
          display_name: String(d.display_name),
        })),
      );
    } catch (err) {
      console.warn('[UslOntologyPage] listUslOntologies failed:', err);
      setItems([]);
      setDomains([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!domainFilter) return items;
    return items.filter((o) => o.domain_code === domainFilter);
  }, [items, domainFilter]);

  const totalTypes = useMemo(
    () =>
      filtered.reduce((acc, o) => {
        const c = o.type_counts || {};
        TYPE_COUNT_META.forEach((m) => {
          acc[m.key] = (acc[m.key] || 0) + (Number(c[m.key]) || 0);
        });
        return acc;
      }, {} as Record<string, number>),
    [filtered],
  );

  const handleDelete = async (record: UslOntology) => {
    try {
      await deleteOntology(record.ontology_id);
      message.success(`已删除本体 ${record.display_label}`);
      void fetchData();
    } catch (err) {
      console.error(err);
      message.error('删除失败');
    }
  };

  const columns: ColumnsType<UslOntology> = [
    {
      title: '领域',
      dataIndex: 'domain_display_name',
      width: 200,
      render: (v: string, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{v || r.domain_code}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            code: {r.domain_code}
          </Text>
        </Space>
      ),
    },
    {
      title: '本体名称',
      dataIndex: 'name',
      width: 220,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '类型分布',
      key: 'type_counts',
      render: (_, r) => {
        const c = r.type_counts || {};
        return (
          <Space size={4} wrap>
            {TYPE_COUNT_META.map((m) => (
              <Tag key={m.key} color={Number(c[m.key]) > 0 ? m.color : 'default'}>
                {m.label} {Number(c[m.key]) || 0}
              </Tag>
            ))}
          </Space>
        );
      },
    },
    {
      title: '工作空间',
      dataIndex: 'workspace_id',
      width: 140,
      ellipsis: true,
      render: (v?: string) => v || <Text type="secondary">—</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => setDetail(record)}
          >
            详情
          </Button>
          <Popconfirm
            title={`确定删除本体 ${record.display_label}？`}
            description="删除后该领域对应的本体定义将被清除，可能影响后续约束性抽取"
            okButtonProps={{ danger: true }}
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(record)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <SemanticAdminTabsContainer>
      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Alert
          type="info"
          showIcon
          icon={<SafetyCertificateOutlined />}
          message={t('USL 系统本体')}
          description={t(
            '以下本体由「USL → Graphiti 双写」时系统自动生成，与领域一一对应（命名 USL__{code}）。此处提供可读的领域名与类型分布，便于统一管理与清理。',
          )}
        />

        <Row gutter={16}>
          <Col xs={24} sm={8}>
            <Card variant="borderless">
              <Statistic
                title="USL 本体数"
                value={filtered.length}
                prefix={<ApartmentOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={16}>
            <Card variant="borderless">
              <Space size={4} wrap>
                {TYPE_COUNT_META.map((m) => (
                  <Tag
                    key={m.key}
                    color={Number(totalTypes[m.key]) > 0 ? m.color : 'default'}
                  >
                    {m.label}: {Number(totalTypes[m.key]) || 0}
                  </Tag>
                ))}
              </Space>
            </Card>
          </Col>
        </Row>

        <Card variant="borderless">
          <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
            <Space>
              <Select
                allowClear
                showSearch
                placeholder="按领域筛选"
                style={{ width: 240 }}
                value={domainFilter}
                onChange={(v) => setDomainFilter(v)}
                options={domains.map((d) => ({
                  value: d.code,
                  label: `${d.display_name}（${d.code}）`,
                }))}
                optionFilterProp="label"
              />
              <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>
                刷新
              </Button>
            </Space>
          </Space>

          <Table<UslOntology>
            rowKey="ontology_id"
            size="middle"
            loading={loading}
            columns={columns}
            dataSource={filtered}
            locale={{
              emptyText: <Empty description="暂无 USL 本体，执行 USL 双写后会自动生成" />,
            }}
            pagination={{ pageSize: 10, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          />
        </Card>
      </Space>

      <Drawer
        title="本体详情"
        width={520}
        open={!!detail}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="领域">
              {detail.domain_display_name || detail.domain_code}
            </Descriptions.Item>
            <Descriptions.Item label="领域 code">{detail.domain_code}</Descriptions.Item>
            <Descriptions.Item label="本体名称">
              <Text code>{detail.name}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="本体 ID">
              <Text code copyable>{detail.ontology_id}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="工作空间">
              {detail.workspace_id || '—'}
            </Descriptions.Item>
            <Descriptions.Item label="类型分布">
              <Space size={4} wrap>
                {TYPE_COUNT_META.map((m) => (
                  <Tag key={m.key} color={Number(detail.type_counts?.[m.key]) > 0 ? m.color : 'default'}>
                    {m.label} {Number(detail.type_counts?.[m.key]) || 0}
                  </Tag>
                ))}
              </Space>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </SemanticAdminTabsContainer>
  );
}
