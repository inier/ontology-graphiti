import { Timeline, Tag, Empty } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  EyeOutlined,
  CompassOutlined,
  AimOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';

interface DecisionStep {
  step_id?: string;
  phase: string;
  description: string;
  evidence?: Record<string, unknown>[];
  timestamp?: string;
}

interface DecisionTimelineProps {
  decisionId: string;
  steps: DecisionStep[];
}

const PHASE_CONFIG: Record<
  string,
  { color: string; icon: React.ReactNode }
> = {
  observe: { color: 'blue', icon: <EyeOutlined /> },
  orient: { color: 'orange', icon: <CompassOutlined /> },
  decide: { color: 'green', icon: <AimOutlined /> },
  act: { color: 'red', icon: <ThunderboltOutlined /> },
};

export function DecisionTimeline({ decisionId, steps }: DecisionTimelineProps) {
  const { t } = useI18n('agent');

  if (!steps || steps.length === 0) {
    return (
      <Card title={t('decisionTimeline')} size="small">
        <Empty description={t('noData')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    );
  }

  const timelineItems = steps.map((step, index) => {
    const config = PHASE_CONFIG[step.phase] || {
      color: 'default',
      icon: null,
    };

    return {
      key: step.step_id || index,
      color: config.color as
        | 'blue'
        | 'orange'
        | 'green'
        | 'red'
        | 'default'
        | 'gray',
      dot: config.icon,
      children: (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Tag color={config.color}>{t(step.phase)}</Tag>
            {step.timestamp && (
              <span style={{ fontSize: 12, color: '#8c8c8c' }}>
                {step.timestamp}
              </span>
            )}
          </div>
          <div style={{ fontSize: 13, color: '#595959' }}>
            {step.description}
          </div>
          {step.evidence && step.evidence.length > 0 && (
            <div style={{ marginTop: 4, fontSize: 12, color: '#8c8c8c' }}>
              {t('evidence')}: {step.evidence.length} items
            </div>
          )}
        </div>
      ),
    };
  });

  return (
    <Card title={`${t('decisionTimeline')} #${decisionId.slice(0, 8)}`} size="small">
      <Timeline items={timelineItems} />
    </Card>
  );
}
