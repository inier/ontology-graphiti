import { Progress, Tag, Space } from 'antd';

interface SimulationProgressProps {
  progress: number;
  status: 'idle' | 'running' | 'completed' | 'failed' | 'paused';
}

const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  idle: { color: 'default', label: 'Idle' },
  running: { color: 'processing', label: 'Running' },
  completed: { color: 'green', label: 'Completed' },
  failed: { color: 'red', label: 'Failed' },
  paused: { color: 'orange', label: 'Paused' },
};

function SimulationProgress({ progress, status }: SimulationProgressProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
  const clampedProgress = Math.max(0, Math.min(100, progress));

  let strokeColor: string = '#1890ff';
  if (status === 'completed') strokeColor = '#52c41a';
  else if (status === 'failed') strokeColor = '#ff4d4f';
  else if (status === 'paused') strokeColor = '#faad14';
  else if (clampedProgress > 80) strokeColor = '#52c41a';

  return (
    <Space orientation="vertical" style={{ width: '100%' }} size="small">
      <Progress
        percent={clampedProgress}
        status={status === 'failed' ? 'exception' : status === 'completed' ? 'success' : status === 'paused' ? 'normal' : 'active'}
        strokeColor={strokeColor}
        size="small"
      />
      <Tag color={config.color}>{config.label}</Tag>
    </Space>
  );
}

export default SimulationProgress;
