/**
 * MaterializedViewConfig 组件 —— 物化视图配置界面（FR-035 / T390）
 *
 * 左侧：ObjectType 树（带 checkbox 选择）
 * 右侧：选定 ObjectType 的所有 Computed Property 列表 + 物化选项
 *   - Schedule 字段（Cron 表达式 + 预设下拉：每 5 分钟/每小时/每天/手动）
 *   - 物化目标存储（Select：SQLite/Neo4j/Redis）
 *   - "Trigger Now" 按钮
 * 底部：保存配置按钮
 * 状态指示器：显示最近一次物化时间 + 耗时 + 错误数
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Tree, Checkbox, Typography, Tag, Space, Button, Form, Select, Input, Empty, Spin, message, Statistic, List, Tooltip,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import {
  ReloadOutlined, PlayCircleOutlined, SaveOutlined, CheckOutlined, CloseOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import { apiClient } from '../../shared/services/apiClient';
import { useI18n } from '../../shared/hooks/useI18n';

const { Text, Title } = Typography;

export interface MaterializedViewConfigProps {
  workspaceId?: string;
}

interface ComputedSummary {
  id: string;
  name: string;
  expression: string;
}

interface ObjectTypeNode {
  object_type_id: string;
  name: string;
  children?: ObjectTypeNode[];
}

interface MaterializedView {
  id: string;
  object_type_id: string;
  object_type_name: string;
  computed_property_ids: string[];
  schedule_cron: string;
  storage: 'sqlite' | 'neo4j' | 'redis';
  enabled: boolean;
  last_run_at?: string;
  last_run_duration_ms?: number;
  error_count: number;
}

const STORAGE_OPTIONS = [
  { value: 'sqlite', label: 'SQLite' },
  { value: 'neo4j', label: 'Neo4j' },
  { value: 'redis', label: 'Redis' },
];

const SCHEDULE_PRESETS: Array<{ value: string; label: string; cron: string }> = [
  { value: '5min', label: '每 5 分钟', cron: '*/5 * * * *' },
  { value: 'hourly', label: '每小时', cron: '0 * * * *' },
  { value: 'daily', label: '每天 (00:00)', cron: '0 0 * * *' },
  { value: 'manual', label: '手动', cron: '' },
];

