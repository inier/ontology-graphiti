/**
 * MixinConfig 组件 —— Mixin 列表 + 挂接到 ObjectType（FR-033 / T363）
 *
 * 顶部：Tabs "Mixin Library" / "Mixin Bindings"
 * Tab 1 (Mixin Library):
 *   - 表格列出所有 Mixin（name / description / 属性数 / 引用类型数）
 *   - "Create Mixin" 按钮 → Modal 输入 name + properties
 *   - 编辑 / 删除 操作
 * Tab 2 (Mixin Bindings):
 *   - 左：ObjectType 列表（带搜索）
 *   - 右：当前 ObjectType 已挂接的 Mixin（Transfer）
 *   - "Save Bindings" 按钮 → 按差集调用 attach / detach
 *
 * ── 后端真实契约（此前本组件整体对不上，全部请求 404 / 422）────────────
 *   `Mixin` 模型（inheritance/models/mixin.py）：
 *     `{ id, name, description, properties: string[], target_type_ids: string[], created_at }`
 *     · `properties` 只是**属性名列表**，不是带 data_type/required/密级的对象；
 *     · 主键字段名是 `id`，不是 `mixin_id`；
 *     · 没有 `property_count` / `used_by_count` / `bound_mixin_ids`，均由本地派生。
 *   端点（inheritance/api/routes.py，前缀 `/api/ontology/inheritance`）：
 *     GET/POST      /mixins
 *     GET/PUT/DELETE /mixins/{id}
 *     POST          /mixins/{id}/attach/{type_id}
 *     POST          /mixins/{id}/detach/{type_id}
 *   不存在 `/api/ontology/mixins`，也不存在 `/object-types/{id}/mixins`（GET/PUT 都没有），
 *   因此「某类型绑定了哪些 Mixin」只能由 `target_type_ids` 反查、绑定只能走 attach/detach。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Tabs, Tag, Button, Space, Typography, Empty, Spin, Modal, Form, Input, Popconfirm, Transfer, Input as AntInput, Select, message, Row, Col,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { TransferProps } from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined, AppstoreOutlined, LinkOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;
const { TextArea } = AntInput;
const { Search } = AntInput;

/** 继承 API 前缀（mixin 挂在 inheritance 命名空间下） */
const MIXIN_BASE = '/api/ontology/inheritance/mixins';

interface Mixin {
  id: string;
  name: string;
  description: string;
  /** 复用的属性名列表 */
  properties: string[];
  /** 已挂接的 ObjectType id 列表 */
  target_type_ids: string[];
  created_at?: string;
}

interface ObjectTypeSummary {
  object_type_id: string;
  name: string;
}

interface MixinFormValues {
  name: string;
  description?: string;
  properties?: string[];
}

