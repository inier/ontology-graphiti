import { useState, useEffect, useCallback } from 'react';
import { Card, List, Collapse, Tag, Rate, Progress, Space, Typography } from 'antd';
import { SafetyOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { apiClient } from '../../shared/services/apiClient';
import { useI18n } from '../../shared/hooks/useI18n';

const { Text, Paragraph } = Typography;

interface Recommendation {
  recommendation_id: string;
  title: string;
  description: string;
  ranking: number;
  risk_level: string;
  risk_score: number;
  confidence: number;
  explanation: string;
  actions: string[];
}

interface RecommendationPanelProps {
  scenarioId?: string;
  sandboxId?: string;
}

const RISK_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
  critical: '#cf1322',
};

function RecommendationPanel({ scenarioId, sandboxId }: RecommendationPanelProps) {
  const { t } = useI18n('simulation');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRecommendations = useCallback(async () => {
    if (!scenarioId && !sandboxId) return;
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (scenarioId) params.scenario_id = scenarioId;
      if (sandboxId) params.sandbox_id = sandboxId;
      const qs = new URLSearchParams(params).toString();
      const data = await apiClient.get<{ recommendations: Recommendation[] }>(`/api/simulation/recommendations?${qs}`);
      setRecommendations(data.recommendations || []);
    } catch {
      setRecommendations([]);
    } finally {
      setLoading(false);
    }
  }, [scenarioId, sandboxId]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  const sortedRecommendations = [...recommendations].sort((a, b) => a.ranking - b.ranking);

  return (
    <Card
      title={t('recommendation.title', 'Decision Recommendations')}
      size="small"
      loading={loading}
    >
      {sortedRecommendations.length === 0 ? (
        <Text type="secondary">{t('recommendation.empty', 'No recommendations available')}</Text>
      ) : (
        <List
          dataSource={sortedRecommendations}
          renderItem={(item) => (
            <List.Item key={item.recommendation_id}>
              <Card
                size="small"
                style={{ width: '100%' }}
                title={
                  <Space>
                    <Tag color="gold">#{item.ranking}</Tag>
                    <Text strong>{item.title}</Text>
                  </Space>
                }
                extra={
                  <Space>
                    <Tag color={RISK_COLORS[item.risk_level] || 'default'} icon={
                      item.risk_level === 'low' ? <CheckCircleOutlined /> :
                      item.risk_level === 'high' || item.risk_level === 'critical' ? <WarningOutlined /> :
                      <SafetyOutlined />
                    }>
                      {item.risk_level}
                    </Tag>
                  </Space>
                }
              >
                <Space direction="vertical" style={{ width: '100%' }} size="small">
                  <Paragraph style={{ marginBottom: 4 }}>{item.description}</Paragraph>

                  <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>{t('recommendation.riskScore', 'Risk Score')}</Text>
                      <Progress
                        percent={Math.round(item.risk_score)}
                        size="small"
                        strokeColor={RISK_COLORS[item.risk_level] || '#1890ff'}
                        style={{ width: 120 }}
                      />
                    </div>
                    <div>
                      <Text type="secondary" style={{ fontSize: 12 }}>{t('recommendation.confidence', 'Confidence')}</Text>
                      <div>
                        <Rate disabled value={Math.round(item.confidence * 5)} style={{ fontSize: 14 }} />
                        <Text style={{ marginLeft: 8, fontSize: 12 }}>{(item.confidence * 100).toFixed(0)}%</Text>
                      </div>
                    </div>
                  </div>

                  <Collapse
                    size="small"
                    items={[{
                      key: item.recommendation_id,
                      label: t('recommendation.explanation', 'Explanation'),
                      children: (
                        <Space direction="vertical" style={{ width: '100%' }}>
                          <Paragraph style={{ fontSize: 13 }}>{item.explanation}</Paragraph>
                          {item.actions && item.actions.length > 0 && (
                            <div>
                              <Text strong style={{ fontSize: 12 }}>{t('recommendation.actions', 'Suggested Actions')}:</Text>
                              <ul style={{ margin: '4px 0', paddingLeft: 20 }}>
                                {item.actions.map((action, idx) => (
                                  <li key={idx}><Text style={{ fontSize: 12 }}>{action}</Text></li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </Space>
                      ),
                    }]}
                  />
                </Space>
              </Card>
            </List.Item>
          )}
        />
      )}
    </Card>
  );
}

export default RecommendationPanel;
