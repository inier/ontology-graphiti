import { useState } from 'react';
import { Card, Button, Space } from 'antd';
import { StepForwardOutlined, StepBackwardOutlined, PauseOutlined, CaretRightOutlined, ReloadOutlined } from '@ant-design/icons';

interface TimelineEvent {
  id: string;
  type: string;
  timestamp: string;
  title: string;
  description: string;
  participants: string[];
  location?: string;
}

interface TimelineViewProps {
  events: TimelineEvent[];
  currentIndex: number;
  onIndexChange: (index: number) => void;
  playing?: boolean;
  onPlay?: () => void;
  onPause?: () => void;
}

export function TimelineView({ events, currentIndex, onIndexChange, playing, onPlay, onPause }: TimelineViewProps) {
  const [speed, setSpeed] = useState(1);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <Card
      title="事件时间线"
      extra={
        <Space>
          <Button.Group>
            <Button icon={<StepBackwardOutlined />} onClick={() => onIndexChange(Math.max(0, currentIndex - 1))} />
            {playing ? (
              <Button icon={<PauseOutlined />} onClick={onPause} />
            ) : (
              <Button icon={<CaretRightOutlined />} onClick={onPlay} />
            )}
            <Button icon={<StepForwardOutlined />} onClick={() => onIndexChange(Math.min(events.length - 1, currentIndex + 1))} />
          </Button.Group>
          <Button.Group>
            {[0.5, 1, 2, 4].map((s) => (
              <Button key={s} type={speed === s ? 'primary' : 'default'} onClick={() => setSpeed(s)}>
                {s}x
              </Button>
            ))}
          </Button.Group>
          <Button icon={<ReloadOutlined />}>重置</Button>
        </Space>
      }
      style={{ borderRadius: 8 }}
    >
      <div style={{ position: 'relative', padding: '20px 0' }}>
        <div
          style={{
            position: 'absolute',
            top: 40,
            left: 0,
            right: 0,
            height: 4,
            background: '#e8e8e8',
            borderRadius: 2,
          }}
        />
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            position: 'relative',
            overflowX: 'auto',
            paddingBottom: 20,
          }}
        >
          {events.map((event, index) => (
            <div
              key={event.id}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                minWidth: 120,
                cursor: 'pointer',
              }}
              onClick={() => onIndexChange(index)}
            >
              <div
                style={{
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  background: index <= currentIndex ? '#ff4d4f' : '#d9d9d9',
                  border: index === currentIndex ? '3px solid #1890ff' : 'none',
                  zIndex: 1,
                  transition: 'all 0.3s',
                }}
              />
              <div
                style={{
                  marginTop: 12,
                  padding: '8px 12px',
                  background: index === currentIndex ? '#e6f7ff' : '#f5f5f5',
                  borderRadius: 4,
                  borderLeft: `3px solid ${index <= currentIndex ? '#ff4d4f' : '#d9d9d9'}`,
                  fontSize: 12,
                  textAlign: 'center',
                  maxWidth: 140,
                }}
              >
                <div style={{ fontWeight: 500, color: '#262626' }}>{formatTime(event.timestamp)}</div>
                <div style={{ color: '#8c8c8c', marginTop: 4 }}>{event.title}</div>
              </div>
            </div>
          ))}
        </div>

        {events[currentIndex] && (
          <div
            style={{
              marginTop: 24,
              padding: 20,
              background: '#ffffff',
              borderRadius: 8,
              border: '1px solid #d9d9d9',
              boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
            }}
          >
            <div style={{ display: 'flex', gap: 16, marginBottom: 12 }}>
              <span style={{ padding: '2px 8px', background: '#ff4d4f', color: '#fff', borderRadius: 4, fontSize: 12 }}>
                {events[currentIndex].type}
              </span>
              <span style={{ color: '#8c8c8c' }}>{events[currentIndex].location}</span>
            </div>
            <h3 style={{ fontSize: 16, fontWeight: 500, marginBottom: 8 }}>{events[currentIndex].title}</h3>
            <p style={{ color: '#595959', marginBottom: 12 }}>{events[currentIndex].description}</p>
            <div style={{ fontSize: 12, color: '#8c8c8c' }}>
              参与方: {events[currentIndex].participants.join(', ')}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
