import { Timeline, Button, Slider, Card, Tag, Space, Typography } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, FastForwardOutlined } from '@ant-design/icons';
import { useI18n } from '../../shared/hooks/useI18n';

const { Text } = Typography;

interface TimelineEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  description?: string;
  data?: Record<string, unknown>;
}

interface ClockState {
  state: 'stopped' | 'running' | 'paused';
  speed: number;
  current_time: string;
}

interface TimelineViewProps {
  events: TimelineEvent[];
  clockState: ClockState;
  onClockControl?: (action: string, speed?: number) => void;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  attack: 'red',
  defend: 'blue',
  move: 'green',
  retreat: 'orange',
  observe: 'purple',
  reinforce: 'cyan',
  communication: 'geekblue',
  logistics: 'magenta',
};

function TimelineView({ events, clockState, onClockControl }: TimelineViewProps) {
  const { t } = useI18n('simulation');

  const handlePlay = () => onClockControl?.('start', clockState.speed || 1);
  const handlePause = () => onClockControl?.('pause');
  const handleSpeedChange = (speed: number) => onClockControl?.('set_speed', speed);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Card
        title={t('timeline.clock', 'Clock Control')}
        size="small"
        extra={
          <Tag color={clockState.state === 'running' ? 'green' : clockState.state === 'paused' ? 'orange' : 'default'}>
            {clockState.state}
          </Tag>
        }
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Space>
            <Button
              icon={<PlayCircleOutlined />}
              onClick={handlePlay}
              disabled={clockState.state === 'running'}
              size="small"
            >
              {t('timeline.play', 'Play')}
            </Button>
            <Button
              icon={<PauseCircleOutlined />}
              onClick={handlePause}
              disabled={clockState.state !== 'running'}
              size="small"
            >
              {t('timeline.pause', 'Pause')}
            </Button>
            <Button
              icon={<FastForwardOutlined />}
              onClick={() => handleSpeedChange((clockState.speed || 1) * 2)}
              size="small"
            >
              {t('timeline.speedUp', 'Speed Up')}
            </Button>
          </Space>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('timeline.speed', 'Speed')}: {clockState.speed || 1}x
            </Text>
            <Slider
              min={0.1}
              max={10}
              step={0.1}
              value={clockState.speed || 1}
              onChange={handleSpeedChange}
              marks={{ 0.1: '0.1x', 1: '1x', 5: '5x', 10: '10x' }}
            />
          </div>
          {clockState.current_time && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {t('timeline.currentTime', 'Current Time')}: {clockState.current_time}
            </Text>
          )}
        </Space>
      </Card>

      <Card title={t('timeline.events', 'Event Timeline')} size="small">
        {events && events.length > 0 ? (
          <Timeline
            items={events.map(event => ({
              color: EVENT_TYPE_COLORS[event.event_type] || 'blue',
              children: (
                <Space direction="vertical" size={2}>
                  <Space>
                    <Tag color={EVENT_TYPE_COLORS[event.event_type] || 'blue'}>
                      {event.event_type}
                    </Tag>
                    <Text style={{ fontSize: 12 }} type="secondary">
                      {event.timestamp}
                    </Text>
                  </Space>
                  {event.description && <Text style={{ fontSize: 13 }}>{event.description}</Text>}
                </Space>
              ),
            }))}
          />
        ) : (
          <Text type="secondary">{t('timeline.noEvents', 'No events in timeline')}</Text>
        )}
      </Card>
    </Space>
  );
}

export default TimelineView;