export function MixinConfig() {
  const [activeTab, setActiveTab] = useState<'library' | 'bindings'>('library');
  const [mixins, setMixins] = useState<Mixin[]>([]);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<Mixin | null>(null);
  const [form] = Form.useForm<MixinFormValues>();

  // Bindings state
  const [objectTypes, setObjectTypes] = useState<ObjectTypeSummary[]>([]);
  const [selectedObjectTypeId, setSelectedObjectTypeId] = useState<string | null>(null);
  const [objectTypeSearch, setObjectTypeSearch] = useState('');
  const [saving, setSaving] = useState(false);
  /**
   * 用户在 Transfer 里的未保存改动。
   * `null` = 还没改过，直接用 `target_type_ids` 反查出来的真实绑定；
   * 避免「用 effect 把 props 派生的值写进 state」这种会多一次渲染的写法。
   */
  const [pendingMixinIdsState, setPendingMixinIds] = useState<string[] | null>(null);

  const fetchMixins = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ mixins?: Mixin[] }>(MIXIN_BASE);
      setMixins(data?.mixins ?? []);
    } catch (e) {
      message.error(`加载 Mixin 失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchObjectTypes = useCallback(async () => {
    try {
      const data = await apiClient.get<{ object_types?: ObjectTypeSummary[] }>('/api/ontology/object-types');
      setObjectTypes(data?.object_types ?? []);
    } catch (e) {
      message.error(`加载 ObjectType 失败: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    // 数据拉取；两个 fetch 内部都先 await 再 setState，规则无法穿透 async 边界，
    // 按仓库既有约定显式豁免（同 InheritanceGraph）。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchMixins();
    void fetchObjectTypes();
  }, [fetchMixins, fetchObjectTypes]);

  /** 某 ObjectType 当前挂接的 Mixin id —— 由 target_type_ids 反查（后端无专用端点）。 */
  const boundMixinIdsOf = useCallback(
    (objectTypeId: string) => mixins.filter((m) => (m.target_type_ids ?? []).includes(objectTypeId)).map((m) => m.id),
    [mixins],
  );

  const pendingMixinIds = useMemo(
    () => pendingMixinIdsState ?? (selectedObjectTypeId ? boundMixinIdsOf(selectedObjectTypeId) : []),
    [pendingMixinIdsState, selectedObjectTypeId, boundMixinIdsOf],
  );

  const openCreate = useCallback(() => {
    setEditing(null);
    form.resetFields();
    setEditOpen(true);
  }, [form]);

  const openEdit = useCallback((m: Mixin) => {
    setEditing(m);
    form.setFieldsValue({ name: m.name, description: m.description, properties: m.properties ?? [] });
    setEditOpen(true);
  }, [form]);

  const handleSaveMixin = useCallback(async () => {
    try {
      const values = await form.validateFields();
      const payload = {
        name: values.name,
        description: values.description ?? '',
        // 后端 CreateMixinRequest.properties 是 List[str]，只存属性名
        properties: (values.properties ?? []).filter(Boolean),
      };
      if (editing) {
        await apiClient.put(`${MIXIN_BASE}/${encodeURIComponent(editing.id)}`, payload);
        message.success('Mixin 已更新');
      } else {
        await apiClient.post(MIXIN_BASE, payload);
        message.success('Mixin 已创建');
      }
      setEditOpen(false);
      void fetchMixins();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`保存失败: ${(e as Error).message}`);
    }
  }, [form, editing, fetchMixins]);

  const handleDeleteMixin = useCallback(async (m: Mixin) => {
    try {
      await apiClient.delete(`${MIXIN_BASE}/${encodeURIComponent(m.id)}`);
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
    return objectTypes.filter((o) => (o.name ?? '').toLowerCase().includes(kw));
  }, [objectTypes, objectTypeSearch]);

  const handleSelectObjectType = useCallback((id: string) => {
    setSelectedObjectTypeId(id);
    // 切换对象类型时丢弃上一个类型的未保存改动，回落到新类型的真实绑定。
    setPendingMixinIds(null);
  }, []);

  const transferData: TransferProps['dataSource'] = useMemo(
    () => mixins.map((m) => ({
      key: m.id,
      title: m.name,
      description: m.description,
    })),
    [mixins],
  );

  /**
   * 保存绑定：后端只有 attach / detach 两个按 (mixin, type) 的单条端点，
   * 没有幂等的「整体覆盖」PUT，故此处按差集逐条调用。
   */
  const handleSaveBindings = useCallback(async () => {
    if (!selectedObjectTypeId) {
      message.warning('请先选择一个 ObjectType');
      return;
    }
    setSaving(true);
    try {
      const current = new Set(boundMixinIdsOf(selectedObjectTypeId));
      const next = new Set(pendingMixinIds);
      const toAttach = [...next].filter((id) => !current.has(id));
      const toDetach = [...current].filter((id) => !next.has(id));
      if (toAttach.length === 0 && toDetach.length === 0) {
        message.info('绑定未变更');
        return;
      }
      await Promise.all([
        ...toAttach.map((id) =>
          apiClient.post(
            `${MIXIN_BASE}/${encodeURIComponent(id)}/attach/${encodeURIComponent(selectedObjectTypeId)}`,
            {},
          ),
        ),
        ...toDetach.map((id) =>
          apiClient.post(
            `${MIXIN_BASE}/${encodeURIComponent(id)}/detach/${encodeURIComponent(selectedObjectTypeId)}`,
            {},
          ),
        ),
      ]);
      message.success(`绑定已保存（新增 ${toAttach.length}，移除 ${toDetach.length}）`);
      await fetchMixins();
      // 保存后回落到「由后端数据派生」，清掉本地未保存态。
      setPendingMixinIds(null);
    } catch (e) {
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [selectedObjectTypeId, pendingMixinIds, boundMixinIdsOf, fetchMixins]);

  const columns: ColumnsType<Mixin> = [
    { title: '名称', dataIndex: 'name', key: 'name', render: (v: string) => <Text strong>{v}</Text> },
    { title: '描述', dataIndex: 'description', key: 'description', render: (v?: string) => v || <Text type="secondary">-</Text> },
    {
      title: '属性数',
      key: 'property_count',
      width: 90,
      align: 'right',
      render: (_: unknown, r) => r.properties?.length ?? 0,
    },
    {
      title: '引用类型数',
      key: 'used_by_count',
      width: 110,
      align: 'right',
      render: (_: unknown, r) => {
        const n = r.target_type_ids?.length ?? 0;
        return <Tag color={n > 0 ? 'blue' : 'default'}>{n}</Tag>;
      },
    },
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
                      rowKey="id"
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
                                    <Tag>{boundMixinIdsOf(ot.object_type_id).length} mixins</Tag>
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
        onCancel={() => { setEditOpen(false); form.resetFields(); }}
        okText="保存"
        cancelText="取消"
        width={640}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" preserve={false}>
          <Form.Item name="name" label="Mixin 名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="mixin_name" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="Mixin 用途" />
          </Form.Item>
          <Form.Item
            name="properties"
            label="属性名列表"
            extra="Mixin 只声明「复用哪些属性名」；属性的数据类型与约束在 ObjectType 上定义。"
          >
            <Select mode="tags" placeholder="输入属性名后回车" tokenSeparators={[',', ' ']} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

export default MixinConfig;
