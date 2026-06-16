import { Card, Row, Col, Descriptions, Tag, Typography, Space } from 'antd';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface ScenarioData {
  scenario_id: string;
  name: string;
  status: string;
  risk_level: string;
  risk_score: number;
  confidence: number;
  metrics: Record<string, number>;
  recommendation?: string;
}

interface ParallelComparisonProps {
  scenarios: ScenarioData[];
  results: Array<Record<string, unknown>>;
}

const RISK_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
  critical: '#cf1322',
};

function ParallelComparison({ scenarios, results }: ParallelComparisonProps) {
  const { t } = useI18n('simulation');

  if (!scenarios || scenarios.length === 0) {
    return (
      <Card>
        <Text type="secondary">{t('comparison.empty', 'No scenarios to compare')}</Text>
      </Card>
    );
  }

  const colSpan = Math.max(6, Math.floor(24 / scenarios.length));

  const allMetricKeys = Array.from(
    new Set(scenarios.flatMap(s => Object.keys(s.metrics || {})))
  );

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Row gutter={[16, 16]}>
        {scenarios.map((scenario) => (
          <Col span={colSpan} key={scenario.scenario_id}>
            <Card
              title={scenario.name}
              size="small"
              extra={<Tag color={RISK_COLORS[scenario.risk_level] || 'default'}>{scenario.risk_level}</Tag>}
            >
              <Descriptions size="small" column={1} variant="bordered">
                <Descriptions.Item label={t('comparison.status', 'Status')}>
                  <Tag color={scenario.status === 'completed' ? 'green' : 'processing'}>{scenario.status}</Tag>
                </Descriptions.Item>
                <Descriptions.Item label={t('comparison.riskScore', 'Risk Score')}>
                  <Text style={{ color: RISK_COLORS[scenario.risk_level] || '#999' }}>
                    {scenario.risk_score.toFixed(1)}
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label={t('comparison.confidence', 'Confidence')}>
                  <Text>{(scenario.confidence * 100).toFixed(1)}%</Text>
                </Descriptions.Item>
              </Descriptions>
              {scenario.recommendation && (
                <div style={{ marginTop: 8, padding: '4px 8px', background: '#fafafa', borderRadius: 4 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>{scenario.recommendation}</Text>
                </div>
              )}
            </Card>
          </Col>
        ))}
      </Row>

      {allMetricKeys.length > 0 && (
        <Card title={t('comparison.metrics', 'Key Metrics Comparison')} size="small">
          <Row gutter={[16, 8]}>
            {allMetricKeys.map(key => {
              const values = scenarios.map(s => s.metrics?.[key]);
              const maxVal = Math.max(...values.filter((v): v is number => v != null));
              return (
                <Col span={Math.max(6, Math.floor(24 / allMetricKeys.length))} key={key}>
                  <Card size="small" type="inner" title={key}>
                    {scenarios.map((s) => {
                      const val = s.metrics?.[key];
                      const isMax = val != null && val === maxVal;
                      return (
                        <div key={s.scenario_id} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text style={{ fontSize: 12 }}>{s.name}</Text>
                          <Tag color={isMax ? 'gold' : 'default'}>
                            {val != null ? val.toFixed(3) : '-'}
                          </Tag>
                        </div>
                      );
                    })}
                  </Card>
                </Col>
              );
            })}
          </Row>
        </Card>
      )}

      {results && results.length > 0 && (
        <Card title={t('comparison.rawResults', 'Raw Results')} size="small">
          {results.map((r, idx) => (
            <Card key={idx} size="small" type="inner" style={{ marginBottom: 8 }}>
              <pre style={{ fontSize: 11, margin: 0, overflow: 'auto', maxHeight: 120 }}>
                {JSON.stringify(r, null, 2)}
              </pre>
            </Card>
          ))}
        </Card>
      )}
    </Space>
  );
}

export default ParallelComparison;
