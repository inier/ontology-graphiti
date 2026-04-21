import { useState, useEffect } from 'react';
import { Card, Button, Space, Select, message, Spin, Table } from 'antd';
import { ReloadOutlined, ExportOutlined } from '@ant-design/icons';
import { TimelineView } from '../components/TimelineView';
import { api } from '../../shared/services/api';
import type { Scenario, TimelineEvent } from '../../shared/types';

export function Timeline() {
  const [scenarioId, setScenarioId] = useState('');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadScenarios();
  }, []);

  const loadScenarios = async () => {
    try {
      const data = await api.listScenarios();
      setScenarios(data);
    } catch (error) {
      console.error('加载场景失败', error);
      message.error('加载场景失败');
    }
  };

  const loadTimeline = async () => {
    if (!scenarioId) {
      message.warning('请选择场景');
      return;
    }
    try {
      setLoading(true);
      const data = await api.getTimeline(scenarioId);
      setEvents(data);
    } catch (error) {
      console.error('加载时间线失败', error);
      message.error('加载时间线失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="时间线"
        extra={
          <Space>
            <Button icon={<ExportOutlined />}>
              导出
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadTimeline}>
              刷新
            </Button>
          </Space>
        }
      >
        <div style={{ marginBottom: 16 }}>
          <Select
            placeholder="选择场景"
            style={{ width: 300, marginRight: 16 }}
            value={scenarioId}
            onChange={setScenarioId}
            options={scenarios.map(s => ({ value: s.scenario_id, label: s.name }))}
          />
          <Button type="primary" onClick={loadTimeline} loading={loading}>
            加载时间线
          </Button>
        </div>

        <div style={{ height: 600, border: '1px solid #e8e8e8' }}>
          {loading ? (
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
              <Spin size="large" />
            </div>
          ) : (
            <TimelineView events={events} />
          )}
        </div>

        <Card title="事件列表" style={{ marginTop: 16 }}>
          <Table
            columns={[
              {
                title: '时间',
                dataIndex: 'timestamp',
                key: 'timestamp',
                render: (timestamp: string) => new Date(timestamp).toLocaleString('zh-CN'),
              },
              {
                title: '类型',
                dataIndex: 'event_type',
                key: 'event_type',
              },
              {
                title: '参与者',
                dataIndex: 'participants',
                key: 'participants',
                render: (participants: string[]) => participants.join(', '),
              },
              {
                title: '描述',
                dataIndex: 'description',
                key: 'description',
                ellipsis: true,
              },
              {
                title: '位置',
                dataIndex: 'location',
                key: 'location',
              },
            ]}
            dataSource={events}
            rowKey="event_id"
            pagination={{ pageSize: 10 }}
          />
        </Card>
      </Card>
    </div>
  );
}