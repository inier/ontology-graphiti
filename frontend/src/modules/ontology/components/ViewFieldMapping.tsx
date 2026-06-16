/**
 * ViewFieldMapping 组件 —— 视图字段映射 / 过滤 / 排序 / 脱敏规则（FR-036 / T402）
 *
 * 三栏布局：
 *   - 左侧：ObjectType 字段树（可拖拽 / 双击加入）
 *   - 中间：当前视图的"已选字段"列表（可排序、删除、别名编辑）
 *   - 右侧：选中字段的属性面板（Display Label / Visible / Redaction Rule / Pattern）
 *
 * 底部 Tabs：
 *   - Filters: 字段过滤条件列表（field + operator + value）
 *   - Sort:    排序规则列表（field + direction）
 *   - Limit:   数字输入框（行数限制）
 *   - Permissions: 角色多选 + 每角色 redaction
 *
 * 顶部 "Test Query" 按钮 → 右侧 Drawer 显示模拟查询结果
 *
 * 对应后端：
 *   GET  /api/ontology/views/{id}
 *   PUT  /api/ontology/views/{id}
 *   POST /api/ontology/views/{id}/query  body: {user_id, ws_id, role}
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Tree, Input, Button, Space, Typography, Tag, Switch, Select, Empty, Spin, Drawer,
  Tabs, InputNumber, Form, List, Popconfirm, Table, message, Alert, Checkbox,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { ColumnsType } from 'antd/es/table';
import {
  ReloadOutlined, PlayCircleOutlined, PlusOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined, SaveOutlined,
} from '@ant-design/icons';
import { viewApi, type ObjectView, type ViewPermission } from '../services/viewApi';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;
const { Search } = Input;

export interface ViewFieldMappingProps {
  viewId: string;
  onClose?: () => void;
}

interface ObjectTypeField {
  name: string;
  data_type: string;
  required: boolean;
}

interface ObjectTypeInfo {
  object_type_id: string;
  name: string;
  display_name?: string;
  properties: ObjectTypeField[];
}

type RedactionRule = 'NONE' | 'REMOVE' | 'MASK_EMAIL' | 'MASK_SSN' | 'CUSTOM_PATTERN';

const REDACTION_OPTIONS: Array<{ value: RedactionRule; label: string }> = [
  { value: 'NONE', label: 'None (不处理)' },
  { value: 'REMOVE', label: 'Remove (移除字段)' },
  { value: 'MASK_EMAIL', label: 'Mask Email' },
  { value: 'MASK_SSN', label: 'Mask SSN' },
  { value: 'CUSTOM_PATTERN', label: 'Custom Pattern' },
];

const OPERATOR_OPTIONS = [
  { value: 'eq', label: '=' },
  { value: 'ne', label: '≠' },
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'contains', label: 'contains' },
  { value: 'starts_with', label: 'starts_with' },
  { value: 'in', label: 'in' },
];

interface SelectedField {
  /** 字段名（实际属性 key） */
  name: string;
  /** 在视图中的显示名（别名） */
  displayLabel: string;
  visible: boolean;
  redaction: RedactionRule;
  /** 仅在 redaction=CUSTOM_PATTERN 时使用 */
  customPattern?: string;
}

interface FilterRule {
  id: string;
  field: string;
  operator: string;
  value: string;
}

interface SortRule {
  id: string;
  field: string;
  direction: 'asc' | 'desc';
}

interface TestQueryResult {
  rows: Array<Record<string, unknown>>;
  total_count: number;
  truncated: boolean;
}

