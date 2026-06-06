/**
 * ComputedPropertyList 组件 —— 计算属性列表（FR-035 / T389）
 *
 * 顶部：ObjectType 筛选器（Select）+ 搜索框
 * 表格列：Name | ObjectType | Expression (截断) | Dependencies Count | Materialized | Actions
 * "Materialized" 列显示 ✓/✗ 标记
 * 操作：Edit / Test / Delete / Toggle Materialize
 * 顶部按钮 "New Computed Property"
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Table, Tag, Button, Space, Select, Input, Typography, Empty, Spin, Popconfirm, Modal, Form, Input as AntInput, message, Tooltip,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined, CheckOutlined, CloseOutlined,
} from '@ant-design/icons';
import { apiClient } from '../../shared/services/apiClient';
import { useI18n } from '../../shared/hooks/useI18n';

const { Text, Title } = Typography;
const { TextArea } = AntInput;

export interface ComputedPropertyListProps {
  objectTypeId?: string;
  onEdit?: (id: string) => void;
}

interface ComputedProperty {
  id: string;
  name: string;
  object_type_id: string;
  object_type_name?: string;
  expression: string;
  dependencies: string[];
  materialized: boolean;
  updated_at?: string;
}

interface ComputedFormValues {
  name: string;
  object_type_id: string;
  expression: string;
  dependencies: string;
  materialized: boolean;
}

const EXPRESSION_MAX = 80;

export function ComputedPropertyList({ objectTypeId, onEdit }: ComputedPropertyListProps) {
  const { t } = useI18n();
  void t;
  const [items, setItems] = useState<ComputedProperty[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string | undefined>(objectTypeId);
  const [searchText, setSearchText] = useState('');
  const [objectTypeOptions, setObjectTypeOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<ComputedProperty | null>(null);
  const [form] = Form.useForm<ComputedFormValues>();
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; result: unknown } | null>(null);

  const fetchObjectTypes = useCallback(async () => {
    try {
      const data = await apiClient.get<{ object_types: Array<{ object_type_id: string; name: string }> }>(
        '/api/ontology/object-types',
      );
      setObjectTypeOptions(
        (data.object_types || []).map((o) => ({ value: o.object_type_id, label: o.name })),
      );
    } catch {
      setObjectTypeOptions([]);
    }
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      if (filter) qs.set('object_type_id', filter);
      const data = await apiClient.get<{ computed: ComputedProperty[] }>(
        `/api/ontology/computed${qs.toString() ? '?' + qs.toString() : ''}`,
      );
      setItems(data.computed || []);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void fetchObjectTypes();
    void fetchItems();
  }, [fetchObjectTypes, fetchItems]);

  const filtered = useMemo(() => {
    if (!searchText) return items;
    const kw = searchText.toLowerCase();
    return items.filter(
      (i) =>
        i.name.toLowerCase().includes(kw) ||
        (i.object_type_name || '').toLowerCase().includes(kw) ||
        i.expression.toLowerCase().includes(kw),
    );
  }, [items, searchText]);

  const openCreate = useCallback(() => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ materialized: false, dependencies: '' });
    setEditOpen(true);
  }, [form]);

  const openEdit = useCallback((item: ComputedProperty) => {
    setEditing(item);
    form.setFieldsValue({
      name: item.name,
      object_type_id: item.object_type_id,
      expression: item.expression,
      dependencies: (item.dependencies || []).join(', '),
      materialized: item.materialized,
    });
    setEditOpen(true);
    onEdit?.(item.id);
  }, [form, onEdit]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        name: values.name,
        object_type_id: values.object_type_id,
        expression: values.expression,
        dependencies: values.dependencies
          ? values.dependencies.split(',').map((d) => d.trim()).filter(Boolean)
          : [],
        materialized: values.materialized,
      };
      if (editing) {
        await apiClient.put(`/api/ontology/computed/${editing.id}`, payload);
        message.success('已更新');
      } else {
        await apiClient.post('/api/ontology/computed', payload);
        message.success('已创建');
      }
      setEditOpen(false);
      void fetchItems();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`保存失败: ${(e as Error).message}`);
    }
  }, [form, editing, fetchItems]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await apiClient.delete(`/api/ontology/computed/${id}`);
      message.success('已删除');
      void fetchItems();
    } catch (e) {
      message.error(`删除失败: ${(e as Error).message}`);
    }
  }, [fetchItems]);

  const handleToggleMaterialize = useCallback(async (item: ComputedProperty) => {
    try {
      if (!item.materialized) {
        await apiClient.post(`/api/ontology/computed/${item.id}/materialize`, {});
        message.success('已触发物化');
      } else {
        message.info('已物化（toggle 由后端支持）');
      }
      void fetchItems();
    } catch (e) {
      message.error(`操作失败: ${(e as Error).message}`);
    }
  }, [fetchItems]);

  const handleTest = useCallback(async (item: ComputedProperty) => {
    setTesting(item.id);
    try {
      const data = await apiClient.post<{ result: unknown }>(
        `/api/ontology/computed/${item.id}/test`,
        {},
      );
      setTestResult({ id: item.id, result: data.result });
      message.success('测试完成');
    } catch (e) {
      message.error(`测试失败: ${(e as Error).message}`);
    } finally {
      setTesting(null);
    }
  }, []);

  const columns: ColumnsType<ComputedProperty> = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (v: string) => <Text strong>{v}</Text> },
    { title: 'ObjectType', dataIndex: 'object_type_name', key: 'object_type_name', width: 140, render: (v?: string) => v ? <Tag color="blue">{v}</Tag> : '-' },
    {
      title: '表达式',
      dataIndex: 'expression',
      key: 'expression',
      render: (v: string) => (
        <Tooltip title={v}>
          <Text code style={{ fontSize: 12 }}>{v.length > EXPRESSION_MAX ? v.slice(0, EXPRESSION_MAX) + '...' : v}</Text>
        </Tooltip>
      ),
    },
    { title: '依赖数', dataIndex: 'dependencies', key: 'dependencies', width: 100, align: 'right', render: (v: string[]) => <Tag>{v?.length || 0}</Tag> },
    {
      title: '已物化',
      dataIndex: 'materialized',
      key: 'materialized',
      width: 90,
      render: (v: boolean) => v
        ? <Tag color="green" icon={<CheckOutlined />}>是</Tag>
        : <Tag color="default" icon={<CloseOutlined />}>否</Tag>,
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      render: (_: unknown, r) => (
        <Space size={4} wrap>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEdit(r)}>Edit</Button>
          <Button
            size="small"
            type="link"
            icon={<PlayCircleOutlined />}
            loading={testing === r.id}
            onClick={() => handleTest(r)}
          >
            Test
          </Button>
          <Button
            size="small"
            type="link"
            onClick={() => handleToggleMaterialize(r)}
          >
            {r.materialized ? 'Refresh' : 'Materialize'}
          </Button>
          <Popconfirm
            title="确认删除？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDelete(r.id)}
          >
            <Button size="small" type="link" danger icon={<DeleteOutlined />}>Delete</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="computed-property-list" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>计算属性</Title>
        <Space wrap>
          <Select
            allowClear
            placeholder="按 ObjectType 筛选"
            value={filter}
            onChange={(v) => setFilter(v)}
            style={{ minWidth: 180 }}
            options={objectTypeOptions}
            showSearch
            optionFilterProp="label"
          />
          <Input.Search
            placeholder="搜索"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchItems()}>刷新</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            New Computed Property
          </Button>
        </Space>
      </Space>

      <Card>
        <Spin spinning={loading}>
          {filtered.length === 0 ? (
            <Empty description="暂无计算属性" />
          ) : (
            <Table<ComputedProperty>
              rowKey="id"
              size="small"
              dataSource={filtered}
              columns={columns}
              pagination={{ pageSize: 10 }}
            />
          )}
        </Spin>
      </Card>

      <Modal
        title={editing ? '编辑计算属性' : '创建计算属性'}
        open={editOpen}
        onOk={handleSave}
        onCancel={() => { setEditOpen(false); form.resetFields(); }}
        okText="保存"
        cancelText="取消"
        width={680}
        destroyOnClose
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="name"
            label="名称"
            rules={[
              { required: true, message: '请输入名称' },
              { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: '以字母开头，仅允许字母数字下划线' },
            ]}
          >
            <Input placeholder="full_name" />
          </Form.Item>
          <Form.Item
            name="object_type_id"
            label="ObjectType"
            rules={[{ required: true, message: '请选择 ObjectType' }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={objectTypeOptions}
              placeholder="选择 ObjectType"
            />
          </Form.Item>
          <Form.Item
            name="expression"
            label="表达式"
            rules={[{ required: true, message: '请输入表达式' }]}
          >
            <TextArea
              rows={4}
              placeholder='CONCAT(first_name, " ", last_name)'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          <Form.Item
            name="dependencies"
            label="依赖属性（逗号分隔）"
          >
            <Input placeholder="first_name, last_name" />
          </Form.Item>
          <Form.Item name="materialized" label="启用物化" valuePropName="checked">
            <Select
              options={[{ value: true, label: '是' }, { value: false, label: '否' }]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="测试结果"
        open={!!testResult}
        onCancel={() => setTestResult(null)}
        footer={<Button onClick={() => setTestResult(null)}>关闭</Button>}
      >
        <pre
          style={{
            background: '#fafafa',
            padding: 12,
            borderRadius: 4,
            maxHeight: 400,
            overflow: 'auto',
            fontSize: 12,
            fontFamily: 'monospace',
          }}
        >
          {JSON.stringify(testResult, null, 2)}
        </pre>
      </Modal>
    </div>
  );
}

export default ComputedPropertyList;
