/**
 * 关系基数约束 (Cardinality) 表格
 * 列：关系名 / 定义域术语 / 值域术语 / min_card NumberInput / max_card / 操作
 * 底部工具栏：新建 / 编辑行 / 删除
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Table,
  Button,
  Space,
  Select,
  Input,
  InputNumber,
  App,
  Tooltip,
  Popconfirm,
  Modal,
  Form,
  Tag,
  Typography,
  Empty,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
  MinusOutlined,
} from '@ant-design/icons';
import type { UslCardinality, UslTerm } from '../types';
import {
  listCardinalities,
  createCardinality,
  updateCardinality,
  deleteCardinality,
  listTerms,
} from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';

const { Text } = Typography;

interface CardFormValues {
  rel_name: string;
  domain_term: string;
  range_term: string;
  min_card: number;
  max_card: number;
  description?: string;
}

const MAX_CARD_INF = -1;

export function CardinalityTable() {
  const { message } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslCardinality[]>([]);
  const [termOptions, setTermOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [relOptions, setRelOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<UslCardinality | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<CardFormValues>();

  const fetchData = async () => {
    if (!currentDomain) return;
    setLoading(true);
    try {
      const [c, t] = await Promise.all([
        listCardinalities(currentDomain.code),
        listTerms(currentDomain.code, { page: 1, page_size: 500 }).catch(() => ({ items: [] as UslTerm[] })),
      ]);
      setItems(Array.isArray(c) ? c : []);
      const termList: UslTerm[] = 'items' in t ? (t.items as UslTerm[]) : [];
      const sorted = [...termList].sort((a, b) =>
        a.canonical.localeCompare(b.canonical, 'zh-Hans-CN'),
      );
      const allTerms = sorted.map((tm) => ({
        label: `${tm.canonical}（${tm.en || '-'} · ${tm.semantic_type}）`,
        value: tm.canonical,
      }));
      setTermOptions(allTerms);
      // 关系名：语义类型 == link_type 的术语 canonical
      const rels = termList
        .filter((tm) => tm.semantic_type === 'link_type')
        .map((tm) => ({
          label: `${tm.canonical}（${tm.en || '-'}）`,
          value: tm.canonical,
        }));
      setRelOptions(rels.length > 0 ? rels : allTerms); // 回退：没 link_type 术语就展示所有
    } catch (err) {
      console.warn('[CardinalityTable] fetch failed:', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentDomain?.code]);

  const handleOpenCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ min_card: 0, max_card: MAX_CARD_INF });
    setFormOpen(true);
  };

  const handleEdit = (record: UslCardinality) => {
    setEditing(record);
    form.setFieldsValue({
      rel_name: record.rel_name,
      domain_term: record.domain_term,
      range_term: record.range_term,
      min_card: record.min_card ?? 0,
      max_card: record.max_card ?? MAX_CARD_INF,
      description: record.description || '',
    });
    setFormOpen(true);
  };

  const handleDelete = async (record: UslCardinality) => {
    if (!record.id) return;
    try {
      await deleteCardinality(record.id);
      message.success(`已删除基数约束 ${record.rel_name}`);
      void fetchData();
    } catch (err) {
      message.error(`删除失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleSubmit = async () => {
    if (!currentDomain) return;
    try {
      const v = await form.validateFields();
      if (v.min_card < 0) {
        message.error('min_card 不能为负数');
        return;
      }
      if (v.max_card !== MAX_CARD_INF && v.max_card < v.min_card) {
        message.error('max_card 应 ≥ min_card（或填 -1 代表无限）');
        return;
      }
      setSubmitting(true);
      const payload = {
        domain_id: currentDomain.code,
        rel_name: v.rel_name,
        domain_term: v.domain_term,
        range_term: v.range_term,
        min_card: v.min_card,
        max_card: v.max_card,
        description: v.description?.trim() || undefined,
      };
      if (editing?.id) {
        await updateCardinality(editing.id, payload);
        message.success('基数约束已更新');
      } else {
        // 去重：(rel, domain, range) 三元组唯一
        const dup = items.some(
          (i) =>
            i.rel_name === payload.rel_name &&
            i.domain_term === payload.domain_term &&
            i.range_term === payload.range_term,
        );
        if (dup) {
          message.warning('完全相同的三元组 (rel, domain, range) 已存在，改为编辑');
          setSubmitting(false);
          return;
        }
        await createCardinality(payload);
        message.success('基数约束已创建');
      }
      setFormOpen(false);
      void fetchData();
    } catch (err) {
      if (err instanceof Error && !String(err.message).includes('validate')) {
        message.error(err.message || '提交失败');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const sortedTermOptions = useMemo(
    () => [...termOptions].sort((a, b) => a.value.localeCompare(b.value, 'zh-Hans-CN')),
    [termOptions],
  );

  const renderCard = (minC?: number, maxC?: number) => {
    const mn = minC ?? 0;
    const mx = (maxC === undefined || maxC === MAX_CARD_INF) ? '∞' : String(maxC);
    return (
      <Tag color="cyan" style={{ marginRight: 0 }}>
        {mn}
        <MinusOutlined style={{ margin: '0 4px', fontSize: 10 }} />
        {mx}
      </Tag>
    );
  };

  const columns: ColumnsType<UslCardinality> = [
    {
      title: '关系名 rel',
      dataIndex: 'rel_name',
      width: 160,
      render: (v: string) => <Tag color="green">{v}</Tag>,
    },
    {
      title: '定义域 (source)',
      dataIndex: 'domain_term',
      width: 180,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '→',
      key: '_arrow',
      width: 40,
      align: 'center',
      render: () => <Text type="secondary">→</Text>,
    },
    {
      title: '值域 (target)',
      dataIndex: 'range_term',
      width: 180,
      render: (v: string) => <Tag color="geekblue">{v}</Tag>,
    },
    {
      title: '基数 min - max',
      key: '_card',
      width: 160,
      align: 'center',
      render: (_: unknown, r) => renderCard(r.min_card, r.max_card),
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
      render: (v?: string) => v || <Text type="secondary">—</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 180,
      fixed: 'right',
      render: (_: unknown, record) => (
        <Space size="small">
          <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
            <Button
              size="small"
              type="text"
              icon={<EditOutlined />}
              disabled={!canWrite || !record.id}
              onClick={() => handleEdit(record)}
            >
              编辑
            </Button>
          </Tooltip>
          <Popconfirm
            title={`删除基数约束 ${record.rel_name} (${record.domain_term} → ${record.range_term})？`}
            onConfirm={() => handleDelete(record)}
            okButtonProps={{ danger: true }}
            okText="删除"
            cancelText="取消"
            disabled={!canWrite || !record.id}
          >
            <Button size="small" danger type="text" icon={<DeleteOutlined />} disabled={!canWrite || !record.id}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  if (!currentDomain) {
    return (
      <div style={{ padding: 48, textAlign: 'center', color: '#8c8c8c', background: '#fafafa', borderRadius: 6 }}>
        请先选择语义域
      </div>
    );
  }

  return (
    <div>
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }}>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void fetchData()}>
            刷新
          </Button>
          <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              disabled={!canWrite}
              onClick={handleOpenCreate}
            >
              新建基数约束
            </Button>
          </Tooltip>
        </Space>
        <Space>
          <Tag color="default">共 {items.length} 条基数约束</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            max_card = -1 表示「无限」（OWL maxCardinality unspecified）
          </Text>
        </Space>
      </Space>

      <Table<UslCardinality>
        rowKey={(r) => r.id || `${r.rel_name}-${r.domain_term}-${r.range_term}`}
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={items}
        pagination={false}
        locale={{
          emptyText: (
            <Empty
              description={
                <Text type="secondary">
                  暂无基数约束；常见模式如「人物 owns − 0..∞ − 资产」、「订单 has − 1..1 − 客户」
                </Text>
              }
            />
          ),
        }}
      />

      <Modal
        title={editing ? '编辑基数约束' : '新建基数约束'}
        open={formOpen}
        onCancel={() => setFormOpen(false)}
        onOk={handleSubmit}
        okText={editing ? '保存' : '创建'}
        cancelText="取消"
        okButtonProps={{ disabled: !canWrite, loading: submitting }}
        destroyOnHidden
        width={600}
      >
        <Form form={form} layout="vertical" preserve={false} requiredMark="optional">
          <Form.Item
            label="关系名 rel（建议选 link_type 语义类型的术语）"
            name="rel_name"
            rules={[{ required: true, message: '必选' }]}
          >
            <Select
              showSearch
              options={relOptions}
              disabled={!canWrite}
              filterOption={(i, o) =>
                !!(o?.label && String(o.label).toLowerCase().includes(i.toLowerCase()))
              }
            />
          </Form.Item>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item
              label="定义域 (source)"
              name="domain_term"
              style={{ width: '50%' }}
              rules={[{ required: true, message: '必选' }]}
            >
              <Select
                showSearch
                options={sortedTermOptions}
                disabled={!canWrite}
                filterOption={(i, o) =>
                  !!(o?.label && String(o.label).toLowerCase().includes(i.toLowerCase()))
                }
              />
            </Form.Item>
            <Form.Item
              label="值域 (target)"
              name="range_term"
              style={{ width: '50%' }}
              rules={[{ required: true, message: '必选' }]}
            >
              <Select
                showSearch
                options={sortedTermOptions}
                disabled={!canWrite}
                filterOption={(i, o) =>
                  !!(o?.label && String(o.label).toLowerCase().includes(i.toLowerCase()))
                }
              />
            </Form.Item>
          </Space.Compact>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item
              label="最小基数 min_card"
              name="min_card"
              style={{ width: '30%' }}
              rules={[{ required: true, message: '必填' }]}
            >
              <InputNumber min={0} step={1} style={{ width: '100%' }} disabled={!canWrite} />
            </Form.Item>
            <Form.Item
              label="最大基数 max_card（-1 表示无限）"
              name="max_card"
              style={{ width: '30%' }}
              rules={[{ required: true, message: '必填' }]}
            >
              <InputNumber step={1} style={{ width: '100%' }} disabled={!canWrite} />
            </Form.Item>
          </Space.Compact>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} placeholder="可选" disabled={!canWrite} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
