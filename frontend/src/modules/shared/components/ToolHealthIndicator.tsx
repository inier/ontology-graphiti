import { Card, Typography, Space, Progress, Tag } from 'antd';

const { Text } = Typography;

interface ToolHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  success_rate: number;
  avg_duration_ms: number;
  error_count?: number;
  last_error?: string;
}

interface ToolHealthIndicatorProps {
  toolName: string;
  health: ToolHealth;
  style?: React.CSSProperties;
}

const statusColors = {
  healthy: '#52c41a',
  degraded: '#faad14',
  unhealthy: '#ff4d4f',
};

const statusText = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  unhealthy: 'Unhealthy',
};

export const ToolHealthIndicator: React.FC<ToolHealthIndicatorProps> = ({
  toolName,
  health,
  style,
}) => {
  const getProgressStatus = (): 'success' | 'normal' | 'exception' => {
    if (health.success_rate >= 90) return 'success';
    if (health.success_rate >= 70) return 'normal';
    return 'exception';
  };

  return (
    <Card size="small" style={style}>
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Space style={{ justifyContent: 'space-between', width: '100%' }}>
          <Text strong>{toolName}</Text>
          <Tag color={statusColors[health.status]}>{statusText[health.status]}</Tag>
        </Space>

        <div>
          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Text type="secondary">Success Rate</Text>
            <Text>{health.success_rate.toFixed(1)}%</Text>
          </Space>
          <Progress
            percent={health.success_rate}
            status={getProgressStatus()}
            showInfo={false}
            strokeColor={statusColors[health.status]}
            size="small"
          />
        </div>

        <div>
          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Text type="secondary">Avg Duration</Text>
            <Text>{health.avg_duration_ms.toFixed(0)}ms</Text>
          </Space>
        </div>

        {health.error_count !== undefined && health.error_count > 0 && (
          <div>
            <Text type="secondary">Errors (24h)</Text>
            <Tag color="red" style={{ marginLeft: 8 }}>{health.error_count}</Tag>
          </div>
        )}

        {health.last_error && (
          <div>
            <Text style={{ fontSize: 12, color: '#ff4d4f' }}>
              Last Error: {health.last_error}
            </Text>
          </div>
        )}
      </Space>
    </Card>
  );
};