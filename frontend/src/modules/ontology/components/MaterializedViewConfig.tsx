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
  Card, Row, Col, Tree, Checkbox, Typography, Tag, Space, Button, Select, Input, Empty, Spin, message, Statistic, List, Tooltip,
} from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import type { DataNode } from 'antd/es/tree';
import {
  ReloadOutlined, PlayCircleOutlined, SaveOutlined, CheckOutlined, CloseOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

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

export function MaterializedViewConfig({ workspaceId }: MaterializedViewConfigProps) {
  const { t } = useI18n('ontology');
  const [objectTypeTree, setObjectTypeTree] = useState<ObjectTypeNode[]>([]);
  const [selectedObjectTypeIds, setSelectedObjectTypeIds] = useState<string[]>([]);
  const [computedByOT, setComputedByOT] = useState<Record<string, ComputedSummary[]>>({});
  const [views, setViews] = useState<MaterializedView[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedView, setSelectedView] = useState<MaterializedView | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const STORAGE_OPTIONS = useMemo(() => [
    { value: 'sqlite', label: t('materializedView.storageSqlite') },
    { value: 'neo4j', label: t('materializedView.storageNeo4j') },
    { value: 'redis', label: t('materializedView.storageRedis') },
  ], [t]);

  const SCHEDULE_PRESETS: Array<{ value: string; label: string; cron: string }> = useMemo(() => [
    { value: '5min', label: t('materializedView.schedule5min'), cron: '*/5 * * * *' },
    { value: 'hourly', label: t('materializedView.scheduleHourly'), cron: '0 * * * *' },
    { value: 'daily', label: t('materializedView.scheduleDaily'), cron: '0 0 * * *' },
    { value: 'manual', label: t('materializedView.scheduleManual'), cron: '' },
  ], [t]);

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
      message.error(t('materializedView.loadFailed', { msg: (e as Error).message }));
    } finally {
      setLoading(false);
    }
  }, [t]);

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
  }, [form, SCHEDULE_PRESETS]);

  const handlePresetChange = useCallback((preset: string) => {
    const found = SCHEDULE_PRESETS.find((p) => p.value === preset);
    if (found) {
      form.setFieldsValue({ cron: found.cron });
    }
  }, [form, SCHEDULE_PRESETS]);

  const handleSave = useCallback(async () => {
    if (!selectedView) {
      message.warning(t('materializedView.selectOrCreateView'));
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
      message.success(t('materializedView.saved'));
      void fetchAll();
    } catch (e) {
      if ((e as { errorFields?: unknown[] }).errorFields) return;
      message.error(t('materializedView.saveFailed', { msg: (e as Error).message }));
    } finally {
      setSaving(false);
    }
  }, [form, selectedView, fetchAll, t]);

  const handleTrigger = useCallback(async () => {
    if (!selectedView) {
      message.warning(t('materializedView.selectView'));
      return;
    }
    setTriggering(true);
    try {
      await apiClient.post(
        `/api/ontology/computed/materialized-views/${selectedView.id}/trigger`,
        {},
      );
      message.success(t('materializedView.triggered'));
      void fetchAll();
    } catch (e) {
      message.error(t('materializedView.triggerFailed', { msg: (e as Error).message }));
    } finally {
      setTriggering(false);
    }
  }, [selectedView, fetchAll, t]);

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
        <Title level={3} style={{ margin: 0 }}>{t('materializedView.title')}</Title>
        <Button icon={<ReloadOutlined />} onClick={() => void fetchAll()}>{t('materializedView.refresh')}</Button>
      </Space>

      <Spin spinning={loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Card size="small" title={t('materializedView.objectTypeCardTitle')}>
              {treeData.length === 0 ? (
                <Empty description={t('materializedView.noObjectType')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
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
                    {t('materializedView.selectedObjectTypeCount', { count: selectedObjectTypeIds.length })}
                  </Text>
                </div>
              )}
            </Card>

            <Card size="small" title={t('materializedView.configuredViewsTitle')} style={{ marginTop: 12 }}>
              {views.length === 0 ? (
                <Empty description={t('materializedView.noViews')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
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
                      <Space orientation="vertical" size={2} style={{ width: '100%' }}>
                        <Space>
                          <Text strong>{v.object_type_name}</Text>
                          {v.enabled
                            ? <Tag color="green" icon={<CheckOutlined />}>{t('materializedView.enabled')}</Tag>
                            : <Tag color="default" icon={<CloseOutlined />}>{t('materializedView.disabled')}</Tag>}
                        </Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {v.schedule_cron || t('materializedView.manual')} · {v.storage}
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
                <Empty description={t('materializedView.selectFromLeft')} />
              </Card>
            ) : (
              <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                <Card size="small" title={t('materializedView.viewTitle', { name: selectedOTName })}>
                  <Row gutter={12}>
                    <Col span={8}>
                      <Statistic
                        title={t('materializedView.statLastRun')}
                        value={selectedView.last_run_at ? new Date(selectedView.last_run_at).toLocaleString() : t('materializedView.neverRun')}
                        styles={{ content: { fontSize: 14 } }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title={t('materializedView.statDuration')}
                        value={selectedView.last_run_duration_ms ?? 0}
                        styles={{ content: { fontSize: 14 } }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title={t('materializedView.statErrorCount')}
                        value={selectedView.error_count}
                        styles={{ content: { fontSize: 14, color: selectedView.error_count > 0 ? '#ff4d4f' : undefined } }}
                      />
                    </Col>
                  </Row>
                </Card>

                <Card size="small" title={t('materializedView.configTitle')}>
                  <Form
                    form={form}
                    layout="vertical"
                    initialValues={{ storage: 'sqlite', enabled: true }}
                  >
                    <Row gutter={12}>
                      <Col xs={24} md={12}>
                        <Form.Item name="schedule_preset" label={t('materializedView.schedulePreset')}>
                          <Select
                            options={[
                              ...SCHEDULE_PRESETS,
                              { value: 'custom', label: t('materializedView.scheduleCustom') },
                            ]}
                            onChange={handlePresetChange}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item
                          name="cron"
                          label={t('materializedView.cronExpression')}
                          tooltip={t('materializedView.cronTooltip')}
                        >
                          <Input
                            placeholder={t('materializedView.cronPlaceholder')}
                            prefix={<ClockCircleOutlined />}
                          />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={12}>
                      <Col xs={24} md={12}>
                        <Form.Item name="storage" label={t('materializedView.storageLabel')}>
                          <Select options={STORAGE_OPTIONS} />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item name="enabled" label={t('materializedView.enableLabel')} valuePropName="checked">
                          <Checkbox>{t('materializedView.enableMaterialize')}</Checkbox>
                        </Form.Item>
                      </Col>
                    </Row>
                    <Form.Item label={t('materializedView.computedProperties')}>
                      {computedOptions.length === 0 ? (
                        <Empty description={t('materializedView.noComputedProperties')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
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
                      {t('materializedView.saveConfig')}
                    </Button>
                    <Button
                      icon={<PlayCircleOutlined />}
                      loading={triggering}
                      onClick={handleTrigger}
                    >
                      {t('materializedView.triggerNow')}
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
