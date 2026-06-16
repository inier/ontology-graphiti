/**
 * ObjectViewList 组件 —— Object View 列表（FR-036 / T401）
 *
 * 顶部：ObjectType 筛选器（Select）+ 搜索框 + "New View" 按钮
 * 表格列：Name | ObjectType | Description (截断) | Permission Count | Created By | Created At | Actions
 * 状态徽章：active (绿) / draft (黄) / archived (灰)
 * 操作：Preview / Edit / Clone / Delete / Toggle Active
 *
 * 对应后端：
 *   GET    /api/ontology/views?base_type=...
 *   POST   /api/ontology/views
 *   PUT    /api/ontology/views/{id}
 *   DELETE /api/ontology/views/{id}
 *   POST   /api/ontology/views/{id}/clone      （后端目前未实现，前端会优雅降级）
 *   GET    /api/ontology/views/{id}/permissions
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Select, Input, Button, Space, Table, Tag, Tooltip, Empty, Spin, Popconfirm, Modal, Form, message, InputNumber, Switch,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  PlusOutlined, ReloadOutlined, EyeOutlined, EditOutlined, CopyOutlined, DeleteOutlined, CheckOutlined, StopOutlined,
} from '@ant-design/icons';
import { viewApi, type ObjectView } from '../services/viewApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Search } = Input;

export interface ObjectViewListProps {
  workspaceId?: string;
  onEdit?: (view: ObjectView) => void;
  onPreview?: (view: ObjectView) => void;
}

interface ObjectTypeOption {
  value: string;
  label: string;
}

interface CreateFormValues {
  name: string;
  base_type_id: string;
  role: string;
  description?: string;
  row_limit?: number;
  enabled?: boolean;
}

const STATUS_META: Record<string, { color: string; label: string }> = {
  active: { color: 'success', label: 'active' },
  draft: { color: 'warning', label: 'draft' },
  archived: { color: 'default', label: 'archived' },
};

function deriveStatus(view: ObjectView): keyof typeof STATUS_META {
  // 当前 ObjectView 只有 enabled 字段；当 row_limit=0 或 description 缺失时归为 draft；
  // 后续若后端新增 status 字段可改回直接读取。
  if (!view.enabled) return 'archived';
  if (!view.description || !view.name) return 'draft';
  return 'active';
}

export function ObjectViewList({ workspaceId, onEdit, onPreview }: ObjectViewListProps) {
  const { t } = useI18n();
  void workspaceId;
  const [views, setViews] = useState<ObjectView[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchText, setSearchText] = useState('');
  const [objectTypeFilter, setObjectTypeFilter] = useState<string | undefined>();
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm<CreateFormValues>();
  const [creating, setCreating] = useState(false);
  const [permissionCounts, setPermissionCounts] = useState<Record<string, number>>({});
  const [objectTypeOptions, setObjectTypeOptions] = useState<ObjectTypeOption[]>([]);

  const fetchViews = useCallback(async () => {
    setLoading(true);
    try {
      const data = await viewApi.list({ base_type: objectTypeFilter });
      const list = data.views || [];
      setViews(list);

      // 拉取每个 view 的权限数量（失败容错为 0）
      const counts: Record<string, number> = {};
      await Promise.allSettled(
        list.map(async (v) => {
          try {
            const perms = await viewApi.listPermissions(v.id);
            counts[v.id] = perms.count ?? (perms.permissions?.length ?? 0);
          } catch {
            counts[v.id] = 0;
          }
        }),
      );
      setPermissionCounts(counts);

      // 提取 ObjectType 选项（去重）
      const seen = new Set<string>();
      const opts: ObjectTypeOption[] = [];
      list.forEach((v) => {
        if (v.base_type_id && !seen.has(v.base_type_id)) {
          seen.add(v.base_type_id);
          opts.push({ value: v.base_type_id, label: v.base_type_id });
        }
      });
      setObjectTypeOptions(opts);
    } catch (e) {
      message.error(`加载视图失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [objectTypeFilter]);

  useEffect(() => { void fetchViews(); }, [fetchViews]);

  const filtered = useMemo(() => {
    if (!searchText) return views;
    const kw = searchText.toLowerCase();
    return views.filter(
      (v) => v.name.toLowerCase().includes(kw) || v.base_type_id.toLowerCase().includes(kw),
    );
  }, [views, searchText]);

  const openCreate = useCallback(() => {
    createForm.resetFields();
    createForm.setFieldsValue({ row_limit: 100, enabled: true, role: 'analyst' });
    setCreateOpen(true);
  }, [createForm]);

  const handleCreate = useCallback(async () => {
    try {
      const values = await createForm.validateFields();
      setCreating(true);
      const user = (() => {
        try { return JSON.parse(localStorage.getItem('user') || '{}')?.username || 'system'; } catch { return 'system'; }
      })();
      const payload = {
        name: values.name,
        base_type_id: values.base_type_id,
        role: values.role,
        description: values.description || '',
        row_limit: values.row_limit || 100,
        enabled: values.enabled ?? true,
        created_by: user,
        projected_properties: [],
        filters: {},
        sort_order: [],
      };
      await viewApi.create(payload);
      message.success('视图已创建');
      setCreateOpen(false);
      void fetchViews();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`创建失败: ${(e as Error).message}`);
    } finally {
      setCreating(false);
    }
  }, [createForm, fetchViews]);

  const handleToggleEnabled = useCallback(async (v: ObjectView) => {
    try {
      await viewApi.update(v.id, { enabled: !v.enabled });
      message.success(v.enabled ? '已停用' : '已启用');
      void fetchViews();
    } catch (e) {
      message.error(`操作失败: ${(e as Error).message}`);
    }
  }, [fetchViews]);

  const handleDelete = useCallback(async (v: ObjectView) => {
    try {
      await viewApi.remove(v.id);
      message.success('视图已删除');
      void fetchViews();
    } catch (e) {
      message.error(`删除失败: ${(e as Error).message}`);
    }
  }, [fetchViews]);

  const handleClone = useCallback(async (v: ObjectView) => {
    // 后端 /api/ontology/views/{id}/clone 当前未必实现 — 我们在客户端构造 clone payload
    try {
      const user = (() => {
        try { return JSON.parse(localStorage.getItem('user') || '{}')?.username || 'system'; } catch { return 'system'; }
      })();
      await viewApi.create({
        name: `${v.name} (copy)`,
        base_type_id: v.base_type_id,
        role: v.role,
        description: v.description,
        projected_properties: [...v.projected_properties],
        filters: { ...v.filters },
        row_limit: v.row_limit,
        sort_order: [...v.sort_order],
        enabled: v.enabled,
        created_by: user,
      });
      message.success('视图已克隆');
      void fetchViews();
    } catch (e) {
      message.error(`克隆失败: ${(e as Error).message}`);
    }
  }, [fetchViews]);

  const columns: ColumnsType<ObjectView> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (v: string, r) => (
        <Space size={4} orientation="vertical" style={{ lineHeight: 1.2 }}>
          <Space>
            <strong>{v}</strong>
            <Tag color={STATUS_META[deriveStatus(r)].color}>{STATUS_META[deriveStatus(r)].label}</Tag>
          </Space>
        </Space>
      ),
    },
    {
      title: 'ObjectType',
      dataIndex: 'base_type_id',
      key: 'base_type_id',
      width: 160,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      render: (v: string) => v || <span style={{ color: '#999' }}>-</span>,
    },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (v: string) => <Tag color="purple">{v}</Tag>,
    },
    {
      title: 'Permission Count',
      key: 'permission_count',
      width: 130,
      align: 'right',
      render: (_: unknown, r) => <Tag color="cyan">{permissionCounts[r.id] ?? 0}</Tag>,
    },
    {
      title: 'Created By',
      dataIndex: 'created_by',
      key: 'created_by',
      width: 120,
    },
    {
      title: 'Created At',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 240,
      fixed: 'right',
      render: (_: unknown, r) => (
        <Space size={2}>
          <Tooltip title="Preview">
            <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => onPreview?.(r)} />
          </Tooltip>
          <Tooltip title="Edit">
            <Button size="small" type="link" icon={<EditOutlined />} onClick={() => onEdit?.(r)} />
          </Tooltip>
          <Tooltip title="Clone">
            <Button size="small" type="link" icon={<CopyOutlined />} onClick={() => void handleClone(r)} />
          </Tooltip>
          <Tooltip title={r.enabled ? 'Deactivate' : 'Activate'}>
            <Button
              size="small"
              type="link"
              icon={r.enabled ? <StopOutlined /> : <CheckOutlined />}
              onClick={() => void handleToggleEnabled(r)}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除此视图？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => void handleDelete(r)}
          >
            <Tooltip title="Delete">
              <Button size="small" type="link" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="object-view-list" style={{ padding: 16 }}>
      <Card size="small">
        <Row gutter={8} align="middle" justify="space-between" style={{ marginBottom: 12 }}>
          <Col xs={24} md={16}>
            <Space wrap>
              <Select
                allowClear
                placeholder="按 ObjectType 筛选"
                style={{ minWidth: 200 }}
                value={objectTypeFilter}
                onChange={(v) => setObjectTypeFilter(v)}
                options={objectTypeOptions}
              />
              <Search
                placeholder="按名称搜索"
                allowClear
                style={{ width: 220 }}
                onChange={(e) => setSearchText(e.target.value)}
                onSearch={setSearchText}
              />
            </Space>
          </Col>
          <Col xs={24} md={8} style={{ textAlign: 'right' }}>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={() => void fetchViews()}>
                {t('common.refresh') || '刷新'}
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
                {t('ontology.view.new') || 'New View'}
              </Button>
            </Space>
          </Col>
        </Row>

        <Spin spinning={loading}>
          {filtered.length === 0 ? (
            <Empty description="暂无视图" />
          ) : (
            <Table<ObjectView>
              rowKey="id"
              size="small"
              dataSource={filtered}
              columns={columns}
              pagination={{ pageSize: 10, showSizeChanger: true }}
              scroll={{ x: 1100 }}
            />
          )}
        </Spin>
      </Card>

      {/* Create Modal */}
      <Modal
        title="新建视图"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void handleCreate()}
        confirmLoading={creating}
        okText="创建"
        cancelText="取消"
        destroyOnHidden
      >
        <Form<CreateFormValues> form={createForm} layout="vertical">
          <Form.Item
            name="name"
            label="视图名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input placeholder="e.g. analyst_dashboard" />
          </Form.Item>
          <Form.Item
            name="base_type_id"
            label="ObjectType"
            rules={[{ required: true, message: '请输入 ObjectType ID' }]}
          >
            <Input placeholder="e.g. Person" />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请输入角色' }]}
          >
            <Input placeholder="e.g. analyst" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="可选" />
          </Form.Item>
          <Form.Item name="row_limit" label="行数限制">
            <InputNumber min={0} max={10000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default ObjectViewList;
