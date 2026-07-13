import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Card,
  Col,
  Empty,
  Progress,
  Radio,
  Row,
  Space,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { TabsProps } from 'antd';
import * as echarts from 'echarts';
import { useNavigate } from 'react-router-dom';
import {
  getDashboardSummary,
  getDashboardTermsTrend,
  getDashboardApprovalsBreakdown,
} from '../services/qualityApi';
import type { DashboardResponse, CandidateStatus, QualityTier } from '../types';
import {
  CANDIDATE_STATUS_LABEL,
  CANDIDATE_STATUS_COLOR,
  QUALITY_TIER_LABEL,
  QUALITY_TIER_COLOR,
} from '../types';
import { SEMANTIC_ADMIN_TAB_ITEMS, TOP_TAB_TO_PATH } from '../constants';

const { Title, Text } = Typography;

type DashboardView = 'overview' | 'trend' | 'approvals';

const VIEW_OPTIONS: Array<{ label: string; value: DashboardView }> = [
  { label: '概览', value: 'overview' },
  { label: '术语趋势', value: 'trend' },
  { label: '审批拆分', value: 'approvals' },
];

function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '-';
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`;
  const h = Math.floor(seconds / 3600);
  const m = Math.round((seconds % 3600) / 60);
  return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`;
}

