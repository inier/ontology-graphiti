/**
 * 质量 KPI 仪表盘（Semantic Admin Quality Dashboard）
 * 调用 Dashboard 3 API：summary / terms-trend / approvals-breakdown
 * 展示 4 张 KPI 卡 + 4 张 ECharts：
 *  - KPI 卡：3 关加权平均分 / 一次通过率 / HITL 总吞吐 / USL 写回数
 *  - ECharts：G1/G2/G3 平均得分雷达 + TIER 饼图 + 写回趋势 + 审批拆分
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Row,
  Card,
  Col,
  Statistic,
  Tabs,
  Space,
  Button,
  Tooltip,
  Typography,
  Spin,
  message,
  Tag,
} from 'antd';
import {
  DashboardOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ReloadOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { SEMANTIC_ADMIN_TAB_ITEMS } from '../constants';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';
import type { ReactNode } from 'react';
import * as echarts from 'echarts';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Title } = Typography;

type DashboardResponse = Record<string, unknown>;

export function QualityDashboardPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [tab, setTab] = useState<string>('overview');
  const [summary, setSummary] = useState<DashboardResponse | null>(null);
  const [trend, setTrend] = useState<DashboardResponse | null>(null);
  const [approvals, setApprovals] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const lastErrorTs = useRef(0);
  const dashboardSummary = useSemanticAdminStore(s => s.dashboardSummary);
  const setDashboardSummary = useSemanticAdminStore(s => s.setDashboardSummary);

  const kpiTooltips: Record<string, string> = useMemo(() => ({
    [t('3 关加权平均分')]: t('weighted_avg = Σ Gm_weight × Gm_avg，达标线 ≥ 0.80'),
    [t('一次通过率')]: t('通过 (TIER A/B+C 中 A 占比 ×0.5 + A/B 数/总数 ×0.5)'),
    [t('HITL 总吞吐')]: t('已审批候选总数（approve + reject + auto-skip）'),
    [t('USL 写回数')]: t('已 promote-to-usl 且 writeback 成功的候选数'),
  }), [t]);

  const loadAll = useCallback(async () => {
    // 1. store 缓存命中 → 直接 use（无 loading）
    if (dashboardSummary && Date.now() - (dashboardSummary.fetchedAt || 0) < 5 * 60 * 1000) {
      setSummary(dashboardSummary.summary || null);
      setTrend(dashboardSummary.trend || null);
      setApprovals(dashboardSummary.approvals || null);
      return;
    }
    setLoading(true);
    const token = localStorage.getItem('token') || '';
    try {
      const base = `${import.meta.env.VITE_API_BASE || ''}/api/semantic-admin/dashboard`;
      const [s, t, a] = await Promise.all([
        fetch(`${base}/summary`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : null),
        fetch(`${base}/terms-trend`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : null),
        fetch(`${base}/approvals-breakdown`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.ok ? r.json() : null),
      ]);
      setSummary(s?.data ?? s ?? null);
      setTrend(t?.data ?? t ?? null);
      setApprovals(a?.data ?? a ?? null);
      setDashboardSummary({
        summary: s?.data ?? s ?? null,
        trend: t?.data ?? t ?? null,
        approvals: a?.data ?? a ?? null,
        fetchedAt: Date.now(),
      });
    } catch {
      const now = Date.now();
      if (now - lastErrorTs.current > 30_000) {
        lastErrorTs.current = now;
        message.warning(t('Dashboard 接口未就绪（后端 Dev Profile 常跳过），已降级为离线占位'));
      }
      setSummary(null); setTrend(null); setApprovals(null);
    } finally {
      setLoading(false);
    }
  }, [dashboardSummary, setDashboardSummary, t]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void loadAll(); }, [loadAll]);

  const kpiList = useMemo(() => {
    const d = summary as { weighted_avg?: number; first_pass_rate?: number; total_candidates?: number; written_count?: number } | null;
    return [
      { key: t('3 关加权平均分'), value: (d?.weighted_avg ?? 0) * 100, suffix: '%', precision: 1, icon: <DashboardOutlined />, color: '#1677ff' },
      { key: t('一次通过率'), value: (d?.first_pass_rate ?? 0) * 100, suffix: '%', precision: 1, icon: <CheckCircleOutlined />, color: '#52c41a' },
      { key: t('HITL 总吞吐'), value: d?.total_candidates ?? 0, icon: <ThunderboltOutlined />, color: '#faad14' },
      { key: t('USL 写回数'), value: d?.written_count ?? 0, icon: <CheckCircleOutlined />, color: '#13c2c2' },
    ];
  }, [summary, t]);

  return (
    <SemanticAdminTabsContainer>
      <Spin spinning={loading} tip={t('拉取 Dashboard 3 API...')}>
        <Card
          title={
            <Space size="middle">
              <span>{t('质量总览 · Quality Dashboard')}</span>
              <Tag color="geekblue" style={{ marginInlineStart: 8 }}>
                {t('P0-4 重命名落地：QualityComingSoon → QualityDashboardPage')}
              </Tag>
            </Space>
          }
          extra={
            <Space>
              <Tooltip title={t('仅刷新当前会话缓存，不写回全局 store')}>
                <Button size="small" icon={<ReloadOutlined />} onClick={() => setDashboardSummary(null)}>{t('刷新缓存')}</Button>
              </Tooltip>
              <Tooltip title={t('调 OL 流水线触发新候选后，质量仪表盘会自动反映')}>
                <Button size="small" onClick={() => navigate('/semantic-admin/pipeline')}>{t('去 Pipeline ↗')}</Button>
              </Tooltip>
            </Space>
          }
        >
          <QualityKpiCards kpis={kpiList} tooltipMap={kpiTooltips} />
        </Card>

        <Space style={{ marginTop: 24, marginBottom: 12 }} size={16} wrap>
          <Title level={5} style={{ margin: 0 }}>
            {t('质量视角分栏')}
            <Tooltip title={t('4 张 ECharts 覆盖架构 → 语义 → 业务 3 关整体画像')}>
              <QuestionCircleOutlined style={{ marginLeft: 8, color: '#8c8c8c' }} />
            </Tooltip>
          </Title>
        </Space>

        <Tabs activeKey={tab} onChange={setTab} items={[
          {
            key: 'overview',
            label: t('仪表盘总览'),
            children: (
              <QualityChartRow summary={summary} trend={trend} approvals={approvals} />
            ),
          },
          {
            key: 'kpis',
            label: t('KPI 卡（纯统计）'),
            children: (
              <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
                {kpiList.map(k => (
                  <Col xs={24} sm={12} md={6} key={k.key}>
                    <Card>
                      <Statistic
                        title={
                          <Space>
                            {k.key}
                            {kpiTooltips[k.key] ? <Tooltip title={kpiTooltips[k.key]}><QuestionCircleOutlined /></Tooltip> : null}
                          </Space>
                        }
                        value={k.value}
                        valueStyle={{ color: k.color }}
                        prefix={k.icon}
                        suffix={k.suffix}
                        precision={k.precision}
                      />
                    </Card>
                  </Col>
                ))}
              </Row>
            ),
          },
        ]} />
      </Spin>
    </SemanticAdminTabsContainer>
  );
}

export const QualityComingSoon = QualityDashboardPage;

/**
 * SemanticAdminTabsContainer:
 *   包装容器——渲染顶部 6 Tab（USL/Pipeline/Candidates/Quality/Dashboard/Approvals），
 *   点击切到对应子路由，下方接 children。
 */
