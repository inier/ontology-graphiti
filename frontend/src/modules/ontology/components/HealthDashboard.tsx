/**
 * HealthDashboard 组件 —— 数据健康扫描结果可视化看板（FR-031 / T330）
 *
 * 顶部 KPI 卡片：Total Rules / Pass Rate / Failing Rules / Last Scan
 * 主区域 Tabs：By Rule（表格）/ By Object Type（饼图）/ Timeline（折线图）
 * 顶部"Run Scan Now"按钮触发单规则扫描
 * 规则详情 Drawer：点击表格行查看最近 10 条 violation
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Card, Row, Col, Tabs, Table, Tag, Button, Space, Empty, Spin, Drawer, Typography, Statistic, message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ReloadOutlined, ThunderboltOutlined, CheckCircleTwoTone, CloseCircleTwoTone, WarningTwoTone, MinusCircleTwoTone } from '@ant-design/icons';
import * as echarts from 'echarts';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text, Title } = Typography;

export interface HealthDashboardProps {
  workspaceId?: string;
}

type RuleStatus = 'PASS' | 'FAIL' | 'WARN' | 'SKIP';

interface HealthRule {
  rule_id: string;
  name: string;
  description?: string;
  object_type?: string;
  status: RuleStatus;
  failure_count: number;
  last_checked_at?: string;
}

interface HealthReportPoint {
  date: string;
  pass_rate: number;
  fail_count: number;
}

interface HealthViolation {
  id: string;
  rule_id: string;
  entity_id: string;
  entity_type: string;
  message: string;
  detected_at: string;
}

const STATUS_META: Record<RuleStatus, { color: string; label: string; icon: React.ReactNode }> = {
  PASS: { color: 'success', label: 'PASS', icon: <CheckCircleTwoTone twoToneColor="#52c41a" /> },
  FAIL: { color: 'error', label: 'FAIL', icon: <CloseCircleTwoTone twoToneColor="#ff4d4f" /> },
  WARN: { color: 'warning', label: 'WARN', icon: <WarningTwoTone twoToneColor="#faad14" /> },
  SKIP: { color: 'default', label: 'SKIP', icon: <MinusCircleTwoTone twoToneColor="#bfbfbf" /> },
};

export function HealthDashboard({ workspaceId }: HealthDashboardProps) {
  const { t } = useI18n();
  void workspaceId;
  const [rules, setRules] = useState<HealthRule[]>([]);
  const [reports, setReports] = useState<HealthReportPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [selectedRule, setSelectedRule] = useState<HealthRule | null>(null);
  const [violations, setViolations] = useState<HealthViolation[]>([]);
  const [violationsLoading, setViolationsLoading] = useState(false);
  const [lastScan, setLastScan] = useState<string | null>(null);

  const pieRef = useRef<HTMLDivElement>(null);
  const lineRef = useRef<HTMLDivElement>(null);
  const pieChart = useRef<echarts.ECharts | null>(null);
  const lineChart = useRef<echarts.ECharts | null>(null);

  const stats = useMemo(() => {
    const total = rules.length;
    const failing = rules.filter((r) => r.status === 'FAIL').length;
    const passing = rules.filter((r) => r.status === 'PASS').length;
    const passRate = total === 0 ? 0 : Math.round((passing / total) * 100);
    return { total, failing, passing, passRate };
  }, [rules]);

  const fetchRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ rules: HealthRule[]; last_scan_at?: string }>(
        '/api/ontology/health/rules',
      );
      setRules(data.rules || []);
      setLastScan(data.last_scan_at ?? null);
    } catch (e) {
      message.error(`加载规则失败: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchReports = useCallback(async () => {
    try {
      const data = await apiClient.get<{ reports: HealthReportPoint[] }>(
        '/api/ontology/health/reports?days=30',
      );
      setReports(data.reports || []);
    } catch (e) {
      message.error(`加载报告失败: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    void fetchRules();
    void fetchReports();
  }, [fetchRules, fetchReports]);

  // Pie chart by object type
  useEffect(() => {
    if (!pieRef.current) return;
    pieChart.current = echarts.init(pieRef.current);
    const aggregate: Record<string, number> = {};
    rules.forEach((r) => {
      if (r.status === 'FAIL') {
        const key = r.object_type || 'Unknown';
        aggregate[key] = (aggregate[key] || 0) + (r.failure_count || 1);
      }
    });
    const data = Object.entries(aggregate).map(([name, value]) => ({ name, value }));
    pieChart.current.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, type: 'scroll' },
      series: [
        {
          name: '失败数',
          type: 'pie',
          radius: ['40%', '70%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
          label: { formatter: '{b}: {d}%' },
          data,
        },
      ],
    });
    const handleResize = () => pieChart.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      pieChart.current?.dispose();
      pieChart.current = null;
    };
  }, [rules]);

  // Line chart timeline
  useEffect(() => {
    if (!lineRef.current) return;
    lineChart.current = echarts.init(lineRef.current);
    const dates = reports.map((r) => r.date);
    const passRates = reports.map((r) => r.pass_rate);
    const fails = reports.map((r) => r.fail_count);
    lineChart.current.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['通过率 %', '失败数'] },
      grid: { left: 40, right: 40, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: dates },
      yAxis: [
        { type: 'value', name: '通过率 %', max: 100, position: 'left' },
        { type: 'value', name: '失败数', position: 'right' },
      ],
      series: [
        { name: '通过率 %', type: 'line', smooth: true, data: passRates, yAxisIndex: 0, areaStyle: { opacity: 0.15 } },
        { name: '失败数', type: 'line', smooth: true, data: fails, yAxisIndex: 1, lineStyle: { type: 'dashed' } },
      ],
    });
    const handleResize = () => lineChart.current?.resize();
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      lineChart.current?.dispose();
      lineChart.current = null;
    };
  }, [reports]);

  const handleRunScanNow = useCallback(async () => {
    setScanning(true);
    try {
      const failed = rules.filter((r) => r.status === 'FAIL');
      const targets = failed.length > 0 ? failed : rules;
      await Promise.allSettled(
        targets.map((r) =>
          apiClient.post(`/api/ontology/health/rules/${r.rule_id}/scan`, {}),
        ),
      );
      message.success('扫描已触发');
      await fetchRules();
      await fetchReports();
    } catch (e) {
      message.error(`扫描失败: ${(e as Error).message}`);
    } finally {
      setScanning(false);
    }
  }, [rules, fetchRules, fetchReports]);

  const handleRowClick = useCallback(async (rule: HealthRule) => {
    setSelectedRule(rule);
    setViolationsLoading(true);
    try {
      const data = await apiClient.get<{ violations: HealthViolation[] }>(
        `/api/ontology/health/rules/${rule.rule_id}/violations?limit=10`,
      );
      setViolations(data.violations || []);
    } catch (e) {
      message.error(`加载违规失败: ${(e as Error).message}`);
      setViolations([]);
    } finally {
      setViolationsLoading(false);
    }
  }, []);

  const columns: ColumnsType<HealthRule> = [
    {
      title: '规则',
      dataIndex: 'name',
      key: 'name',
      render: (_: string, r) => (
        <Space size={4} orientation="vertical" style={{ lineHeight: 1.2 }}>
          <Text strong>{r.name}</Text>
          {r.description && <Text type="secondary" style={{ fontSize: 12 }}>{r.description}</Text>}
        </Space>
      ),
    },
    { title: '对象类型', dataIndex: 'object_type', key: 'object_type', width: 140, render: (v?: string) => v ? <Tag color="blue">{v}</Tag> : '-' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (s: RuleStatus) => {
        const meta = STATUS_META[s];
        return <Tag color={meta.color} icon={meta.icon as React.ReactElement}>{meta.label}</Tag>;
      },
    },
    { title: '失败数', dataIndex: 'failure_count', key: 'failure_count', width: 90, align: 'right' },
    {
      title: '最近检查',
      dataIndex: 'last_checked_at',
      key: 'last_checked_at',
      width: 170,
      render: (v?: string) => v ? new Date(v).toLocaleString() : '-',
    },
  ];

  const violationColumns: ColumnsType<HealthViolation> = [
    { title: '实体', dataIndex: 'entity_id', key: 'entity_id', width: 130 },
    { title: '类型', dataIndex: 'entity_type', key: 'entity_type', width: 120, render: (v: string) => <Tag color="purple">{v}</Tag> },
    { title: '描述', dataIndex: 'message', key: 'message' },
    { title: '检测时间', dataIndex: 'detected_at', key: 'detected_at', width: 170, render: (v: string) => new Date(v).toLocaleString() },
  ];

  return (
    <div data-testid="health-dashboard" style={{ padding: 16 }}>
      <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
        <Title level={3} style={{ margin: 0 }}>{t('ontology.health.title') || '数据健康看板'}</Title>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => { void fetchRules(); void fetchReports(); }} loading={loading}>
            {t('common.refresh') || '刷新'}
          </Button>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={handleRunScanNow}
            loading={scanning}
          >
            {t('ontology.health.runScan') || 'Run Scan Now'}
          </Button>
        </Space>
      </Space>

      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title={t('ontology.health.totalRules') || 'Total Rules'} value={stats.total} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('ontology.health.passRate') || 'Pass Rate'}
              value={stats.passRate}
              suffix="%"
              styles={{ content: stats.passRate >= 90 ? { color: '#52c41a' } : stats.passRate >= 60 ? { color: '#faad14' } : { color: '#ff4d4f' } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card><Statistic title={t('ontology.health.failingRules') || 'Failing Rules'} value={stats.failing} styles={{ content: { color: '#ff4d4f' } }} /></Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title={t('ontology.health.lastScan') || 'Last Scan'}
              value={lastScan ? new Date(lastScan).toLocaleString() : '-'}
              styles={{ content: { fontSize: 14 } }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Tabs
          defaultActiveKey="rule"
          items={[
            {
              key: 'rule',
              label: t('ontology.health.tabRule') || 'By Rule',
              children: (
                <Spin spinning={loading}>
                  {rules.length === 0 ? (
                    <Empty description="暂无规则" />
                  ) : (
                    <Table<HealthRule>
                      rowKey="rule_id"
                      size="small"
                      dataSource={rules}
                      columns={columns}
                      pagination={{ pageSize: 10 }}
                      onRow={(record) => ({ onClick: () => handleRowClick(record), style: { cursor: 'pointer' } })}
                    />
                  )}
                </Spin>
              ),
            },
            {
              key: 'type',
              label: t('ontology.health.tabType') || 'By Object Type',
              children: (
                <Spin spinning={loading}>
                  {stats.failing === 0 ? (
                    <Empty description="暂无失败规则" />
                  ) : (
                    <div ref={pieRef} style={{ width: '100%', height: 360 }} />
                  )}
                </Spin>
              ),
            },
            {
              key: 'timeline',
              label: t('ontology.health.tabTimeline') || 'Timeline',
              children: (
                <Spin spinning={loading}>
                  {reports.length === 0 ? (
                    <Empty description="暂无历史报告" />
                  ) : (
                    <div ref={lineRef} style={{ width: '100%', height: 360 }} />
                  )}
                </Spin>
              ),
            },
          ]}
        />
      </Card>

      <Drawer
        title={selectedRule ? `规则详情: ${selectedRule.name}` : '规则详情'}
        open={!!selectedRule}
        onClose={() => setSelectedRule(null)}
        width={640}
      >
        {selectedRule && (
          <Space orientation="vertical" size="middle" style={{ width: '100%' }}>
            <Card size="small">
              <Space wrap>
                <Text>状态：</Text>
                <Tag color={STATUS_META[selectedRule.status].color}>
                  {STATUS_META[selectedRule.status].label}
                </Tag>
                <Text>对象类型：</Text>
                <Tag color="blue">{selectedRule.object_type || '-'}</Tag>
                <Text>失败数：</Text>
                <Text strong>{selectedRule.failure_count}</Text>
              </Space>
              {selectedRule.description && (
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">{selectedRule.description}</Text>
                </div>
              )}
            </Card>
            <Card size="small" title="最近 10 条 Violation">
              <Spin spinning={violationsLoading}>
                {violations.length === 0 ? (
                  <Empty description="暂无违规" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                ) : (
                  <Table<HealthViolation>
                    rowKey="id"
                    size="small"
                    dataSource={violations}
                    columns={violationColumns}
                    pagination={false}
                  />
                )}
              </Spin>
            </Card>
          </Space>
        )}
      </Drawer>
    </div>
  );
}

export default HealthDashboard;
