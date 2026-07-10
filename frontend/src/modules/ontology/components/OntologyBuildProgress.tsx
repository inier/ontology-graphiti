import { Progress, Tag, Space, Tooltip, Alert } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import {
  CheckCircleFilled,
  LoadingOutlined,
  ClockCircleOutlined,
  WarningFilled,
  CloseCircleFilled,
  SyncOutlined
} from '@ant-design/icons';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export interface Stage {
  id: string;
  name: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error' | 'warning';
  startTime?: Date;
  endTime?: Date;
  errorMessage?: string;
}

export interface ProgressTrackerProps {
  stages: Stage[];
  currentStage: string;
  progress: number;
  estimatedTimeRemaining?: number;
  onStageClick?: (stage: Stage) => void;
  taskDescription?: string;
  errorMessage?: string;
}

const STAGE_COLORS = {
  pending: '#d9d9d9',
  in_progress: '#1890ff',
  completed: '#52c41a',
  error: '#ff4d4f',
  warning: '#faad14'
};

const STATUS_ICONS = {
  pending: <ClockCircleOutlined style={{ color: STAGE_COLORS.pending }} />,
  in_progress: <LoadingOutlined style={{ color: STAGE_COLORS.in_progress, animation: 'spin 1s linear infinite' }} />,
  completed: <CheckCircleFilled style={{ color: STAGE_COLORS.completed }} />,
  error: <CloseCircleFilled style={{ color: STAGE_COLORS.error }} />,
  warning: <WarningFilled style={{ color: STAGE_COLORS.warning }} />
};

type StatusKey = keyof typeof STATUS_ICONS;

const STATUS_KEY_MAP: Record<StatusKey, string> = {
  pending: 'buildProgress.statusPending',
  in_progress: 'buildProgress.statusInProgress',
  completed: 'buildProgress.statusCompleted',
  error: 'buildProgress.statusError',
  warning: 'buildProgress.statusWarning',
};

function formatTime(seconds?: number, t: (key: string, opts?: Record<string, unknown>) => string): string {
  if (!seconds) return '--';
  if (seconds < 60) return `${Math.round(seconds)}${t('buildProgress.seconds')}`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return t('buildProgress.minutesSeconds', { m: minutes, s: remainingSeconds });
}

function StageNode({
  stage,
  isLast,
  onClick,
  t,
}: {
  stage: Stage;
  isLast: boolean;
  onClick?: () => void;
  t: (key: string) => string;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', minWidth: 100 }}>
      <Tooltip title={stage.errorMessage || stage.name}>
        <div
          onClick={onClick}
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            cursor: onClick ? 'pointer' : 'default',
            transition: 'transform 0.3s ease-out',
            transform: stage.status === 'in_progress' ? 'scale(1.1)' : 'scale(1)'
          }}
        >
          <div style={{ fontSize: 24, marginBottom: 4 }}>
            {STATUS_ICONS[stage.status]}
          </div>
          <div
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: stage.status === 'in_progress' ? '#1890ff' :
                     stage.status === 'completed' ? '#52c41a' :
                     stage.status === 'error' ? '#ff4d4f' :
                     stage.status === 'warning' ? '#faad14' : '#8c8c8c',
              marginBottom: 4
            }}
          >
            {stage.name}
          </div>
          <Tag
            color={STAGE_COLORS[stage.status]}
            style={{ margin: 0, fontSize: 12 }}
          >
            {t(STATUS_KEY_MAP[stage.status])}
          </Tag>
        </div>
      </Tooltip>
      {!isLast && (
        <div
          style={{
            width: 60,
            height: 2,
            background: stage.status === 'completed' ? STAGE_COLORS.completed : STAGE_COLORS.pending,
            margin: '0 8px',
            transition: 'background 0.3s ease-out'
          }}
        />
      )}
    </div>
  );
}

export function OntologyBuildProgress({
  stages,
  currentStage,
  progress,
  estimatedTimeRemaining,
  onStageClick,
  taskDescription,
  errorMessage
}: ProgressTrackerProps) {
  const { t } = useI18n('ontology');
  return (
    <Card
      style={{ borderRadius: 8, marginBottom: 16 }}
      styles={{ body: { padding: '16px 24px' } }}
    >
      {taskDescription && (
        <div style={{ marginBottom: 16 }}>
          <Space>
            <SyncOutlined spin={stages.some(s => s.status === 'in_progress')} />
            <span style={{ color: '#8c8c8c', fontSize: 14 }}>{t('buildProgress.currentTask')}:</span>
            <span style={{ color: '#262626', fontSize: 14, fontWeight: 500 }}>
              {taskDescription}
            </span>
          </Space>
        </div>
      )}

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'center',
          flexWrap: 'wrap',
          gap: 8,
          padding: '16px 0'
        }}
      >
        {stages.map((stage, index) => (
          <StageNode
            key={stage.id}
            stage={stage}
            isLast={index === stages.length - 1}
            onClick={onStageClick ? () => onStageClick(stage) : undefined}
            t={t}
          />
        ))}
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 16,
          padding: '12px 16px',
          background: '#fafafa',
          borderRadius: 8
        }}
      >
        <Space size={24}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <ClockCircleOutlined style={{ color: '#8c8c8c' }} />
            <span style={{ color: '#8c8c8c', fontSize: 14 }}>{t('buildProgress.estimatedTime')}:</span>
            <span style={{ color: '#262626', fontSize: 14, fontWeight: 500 }}>
              {formatTime(estimatedTimeRemaining, t)}
            </span>
          </div>
        </Space>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 200 }}>
          <span style={{ color: '#8c8c8c', fontSize: 14 }}>{t('buildProgress.realtimeProgress')}:</span>
          <Progress
            percent={Math.round(progress)}
            size="small"
            strokeColor="#1890ff"
            railColor="#e8e8e8"
            style={{ margin: 0, flex: 1 }}
          />
        </div>
      </div>

      {errorMessage && (
        <Alert
          title={t('buildProgress.errorAlert')}
          description={errorMessage}
          type="warning"
          showIcon
          icon={<WarningFilled style={{ color: '#faad14' }} />}
          style={{ marginTop: 16, background: '#fffbe6', borderColor: '#ffe58f' }}
        />
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
      `}</style>
    </Card>
  );
}

export default OntologyBuildProgress;
