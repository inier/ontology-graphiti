/**
 * MaterializationMonitor 组件 —— 物化任务实时监控（FR-035 / T401）
 *
 * 顶部 KPI：Active Jobs / Pending / Failed Today / Total Throughput
 * 主区 Tabs：
 *   - Active:  实时进度条 + 耗时 + 错误数
 *   - History: 历史任务表格
 *   - Stats:   吞吐折线图（ECharts）
 *   - Errors:  失败任务错误详情
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Card, Row, Col, Tabs, Tag, Progress, Button, Space, Statistic, Empty, Spin, Drawer, Typography, message, Alert,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined,
} from '@ant-design/icons';
import type { ReactNode } from 'react';
import * as echarts from 'echarts';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import { AdvancedTable } from '@/modules/shared';

const { Text, Title } = Typography;

export interface MaterializationMonitorProps {
  workspaceId?: string;
  refreshIntervalMs?: number;
}

type JobStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'PAUSED';

interface MaterializationJob {
  job_id: string;
  object_type_name: string;
  computed_property_name: string;
  status: JobStatus;
  progress: number;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  error?: string;
  row_count?: number;
}

interface StatsPoint { ts: string; throughput: number; }

const STATUS_MAP: Record<JobStatus, { color: string; icon: ReactNode }> = {
  PENDING: { color: 'default', icon: <ClockCircleOutlined /> },
  RUNNING: { color: 'processing', icon: <PlayCircleOutlined /> },
  SUCCESS: { color: 'success', icon: <CheckCircleOutlined /> },
  FAILED: { color: 'error', icon: <CloseCircleOutlined /> },
  PAUSED: { color: 'warning', icon: <PauseCircleOutlined /> },
};

export function MaterializationMonitor({ workspaceId, refreshIntervalMs = 10000 }: MaterializationMonitorProps) {
  const { t } = useI18n();
  void t;
  const [jobs, setJobs] = useState<MaterializationJob[]>([]);
  const [stats, setStats] = useState<StatsPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<MaterializationJob | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const qs = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
      const [jobData, statsData] = await Promise.all([
        apiClient.get<{ jobs: MaterializationJob[] }>(`/api/ontology/computed/jobs${qs}`),
        apiClient.get<{ points: StatsPoint[] }>(`/api/ontology/computed/stats${qs}`),
      ]);
      setJobs(jobData.jobs || []);
      setStats(statsData.points || []);
    } catch (e) {
      message.error(`加载失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchAll();
    const timer = setInterval(fetchAll, refreshIntervalMs);
    return () => clearInterval(timer);
  }, [fetchAll, refreshIntervalMs]);

  const totals = useMemo(() => {
    const active = jobs.filter((j) => j.status === 'RUNNING').length;
    const pending = jobs.filter((j) => j.status === 'PENDING').length;
    const failed = jobs.filter((j) => j.status === 'FAILED').length;
    const successToday = jobs.filter((j) => j.status === 'SUCCESS').length;
    return { active, pending, failed, successToday };
  }, [jobs]);

  const statsChart = useMemo(() => {
    const times = stats.map((s) => s.ts);
    const throughput = stats.map((s) => s.throughput);
    return {
      tooltip: { trigger: 'axis' as const },
      xAxis: { type: 'category' as const, data: times },
      yAxis: { type: 'value' as const, name: '行/秒' },
      series: [{ name: 'Throughput', type: 'line' as const, smooth: true, data: throughput, areaStyle: {} }],
    };
  }, [stats]);

  const onAction = useCallback(async (action: 'pause' | 'resume' | 'rerun', jobId: string) => {
    try {
      await apiClient.post(`/api/ontology/computed/jobs/${jobId}/${action}`);
      message.success(`操作已发送: ${action}`);
      fetchAll();
    } catch (e) {
      message.error(`操作失败: ${(e as Error).message}`);
    }
  }, [fetchAll]);

  const activeColumns: ColumnsType<MaterializationJob> = [
    { title: 'Job ID', dataIndex: 'job_id', width: 130 },
    { title: 'ObjectType', dataIndex: 'object_type_name', width: 140 },
    { title: 'Property', dataIndex: 'computed_property_name' },
    {
      title: 'Status', dataIndex: 'status', width: 120,
      render: (s: JobStatus) => <Tag icon={STATUS_MAP[s].icon} color={STATUS_MAP[s].color}>{s}</Tag>,
    },
    {
      title: 'Progress', dataIndex: 'progress', width: 180,
      render: (p: number) => <Progress percent={p} size="small" status={p >= 100 ? 'success' : 'active'} />,
    },
    { title: '行数', dataIndex: 'row_count', width: 90 },
    { title: '耗时(ms)', dataIndex: 'duration_ms', width: 100 },
    {
      title: '操作', width: 200, fixed: 'right',
      render: (_, r) => (
        <Space>
          {r.status === 'RUNNING' && <Button size="small" icon={<PauseCircleOutlined />} onClick={() => onAction('pause', r.job_id)}>暂停</Button>}
          {r.status === 'PAUSED' && <Button size="small" icon={<PlayCircleOutlined />} onClick={() => onAction('resume', r.job_id)}>恢复</Button>}
          {r.status === 'FAILED' && <Button size="small" danger icon={<ReloadOutlined />} onClick={() => onAction('rerun', r.job_id)}>重跑</Button>}
          <Button size="small" onClick={() => { setSelected(r); setDrawerOpen(true); }}>详情</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title={
        <Space>
          <Title level={5} style={{ margin: 0 }}>物化任务监控</Title>
          <Tag color="blue">{workspaceId || 'default'}</Tag>
        </Space>
      }
      extra={
        <Button icon={<ReloadOutlined />} onClick={fetchAll} loading={loading}>刷新</Button>
      }
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="Active" value={totals.active} styles={{ content: { color: '#1677ff' } }} /></Card></Col>
        <Col span={6}><Card><Statistic title="Pending" value={totals.pending} styles={{ content: { color: '#faad14' } }} /></Card></Col>
        <Col span={6}><Card><Statistic title="Failed Today" value={totals.failed} styles={{ content: { color: '#cf1322' } }} /></Card></Col>
        <Col span={6}><Card><Statistic title="Success Today" value={totals.successToday} styles={{ content: { color: '#3f8600' } }} /></Card></Col>
      </Row>

      <Tabs
        defaultActiveKey="active"
        items={[
          { key: 'active', label: `Active / Pending (${totals.active + totals.pending})`, children: <AdvancedTable rowKey="job_id" dataSource={jobs.filter((j) => j.status === 'RUNNING' || j.status === 'PENDING')} columns={activeColumns} pagination={false} size="small" /> },
          { key: 'history', label: `History (${jobs.length})`, children: <AdvancedTable rowKey="job_id" dataSource={jobs} columns={activeColumns} pagination={{ pageSize: 20 }} size="small" /> },
          {
            key: 'stats', label: 'Stats',
            children: stats.length === 0 ? <Empty description="暂无统计数据" /> : (
              <div ref={(el) => { if (el) echarts.init(el).setOption(statsChart); }} style={{ width: '100%', height: 320 }} />
            ),
          },
          {
            key: 'errors', label: `Errors (${totals.failed})`,
            children: (
              <Spin spinning={loading}>
                {jobs.filter((j) => j.status === 'FAILED').length === 0 ? <Empty description="无失败任务" /> : (
                  <AdvancedTable
                    rowKey="job_id"
                    pagination={false}
                    size="small"
                    dataSource={jobs.filter((j) => j.status === 'FAILED')}
                    columns={[
                      { title: 'Job ID', dataIndex: 'job_id' },
                      { title: 'ObjectType', dataIndex: 'object_type_name' },
                      { title: 'Property', dataIndex: 'computed_property_name' },
                      { title: '错误', dataIndex: 'error', render: (e?: string) => <Text type="danger">{e || '-'}</Text> },
                      { title: '失败时间', dataIndex: 'finished_at' },
                    ]}
                  />
                )}
              </Spin>
            ),
          },
        ]}
      />

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title={`任务详情: ${selected?.job_id || ''}`}>
        {selected && (
          <Space orientation="vertical" style={{ width: '100%' }}>
            <Alert type={selected.status === 'FAILED' ? 'error' : 'info'} showIcon message={`Status: ${selected.status}`} />
            <Text>ObjectType: <Text code>{selected.object_type_name}</Text></Text>
            <Text>Property: <Text code>{selected.computed_property_name}</Text></Text>
            <Text>Progress: <Progress percent={selected.progress} /></Text>
            <Text>Rows: {selected.row_count ?? '-'}</Text>
            <Text>Duration: {selected.duration_ms ?? '-'} ms</Text>
            {selected.error && <Alert type="error" message="Error" description={selected.error} />}
          </Space>
        )}
      </Drawer>
    </Card>
  );
}

export default MaterializationMonitor;