export function ViewFieldMapping({ viewId, onClose }: ViewFieldMappingProps) {
  const { t } = useI18n();
  void t;
  const [view, setView] = useState<ObjectView | null>(null);
  const [objectType, setObjectType] = useState<ObjectTypeInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // 三栏
  const [selectedFields, setSelectedFields] = useState<SelectedField[]>([]);
  const [activeFieldName, setActiveFieldName] = useState<string | null>(null);
  const [searchField, setSearchField] = useState('');

  // Tabs state
  const [filters, setFilters] = useState<FilterRule[]>([]);
  const [sorts, setSorts] = useState<SortRule[]>([]);
  const [rowLimit, setRowLimit] = useState<number>(100);
  const [permissions, setPermissions] = useState<ViewPermission[]>([]);
  const [filterForm] = Form.useForm();
  const [sortForm] = Form.useForm();
  const [permForm] = Form.useForm();

  // Test query
  const [testOpen, setTestOpen] = useState(false);
  const [testResult, setTestResult] = useState<TestQueryResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testRole, setTestRole] = useState('analyst');

  const activeField = useMemo(
    () => selectedFields.find((f) => f.name === activeFieldName) || null,
    [selectedFields, activeFieldName],
  );

  const fetchView = useCallback(async () => {
    setLoading(true);
    try {
      const v = await viewApi.get(viewId);
      setView(v);
      setSelectedFields(
        (v.projected_properties || []).map((name) => ({
          name,
          displayLabel: name,
          visible: true,
          redaction: 'NONE' as RedactionRule,
        })),
      );
      setFilters(
        Object.entries(v.filters || {}).map(([field, val], idx) => {
          if (val !== null && val !== undefined && typeof val !== 'object') {
            // Simple flat filters like { "name": "John" } → eq
            return { id: `f${idx}`, field, operator: 'eq', value: String(val) };
          }
          if (val && typeof val === 'object') {
            const obj = val as Record<string, unknown>;
            const op = Object.keys(obj)[0] || 'eq';
            return { id: `f${idx}`, field, operator: op, value: String(obj[op] ?? '') };
          }
          return { id: `f${idx}`, field, operator: 'eq', value: '' };
        }),
      );
      setSorts(
        (v.sort_order || []).map((s, idx) => ({
          id: `s${idx}`,
          field: String(s.field || ''),
          direction: (s.direction === 'desc' ? 'desc' : 'asc') as 'asc' | 'desc',
        })),
      );
      setRowLimit(v.row_limit ?? 100);
    } catch (e) {
      message.error(`加载视图失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [viewId]);

  const fetchObjectType = useCallback(async (typeId: string) => {
    try {
      // 视图 API 不直接返回 ObjectType schema；这里通过额外端点获取
      // 若没有端点则用空 schema 兜底
      const { apiClient } = await import('@/modules/shared/services/apiClient');
      try {
        const ot = await apiClient.get<{ object_type: ObjectTypeInfo }>(
          `/api/ontology/object-types/${encodeURIComponent(typeId)}`,
        );
        setObjectType(ot.object_type);
        return;
      } catch {
        // 端点不可用 — 兜底空 schema
      }
      setObjectType({ object_type_id: typeId, name: typeId, properties: [] });
    } catch {
      setObjectType(null);
    }
  }, []);

  const fetchPermissions = useCallback(async () => {
    try {
      const data = await viewApi.listPermissions(viewId);
      setPermissions(data.permissions || []);
    } catch {
      // 容错 — 不影响主流程
      setPermissions([]);
    }
  }, [viewId]);

  useEffect(() => { void fetchView(); }, [fetchView]);
  useEffect(() => {
    if (view) {
      void fetchObjectType(view.base_type_id);
    }
  }, [view, fetchObjectType]);
  useEffect(() => { void fetchPermissions(); }, [fetchPermissions]);

  const treeData: DataNode[] = useMemo(() => {
    if (!objectType) return [];
    return [
      {
        title: objectType.display_name || objectType.name,
        key: objectType.object_type_id,
        children: (objectType.properties || []).map((p) => ({
          title: (
            <Space size={4}>
              <span>{p.name}</span>
              <Tag color="blue">{p.data_type}</Tag>
              {p.required && <Tag color="red">required</Tag>}
            </Space>
          ),
          key: p.name,
          isLeaf: true,
        })),
      },
    ];
  }, [objectType]);

  const filteredTreeData = useMemo(() => {
    if (!searchField) return treeData;
    const kw = searchField.toLowerCase();
    return treeData.map((node) => ({
      ...node,
      children: (node.children || []).filter((c) => {
        const key = typeof c.key === 'string' ? c.key : String(c.key);
        return key.toLowerCase().includes(kw);
      }),
    }));
  }, [treeData, searchField]);

  const addField = useCallback((fieldName: string) => {
    if (selectedFields.some((f) => f.name === fieldName)) {
      message.warning('字段已存在');
      return;
    }
    setSelectedFields((prev) => [
      ...prev,
      { name: fieldName, displayLabel: fieldName, visible: true, redaction: 'NONE' },
    ]);
    setActiveFieldName(fieldName);
  }, [selectedFields]);

  const removeField = useCallback((name: string) => {
    setSelectedFields((prev) => prev.filter((f) => f.name !== name));
    if (activeFieldName === name) setActiveFieldName(null);
  }, [activeFieldName]);

  const moveField = useCallback((name: string, dir: -1 | 1) => {
    setSelectedFields((prev) => {
      const idx = prev.findIndex((f) => f.name === name);
      if (idx < 0) return prev;
      const newIdx = idx + dir;
      if (newIdx < 0 || newIdx >= prev.length) return prev;
      const copy = [...prev];
      const [item] = copy.splice(idx, 1);
      copy.splice(newIdx, 0, item);
      return copy;
    });
  }, []);

  const updateActiveField = useCallback((patch: Partial<SelectedField>) => {
    if (!activeFieldName) return;
    setSelectedFields((prev) => prev.map((f) => (f.name === activeFieldName ? { ...f, ...patch } : f)));
  }, [activeFieldName]);

  const handleAddFilter = useCallback(async () => {
    try {
      const v = await filterForm.validateFields();
      setFilters((prev) => [...prev, { id: `f${Date.now()}`, ...v }]);
      filterForm.resetFields();
    } catch (e) {
      if (!(e as { errorFields?: unknown[] }).errorFields) {
        message.error(`添加失败: ${(e as Error).message}`);
      }
    }
  }, [filterForm]);

  const handleAddSort = useCallback(async () => {
    try {
      const v = await sortForm.validateFields();
      setSorts((prev) => [...prev, { id: `s${Date.now()}`, ...v }]);
      sortForm.resetFields();
    } catch (e) {
      if (!(e as { errorFields?: unknown[] }).errorFields) {
        message.error(`添加失败: ${(e as Error).message}`);
      }
    }
  }, [sortForm]);

  const handleAddPermission = useCallback(async () => {
    try {
      const v = await permForm.validateFields();
      const created = await viewApi.attachPermission(viewId, {
        role: v.role,
        can_export: v.can_export ?? false,
        can_share: v.can_share ?? false,
        redaction_rules: {},
      });
      setPermissions((prev) => [...prev.filter((p) => p.id !== created.id), created]);
      permForm.resetFields();
      message.success('权限已添加');
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`添加失败: ${(e as Error).message}`);
    }
  }, [permForm, viewId]);

  const handleRemovePermission = useCallback(async (perm: ViewPermission) => {
    try {
      await viewApi.detachPermission(perm.id);
      setPermissions((prev) => prev.filter((p) => p.id !== perm.id));
      message.success('权限已移除');
    } catch (e) {
      message.error(`移除失败: ${(e as Error).message}`);
    }
  }, []);

  const handleUpdatePermissionRedaction = useCallback(async (perm: ViewPermission, field: string, value: string) => {
    try {
      const next: Record<string, string> = { ...(perm.redaction_rules as Record<string, string>) };
      if (value) next[field] = value; else delete next[field];
      const updated = await viewApi.attachPermission(viewId, {
        role: perm.role,
        can_export: perm.can_export,
        can_share: perm.can_share,
        redaction_rules: next,
      });
      setPermissions((prev) => prev.map((p) => (p.id === perm.id ? updated : p)));
    } catch (e) {
      message.error(`更新失败: ${(e as Error).message}`);
    }
  }, [viewId]);

  const handleSave = useCallback(async () => {
    if (!view) return;
    setSaving(true);
    try {
      const filtersObj: Record<string, Record<string, unknown>> = {};
      filters.forEach((f) => { filtersObj[f.field] = { [f.operator]: f.value }; });
      await viewApi.update(viewId, {
        projected_properties: selectedFields.map((f) => f.name),
        filters: filtersObj,
        sort_order: sorts.map((s) => ({ field: s.field, direction: s.direction })),
        row_limit: rowLimit,
      });
      message.success('已保存');
    } catch (e) {
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [view, viewId, selectedFields, filters, sorts, rowLimit]);

  const handleTestQuery = useCallback(async () => {
    setTestOpen(true);
    setTestLoading(true);
    try {
      const data = await viewApi.query(viewId, {
        user_id: 'tester',
        ws_id: view?.role || 'default',
        role: testRole,
      });
      setTestResult(data);
    } catch (e) {
      message.error(`查询失败: ${(e as Error).message}`);
      setTestResult(null);
    } finally {
      setTestLoading(false);
    }
  }, [viewId, testRole, view]);

  if (!view) {
    return (
      <div style={{ padding: 16 }}>
        <Spin spinning={loading}>
          <Empty description="加载中..." />
        </Spin>
      </div>
    );
  }

  const filterColumns: ColumnsType<FilterRule> = [
    { title: '字段', dataIndex: 'field', key: 'field' },
    { title: '操作符', dataIndex: 'operator', key: 'operator', render: (v: string) => <Tag>{v}</Tag> },
    { title: '值', dataIndex: 'value', key: 'value' },
    {
      title: '操作',
      key: 'op',
      width: 80,
      render: (_: unknown, r) => (
        <Button size="small" danger type="link" icon={<DeleteOutlined />} onClick={() => setFilters((prev) => prev.filter((f) => f.id !== r.id))} />
      ),
    },
  ];

  const sortColumns: ColumnsType<SortRule> = [
    { title: '字段', dataIndex: 'field', key: 'field' },
    { title: '方向', dataIndex: 'direction', key: 'direction', render: (v: string) => <Tag color={v === 'asc' ? 'blue' : 'purple'}>{v}</Tag> },
    {
      title: '操作',
      key: 'op',
      width: 80,
      render: (_: unknown, r) => (
        <Button size="small" danger type="link" icon={<DeleteOutlined />} onClick={() => setSorts((prev) => prev.filter((s) => s.id !== r.id))} />
      ),
    },
  ];

  const fieldOptions = selectedFields.map((f) => ({ value: f.name, label: f.name }));

  return (
    <div data-testid="view-field-mapping" style={{ padding: 16 }}>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }} wrap>
          <Space>
            <Title level={4} style={{ margin: 0 }}>{view.name}</Title>
            <Tag color="blue">{view.base_type_id}</Tag>
            <Tag color="purple">{view.role}</Tag>
            {view.enabled ? <Tag color="green">enabled</Tag> : <Tag>disabled</Tag>}
          </Space>
          <Space>
            {onClose && <Button onClick={onClose}>关闭</Button>}
            <Button icon={<PlayCircleOutlined />} onClick={() => void handleTestQuery()}>
              Test Query
            </Button>
            <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={() => void handleSave()}>
              保存
            </Button>
          </Space>
        </Space>
      </Card>

      <Row gutter={12}>
        {/* 左侧字段树 */}
        <Col xs={24} md={6}>
          <Card size="small" title={`字段库: ${view.base_type_id}`}>
            <Search
              placeholder="搜索字段"
              allowClear
              size="small"
              style={{ marginBottom: 8 }}
              onChange={(e) => setSearchField(e.target.value)}
            />
            {!objectType ? (
              <Empty description="无字段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : filteredTreeData[0]?.children?.length === 0 ? (
              <Empty description="无匹配字段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Tree
                treeData={filteredTreeData}
                defaultExpandAll
                onDoubleClick={(_, node) => {
                  const key = typeof node.key === 'string' ? node.key : String(node.key);
                  if (key !== objectType.object_type_id) {
                    addField(key);
                  }
                }}
                blockNode
              />
            )}
            <Alert
              type="info"
              showIcon
              style={{ marginTop: 8, fontSize: 12 }}
              message="双击叶子节点加入视图"
            />
          </Card>
        </Col>

        {/* 中间已选字段 */}
        <Col xs={24} md={10}>
          <Card
            size="small"
            title={`已选字段 (${selectedFields.length})`}
            extra={selectedFields.length > 0 && (
              <Button size="small" danger type="link" onClick={() => { setSelectedFields([]); setActiveFieldName(null); }}>
                清空
              </Button>
            )}
          >
            {selectedFields.length === 0 ? (
              <Empty description="请从左侧添加字段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <List
                size="small"
                dataSource={selectedFields}
                renderItem={(f, idx) => (
                  <List.Item
                    onClick={() => setActiveFieldName(f.name)}
                    style={{
                      cursor: 'pointer',
                      background: activeFieldName === f.name ? '#e6f4ff' : undefined,
                      padding: '6px 12px',
                    }}
                    actions={[
                      <Button
                        key="up"
                        size="small"
                        type="text"
                        icon={<ArrowUpOutlined />}
                        disabled={idx === 0}
                        onClick={(e) => { e.stopPropagation(); moveField(f.name, -1); }}
                      />,
                      <Button
                        key="down"
                        size="small"
                        type="text"
                        icon={<ArrowDownOutlined />}
                        disabled={idx === selectedFields.length - 1}
                        onClick={(e) => { e.stopPropagation(); moveField(f.name, 1); }}
                      />,
                      <Button
                        key="del"
                        size="small"
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={(e) => { e.stopPropagation(); removeField(f.name); }}
                      />,
                    ]}
                  >
                    <Space>
                      <Text strong>{f.displayLabel || f.name}</Text>
                      {!f.visible && <Tag>hidden</Tag>}
                      {f.redaction !== 'NONE' && <Tag color="orange">{f.redaction}</Tag>}
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>

        {/* 右侧属性面板 */}
        <Col xs={24} md={8}>
          <Card size="small" title="字段属性">
            {!activeField ? (
              <Empty description="请选择字段" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                <div>
                  <Text type="secondary">字段名</Text>
                  <Input value={activeField.name} disabled />
                </div>
                <div>
                  <Text type="secondary">Display Label</Text>
                  <Input
                    value={activeField.displayLabel}
                    onChange={(e) => updateActiveField({ displayLabel: e.target.value })}
                    placeholder="别名"
                  />
                </div>
                <div>
                  <Space>
                    <Text type="secondary">Visible</Text>
                    <Switch
                      checked={activeField.visible}
                      onChange={(v) => updateActiveField({ visible: v })}
                    />
                  </Space>
                </div>
                <div>
                  <Text type="secondary">Redaction Rule</Text>
                  <Select
                    style={{ width: '100%' }}
                    value={activeField.redaction}
                    onChange={(v) => updateActiveField({ redaction: v as RedactionRule })}
                    options={REDACTION_OPTIONS}
                  />
                </div>
                {activeField.redaction === 'CUSTOM_PATTERN' && (
                  <div>
                    <Text type="secondary">Pattern (使用 # 占位保留原字符)</Text>
                    <Input
                      value={activeField.customPattern || ''}
                      onChange={(e) => updateActiveField({ customPattern: e.target.value })}
                      placeholder="e.g. ###-##-####"
                    />
                  </div>
                )}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Card size="small" style={{ marginTop: 12 }}>
        <Tabs
          defaultActiveKey="filters"
          items={[
            {
              key: 'filters',
              label: 'Filters',
              children: (
                <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                  <Form form={filterForm} layout="inline" initialValues={{ operator: 'eq' }}>
                    <Form.Item name="field" rules={[{ required: true, message: '字段' }]}>
                      <Select placeholder="字段" style={{ width: 180 }} options={fieldOptions} allowClear showSearch />
                    </Form.Item>
                    <Form.Item name="operator">
                      <Select options={OPERATOR_OPTIONS} style={{ width: 130 }} />
                    </Form.Item>
                    <Form.Item name="value" rules={[{ required: true, message: '值' }]}>
                      <Input placeholder="值" style={{ width: 200 }} />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" icon={<PlusOutlined />} onClick={() => void handleAddFilter()}>
                        添加
                      </Button>
                    </Form.Item>
                  </Form>
                  {filters.length === 0 ? (
                    <Empty description="暂无过滤条件" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table<FilterRule> rowKey="id" size="small" dataSource={filters} columns={filterColumns} pagination={false} />
                  )}
                </Space>
              ),
            },
            {
              key: 'sort',
              label: 'Sort',
              children: (
                <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                  <Form form={sortForm} layout="inline" initialValues={{ direction: 'asc' }}>
                    <Form.Item name="field" rules={[{ required: true, message: '字段' }]}>
                      <Select placeholder="字段" style={{ width: 220 }} options={fieldOptions} allowClear showSearch />
                    </Form.Item>
                    <Form.Item name="direction">
                      <Select
                        options={[
                          { value: 'asc', label: '升序 asc' },
                          { value: 'desc', label: '降序 desc' },
                        ]}
                        style={{ width: 130 }}
                      />
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" icon={<PlusOutlined />} onClick={() => void handleAddSort()}>
                        添加
                      </Button>
                    </Form.Item>
                  </Form>
                  {sorts.length === 0 ? (
                    <Empty description="暂无排序" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table<SortRule> rowKey="id" size="small" dataSource={sorts} columns={sortColumns} pagination={false} />
                  )}
                </Space>
              ),
            },
            {
              key: 'limit',
              label: 'Limit',
              children: (
                <Space orientation="vertical">
                  <Text>查询返回行数限制</Text>
                  <InputNumber min={0} max={10000} value={rowLimit} onChange={(v) => setRowLimit(Number(v) || 0)} />
                </Space>
              ),
            },
            {
              key: 'permissions',
              label: 'Permissions',
              children: (
                <Space orientation="vertical" style={{ width: '100%' }} size="middle">
                  <Form form={permForm} layout="inline" initialValues={{ can_export: false, can_share: false }}>
                    <Form.Item name="role" rules={[{ required: true, message: '角色' }]}>
                      <Input placeholder="角色名" style={{ width: 160 }} />
                    </Form.Item>
                    <Form.Item name="can_export" valuePropName="checked">
                      <Checkbox>can_export</Checkbox>
                    </Form.Item>
                    <Form.Item name="can_share" valuePropName="checked">
                      <Checkbox>can_share</Checkbox>
                    </Form.Item>
                    <Form.Item>
                      <Button type="primary" icon={<PlusOutlined />} onClick={() => void handleAddPermission()}>
                        添加角色
                      </Button>
                    </Form.Item>
                  </Form>

                  {permissions.length === 0 ? (
                    <Empty description="暂无角色权限" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <List
                      size="small"
                      dataSource={permissions}
                      renderItem={(p) => (
                        <List.Item
                          actions={[
                            <Popconfirm
                              key="del"
                              title="确认移除此角色？"
                              onConfirm={() => void handleRemovePermission(p)}
                            >
                              <Button size="small" danger type="link" icon={<DeleteOutlined />} />
                            </Popconfirm>,
                          ]}
                        >
                          <Space orientation="vertical" style={{ width: '100%' }}>
                            <Space>
                              <Tag color="purple">{p.role}</Tag>
                              {p.can_export && <Tag color="green">export</Tag>}
                              {p.can_share && <Tag color="blue">share</Tag>}
                            </Space>
                            {Object.keys(p.redaction_rules || {}).length > 0 && (
                              <Space wrap>
                                {Object.entries(p.redaction_rules as Record<string, string>).map(([field, rule]) => (
                                  <Space key={field} size={4}>
                                    <Text type="secondary" style={{ fontSize: 12 }}>{field}:</Text>
                                    <Tag color="orange">{rule}</Tag>
                                    <Button
                                      size="small"
                                      type="link"
                                      icon={<DeleteOutlined />}
                                      onClick={() => void handleUpdatePermissionRedaction(p, field, '')}
                                    />
                                  </Space>
                                ))}
                              </Space>
                            )}
                          </Space>
                        </List.Item>
                      )}
                    />
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title={`Test Query — 角色: ${testRole}`}
        open={testOpen}
        onClose={() => setTestOpen(false)}
        width={640}
        extra={
          <Space>
            <Select
              size="small"
              value={testRole}
              onChange={setTestRole}
              options={[
                { value: 'analyst', label: 'analyst' },
                { value: 'admin', label: 'admin' },
                { value: 'viewer', label: 'viewer' },
              ]}
            />
            <Button size="small" icon={<ReloadOutlined />} onClick={() => void handleTestQuery()}>
              重新查询
            </Button>
          </Space>
        }
      >
        <Spin spinning={testLoading}>
          {!testResult ? (
            <Empty description="无结果" />
          ) : (
            <Space orientation="vertical" style={{ width: '100%' }}>
              <Space>
                <Tag color="blue">Total: {testResult.total_count}</Tag>
                {testResult.truncated && <Tag color="orange">truncated</Tag>}
              </Space>
              {testResult.rows.length === 0 ? (
                <Empty description="无返回数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <pre style={{ background: '#fafafa', padding: 12, borderRadius: 4, maxHeight: 480, overflow: 'auto' }}>
                  {JSON.stringify(testResult.rows.slice(0, 20), null, 2)}
                </pre>
              )}
            </Space>
          )}
        </Spin>
      </Drawer>
    </div>
  );
}

export default ViewFieldMapping;
