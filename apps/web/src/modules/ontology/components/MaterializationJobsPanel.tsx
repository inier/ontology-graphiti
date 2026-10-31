/**
 * MaterializationJobsPanel —— 物化任务（MaterializationJob）观测与触发
 *
 * ── 为什么不是「物化视图配置」─────────────────────────────────────
 * 原 `MaterializedViewConfig` 假设了一套后端并不存在的模型：
 * `MaterializedView { schedule_cron, storage: sqlite|neo4j|redis, enabled,
 * computed_property_ids[], last_run_duration_ms, error_count }`，
 * 以及 `/computed/materialized-views` 的 CRUD + `/trigger` 端点——全部 404。
 *
 * 后端真实存在的是（computed/models/job.py、computed/api/routes.py）：
 *   - ComputedProperty 自带 `materialization: none|full|incremental` 物化策略；
 *   - 每次重算落一条 `MaterializationJob { id, property_id, status: pending|running|done|failed,
 *     started_at, finished_at, processed_count, error_message, triggered_by: manual|incremental|scheduled,
 *     mode: full|incremental }`；
 *   - 触发：`POST /computed/properties/{id}/recompute  {mode}`；
 *   - 历史：`GET  /computed/properties/{id}/jobs?limit=N`；
 *   - 单条：`GET  /computed/jobs/{job_id}`。
 * 没有 cron、没有多存储后端、没有进度百分比、没有吞吐序列——所以这里只做
 * 「按属性看物化策略 + 触发重算 + 看任务历史」，不编造调度器和图表。
 *
 * 原 `MaterializationMonitor.tsx`（假状态枚举 + ECharts 吞吐折线 + progress 进度条）
 * 已删除：无任何引用，且模型与后端不符，属于伪实现。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Tag, Button, Space, Statistic, Empty, Spin, Typography, message, List, Alert, Select,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ReloadOutlined, PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;

const COMPUTED_BASE = '/api/ontology/computed';

type MaterializationType = 'none' | 'full' | 'incremental';
type JobStatus = 'pending' | 'running' | 'done' | 'failed';
type JobTrigger = 'manual' | 'incremental' | 'scheduled';

interface ComputedPropertyBrief {
  id: string;
  name: string;
  target_type_id: string;
  expression: string;
  materialization: MaterializationType;
  enabled: boolean;
}

interface MaterializationJob {
  id: string;
  property_id: string;
  status: JobStatus;
  started_at: string;
  finished_at?: string | null;
  processed_count: number;
  error_message: string;
  triggered_by: JobTrigger;
  mode: string;
}

const STATUS_META: Record<JobStatus, { color: string; icon: React.ReactNode }> = {
  pending: { color: 'default', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', icon: <PlayCircleOutlined /> },
  done: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
};

export interface MaterializationJobsPanelProps {
  /** 进入面板时默认选中的计算属性 */
  propertyId?: string;
}

