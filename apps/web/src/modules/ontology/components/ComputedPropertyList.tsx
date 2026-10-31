/**
 * ComputedPropertyList —— 计算属性（派生属性）列表与编辑（T398）
 *
 * ── 后端真实契约（此前本组件全部请求 404 / 字段错位）─────────────────
 *   前缀 `/api/ontology/computed`（computed/api/routes.py）
 *     GET    /properties?target_type=&enabled_only=  → { properties, count }
 *     POST   /properties                             → { properties:[one], count:1 }
 *     GET    /properties/{id}
 *     PUT    /properties/{id}
 *     DELETE /properties/{id}
 *     POST   /properties/{id}/evaluate   body { instance_id, instance_data }
 *     POST   /properties/{id}/recompute  body { mode: 'full'|'incremental', changed_property_id? }
 *     GET    /properties/{id}/jobs?limit=
 *     GET    /jobs/{job_id}
 *
 *   模型字段：`{ id, name, target_type_id, expression, dependencies: string[],
 *   materialization: 'none'|'full'|'incremental', return_type, description,
 *   enabled, created_at, updated_at }`
 *   · 目标类型字段是 `target_type_id`，不是 `object_type_id`；
 *   · 没有 `materialized` 布尔、没有 `object_type_name`（后者本地按 id 映射）；
 *   · 没有 `/computed/{id}/materialize`，重算入口是 `/properties/{id}/recompute`；
 *   · 没有 `/computed/{id}/test`，单实例试算入口是 `/properties/{id}/evaluate`，
 *     且**必须**传 `instance_id`（因此 Test 需要先选实例，不能空 body 调用）。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Tag, Button, Space, Typography, Empty, Spin, Modal, Form, Input, Popconfirm, Select, message, Tooltip, Segmented,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined, PlayCircleOutlined, CheckOutlined, CloseOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;
const { TextArea } = Input;

const COMPUTED_BASE = '/api/ontology/computed';

/** 物化策略：none=每次访问重算；full=全量物化；incremental=依赖变化时增量重算 */
type MaterializationType = 'none' | 'full' | 'incremental';