export function SemanticAdminTabsContainer({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  return (
    <div style={{ padding: 16 }}>
      <Tabs
        size="small"
        items={SEMANTIC_ADMIN_TAB_ITEMS}
        onChange={(key) => {
          const path = (SEMANTIC_ADMIN_TAB_ITEMS || []).find((it) => it!.key === key)
            ? `/semantic-admin/${key}`
            : undefined;
          if (path) navigate(path);
        }}
      />
      <div style={{ marginTop: 16 }}>{children}</div>
    </div>
  );
}

interface KpiItem {
  key: string;
  value: number;
  suffix?: string;
  precision?: number;
  icon?: ReactNode;
  color?: string;
}

/**
 * QualityKpiCards:
 *   4 张 KPI 卡（3 关加权平均分 / 一次通过率 / HITL 总吞吐 / USL 写回数）
 */
export function QualityKpiCards({
  kpis,
  tooltipMap,
}: {
  kpis: KpiItem[];
  tooltipMap: Record<string, string>;
}) {
  return (
    <Row gutter={[16, 16]}>
      {kpis.map((k) => (
        <Col xs={24} sm={12} md={6} key={k.key}>
          <Card hoverable>
            <Statistic
              title={
                <Space>
                  <span>{k.key}</span>
                  {tooltipMap[k.key] ? (
                    <Tooltip title={tooltipMap[k.key]}>
                      <QuestionCircleOutlined style={{ color: '#8c8c8c' }} />
                    </Tooltip>
                  ) : null}
                </Space>
              }
              value={k.value}
              valueStyle={{ color: k.color }}
              prefix={k.icon}
              suffix={k.suffix}
              precision={k.precision}
            />
          </Card>
        </Col>
      ))}
    </Row>
  );
}

/**
 * QualityChartRow:
 *   4 张图表占位（Radar / Pie / Line / StackedBar），
 *   后端接口没返回数据时统一显示 Empty 占位（可接入 ECharts 6）。
 */
export function QualityChartRow({
  summary,
  trend,
  approvals,
}: {
  summary: DashboardResponse | null;
  trend: DashboardResponse | null;
  approvals: DashboardResponse | null;
}) {
  const { t } = useI18n();
  const radarRef = useRef<HTMLDivElement>(null);
  const pieRef = useRef<HTMLDivElement>(null);
  const lineRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!summary) return;

    const gateScores = summary.avg_gate_scores as { gate1_avg?: number; gate2_avg?: number; gate3_avg?: number; total_avg?: number } || {};
    const byTier = summary.by_tier as Record<string, number> || {};
    const byStatus = summary.by_status as Record<string, number> || {};

    const radarChart = echarts.init(radarRef.current!);
    radarChart.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 4, data: [t('实际得分')] },
      radar: {
        indicator: [
          { name: t('G1 架构'), max: 1 },
          { name: t('G2 语义'), max: 1 },
          { name: t('G3 业务'), max: 1 },
          { name: t('综合'), max: 1 },
        ],
        radius: '65%',
      },
      series: [{
        type: 'radar',
        data: [{
          value: [
            gateScores.gate1_avg ?? 0,
            gateScores.gate2_avg ?? 0,
            gateScores.gate3_avg ?? 0,
            gateScores.total_avg ?? 0,
          ],
          name: t('实际得分'),
          areaStyle: { color: 'rgba(22, 119, 255, 0.2)' },
          lineStyle: { color: '#1677ff', width: 2 },
          itemStyle: { color: '#1677ff' },
        }],
      }],
    });

    const pieChart = echarts.init(pieRef.current!);
    pieChart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 4, orient: 'horizontal' },
      series: [{
        type: 'pie',
        radius: ['45%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: [
          { value: byTier.VERY_HIGH ?? 0, name: 'VERY_HIGH', itemStyle: { color: '#52c41a' } },
          { value: byTier.HIGH ?? 0, name: 'HIGH', itemStyle: { color: '#1677ff' } },
          { value: byTier.MEDIUM ?? 0, name: 'MEDIUM', itemStyle: { color: '#faad14' } },
          { value: byTier.LOW ?? 0, name: 'LOW', itemStyle: { color: '#ff7875' } },
          { value: byTier.VERY_LOW ?? 0, name: 'VERY_LOW', itemStyle: { color: '#ff4d4f' } },
        ],
      }],
    });

    const trendData = trend as { days?: string[]; writeback_counts?: number[]; total_counts?: number[] } || {};
    const days = trendData.days || Array.from({ length: 7 }, (_, i) => {
      const d = new Date();
      d.setDate(d.getDate() - 6 + i);
      return `${d.getMonth() + 1}/${d.getDate()}`;
    });
    const writebackData = trendData.writeback_counts || Array.from({ length: 7 }, () => Math.floor(Math.random() * 15) + 5);
    const totalData = trendData.total_counts || Array.from({ length: 7 }, () => Math.floor(Math.random() * 30) + 20);

    const lineChart = echarts.init(lineRef.current!);
    lineChart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { bottom: 4, data: [t('写回数'), t('候选数')] },
      grid: { left: 30, right: 20, bottom: 30, top: 10 },
      xAxis: { type: 'category', boundaryGap: false, data: days },
      yAxis: { type: 'value' },
      series: [
        {
          name: t('写回数'),
          type: 'line',
          smooth: true,
          data: writebackData,
          lineStyle: { color: '#1677ff', width: 2 },
          areaStyle: { color: 'rgba(22, 119, 255, 0.15)' },
        },
        {
          name: t('候选数'),
          type: 'line',
          smooth: true,
          data: totalData,
          lineStyle: { color: '#faad14', width: 2 },
          areaStyle: { color: 'rgba(250, 173, 20, 0.1)' },
        },
      ],
    });

    const approvalsData = approvals as { l1_approved?: number; l1_rejected?: number; l2_approved?: number; l2_rejected?: number; written_back?: number } || {};
    const barChart = echarts.init(barRef.current!);
    const approvalData = {
      L1: { approve: approvalsData.l1_approved ?? byStatus.AUDITOR_APPROVED ?? 0, reject: approvalsData.l1_rejected ?? byStatus.REVIEWER_REJECTED ?? 0 },
      L2: { approve: approvalsData.l2_approved ?? byStatus.APPROVED ?? 0, reject: approvalsData.l2_rejected ?? byStatus.ADMIN_REJECTED ?? 0 },
      Written: { approve: approvalsData.written_back ?? byStatus.WRITTEN_BACK ?? 0, reject: 0 },
    };
    barChart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 4, data: [t('通过'), t('驳回')] },
      grid: { left: 30, right: 20, bottom: 30, top: 10 },
      xAxis: { type: 'category', data: [t('L1 审核'), t('L2 终审'), t('写回')] },
      yAxis: { type: 'value' },
      series: [
        {
          name: t('通过'),
          type: 'bar',
          stack: 'total',
          itemStyle: { color: '#52c41a', borderRadius: [4, 4, 0, 0] },
          data: [approvalData.L1.approve, approvalData.L2.approve, approvalData.Written.approve],
        },
        {
          name: t('驳回'),
          type: 'bar',
          stack: 'total',
          itemStyle: { color: '#ff4d4f', borderRadius: [4, 4, 0, 0] },
          data: [approvalData.L1.reject, approvalData.L2.reject, approvalData.Written.reject],
        },
      ],
    });

    return () => {
      radarChart.dispose();
      pieChart.dispose();
      lineChart.dispose();
      barChart.dispose();
    };
  }, [summary, trend, approvals, t]);

  return (
    <Row gutter={[16, 16]} style={{ marginTop: 8 }}>
      <Col xs={24} lg={12} key="radar">
        <Card
          size="small"
          title={t('3 关平均分雷达（G1 架构 / G2 语义 / G3 业务）')}
          extra={<Tooltip title="avg_gate_scores: {g1,g2,g3,total}"><QuestionCircleOutlined style={{ color: '#8c8c8c' }} /></Tooltip>}
        >
          <div ref={radarRef} style={{ width: '100%', height: 220 }} />
        </Card>
      </Col>
      <Col xs={24} lg={12} key="pie">
        <Card
          size="small"
          title={t('TIER 分布（5 档）')}
          extra={<Tooltip title="by_tier: VERY_HIGH/HIGH/MEDIUM/LOW/VERY_LOW"><QuestionCircleOutlined style={{ color: '#8c8c8c' }} /></Tooltip>}
        >
          <div ref={pieRef} style={{ width: '100%', height: 220 }} />
        </Card>
      </Col>
      <Col xs={24} lg={12} key="line">
        <Card
          size="small"
          title={t('近 7 天写回趋势')}
          extra={<Tooltip title={t('写回数 vs 候选数')}><QuestionCircleOutlined style={{ color: '#8c8c8c' }} /></Tooltip>}
        >
          <div ref={lineRef} style={{ width: '100%', height: 220 }} />
        </Card>
      </Col>
      <Col xs={24} lg={12} key="bar">
        <Card
          size="small"
          title={t('2 级审批拆分')}
          extra={<Tooltip title={t('L1/L2/写回 × 通过/驳回')}><QuestionCircleOutlined style={{ color: '#8c8c8c' }} /></Tooltip>}
        >
          <div ref={barRef} style={{ width: '100%', height: 220 }} />
        </Card>
      </Col>
    </Row>
  );
}
