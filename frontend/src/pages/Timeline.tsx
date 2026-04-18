import { useState, useEffect } from 'react';

import { TimelineView } from '../components/TimelineView';
import { api } from '../services/api';

interface TimelineEvent {
  id: string;
  type: string;
  timestamp: string;
  title: string;
  description: string;
  participants: string[];
  location?: string;
}

export function Timeline() {
  const [events, setEvents] = useState<TimelineEvent[]>([
    {
      id: '1',
      type: 'contact',
      timestamp: '2026-04-16T08:30:00Z',
      title: '双方接触',
      description: '红方装甲营与蓝方机械化步兵营在B区发生接触',
      participants: ['红方装甲营', '蓝方机械化步兵营'],
      location: 'B区',
    },
    {
      id: '2',
      type: 'attack',
      timestamp: '2026-04-16T09:00:00Z',
      title: '红方发起进攻',
      description: '红方装甲营对蓝方阵地发起进攻',
      participants: ['红方装甲营'],
      location: 'B区北侧',
    },
    {
      id: '3',
      type: 'reinforcement',
      timestamp: '2026-04-16T09:30:00Z',
      title: '蓝方增援到达',
      description: '蓝方增援部队抵达战场',
      participants: ['蓝方增援部队'],
      location: 'B区南侧',
    },
    {
      id: '4',
      type: 'engagement',
      timestamp: '2026-04-16T10:00:00Z',
      title: '激烈交战',
      description: '双方在B区展开激烈交火',
      participants: ['红方装甲营', '蓝方机械化步兵营', '蓝方增援部队'],
      location: 'B区',
    },
    {
      id: '5',
      type: 'retreat',
      timestamp: '2026-04-16T10:30:00Z',
      title: '蓝方撤退',
      description: '蓝方部队撤退至D区',
      participants: ['蓝方机械化步兵营', '蓝方增援部队'],
      location: 'D区',
    },
  ]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const loadTimeline = async () => {
      try {
        const timelineData = await api.getTimeline('default');
        if (timelineData && timelineData.length > 0) {
          setEvents(timelineData.map((e: { event_id: string; event_type: string; timestamp: string; description: string; participants: string[]; location?: string }) => ({
            id: e.event_id,
            type: e.event_type,
            timestamp: e.timestamp,
            title: e.event_type,
            description: e.description,
            participants: e.participants || [],
            location: e.location,
          })));
        }
      } catch (error) {
        console.error('加载时间线失败', error);
      }
    };
    loadTimeline();
  }, []);

  return (
    <div>
      <TimelineView
        events={events}
        currentIndex={currentIndex}
        onIndexChange={setCurrentIndex}
        playing={playing}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
      />
    </div>
  );
}