interface ComputedProperty {
  id: string;
  name: string;
  target_type_id: string;
  expression: string;
  dependencies: string[];
  materialization: MaterializationType;
  return_type: string;
  description: string;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

interface ComputedFormValues {
  name: string;
  target_type_id: string;
  expression: string;
  dependencies: string;
  materialization: MaterializationType;
  return_type: string;
  description: string;
  enabled: boolean;
}

interface EvaluateResult {
  property_id?: string;
  instance_id?: string;
  value?: unknown;
  status?: string;
}

const EXPRESSION_MAX = 80;

export interface ComputedPropertyListProps {
  /** 若传入，则作为初始的目标类型筛选 */
  objectTypeId?: string;
  onEdit?: (id: string) => void;
}

export function ComputedPropertyList({ objectTypeId, onEdit }: ComputedPropertyListProps) {
  const { t } = useI18n('ontology');
  const [items, setItems] = useState<ComputedProperty[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<string | undefined>(objectTypeId);
  const [searchText, setSearchText] = useState('');
  const [typeNames, setTypeNames] = useState<Record<string, string>>({});
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<ComputedProperty | null>(null);
  const [form] = Form.useForm<ComputedFormValues>();

  // 单实例试算（evaluate 必须带 instance_id，故不能一键无参调用）
  const [testTarget, setTestTarget] = useState<ComputedProperty | null>(null);
  const [testInstanceId, setTestInstanceId] = useState('');
  const [testData, setTestData] = useState('');
  const [testRunning, setTestRunning] = useState(false);
  const [testResult, setTestResult] = useState<EvaluateResult | null>(null);

  // 重算结果（job_ids / affected）
  const [recomputing, setRecomputing] = useState<string | null>(null);

  const typeOptions = useMemo(
    () => Object.entries(typeNames).map(([value, label]) => ({ value, label })),
    [typeNames],
  );

  const fetchObjectTypes = useCallback(async () => {
    try {
      const data = await apiClient.get<{ object_types?: Array<{ object_type_id: string; name: string }> }>(
        '/api/ontology/object-types',
      );
      const map: Record<string, string> = {};
      for (const o of data?.object_types ?? []) map[o.object_type_id] = o.name;
      setTypeNames(map);
    } catch {
      setTypeNames({});
    }
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const qs = new URLSearchParams();
      // 后端筛选参数名是 target_type（不是 object_type_id）
      if (filter) qs.set('target_type', filter);
      const data = await apiClient.get<{ properties?: ComputedProperty[] }>(
        `${COMPUTED_BASE}/properties${qs.toString() ? '?' + qs.toString() : ''}`,
      );
      setItems(data?.properties ?? []);
    } catch (e) {
      message.error(t('加载失败: {{message}}', { message: (e as Error).message }));
    } finally {
      setLoading(false);
    }
  }, [filter, t]);

  useEffect(() => {
    // 数据拉取；两个 fetch 内部都先 await 再 setState，规则无法穿透 async 边界，
    // 按仓库既有约定显式豁免。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchObjectTypes();
    void fetchItems();
  }, [fetchObjectTypes, fetchItems]);

  const filtered = useMemo(() => {
    if (!searchText) return items;
    const kw = searchText.toLowerCase();
    return items.filter(
      (i) =>
        (i.name ?? '').toLowerCase().includes(kw) ||
        (typeNames[i.target_type_id] ?? '').toLowerCase().includes(kw) ||
        (i.expression ?? '').toLowerCase().includes(kw),
    );
  }, [items, searchText, typeNames]);

  const openCreate = useCallback(() => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      materialization: 'incremental',
      return_type: 'any',
      dependencies: '',
      description: '',
      enabled: true,
      target_type_id: filter,
    });
    setEditOpen(true);
  }, [form, filter]);

  const openEdit = useCallback((item: ComputedProperty) => {
    setEditing(item);
    form.setFieldsValue({
      name: item.name,
      target_type_id: item.target_type_id,
      expression: item.expression,
      dependencies: (item.dependencies || []).join(', '),
      materialization: item.materialization ?? 'incremental',
      return_type: item.return_type ?? 'any',
      description: item.description ?? '',
      enabled: item.enabled ?? true,
    });
    setEditOpen(true);
    onEdit?.(item.id);
  }, [form, onEdit]);

  const handleSave = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const base = {
        name: values.name,
        target_type_id: values.target_type_id,
        expression: values.expression,
        dependencies: values.dependencies
          ? values.dependencies.split(',').map((d) => d.trim()).filter(Boolean)
          : [],
        materialization: values.materialization,
        return_type: values.return_type,
        description: values.description ?? '',
        enabled: values.enabled,
      };
      if (editing) {
        await apiClient.put(`${COMPUTED_BASE}/properties/${encodeURIComponent(editing.id)}`, base);
        message.success(t('已更新'));
      } else {
        await apiClient.post(`${COMPUTED_BASE}/properties`, base);
        message.success(t('已创建'));
      }
      setEditOpen(false);
      void fetchItems();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(t('保存失败: {{message}}', { message: (e as Error).message }));
    }
  }, [form, editing, fetchItems, t]);

  const handleDelete = useCallback(async (id: string) => {
    try {
      await apiClient.delete(`${COMPUTED_BASE}/properties/${encodeURIComponent(id)}`);
      message.success(t('已删除'));
      void fetchItems();
    } catch (e) {
      message.error(t('删除失败: {{message}}', { message: (e as Error).message }));
    }
  }, [fetchItems, t]);

  /** 触发重算：none 策略不落库，full / incremental 走 recompute。 */
  const handleRecompute = useCallback(async (item: ComputedProperty) => {
    setRecomputing(item.id);
    try {
      const mode = item.materialization === 'full' ? 'full' : 'incremental';
      const data = await apiClient.post<{ job_ids?: string[]; affected?: string[] }>(
        `${COMPUTED_BASE}/properties/${encodeURIComponent(item.id)}/recompute`,
        { mode },
      );
      const jobs = data?.job_ids?.length ?? 0;
      message.success(`已提交重算（${mode}），任务数 ${jobs}`);
    } catch (e) {
      message.error(t('操作失败: {{message}}', { message: (e as Error).message }));
    } finally {
      setRecomputing(null);
    }
  }, [t]);

  const openTest = useCallback((item: ComputedProperty) => {
    setTestTarget(item);
    setTestInstanceId('');
    setTestData('');
    setTestResult(null);
  }, []);

  const handleTest = useCallback(async () => {
    if (!testTarget) return;
    if (!testInstanceId.trim()) {
      message.warning('请填写要试算的实例 ID');
      return;
    }
    let instanceData: Record<string, unknown> = {};
    if (testData.trim()) {
      try {
        const parsed: unknown = JSON.parse(testData);
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
          message.error('实例数据必须是 JSON 对象');
          return;
        }
        instanceData = parsed as Record<string, unknown>;
      } catch {
        message.error('实例数据不是合法 JSON');
        return;
      }
    }
    setTestRunning(true);
    try {
      const data = await apiClient.post<EvaluateResult>(
        `${COMPUTED_BASE}/properties/${encodeURIComponent(testTarget.id)}/evaluate`,
        { instance_id: testInstanceId.trim(), instance_data: instanceData },
      );
      setTestResult(data ?? null);
    } catch (e) {
      message.error(t('测试失败: {{message}}', { message: (e as Error).message }));
    } finally {
      setTestRunning(false);
    }
  }, [testTarget, testInstanceId, testData, t]);

  const columns: ColumnsType<ComputedProperty> = [
    { title: t('名称'), dataIndex: 'name', key: 'name', render: (v: string) => <Text strong>{v}</Text> },
    {
      title: 'ObjectType',
      key: 'target_type_id',
      width: 150,
      render: (_: unknown, r) => {
        const name = typeNames[r.target_type_id];
        return name ? <Tag color="blue">{name}</Tag> : <Text type="secondary">{r.target_type_id || '-'}</Text>;
      },
    },
    {
      title: t('表达式'),
      dataIndex: 'expression',
      key: 'expression',
      render: (v: string) => (
        <Tooltip title={v}>
          <Text code style={{ fontSize: 12 }}>{v.length > EXPRESSION_MAX ? v.slice(0, EXPRESSION_MAX) + '...' : v}</Text>
        </Tooltip>
      ),
    },
    { title: t('依赖数'), dataIndex: 'dependencies', key: 'dependencies', width: 90, align: 'right', render: (v: string[]) => <Tag>{v?.length || 0}</Tag> },
    {
      title: '物化策略',
      dataIndex: 'materialization',
      key: 'materialization',
      width: 110,
      render: (v: MaterializationType) => (
        <Tag color={v === 'none' ? 'default' : v === 'full' ? 'blue' : 'green'}>{v ?? 'none'}</Tag>
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      key: 'enabled',
      width: 80,
      render: (v: boolean) => v
        ? <Tag color="green" icon={<CheckOutlined />}>{t('是')}</Tag>
        : <Tag color="default" icon={<CloseOutlined />}>{t('否')}</Tag>,
    },
    {
      title: t('操作'),
      key: 'actions',
      width: 300,
      render: (_: unknown, r) => (
        <Space size={4} wrap>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEdit(r)}>Edit</Button>
          <Button
            size="small"
            type="link"
            icon={<PlayCircleOutlined />}
            onClick={() => openTest(r)}
          >
            Test
          </Button>
          <Button
            size="small"
            type="link"
            loading={recomputing === r.id}
            disabled={r.materialization === 'none'}
            onClick={() => { void handleRecompute(r); }}
          >
            Recompute
          </Button>
          <Popconfirm
            title={t('确认删除？')}
            okText={t('删除')}
            cancelText={t('取消')}
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
        <Title level={3} style={{ margin: 0 }}>{t('计算属性')}</Title>
        <Space wrap>
          <Select
            allowClear
            placeholder={t('按 ObjectType 筛选')}
            value={filter}
            onChange={(v) => setFilter(v)}
            style={{ minWidth: 180 }}
            options={typeOptions}
            showSearch
            optionFilterProp="label"
          />
          <Input.Search
            placeholder={t('搜索')}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />
          <Button icon={<ReloadOutlined />} onClick={() => void fetchItems()}>{t('刷新')}</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
            New Computed Property
          </Button>
        </Space>
      </Space>

      <Card>
        <Spin spinning={loading}>
          {filtered.length === 0 ? (
            <Empty description={t('暂无计算属性')} />
          ) : (
            <AdvancedTable<ComputedProperty>
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
        title={editing ? t('编辑计算属性') : t('创建计算属性')}
        open={editOpen}
        onOk={handleSave}
        onCancel={() => { setEditOpen(false); form.resetFields(); }}
        okText={t('保存')}
        cancelText={t('取消')}
        width={720}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item
            name="name"
            label={t('名称')}
            rules={[
              { required: true, message: t('请输入名称') },
              { pattern: /^[a-zA-Z][a-zA-Z0-9_]*$/, message: t('以字母开头，仅允许字母数字下划线') },
            ]}
          >
            <Input placeholder="full_name" />
          </Form.Item>
          <Form.Item
            name="target_type_id"
            label="ObjectType"
            rules={[{ required: true, message: t('请选择 ObjectType') }]}
          >
            <Select
              showSearch
              optionFilterProp="label"
              options={typeOptions}
              placeholder={t('选择 ObjectType')}
            />
          </Form.Item>
          <Form.Item
            name="expression"
            label={t('表达式')}
            rules={[{ required: true, message: t('请输入表达式') }]}
          >
            <TextArea
              rows={4}
              placeholder="properties.amount * properties.quantity"
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          <Form.Item name="dependencies" label={t('依赖属性（逗号分隔）')}>
            <Input placeholder="amount, quantity" />
          </Form.Item>
          <Space size={16} wrap style={{ display: 'flex' }}>
            <Form.Item name="materialization" label="物化策略" style={{ minWidth: 200 }}>
              <Segmented
                options={[
                  { value: 'none', label: 'none' },
                  { value: 'full', label: 'full' },
                  { value: 'incremental', label: 'incremental' },
                ]}
              />
            </Form.Item>
            <Form.Item name="return_type" label="返回类型" style={{ minWidth: 160 }}>
              <Select
                options={[
                  { value: 'any', label: 'any' },
                  { value: 'string', label: 'string' },
                  { value: 'number', label: 'number' },
                  { value: 'boolean', label: 'boolean' },
                ]}
              />
            </Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked" style={{ minWidth: 100 }}>
              <Segmented
                options={[
                  { value: true, label: t('是') },
                  { value: false, label: t('否') },
                ]}
              />
            </Form.Item>
          </Space>
          <Form.Item name="description" label={t('描述')}>
            <TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 单实例试算：evaluate 必须带 instance_id，故先收集实例信息再调用 */}
      <Modal
        title={`试算 · ${testTarget?.name ?? ''}`}
        open={!!testTarget}
        onOk={handleTest}
        okText="试算"
        cancelText={t('关闭')}
        confirmLoading={testRunning}
        onCancel={() => setTestTarget(null)}
        width={640}
      >
        <Form layout="vertical">
          <Form.Item label="实例 ID" required>
            <Input
              value={testInstanceId}
              onChange={(e) => setTestInstanceId(e.target.value)}
              placeholder="instance_uuid"
            />
          </Form.Item>
          <Form.Item label="实例数据（JSON 对象，可留空）">
            <TextArea
              rows={4}
              value={testData}
              onChange={(e) => setTestData(e.target.value)}
              placeholder='{"amount": 3, "quantity": 4}'
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
        </Form>
        {testResult && (
          <pre
            style={{
              background: '#fafafa',
              padding: 12,
              borderRadius: 4,
              maxHeight: 240,
              overflow: 'auto',
              fontSize: 12,
              fontFamily: 'monospace',
            }}
          >
            {JSON.stringify(testResult, null, 2)}
          </pre>
        )}
      </Modal>
    </div>
  );
}

export default ComputedPropertyList;