export function MaterializedViewConfig({ workspaceId }: MaterializedViewConfigProps) {
  const { t } = useI18n();
  void t;
  void workspaceId;
  const [objectTypeTree, setObjectTypeTree] = useState<ObjectTypeNode[]>([]);
  const [selectedObjectTypeIds, setSelectedObjectTypeIds] = useState<string[]>([]);
  const [computedByOT, setComputedByOT] = useState<Record<string, ComputedSummary[]>>({});
  const [views, setViews] = useState<MaterializedView[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedView, setSelectedView] = useState<MaterializedView | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [otRes, viewRes] = await Promise.all([
        apiClient.get<{ object_types: ObjectTypeNode[] }>('/api/ontology/object-types?tree=true'),
        apiClient.get<{ views: MaterializedView[] }>('/api/ontology/computed/materialized-views'),
      ]);
      setObjectTypeTree(otRes.object_types || []);
      setViews(viewRes.views || []);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  const computedOptions = useMemo(() => {
    if (!selectedView) return [];
    return computedByOT[selectedView.object_type_id] || [];
  }, [selectedView, computedByOT]);

  const fetchComputedForOT = useCallback(async (otId: string) => {
    if (computedByOT[otId]) return;
    try {
      const data = await apiClient.get<{ computed: ComputedSummary[] }>(
        `/api/ontology/computed?object_type_id=${otId}`,
      );
      setComputedByOT((prev) => ({ ...prev, [otId]: data.computed || [] }));
    } catch {
      setComputedByOT((prev) => ({ ...prev, [otId]: [] }));
    }
  }, [computedByOT]);

  useEffect(() => {
    selectedObjectTypeIds.forEach((id) => { void fetchComputedForOT(id); });
  }, [selectedObjectTypeIds, fetchComputedForOT]);

  const treeData: DataNode[] = useMemo(
    () => objectTypeTree.map((ot) => ({
      title: ot.name,
      key: ot.object_type_id,
      children: ot.children?.map((c) => ({
        title: c.name,
        key: c.object_type_id,
      })),
    })),
    [objectTypeTree],
  );

  const onCheck = useCallback((checked: unknown) => {
    const c = checked as { checked?: string[]; halfChecked?: string[] } | string[];
    const ids = Array.isArray(c) ? c : (c.checked ?? []);
    setSelectedObjectTypeIds(ids);
    setSelectedView(null);
  }, []);

  const handleSelectView = useCallback((v: MaterializedView) => {
    setSelectedView(v);
    setSelectedObjectTypeIds([v.object_type_id]);
    form.setFieldsValue({
      schedule_preset: SCHEDULE_PRESETS.find((p) => p.cron === v.schedule_cron)?.value || 'custom',
      cron: v.schedule_cron,
      storage: v.storage,
      enabled: v.enabled,
      computed_property_ids: v.computed_property_ids,
    });
  }, [form]);

  const handlePresetChange = useCallback((preset: string) => {
    const found = SCHEDULE_PRESETS.find((p) => p.value === preset);
    if (found) {
      form.setFieldsValue({ cron: found.cron });
    }
  }, [form]);

  const handleSave = useCallback(async () => {
    if (!selectedView) {
      message.warning('请先选择或新建视图');
      return;
    }
    try {
      const values = await form.validateFields();
      setSaving(true);
      await apiClient.put(
        `/api/ontology/computed/materialized-views/${selectedView.id}`,
        {
          schedule_cron: values.cron,
          storage: values.storage,
          enabled: values.enabled,
          computed_property_ids: values.computed_property_ids,
        },
      );
      message.success('已保存');
      void fetchAll();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(`保存失败: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }, [form, selectedView, fetchAll]);

  const handleTrigger = useCallback(async () => {
    if (!selectedView) {
      message.warning('请先选择视图');
      return;
    }
    setTriggering(true);
    try {
      await apiClient.post(
        `/api/ontology/computed/materialized-views/${selectedView.id}/trigger`,
        {},
      );
      message.success('物化已触发');
      void fetchAll();
    } catch (e) {
      message.error(`触发失败: ${(e as Error).message}`);
    } finally {
      setTriggering(false);
    }
  }, [selectedView, fetchAll]);

  const selectedOTName = useMemo(() => {
    if (!selectedView) return '';
    const findName = (nodes: ObjectTypeNode[]): string | null => {
      for (const n of nodes) {
        if (n.object_type_id === selectedView.object_type_id) return n.name;
        if (n.children) {
          const r = findName(n.children);
          if (r) return r;
        }
      }
      return null;
    };
    return findName(objectTypeTree) || selectedView.object_type_name;
  }, [selectedView, objectTypeTree]);

  return (
    <div data-testid="materialized-view-config" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>物化视图配置</Title>
        <Button icon={<ReloadOutlined />} onClick={() => void fetchAll()}>刷新</Button>
      </Space>

      <Spin spinning={loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Card size="small" title="ObjectType">
              {treeData.length === 0 ? (
                <Empty description="无 ObjectType" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <Tree
                  checkable
                  treeData={treeData}
                  checkedKeys={selectedObjectTypeIds}
                  onCheck={onCheck}
                  defaultExpandAll
                />
              )}
              {selectedObjectTypeIds.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    已选 {selectedObjectTypeIds.length} 个 ObjectType
                  </Text>
                </div>
              )}
            </Card>

            <Card size="small" title="已配置视图" style={{ marginTop: 12 }}>
              {views.length === 0 ? (
                <Empty description="暂无视图" image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <List
                  size="small"
                  dataSource={views}
                  renderItem={(v) => (
                    <List.Item
                      onClick={() => handleSelectView(v)}
                      style={{
                        cursor: 'pointer',
                        background: selectedView?.id === v.id ? '#e6f4ff' : undefined,
                      }}
                    >
                      <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space>
                          <Text strong>{v.object_type_name}</Text>
                          {v.enabled
                            ? <Tag color="green" icon={<CheckOutlined />}>enabled</Tag>
                            : <Tag color="default" icon={<CloseOutlined />}>disabled</Tag>}
                        </Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {v.schedule_cron || 'manual'} · {v.storage}
                        </Text>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Col>

          <Col xs={24} md={16}>
            {!selectedView ? (
              <Card>
                <Empty description="请从左侧选择一个 ObjectType 或已配置视图" />
              </Card>
            ) : (
              <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                <Card size="small" title={`视图: ${selectedOTName}`}>
                  <Row gutter={12}>
                    <Col span={8}>
                      <Statistic
                        title="最近物化时间"
                        value={selectedView.last_run_at ? new Date(selectedView.last_run_at).toLocaleString() : '从未运行'}
                        valueStyle={{ fontSize: 14 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="耗时 (ms)"
                        value={selectedView.last_run_duration_ms ?? 0}
                        valueStyle={{ fontSize: 14 }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="错误数"
                        value={selectedView.error_count}
                        valueStyle={{ fontSize: 14, color: selectedView.error_count > 0 ? '#ff4d4f' : undefined }}
                      />
                    </Col>
                  </Row>
                </Card>

                <Card size="small" title="配置">
                  <Form
                    form={form}
                    layout="vertical"
                    initialValues={{ storage: 'sqlite', enabled: true }}
                  >
                    <Row gutter={12}>
                      <Col xs={24} md={12}>
                        <Form.Item name="schedule_preset" label="Schedule 预设">
                          <Select
                            options={[
                              ...SCHEDULE_PRESETS,
                              { value: 'custom', label: '自定义 Cron' },
                            ]}
                            onChange={handlePresetChange}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item
                          name="cron"
                          label="Cron 表达式"
                          tooltip="标准 5 段 Cron，例：0 0 * * * 表示每天 0 点"
                        >
                          <Input
                            placeholder="0 0 * * *"
                            prefix={<ClockCircleOutlined />}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={12}>
                      <Col xs={24} md={12}>
                        <Form.Item name="storage" label="物化目标存储">
                          <Select options={STORAGE_OPTIONS} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item name="enabled" label="启用" valuePropName="checked">
                          <Checkbox>启用物化任务</Checkbox>
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item label="计算的属性">
                      {computedOptions.length === 0 ? (
                        <Empty description="该 ObjectType 下无计算属性" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                      ) : (
                        <Form.Item name="computed_property_ids" noStyle>
                          <Checkbox.Group style={{ width: '100%' }}>
                            <Row gutter={8}>
                              {computedOptions.map((c) => (
                                <Col span={12} key={c.id}>
                                  <Checkbox value={c.id}>
                                    <Tooltip title={c.expression}>
                                      <Text strong>{c.name}</Text>
                                    </Tooltip>
                                  </Checkbox>
                                </Col>
                              ))}
                            </Row>
                          </Checkbox.Group>
                        </Form.Item>
                      )}
                    </Form.Item>
                  </Form>

                  <Space>
                    <Button
                      type="primary"
                      icon={<SaveOutlined />}
                      loading={saving}
                      onClick={handleSave}
                    >
                      保存配置
                    </Button>
                    <Button
                      icon={<PlayCircleOutlined />}
                      loading={triggering}
                      onClick={handleTrigger}
                    >
                      Trigger Now
                    </Button>
                  </Space>
                </Card>
              </Space>
            )}
          </Col>
        </Row>
      </Spin>
    </div>
  );
}

export default MaterializedViewConfig;
