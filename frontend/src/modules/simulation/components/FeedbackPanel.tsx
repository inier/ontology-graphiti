import { useState, useEffect } from 'react';
import { Card, Descriptions, Button, Tag, Space, Typography, List, Progress, Spin, Empty, message } from 'antd';
import { CheckCircleOutlined, SyncOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';

const { Text } = Typography;

interface FeedbackAnalysis {
  task_id: string;
  total_feedbacks: number;
  average_deviation: number;
  lessons_learned: string[];
  recommendations: string[];
  severity_distribution: Record<string, number>;
}

interface AggregatedFeedback {
  ontology_id: string;
  total_feedbacks: number;
  experience_items: Array<{
    key: string;
    value: unknown;
    count: number;
  }>;
  top_lessons: string[];
}

interface FeedbackPanelProps {
  taskId?: string;
  ontologyId?: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  low: 'green',
  medium: 'orange',
  high: 'red',
  critical: '#cf1322',
};

export default function FeedbackPanel({ taskId, ontologyId }: FeedbackPanelProps) {
  const [analysis, setAnalysis] = useState<FeedbackAnalysis | null>(null);
  const [aggregation, setAggregation] = useState<AggregatedFeedback | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (taskId) loadAnalysis(taskId);
    if (ontologyId) loadAggregation(ontologyId);
  }, [taskId, ontologyId]);

  const loadAnalysis = async (id: string) => {
    setLoading(true);
    try {
      const data = await apiClient.get<FeedbackAnalysis>(`/api/feedback/analysis/${id}`);
      setAnalysis(data);
    } catch {
      setAnalysis(null);
    } finally {
      setLoading(false);
    }
  };

  const loadAggregation = async (id: string) => {
    try {
      const data = await apiClient.get<AggregatedFeedback>(`/api/feedback/aggregate?ontology_id=${encodeURIComponent(id)}`);
      setAggregation(data);
    } catch {
      setAggregation(null);
    }
  };

  const handleCloseLoop = async () => {
    const sourceId = taskId || ontologyId || '';
    if (!sourceId) {
      message.warning('No task or ontology specified');
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.post<{
        status: string;
        feedback_id: string;
        lesson_learned: string;
        graph_updated: boolean;
        episode_created: boolean;
        hook_emitted: boolean;
      }>('/api/feedback/close-loop', {
        source_id: sourceId,
        feedback_type: 'action_result',
        outcome: 'success',
        data: {},
      });
      message.success(`Close-loop completed. Lesson: ${data.lesson_learned || 'N/A'}`);
      if (taskId) loadAnalysis(taskId);
      if (ontologyId) loadAggregation(ontologyId);
    } catch (e) {
      message.error(`Close-loop failed: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  };

  const renderAnalysis = () => {
    if (!analysis) {
      return <Empty description="No feedback analysis available" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Descriptions variant="bordered" size="small" column={2}>
          <Descriptions.Item label="Task ID">{analysis.task_id}</Descriptions.Item>
          <Descriptions.Item label="Total Feedbacks">{analysis.total_feedbacks}</Descriptions.Item>
          <Descriptions.Item label="Avg Deviation" span={2}>
            <Progress
              percent={Math.round((1 - analysis.average_deviation) * 100)}
              size="small"
              strokeColor={analysis.average_deviation > 0.5 ? '#ff4d4f' : analysis.average_deviation > 0.2 ? '#faad14' : '#52c41a'}
            />
          </Descriptions.Item>
        </Descriptions>

        {analysis.severity_distribution && Object.keys(analysis.severity_distribution).length > 0 && (
          <Card title="Severity Distribution" size="small">
            <Space wrap>
              {Object.entries(analysis.severity_distribution).map(([severity, count]) => (
                <Tag key={severity} color={SEVERITY_COLORS[severity] || 'default'}>
                  {severity}: {count}
                </Tag>
              ))}
            </Space>
          </Card>
        )}

        {analysis.lessons_learned && analysis.lessons_learned.length > 0 && (
          <Card title="Lessons Learned" size="small">
            <List
              size="small"
              dataSource={analysis.lessons_learned}
              renderItem={(lesson) => (
                <List.Item>
                  <Space>
                    <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    <Text>{lesson}</Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}

        {analysis.recommendations && analysis.recommendations.length > 0 && (
          <Card title="Recommendations" size="small">
            <List
              size="small"
              dataSource={analysis.recommendations}
              renderItem={(rec) => (
                <List.Item>
                  <Space>
                    <SyncOutlined style={{ color: '#1890ff' }} />
                    <Text>{rec}</Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Space>
    );
  };

  const renderAggregation = () => {
    if (!aggregation) {
      return <Empty description="No experience aggregation available" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Descriptions variant="bordered" size="small" column={2}>
          <Descriptions.Item label="Ontology ID">{aggregation.ontology_id}</Descriptions.Item>
          <Descriptions.Item label="Total Feedbacks">{aggregation.total_feedbacks}</Descriptions.Item>
        </Descriptions>

        {aggregation.experience_items && aggregation.experience_items.length > 0 && (
          <Card title="Experience Aggregation" size="small">
            <List
              size="small"
              dataSource={aggregation.experience_items}
              renderItem={(item) => (
                <List.Item>
                  <Space>
                    <Tag color="blue">{item.key}</Tag>
                    <Text>{typeof item.value === 'string' ? item.value : JSON.stringify(item.value)}</Text>
                    <Tag>count: {item.count}</Tag>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}

        {aggregation.top_lessons && aggregation.top_lessons.length > 0 && (
          <Card title="Top Lessons" size="small">
            <List
              size="small"
              dataSource={aggregation.top_lessons}
              renderItem={(lesson, idx) => (
                <List.Item>
                  <Space>
                    <Tag color="gold">#{idx + 1}</Tag>
                    <Text>{lesson}</Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}
      </Space>
    );
  };

  return (
    <Spin spinning={loading}>
      <Card
        title="Feedback Panel"
        size="small"
        extra={
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={handleCloseLoop}
            loading={loading}
          >
            Close Loop
          </Button>
        }
      >
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          {renderAnalysis()}
          {renderAggregation()}
        </Space>
      </Card>
    </Spin>
  );
}
