/**
 * 不相交约束对 (DisjointPair) 表格
 * 列：术语 A Select / 术语 B Select / 理由 Reason / 操作
 * 底部工具栏：新建 + 刷新 + 删除选中
 */
import React, { useEffect, useMemo, useState } from 'react';
import {
  Table,
  Button,
  Space,
  Select,
  Input,
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
import { PlusOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';
import type { UslDisjointPair, UslTerm } from '../types';
import {
  listDisjointPairs,
  createDisjointPair,
  deleteDisjointPair,
  listTerms,
} from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';

const { Text } = Typography;

interface DisjointFormValues {
  term_a: string;
  term_b: string;
  reason?: string;
}

export function DisjointPairTable() {
  const { message } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslDisjointPair[]>([]);
  const [termOptions, setTermOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [form] = Form.useForm<DisjointFormValues>();

  const fetchData = async () => {
    if (!currentDomain) return;
    setLoading(true);
    try {
      const [p, t] = await Promise.all([
        listDisjointPairs(currentDomain.code),
        listTerms(currentDomain.code, { page: 1, page_size: 500 }).catch(() => ({ items: [] as UslTerm[] })),
      ]);
      setItems(Array.isArray(p) ? p : []);
      const termList: UslTerm[] = 'items' in t ? (t.items as UslTerm[]) : [];
      setTermOptions(
        termList.map((tm) => ({
          label: `${tm.canonical}（${tm.en || '-'}）`,
          value: tm.canonical,
        })),
      );
    } catch (err) {
      console.warn('[DisjointPairTable] fetch failed:', err);
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
    form.resetFields();
    setFormOpen(true);
  };

  const handleDelete = async (record: UslDisjointPair) => {
    if (!record.id) return;
    try {
      await deleteDisjointPair(record.id);
      message.success(`已删除不相交对 (${record.term_a} ⊥ ${record.term_b})`);
      void fetchData();
    } catch (err) {
      message.error(`删除失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    try {
      for (const k of selectedRowKeys) {
        const match = items.find((i) => i.id === String(k));
        if (match?.id) await deleteDisjointPair(match.id);
      }
      message.success(`已批量删除 ${selectedRowKeys.length} 条不相交对`);
      setSelectedRowKeys([]);
      void fetchData();
    } catch (err) {
      message.error(`批量删除失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleSubmit = async () => {
    if (!currentDomain) return;
    try {
      const v = await form.validateFields();
      if (v.term_a === v.term_b) {
        message.error('术语 A 和 术语 B 不能相同');
        return;
      }
      setSubmitting(true);
      // 去重检查：顺序无关
      const exists = items.some(
        (i) =>
          (i.term_a === v.term_a && i.term_b === v.term_b) ||
          (i.term_a === v.term_b && i.term_b === v.term_a),
      );
      if (exists) {
        message.warning('该不相交对已存在（忽略顺序），无需重复创建');
        setSubmitting(false);
        return;
      }
      await createDisjointPair({
        domain_id: currentDomain.code,
        term_a: v.term_a,
        term_b: v.term_b,
        reason: v.reason?.trim() || undefined,
      });
      message.success('不相交对创建成功');
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

  const columns: ColumnsType<UslDisjointPair> = [
    {
      title: '术语 A',
      dataIndex: 'term_a',
      width: 200,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '',
      dataIndex: '_symbol',
      width: 60,
      align: 'center',
      render: () => <span style={{ fontSize: 18, color: '#faad14' }}>⊥</span>,
    },
    {
      title: '术语 B',
      dataIndex: 'term_b',
      width: 200,
      render: (v: string) => <Tag color="geekblue">{v}</Tag>,
    },
    {
      title: '理由 Reason',
      dataIndex: 'reason',
      ellipsis: true,
      render: (v?: string) => v || <Text type="secondary">—</Text>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_: unknown, record) => (
        <Popconfirm
          title={`删除不相交对 (${record.term_a} ⊥ ${record.term_b})？`}
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
      <Space style={{ marginBottom: 12, width: '100%', justifyContent: 'space-between' }} wrap>
        <Space wrap>
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
              新建不相交对
            </Button>
          </Tooltip>
          <Popconfirm
            title={`批量删除选中的 ${selectedRowKeys.length} 条？`}
            disabled={selectedRowKeys.length === 0 || !canWrite}
            okButtonProps={{ danger: true }}
            onConfirm={handleBulkDelete}
            okText="删除"
            cancelText="取消"
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              disabled={selectedRowKeys.length === 0 || !canWrite}
            >
              批量删除（{selectedRowKeys.length}）
            </Button>
          </Popconfirm>
        </Space>
        <Tag color="default">共 {items.length} 条不相交约束</Tag>
      </Space>

      <Table<UslDisjointPair>
        rowKey={(r) => r.id || `${r.term_a}-${r.term_b}`}
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={items.length === 0 ? [] : items}
        rowSelection={{
          type: 'checkbox',
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
          getCheckboxProps: () => ({ disabled: !canWrite }),
        }}
        pagination={false}
        locale={{
          emptyText: (
            <Empty
              description={
                <Text type="secondary">
                  暂无不相交约束；点击「新建不相交对」添加，例如「人物 ⊥ 势力」以阻止同一候选同时 is_a 两者
                </Text>
              }
            />
          ),
        }}
      />

      <Modal
        title="新建不相交约束对"
        open={formOpen}
        onCancel={() => setFormOpen(false)}
        onOk={handleSubmit}
        okText="创建"
        cancelText="取消"
        okButtonProps={{ disabled: !canWrite, loading: submitting }}
        destroyOnHidden
        width={520}
      >
        <Form form={form} layout="vertical" preserve={false} requiredMark="optional">
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item
              label="术语 A"
              name="term_a"
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
              label="术语 B（不能与 A 同时 is_a 指向）"
              name="term_b"
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
          <Form.Item label="不相交理由">
            <Input.TextArea
              rows={3}
              placeholder="例如：规范中定义 人物=自然人/主公；势力=组织/阵营；本体论上互斥"
              onChange={(e) => form.setFieldsValue({ reason: e.target.value })}
              disabled={!canWrite}
            />
          </Form.Item>
          <Form.Item name="reason" hidden>
            <Input />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