export function MaterializationJobsPanel({ propertyId }: MaterializationJobsPanelProps) {
  const { t } = useI18n('ontology');
  const [properties, setProperties] = useState<ComputedPropertyBrief[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>(propertyId);
  const [jobs, setJobs] = useState<MaterializationJob[]>([]);
  const [loading, setLoading] = useState(false);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [triggering, setTriggering] = useState<string | null>(null);

  const fetchProperties = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ properties?: ComputedPropertyBrief[] }>(`${COMPUTED_BASE}/properties`);
      const list = data?.properties ?? [];
      setProperties(list);
      // 只展示真正会落库的（none 策略不产生任务，留在列表里只会误导）
      setSelectedId((prev) => prev ?? list.find((p) => p.materialization !== 'none')?.id ?? list[0]?.id);
    } catch (e) {
      message.error(`加载计算属性失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchJobs = useCallback(async (pid: string) => {
    setJobsLoading(true);
    try {
      const data = await apiClient.get<{ jobs?: MaterializationJob[] }>(
        `${COMPUTED_BASE}/properties/${encodeURIComponent(pid)}/jobs?limit=50`,
      );
      setJobs(data?.jobs ?? []);
    } catch (e) {
      message.error(`加载任务历史失败: ${(e as Error).message}`);
      setJobs([]);
    } finally {
      setJobsLoading(false);
    }
  }, []);

  useEffect(() => {
    // 数据拉取；fetchProperties 内部先 await 再 setState，规则无法穿透 async 边界。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchProperties();
  }, [fetchProperties]);

  useEffect(() => {
    // 没有选中属性时不请求、也不清空 jobs：右栏此时渲染的是「请选择」占位，
    // 用 setState 清空只会多一次渲染。
    if (!selectedId) return;
    // 选中变化即拉任务历史；fetchJobs 内部先 await 再 setState，规则无法穿透 async 边界。
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchJobs(selectedId);
  }, [selectedId, fetchJobs]);

  const selected = useMemo(
    () => properties.find((p) => p.id === selectedId),
    [properties, selectedId],
  );

  const latest = jobs[0];

  const handleRecompute = useCallback(async (mode: 'full' | 'incremental') => {
    if (!selectedId) return;
    setTriggering(mode);
    try {
      const data = await apiClient.post<{ job_ids?: string[]; affected?: string[] }>(
        `${COMPUTED_BASE}/properties/${encodeURIComponent(selectedId)}/recompute`,
        { mode },
      );
      const n = data?.job_ids?.length ?? 0;
      message.success(`已提交 ${mode} 重算，任务数 ${n}`);
      await fetchJobs(selectedId);
    } catch (e) {
      message.error(`触发失败: ${(e as Error).message}`);
    } finally {
      setTriggering(null);
    }
  }, [selectedId, fetchJobs]);

  const columns: ColumnsType<MaterializationJob> = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (v: JobStatus) => {
        const meta = STATUS_META[v] ?? STATUS_META.pending;
        return <Tag color={meta.color} icon={meta.icon}>{v}</Tag>;
      },
    },
    { title: '模式', dataIndex: 'mode', key: 'mode', width: 110 },
    { title: '触发来源', dataIndex: 'triggered_by', key: 'triggered_by', width: 110 },
    {
      title: '处理实例数',
      dataIndex: 'processed_count',
      key: 'processed_count',
      width: 110,
      align: 'right',
      render: (v: number) => v ?? 0,
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (v?: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: '结束时间',
      dataIndex: 'finished_at',
      key: 'finished_at',
      width: 180,
      render: (v?: string | null) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: '错误',
      dataIndex: 'error_message',
      key: 'error_message',
      render: (v?: string) => (v ? <Text type="danger">{v}</Text> : <Text type="secondary">-</Text>),
    },
  ];

  return (
    <div data-testid="materialization-jobs-panel" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }} wrap>
        <Title level={3} style={{ margin: 0 }}>物化任务</Title>
        <Button
          icon={<ReloadOutlined />}
          onClick={() => { void fetchProperties(); if (selectedId) void fetchJobs(selectedId); }}
        >
          刷新
        </Button>
      </Space>

      <Spin spinning={loading}>
        <Row gutter={16}>
          <Col xs={24} md={8}>
            <Card size="small" title="计算属性">
              {properties.length === 0 ? (
                <Empty description={t('暂无计算属性')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
              ) : (
                <List
                  size="small"
                  dataSource={properties}
                  renderItem={(p) => (
                    <List.Item
                      onClick={() => setSelectedId(p.id)}
                      style={{
                        cursor: 'pointer',
                        background: selectedId === p.id ? '#e6f4ff' : undefined,
                      }}
                    >
                      <Space orientation="vertical" size={2} style={{ width: '100%' }}>
                        <Space>
                          <Text strong>{p.name}</Text>
                          <Tag color={p.materialization === 'none' ? 'default' : 'green'}>
                            {p.materialization ?? 'none'}
                          </Tag>
                          {!p.enabled && <Tag>disabled</Tag>}
                        </Space>
                        <Text type="secondary" style={{ fontSize: 12 }}>{p.target_type_id}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              )}
            </Card>
          </Col>

          <Col xs={24} md={16}>
            {!selected ? (
              <Card>
                <Empty description="请选择一个计算属性" />
              </Card>
            ) : (
              <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
                {selected.materialization === 'none' ? (
                  <Alert
                    type="info"
                    showIcon
                    message="该属性物化策略为 none"
                    description="每次访问都实时计算，不落库、不产生物化任务。如需任务历史，请先在「计算属性」里把策略改为 full 或 incremental。"
                  />
                ) : null}

                <Card size="small" title={`${selected.name} · ${selected.materialization}`}>
                  <Row gutter={12}>
                    <Col span={8}>
                      <Statistic
                        title="最近一次状态"
                        value={latest?.status ?? '—'}
                        styles={{ content: { fontSize: 14 } }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="最近处理实例数"
                        value={latest?.processed_count ?? 0}
                        styles={{ content: { fontSize: 14 } }}
                      />
                    </Col>
                    <Col span={8}>
                      <Statistic
                        title="累计任务数"
                        value={jobs.length}
                        styles={{ content: { fontSize: 14 } }}
                      />
                    </Col>
                  </Row>
                  <Space style={{ marginTop: 12 }} wrap>
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      loading={triggering === 'incremental'}
                      onClick={() => { void handleRecompute('incremental'); }}
                    >
                      增量重算
                    </Button>
                    <Button
                      icon={<PlayCircleOutlined />}
                      loading={triggering === 'full'}
                      onClick={() => { void handleRecompute('full'); }}
                    >
                      全量重算
                    </Button>
                    <Select
                      style={{ minWidth: 220 }}
                      value={selectedId}
                      onChange={(v) => setSelectedId(v)}
                      options={properties.map((p) => ({ value: p.id, label: p.name }))}
                      showSearch
                      optionFilterProp="label"
                    />
                  </Space>
                </Card>

                <Card size="small" title="任务历史">
                  <Spin spinning={jobsLoading}>
                    {jobs.length === 0 ? (
                      <Empty description="暂无物化任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ) : (
                      <AdvancedTable<MaterializationJob>
                        rowKey="id"
                        size="small"
                        dataSource={jobs}
                        columns={columns}
                        pagination={{ pageSize: 10 }}
                      />
                    )}
                  </Spin>
                </Card>
              </Space>
            )}
          </Col>
        </Row>
      </Spin>
    </div>
  );
}

export default MaterializationJobsPanel;
