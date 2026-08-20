import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Tag, Alert, Button, Space } from 'antd';
import { ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

interface OPAMetrics {
  total_decisions: number;
  allow_count: number;
  deny_count: number;
  deny_rate_percent: number;
  latency_ms: { p50: number; p95: number; p99: number; avg: number };
  by_package: Record<string, { allow: number; deny: number }>;
  top_deny_reasons: { reason: string; count: number }[];
  audit_failures: number;
  opa_unavailable_count: number;
}

export function OPAMonitorPage() {
  const { t } = useI18n();
  const [metrics, setMetrics] = useState<OPAMetrics | null>(null);
  const [loading, setLoading] = useState(false);

  const loadMetrics = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<OPAMetrics>('/api/opa/metrics?window=300');
      setMetrics(data);
    } catch {
      // 静默
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
    const timer = setInterval(loadMetrics, 10000);
    return () => clearInterval(timer);
  }, []);

  const denyRate = metrics?.deny_rate_percent ?? 0;
  const denyRateColor = denyRate > 30 ? '#ff4d4f' : denyRate > 10 ? '#faad14' : '#52c41a';

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={loadMetrics} loading={loading}>
          {t('刷新')}
        </Button>
      </Space>

      {denyRate > 30 && (
        <Alert
          type="error"
          message={t('DENY 率异常')}
          description={`${denyRate}% 的请求被拒绝，请检查策略配置`}
          showIcon
          icon={<WarningOutlined />}
          style={{ marginBottom: 16 }}
        />
      )}

      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card><Statistic title={t('总决策数')} value={metrics?.total_decisions ?? 0} loading={loading} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('允许')} value={metrics?.allow_count ?? 0} loading={loading}
            styles={{ content: { color: '#52c41a' } }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('拒绝')} value={metrics?.deny_count ?? 0} loading={loading}
            styles={{ content: { color: '#ff4d4f' } }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title={t('拒绝率')} value={`${denyRate}%`} loading={loading}
            styles={{ content: { color: denyRateColor } }} /></Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={8}>
          <Card title={t('延迟 (ms)')} size="small">
            <p>P50: {metrics?.latency_ms?.p50 ?? 0}</p>
            <p>P95: {metrics?.latency_ms?.p95 ?? 0}</p>
            <p>P99: {metrics?.latency_ms?.p99 ?? 0}</p>
            <p>{t('平均')}: {metrics?.latency_ms?.avg ?? 0}</p>
          </Card>
        </Col>
        <Col span={8}>
          <Card title={t('审计失败')} size="small">
            <Statistic value={metrics?.audit_failures ?? 0}
              valueStyle={{ color: (metrics?.audit_failures ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card title={t('OPA 不可用次数')} size="small">
            <Statistic value={metrics?.opa_unavailable_count ?? 0}
              valueStyle={{ color: (metrics?.opa_unavailable_count ?? 0) > 0 ? '#ff4d4f' : '#52c41a' }} />
          </Card>
        </Col>
      </Row>

      <Card title={t('DENY 原因 Top 5')} style={{ marginTop: 16 }}>
        <Table
          dataSource={metrics?.top_deny_reasons || []}
          columns={[
            { title: t('原因'), dataIndex: 'reason', key: 'reason' },
            { title: t('次数'), dataIndex: 'count', key: 'count', width: 100 },
          ]}
          rowKey="reason"
          pagination={false}
          size="small"
        />
      </Card>

      <Card title={t('按策略包统计')} style={{ marginTop: 16 }}>
        <Table
          dataSource={Object.entries(metrics?.by_package || {}).map(([pkg, counts]) => ({
            package: pkg, ...counts,
          }))}
          columns={[
            { title: t('策略包'), dataIndex: 'package', key: 'package' },
            { title: t('允许'), dataIndex: 'allow', key: 'allow', width: 100,
              render: (v: number) => <Tag color="green">{v}</Tag> },
            { title: t('拒绝'), dataIndex: 'deny', key: 'deny', width: 100,
              render: (v: number) => <Tag color="red">{v}</Tag> },
          ]}
          rowKey="package"
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}
