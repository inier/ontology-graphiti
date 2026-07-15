/**
 * 属性规范 (UslPropertySpec) 表格
 * 列：所属术语 / 属性名 / 数据类型(Select) / 单位 / 必填 Switch
 * 底部工具栏：按钮新增
 */
import React, { useEffect, useState, useMemo } from 'react';
import {
  Table,
  Button,
  Space,
  Input,
  Select,
  Switch,
  App,
  Tooltip,
  Popconfirm,
  Form,
  Modal,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import type {
  UslPropertySpec,
  UslTerm,
  PropertyDataType,
} from '../types';
import { PROPERTY_DATA_TYPE_OPTIONS } from '../types';
import {
  listPropertySpecs,
  createPropertySpec,
  updatePropertySpec,
  deletePropertySpec,
  listTerms,
} from '../services/uslApi';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import { useUslPermissions } from '../hooks/useUslPermissions';

const { Text } = Typography;

interface SpecFormValues {
  for_term: string;
  prop_name: string;
  data_type: PropertyDataType;
  unit?: string;
  required: boolean;
  description?: string;
}

export function PropertySpecTable() {
  const { message, modal } = App.useApp();
  const { canWrite } = useUslPermissions();
  const currentDomain = useSemanticAdminStore((s) => s.currentDomain);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<UslPropertySpec[]>([]);
  const [termOptions, setTermOptions] = useState<Array<{ label: string; value: string }>>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<UslPropertySpec | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm<SpecFormValues>();

  const fetchData = async () => {
    if (!currentDomain) return;
    setLoading(true);
    try {
      const [specs, terms] = await Promise.all([
        listPropertySpecs(currentDomain.code),
        // 拉术语列表用于「所属术语」下拉
        listTerms(currentDomain.code, { page_size: 500, page: 1 }).catch(() => ({ items: [] as UslTerm[] })),
      ]);
      setItems(Array.isArray(specs) ? specs : []);
      const termItems: UslTerm[] = 'items' in terms ? (terms.items as UslTerm[]) : [];
      setTermOptions(
        termItems.map((t) => ({
          label: `${t.canonical}（${t.en || '-'}）`,
          value: t.canonical,
        })),
      );
    } catch (err) {
      console.warn('[PropertySpecTable] fetch failed:', err);
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

  const handleCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ data_type: 'string', required: false });
    setFormOpen(true);
  };

  const handleEdit = (record: UslPropertySpec) => {
    setEditing(record);
    form.setFieldsValue({
      for_term: record.for_term,
      prop_name: record.prop_name,
      data_type: record.data_type,
      unit: record.unit || '',
      required: !!record.required,
      description: record.description || '',
    });
    setFormOpen(true);
  };

  const handleDelete = async (record: UslPropertySpec) => {
    if (!record.id) return;
    try {
      await deletePropertySpec(record.id);
      message.success(`属性「${record.for_term}.${record.prop_name}」已删除`);
      void fetchData();
    } catch (err) {
      message.error(`删除失败：${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleSubmit = async () => {
    if (!currentDomain) {
      message.error('请先选择语义域');
      return;
    }
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const payload = {
        domain_id: currentDomain.code,
        for_term: values.for_term,
        prop_name: values.prop_name.trim(),
        data_type: values.data_type,
        unit: values.unit?.trim() || undefined,
        required: values.required,
        description: values.description?.trim() || undefined,
      };
      if (editing?.id) {
        await updatePropertySpec(editing.id, payload);
        message.success('属性规范已更新');
      } else {
        await createPropertySpec(payload);
        message.success('属性规范已创建');
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

  const dataTypeLabelMap = useMemo(() => {
    const m: Record<PropertyDataType, string> = {} as Record<PropertyDataType, string>;
    PROPERTY_DATA_TYPE_OPTIONS.forEach((opt) => {
      m[opt.value] = opt.label;
    });
    return m;
  }, []);

  const columns: ColumnsType<UslPropertySpec> = [
    {
      title: '所属术语 for_term',
      dataIndex: 'for_term',
      width: 160,
      render: (v: string) => <Tag color="geekblue">{v}</Tag>,
    },
    {
      title: '属性名 prop_name',
      dataIndex: 'prop_name',
      width: 160,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '数据类型',
      dataIndex: 'data_type',
      width: 140,
      render: (v: PropertyDataType) => <Tag color="purple">{dataTypeLabelMap[v] || v}</Tag>,
    },
    {
      title: '单位',
      dataIndex: 'unit',
      width: 100,
      render: (v?: string) => v || <Text type="secondary">—</Text>,
    },
    {
      title: '必填',
      dataIndex: 'required',
      width: 80,
      align: 'center',
      render: (v?: boolean) => (
        <Tooltip title={canWrite ? '点击表格中开关无效，用编辑行修改' : ''}>
          <Switch size="small" checked={!!v} disabled />
        </Tooltip>
      ),
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
      width: 160,
      fixed: 'right',
      render: (_: unknown, record) => (
        <Space size="small">
          <Button
            size="small"
            type="text"
            icon={<EditOutlined />}
            disabled={!canWrite || !record.id}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title={`删除属性 ${record.for_term}.${record.prop_name}？`}
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
          <Input
            allowClear
            placeholder="搜索属性名（前端过滤）"
            style={{ width: 240 }}
            onChange={(e) => {
              const kw = e.target.value.trim();
              if (!kw) {
                void fetchData();
                return;
              }
              void listPropertySpecs(currentDomain!.code).then((all) => {
                setItems(all.filter((s) => s.prop_name.includes(kw) || s.for_term.includes(kw)));
              });
            }}
          />
        </Space>
        <Tooltip title={canWrite ? '' : '需要 admin / schema_auditor'}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={!canWrite}
            onClick={handleCreate}
          >
            新建属性规范
          </Button>
        </Tooltip>
      </Space>

      <Table<UslPropertySpec>
        rowKey={(r) => r.id || `${r.for_term}-${r.prop_name}`}
        size="middle"
        loading={loading}
        columns={columns}
        dataSource={items}
        pagination={false}
      />

      <Modal
        title={editing ? '编辑属性规范' : '新建属性规范'}
        open={formOpen}
        onCancel={() => setFormOpen(false)}
        onOk={handleSubmit}
        okText={editing ? '保存' : '创建'}
        cancelText="取消"
        okButtonProps={{ disabled: !canWrite, loading: submitting }}
        destroyOnHidden
        width={520}
      >
        <Form form={form} layout="vertical" preserve={false} requiredMark="optional">
          <Form.Item
            label="所属术语"
            name="for_term"
            rules={[{ required: true, message: '必选' }]}
          >
            <Select
              showSearch
              placeholder="输入或选择术语 canonical"
              options={termOptions}
              disabled={!canWrite}
              filterOption={(input, option) =>
                !!(option?.label && String(option.label).toLowerCase().includes(input.toLowerCase()))
              }
            />
          </Form.Item>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item
              label="属性名"
              name="prop_name"
              style={{ width: '60%' }}
              rules={[{ required: true, message: '必填' }, { pattern: /^[a-z][a-zA-Z0-9_]*$/, message: 'snake_case，如 age / annual_income' }]}
            >
              <Input placeholder="age" disabled={!canWrite} />
            </Form.Item>
            <Form.Item
              label="数据类型"
              name="data_type"
              style={{ width: '40%' }}
              rules={[{ required: true, message: '必选' }]}
            >
              <Select options={PROPERTY_DATA_TYPE_OPTIONS} disabled={!canWrite} />
            </Form.Item>
          </Space.Compact>
          <Space.Compact style={{ width: '100%' }}>
            <Form.Item label="单位" name="unit" style={{ width: '40%' }}>
              <Input placeholder="岁 / 万元" disabled={!canWrite} />
            </Form.Item>
            <Form.Item
              label="必填"
              name="required"
              valuePropName="checked"
              style={{ width: '30%', marginTop: 22 }}
            >
              <Switch disabled={!canWrite} />
            </Form.Item>
          </Space.Compact>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} placeholder="可选" disabled={!canWrite} />
          </Form.Item>
        </Form>
      </Modal>
      {/* 占位引用，避免 lint 未使用；上面使用了 App.useApp 的 modal */}
      <span style={{ display: 'none' }}>{modal ? '' : ''}</span>
    </div>
  );
}
