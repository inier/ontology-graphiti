/**
 * MixinConfig 组件 —— Mixin 列表 + 关联到 ObjectType（FR-033 / T363）
 *
 * 顶部：Tabs "Mixin Library" / "Mixin Bindings"
 * Tab 1 (Mixin Library):
 *   - 表格列出所有 Mixin（name / description / property_count / used_by_count）
 *   - "Create Mixin" 按钮 → Modal 输入 name + properties（PropertyEditor）
 *   - 编辑 / 删除 操作
 * Tab 2 (Mixin Bindings):
 *   - 左：ObjectType 列表（带搜索）
 *   - 右：当前 ObjectType 已绑定的 Mixin（可移除）+ 可添加的 Mixin（Transfer 组件）
 *   - "Save Bindings" 按钮
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Tabs, Tag, Button, Space, Typography, Empty, Spin, Modal, Form, Input, Popconfirm, Transfer, Input as AntInput, Select, Switch, message, Row, Col,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { TransferProps } from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined, LinkOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import type { PropertyDefinition } from '../services/ontologyApi';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;
const { TextArea } = AntInput;
const { Search } = AntInput;

export interface MixinConfigProps {
  workspaceId?: string;
}

interface Mixin {
  mixin_id: string;
  name: string;
  description?: string;
  property_count: number;
  used_by_count: number;
  properties: PropertyDefinition[];
}

interface ObjectTypeSummary {
  object_type_id: string;
  name: string;
  bound_mixin_ids: string[];
}

const DATA_TYPE_OPTIONS = [
  { label: 'String', value: 'string' },
  { label: 'Integer', value: 'integer' },
  { label: 'Float', value: 'float' },
  { label: 'Boolean', value: 'boolean' },
  { label: 'Date', value: 'date' },
  { label: 'DateTime', value: 'datetime' },
  { label: 'JSON', value: 'json' },
  { label: 'Array', value: 'array' },
];

const CLASSIFICATION_OPTIONS = [
  { label: 'TS', value: 'TS' },
  { label: 'S', value: 'S' },
  { label: 'C', value: 'C' },
  { label: 'U', value: 'U' },
];

export function MixinConfig({ workspaceId }: MixinConfigProps) {
  const { t } = useI18n();
  void t;
  void workspaceId;
  const [activeTab, setActiveTab] = useState<'library' | 'bindings'>('library');
  const [mixins, setMixins] = useState<Mixin[]>([]);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<Mixin | null>(null);
  const [form] = Form.useForm();
  const [propertyList, setPropertyList] = useState<PropertyDefinition[]>([]);

  // Bindings state
  const [objectTypes, setObjectTypes] = useState<ObjectTypeSummary[]>([]);
  const [selectedObjectTypeId, setSelectedObjectTypeId] = useState<string | null>(null);
  const [, setBoundMixinIds] = useState<string[]>([]);
  const [objectTypeSearch, setObjectTypeSearch] = useState('');
  const [saving, setSaving] = useState(false);
  const [pendingMixinIds, setPendingMixinIds] = useState<string[]>([]);

  const fetchMixins = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ mixins: Mixin[] }>('/api/ontology/mixins');
      setMixins(data.mixins || []);
    } catch (e) {
      message.error(`加载 Mixin 失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchObjectTypes = useCallback(async () => {
    try {
      const data = await apiClient.get<{ object_types: ObjectTypeSummary[] }>('/api/ontology/object-types');
      setObjectTypes(data.object_types || []);
    } catch (e) {
      message.error(`加载 ObjectType 失败: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    void fetchMixins();
    void fetchObjectTypes();
  }, [fetchMixins, fetchObjectTypes]);

  const openCreate = useCallback(() => {
    setEditing(null);
    form.resetFields();
    setPropertyList([]);
    setEditOpen(true);
  }, [form]);

  const openEdit = useCallback((m: Mixin) => {
    setEditing(m);
    form.setFieldsValue({ name: m.name, description: m.description });
    setPropertyList(m.properties || []);
    setEditOpen(true);
  }, [form]);

  const addProperty = useCallback(() => {
    setPropertyList((prev) => [
      ...prev,
      {
        name: '',
        data_type: 'string',
        required: false,
        classification_level: 'U',
      },
    ]);
  }, []);

  const updateProperty = useCallback((index: number, p: PropertyDefinition) => {
    setPropertyList((prev) => prev.map((it, i) => (i === index ? p : it)));
  }, []);

  const removeProperty = useCallback((index: number) => {
    setPropertyList((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSaveMixin = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        ...values,
        properties: propertyList.filter((p) => p.name),
      };
      if (editing) {
        await apiClient.put(`/api/ontology/mixins/${editing.mixin_id}`, payload);
        message.success('Mixin 已更新');
      } else {
        await apiClient.post('/api/ontology/mixins', payload);
        message.success('Mixin 已创建');
      }
      setEditOpen(false);
      void fetchMixins();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`保存失败: ${(e as Error).message}`);
    }
  }, [form, propertyList, editing, fetchMixins]);

  const handleDeleteMixin = useCallback(async (m: Mixin) => {
    try {
      await apiClient.delete(`/api/ontology/mixins/${m.mixin_id}`);
      message.success('Mixin 已删除');
      void fetchMixins();
    } catch (e) {
      message.error(`删除失败: ${(e as Error).message}`);
    }
  }, [fetchMixins]);

  // ---- Bindings ----
  const filteredObjectTypes = useMemo(() => {
    if (!objectTypeSearch) return objectTypes;
    const kw = objectTypeSearch.toLowerCase();
    return objectTypes.filter((o) => o.name.toLowerCase().includes(kw));
  }, [objectTypes, objectTypeSearch]);

  const fetchObjectTypeMixins = useCallback(async (objectTypeId: string) => {
    try {
      const data = await apiClient.get<{ mixin_ids: string[] }>(
        `/api/ontology/object-types/${objectTypeId}/mixins`,
      );
      const ids = data.mixin_ids || [];
      setBoundMixinIds(ids);
      setPendingMixinIds(ids);
    } catch (e) {
      message.error(`加载绑定失败: ${(e as Error).message}`);
      setBoundMixinIds([]);
      setPendingMixinIds([]);
    }
  }, []);

  useEffect(() => {
    if (selectedObjectTypeId) {
      void fetchObjectTypeMixins(selectedObjectTypeId);
    } else {
      setBoundMixinIds([]);
      setPendingMixinIds([]);
    }
  }, [selectedObjectTypeId, fetchObjectTypeMixins]);

  const handleSelectObjectType = useCallback((id: string) => {
    setSelectedObjectTypeId(id);
  }, []);

  const transferData: TransferProps['dataSource'] = useMemo(
    () => mixins.map((m) => ({
      key: m.mixin_id,
      title: m.name,
      description: m.description,
    })),
    [mixins],
  );

  const handleSaveBindings = useCallback(async () => {
    if (!selectedObjectTypeId) {
      message.warning('请先选择一个 ObjectType');
      return;
    }
    setSaving(true);
    try {
      await apiClient.put(
        `/api/ontology/object-types/${selectedObjectTypeId}/mixins`,
        { mixin_ids: pendingMixinIds },
      );
      message.success('绑定已保存');
      setBoundMixinIds(pendingMixinIds);
      void fetchObjectTypes();
    } catch (e) {
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [selectedObjectTypeId, pendingMixinIds, fetchObjectTypes]);

  const columns: ColumnsType<Mixin> = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (v: string) => <Text strong>{v}</Text> },
    { title: '描述', dataIndex: 'description', key: 'description', render: (v?: string) => v || <Text type="secondary">-</Text> },
    { title: '属性数', dataIndex: 'property_count', key: 'property_count', width: 90, align: 'right' },
    { title: '被引用数', dataIndex: 'used_by_count', key: 'used_by_count', width: 110, align: 'right', render: (v: number) => <Tag color={v > 0 ? 'blue' : 'default'}>{v}</Tag> },
    {
      title: '操作',
      key: 'actions',
      width: 160,
      render: (_: unknown, r) => (
        <Space size={4}>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
          <Popconfirm
            title="确认删除此 Mixin？"
            okText="删除"
            cancelText="取消"
            onConfirm={() => handleDeleteMixin(r)}
          >
            <Button size="small" type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="mixin-config" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>
          <AppstoreOutlined /> Mixin 配置
        </Title>
        {activeTab === 'library' && (
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => void fetchMixins()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              Create Mixin
            </Button>
          </Space>
        )}
      </Space>

      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={(k) => setActiveTab(k as 'library' | 'bindings')}
          items={[
            {
              key: 'library',
              label: 'Mixin Library',
              children: (
                <Spin spinning={loading}>
                  {mixins.length === 0 ? (
                    <Empty description="暂无 Mixin" />
                  ) : (
                    <AdvancedTable<Mixin>
                      rowKey="mixin_id"
                      size="small"
                      dataSource={mixins}
                      columns={columns}
                      pagination={{ pageSize: 10 }}
                    />
                  )}
                </Spin>
              ),
            },
            {
              key: 'bindings',
              label: 'Mixin Bindings',
              children: (
                <div>
                  <Row gutter={16}>
                    <Col xs={24} md={8}>
                      <Card size="small" title="ObjectType">
                        <Search
                          placeholder="搜索 ObjectType"
                          allowClear
                          onChange={(e) => setObjectTypeSearch(e.target.value)}
                          style={{ marginBottom: 8 }}
                        />
                        <Spin spinning={loading && objectTypes.length === 0}>
                          {filteredObjectTypes.length === 0 ? (
                            <Empty description="无 ObjectType" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                          ) : (
                            <div style={{ maxHeight: 400, overflowY: 'auto' }}>
                              {filteredObjectTypes.map((ot) => (
                                <div
                                  key={ot.object_type_id}
                                  onClick={() => handleSelectObjectType(ot.object_type_id)}
                                  style={{
                                    padding: '8px 12px',
                                    borderRadius: 4,
                                    cursor: 'pointer',
                                    background: selectedObjectTypeId === ot.object_type_id ? '#e6f4ff' : undefined,
                                    border: selectedObjectTypeId === ot.object_type_id ? '1px solid #91caff' : '1px solid transparent',
                                    marginBottom: 4,
                                  }}
                                >
                                  <Space>
                                    <Text strong>{ot.name}</Text>
                                    <Tag>{ot.bound_mixin_ids.length} mixins</Tag>
                                  </Space>
                                </div>
                              ))}
                            </div>
                          )}
                        </Spin>
                      </Card>
                    </Col>
                    <Col xs={24} md={16}>
                      <Card
                        size="small"
                        title={
                          <Space>
                            <LinkOutlined />
                            <span>已绑定 Mixin</span>
                            {selectedObjectTypeId && (
                              <Tag color="blue">
                                {objectTypes.find((o) => o.object_type_id === selectedObjectTypeId)?.name}
                              </Tag>
                            )}
                          </Space>
                        }
                        extra={
                          <Button
                            type="primary"
                            size="small"
                            disabled={!selectedObjectTypeId}
                            loading={saving}
                            onClick={handleSaveBindings}
                          >
                            Save Bindings
                          </Button>
                        }
                      >
                        {!selectedObjectTypeId ? (
                          <Empty description="请先选择左侧 ObjectType" />
                        ) : (
                          <Transfer<{ key: string; title: string; description?: string }>
                            dataSource={transferData}
                            titles={['可添加', '已绑定']}
                            targetKeys={pendingMixinIds}
                            onChange={(keys) => setPendingMixinIds(keys as string[])}
                            render={(item) => (
                              <span>
                                <Text strong>{item.title}</Text>
                                {item.description && (
                                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                                    {item.description}
                                  </Text>
                                )}
                              </span>
                            )}
                            listStyle={{ width: '100%', height: 360 }}
                            showSearch
                            filterOption={(input, item) =>
                              item.title.toLowerCase().includes(input.toLowerCase()) ||
                              (item.description || '').toLowerCase().includes(input.toLowerCase())
                            }
                          />
                        )}
                      </Card>
                    </Col>
                  </Row>
                </div>
              ),
            },
          ]}
        />
      </Card>

      <Modal
        title={editing ? '编辑 Mixin' : '创建 Mixin'}
        open={editOpen}
        onOk={handleSaveMixin}
        onCancel={() => { setEditOpen(false); form.resetFields(); setPropertyList([]); }}
        okText="保存"
        cancelText="取消"
        width={720}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="Mixin 名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="mixin_name" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="Mixin 用途" />
          </Form.Item>
          <div style={{ marginBottom: 8 }}>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Text strong>属性列表</Text>
              <Button size="small" icon={<PlusOutlined />} onClick={addProperty}>
                新增属性
              </Button>
            </Space>
          </div>
          {propertyList.length === 0 ? (
            <Empty description="暂无属性" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            propertyList.map((p, idx) => (
              <Card
                key={idx}
                size="small"
                style={{ marginBottom: 8 }}
                extra={
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => removeProperty(idx)}
                  />
                }
              >
                <Row gutter={8}>
                  <Col span={8}>
                    <Form.Item label="属性名" style={{ marginBottom: 0 }}>
                      <Input
                        value={p.name}
                        placeholder="property_name"
                        onChange={(e) => updateProperty(idx, { ...p, name: e.target.value })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="数据类型" style={{ marginBottom: 0 }}>
                      <Select
                        value={p.data_type}
                        onChange={(v) => updateProperty(idx, { ...p, data_type: v as PropertyDefinition['data_type'] })}
                        options={DATA_TYPE_OPTIONS}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={4}>
                    <Form.Item label="必填" style={{ marginBottom: 0 }}>
                      <Switch
                        checked={p.required}
                        onChange={(v) => updateProperty(idx, { ...p, required: v })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="密级" style={{ marginBottom: 0 }}>
                      <Select
                        value={p.classification_level}
                        onChange={(v) => updateProperty(idx, { ...p, classification_level: v as PropertyDefinition['classification_level'] })}
                        options={CLASSIFICATION_OPTIONS}
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>
            ))
          )}
        </Form>
      </Modal>
    </div>
  );
}

export default MixinConfig;