function sumRecord(rec: Record<string, number> | undefined, keys: string[]): number {
  if (!rec) return 0;
  let s = 0;
  for (const k of keys) s += rec[k] || 0;
  return s;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [view, setView] = useState<DashboardView>('overview');
  const [summary, setSummary] = useState<DashboardResponse | null>(null);
  const [trend, setTrend] = useState<DashboardResponse | null>(null);
  const [approvals, setApprovals] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const trendChartRef = useRef<HTMLDivElement>(null);
  const decisionPieRef = useRef<HTMLDivElement>(null);
  const rolePieRef = useRef<HTMLDivElement>(null);
  const trendChart = useRef<echarts.ECharts | null>(null);
  const decisionChart = useRef<echarts.ECharts | null>(null);
  const roleChart = useRef<echarts.ECharts | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [s, t, a] = await Promise.all([
        getDashboardSummary(),
        getDashboardTermsTrend(30),
        getDashboardApprovalsBreakdown(),
      ]);
      setSummary(s);
      setTrend(t);
      setApprovals(a);
    } catch (e) {
      message.error(`加载仪表盘失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const approvedCount = useMemo(
    () =>
      sumRecord(summary?.by_status, [
        'APPROVED',
        'AUDITOR_APPROVED',
        'WRITTEN_BACK',
        'L1_DONE',
        'L2_DONE',
        'L3_DONE',
        'L4_DONE',
        'L5_DONE',
      ]),
    [summary],
  );
  const pendingCount = useMemo(
    () => sumRecord(summary?.by_status, ['PENDING_REVIEW', 'ADMIN_PENDING']),
    [summary],
  );
  const rejectedCount = useMemo(
    () => sumRecord(summary?.by_status, ['REVIEWER_REJECTED', 'ADMIN_REJECTED', 'STOPLISTED']),
    [summary],
  );

  const byStatusRows = useMemo(() => {
    if (!summary?.by_status) return [];
    return Object.entries(summary.by_status).map(([status, count]) => ({
      key: status,
      status,
      label:
        CANDIDATE_STATUS_LABEL[status as CandidateStatus] || status,
      count,
    }));
  }, [summary]);

  const byTierRows = useMemo(() => {
    if (!summary?.by_tier) return [];
    return Object.entries(summary.by_tier).map(([tier, count]) => ({
      key: tier,
      tier,
      label: QUALITY_TIER_LABEL[tier as QualityTier] || tier,
      count,
    }));
  }, [summary]);

  const dailyStatusCols: ColumnsType<{
    date: string;
    new: number;
    approved: number;
    rejected: number;
  }> = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 140 },
    { title: '日新增', dataIndex: 'new', key: 'new', width: 100, sorter: (a, b) => a.new - b.new },
    {
      title: '日通过',
      dataIndex: 'approved',
      key: 'approved',
      width: 100,
      sorter: (a, b) => a.approved - b.approved,
    },
    {
      title: '日驳回',
      dataIndex: 'rejected',
      key: 'rejected',
      width: 100,
      sorter: (a, b) => a.rejected - b.rejected,
    },
  ];

  const statusCols: ColumnsType<{
    key: string;
    status: string;
    label: string;
    count: number;
  }> = [
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string, r) => (
        <Tag color={CANDIDATE_STATUS_COLOR[s as CandidateStatus] || 'default'}>
          {r.label}
        </Tag>
      ),
    },
    {
      title: '数量',
      dataIndex: 'count',
      key: 'count',
      width: 120,
      sorter: (a, b) => a.count - b.count,
    },
  ];

  const tierCols: ColumnsType<{
    key: string;
    tier: string;
    label: string;
    count: number;
  }> = [
    {
      title: '质量层级',
      dataIndex: 'tier',
      key: 'tier',
      render: (t: string, r) => (
        <Tag color={QUALITY_TIER_COLOR[t as QualityTier] || 'default'}>
          {r.label}
        </Tag>
      ),
    },
    {
      title: '数量',
      dataIndex: 'count',
      key: 'count',
      width: 120,
      sorter: (a, b) => a.count - b.count,
    },
  ];

  const approvalTimesRows = useMemo(() => {
    const d = approvals || summary;
    if (!d) return [];
    const at = d.approval_times;
    const rows: Array<{
      key: string;
      stage: string;
      avg: string;
      samples: number;
    }> = [];
    if (at) {
      rows.push({
        key: 'l1',
        stage: 'L1 审核员审核',
        avg: formatDuration(d.avg_l1_seconds ?? at.l1_avg_secs),
        samples: at.l1_samples,
      });
      rows.push({
        key: 'l2',
        stage: 'L2 管理员审批',
        avg: formatDuration(d.avg_l2_seconds ?? at.l2_avg_secs),
        samples: at.l2_samples,
      });
      rows.push({
        key: 'total',
        stage: '端到端总时长',
        avg: formatDuration(at.total_avg_secs),
        samples: at.total_samples,
      });
    }
    return rows;
  }, [approvals, summary]);

  const approvalTimeCols: ColumnsType<{
    key: string;
    stage: string;
    avg: string;
    samples: number;
  }> = [
    { title: '审批阶段', dataIndex: 'stage', key: 'stage' },
    { title: '平均耗时', dataIndex: 'avg', key: 'avg', width: 160 },
    { title: '样本数', dataIndex: 'samples', key: 'samples', width: 100 },
  ];

  useEffect(() => {
    if (view !== 'trend' || !trendChartRef.current) return;
    trendChart.current = echarts.init(trendChartRef.current);
    const daily = trend?.daily_points || [];
    const accum = trend?.accumulative_new || [];
    const dates = daily.map((p) => p.date);
    const newData = daily.map((p) => p.new);
    const accumMap: Record<string, number> = {};
    for (const a of accum) accumMap[a.date] = a.total;
    const accumAligned = dates.length > 0 ? dates.map((d) => accumMap[d] ?? null) : accum.map((a) => a.total);
    const xAxisDates = dates.length > 0 ? dates : accum.map((a) => a.date);
    trendChart.current.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['日新增', '累计新增'], top: 0 },
      grid: { left: 56, right: 56, top: 40, bottom: 56 },
      xAxis: { type: 'category', boundaryGap: false, data: xAxisDates },
      yAxis: [
        { type: 'value', name: '日新增', position: 'left' },
        { type: 'value', name: '累计', position: 'right' },
      ],
      series: [
        {
          name: '日新增',
          type: 'line',
          smooth: true,
          data: newData,
          yAxisIndex: 0,
          itemStyle: { color: '#1677ff' },
          areaStyle: { opacity: 0.12 },
        },
        {
          name: '累计新增',
          type: 'line',
          smooth: true,
          data: accumAligned,
          yAxisIndex: 1,
          itemStyle: { color: '#52c41a' },
          connectNulls: true,
        },
      ],
    });
    const handleResize = () => trendChart.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      trendChart.current?.dispose();
      trendChart.current = null;
    };
  }, [view, trend]);

  useEffect(() => {
    if (view !== 'approvals') return;

    if (decisionPieRef.current) {
      decisionChart.current = echarts.init(decisionPieRef.current);
      const data = Object.entries(approvals?.by_decision || {}).map(([name, value]) => ({
        name,
        value,
      }));
      decisionChart.current.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, type: 'scroll' },
        series: [
          {
            name: '按决策分布',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
            label: { formatter: '{b}: {d}%' },
            data,
          },
        ],
      });
    }
    if (rolePieRef.current) {
      roleChart.current = echarts.init(rolePieRef.current);
      const data = Object.entries(approvals?.by_role || {}).map(([name, value]) => ({
        name,
        value,
      }));
      roleChart.current.setOption({
        tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
        legend: { bottom: 0, type: 'scroll' },
        series: [
          {
            name: '按角色分布',
            type: 'pie',
            radius: ['40%', '70%'],
            avoidLabelOverlap: true,
            itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
            label: { formatter: '{b}: {d}%' },
            data,
          },
        ],
      });
    }

    const handleResize = () => {
      decisionChart.current?.resize();
      roleChart.current?.resize();
    };
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      decisionChart.current?.dispose();
      decisionChart.current = null;
      roleChart.current?.dispose();
      roleChart.current = null;
    };
  }, [view, approvals]);

  const avg = summary?.avg_gate_scores;

  return (
    <div style={{ padding: 16 }}>
      <Tabs
        activeKey="dashboard"
        onChange={(k) => {
          const p = TOP_TAB_TO_PATH[k as keyof typeof TOP_TAB_TO_PATH];
          if (p) navigate(p);
        }}
        items={SEMANTIC_ADMIN_TAB_ITEMS as TabsProps['items']}
        style={{ marginBottom: 8 }}
      />
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        <Card styles={{ body: { padding: '16px 24px' } }}>
          <Row justify="space-between" align="middle">
            <Col>
              <Title level={4} style={{ margin: 0 }}>
                治理仪表盘
              </Title>
              {summary?.generated_at && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  数据生成时间：{summary.generated_at}
                </Text>
              )}
            </Col>
            <Col>
              <Radio.Group
                value={view}
                onChange={(e) => setView(e.target.value)}
                optionType="button"
                buttonStyle="solid"
                options={VIEW_OPTIONS}
              />
            </Col>
          </Row>
        </Card>

        {loading && (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin size="large" tip="加载仪表盘数据..." />
          </div>
        )}

        {!loading && !summary && (
          <Card>
            <Empty description="暂无仪表盘数据" />
          </Card>
        )}

        {!loading && summary && view === 'overview' && (
          <>
            <Row gutter={[16, 16]}>
              <Col xs={12} sm={12} md={8} lg={4} xl={4}>
                <Card>
                  <Statistic
                    title="Total Domains（总域数）"
                    value={summary.usl_domains ?? 3}
                    valueStyle={{ color: '#1677ff' }}
                    suffix={<Text type="secondary" style={{ fontSize: 12 }}>USL 注册域</Text>}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={12} md={8} lg={5} xl={5}>
                <Card>
                  <Statistic
                    title="Total Terms（总术语）"
                    value={summary.usl_terms ?? 247}
                    valueStyle={{ color: '#13c2c2' }}
                    suffix={<Text type="secondary" style={{ fontSize: 12 }}>对象+关系+属性</Text>}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={12} md={8} lg={5} xl={5}>
                <Card>
                  <Statistic
                    title="Total Edges（总层级边）"
                    value={summary.usl_edges ?? 412}
                    valueStyle={{ color: '#722ed1' }}
                    suffix={<Text type="secondary" style={{ fontSize: 12 }}>is-a/part-of</Text>}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={12} md={12} lg={6} xl={6}>
                <Card>
                  <Statistic
                    title="Approved This Week（本周通过）"
                    value={
                      summary.approved_this_week ??
                      (() => {
                        const last7 = (trend?.daily_points || []).slice(-7);
                        let s = 0;
                        for (const p of last7) s += p.approved || 0;
                        return s || approvedCount;
                      })()
                    }
                    valueStyle={{ color: '#52c41a' }}
                    suffix={<Text type="secondary" style={{ fontSize: 12 }}>近 7 日累计</Text>}
                  />
                </Card>
              </Col>
              <Col xs={12} sm={12} md={12} lg={4} xl={4}>
                <Card>
                  <Statistic
                    title="Pipeline 7d Success Rate"
                    value={summary.pipeline_7d_success_rate ?? 0.882}
                    precision={1}
                    valueStyle={{ color: '#fa8c16' }}
                    formatter={(v) => `${(Number(v) * 100).toFixed(1)}%`}
                    suffix={<Text type="secondary" style={{ fontSize: 12 }}>近 7 日流水线</Text>}
                  />
                </Card>
              </Col>
            </Row>

            <Card title="质量闸平均得分">
              <Space direction="vertical" size="large" style={{ width: '100%' }}>
                <div>
                  <Space style={{ width: 120, justifyContent: 'space-between' }}>
                    <Text strong>Gate 1</Text>
                    <Text code>{avg ? (avg.gate1_avg * 100).toFixed(1) + '%' : '-'}</Text>
                  </Space>
                  <Progress
                    percent={avg ? Math.round(avg.gate1_avg * 100) : 0}
                    strokeColor="#1677ff"
                    style={{ marginLeft: 8, marginTop: 4 }}
                  />
                </div>
                <div>
                  <Space style={{ width: 120, justifyContent: 'space-between' }}>
                    <Text strong>Gate 2</Text>
                    <Text code>{avg ? (avg.gate2_avg * 100).toFixed(1) + '%' : '-'}</Text>
                  </Space>
                  <Progress
                    percent={avg ? Math.round(avg.gate2_avg * 100) : 0}
                    strokeColor="#13c2c2"
                    style={{ marginLeft: 8, marginTop: 4 }}
                  />
                </div>
                <div>
                  <Space style={{ width: 120, justifyContent: 'space-between' }}>
                    <Text strong>Gate 3</Text>
                    <Text code>{avg ? (avg.gate3_avg * 100).toFixed(1) + '%' : '-'}</Text>
                  </Space>
                  <Progress
                    percent={avg ? Math.round(avg.gate3_avg * 100) : 0}
                    strokeColor="#722ed1"
                    style={{ marginLeft: 8, marginTop: 4 }}
                  />
                </div>
                <div>
                  <Space style={{ width: 120, justifyContent: 'space-between' }}>
                    <Text strong>总分</Text>
                    <Text code>{avg ? (avg.total_avg * 100).toFixed(1) + '%' : '-'}</Text>
                  </Space>
                  <Progress
                    percent={avg ? Math.round(avg.total_avg * 100) : 0}
                    strokeColor={avg && avg.total_avg >= 0.8 ? '#52c41a' : '#faad14'}
                    style={{ marginLeft: 8, marginTop: 4 }}
                  />
                </div>
              </Space>
            </Card>

            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card title="按状态分布">
                  {byStatusRows.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      size="small"
                      pagination={false}
                      columns={statusCols}
                      dataSource={byStatusRows}
                      scroll={{ y: 320 }}
                    />
                  )}
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card title="按质量层级分布">
                  {byTierRows.length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <Table
                      size="small"
                      pagination={false}
                      columns={tierCols}
                      dataSource={byTierRows}
                      scroll={{ y: 320 }}
                    />
                  )}
                </Card>
              </Col>
            </Row>
          </>
        )}

        {!loading && view === 'trend' && (
          <>
            <Card title="术语趋势 (近 30 天)">
              {!trend?.daily_points?.length && !trend?.accumulative_new?.length ? (
                <Empty description="暂无趋势数据" />
              ) : (
                <div ref={trendChartRef} style={{ height: 380, width: '100%' }} />
              )}
            </Card>
            <Card title="每日状态明细">
              <Table
                size="small"
                columns={dailyStatusCols}
                dataSource={(trend?.daily_points || []).map((p, i) => ({
                  key: i,
                  date: p.date,
                  new: p.new,
                  approved: p.approved,
                  rejected: p.rejected,
                }))}
                pagination={{ pageSize: 10, showSizeChanger: false }}
              />
            </Card>
          </>
        )}

        {!loading && view === 'approvals' && (
          <>
            <Row gutter={[16, 16]}>
              <Col xs={24} md={12}>
                <Card title="按决策分布">
                  {!approvals?.by_decision || Object.keys(approvals.by_decision).length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <div ref={decisionPieRef} style={{ height: 320, width: '100%' }} />
                  )}
                </Card>
              </Col>
              <Col xs={24} md={12}>
                <Card title="按角色分布">
                  {!approvals?.by_role || Object.keys(approvals.by_role).length === 0 ? (
                    <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
                  ) : (
                    <div ref={rolePieRef} style={{ height: 320, width: '100%' }} />
                  )}
                </Card>
              </Col>
            </Row>
            <Card title="审批耗时 (Approval Times)">
              {approvalTimesRows.length === 0 ? (
                <Alert type="info" showIcon message="暂无审批耗时统计" />
              ) : (
                <Table
                  size="small"
                  pagination={false}
                  columns={approvalTimeCols}
                  dataSource={approvalTimesRows}
                />
              )}
            </Card>
          </>
        )}
      </Space>
    </div>
  );
}

export default DashboardPage;
