import { useState, useEffect } from 'react';
import { Timeline, Tag, Card, Space, Select, Button, Input, message } from 'antd';
import { ReloadOutlined, FilterOutlined, SearchOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import type { AuditEvent } from '../../shared/services/api';

export function AuditTimeline() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [filters, setFilters] = useState({
    eventType: 'all',
    severity: 'all',
  });

  useEffect(() => {
    loadEvents();
  }, [filters]);

  const loadEvents = async () => {
    try {
      const data = await api.listAuditEvents({
        event_type: filters.eventType === 'all' ? undefined : filters.eventType,
        severity: filters.severity === 'all' ? undefined : filters.severity,
        limit: 50,
      });
      setEvents(data.events || []);
    } catch (error) {
      console.error('加载审计事件失败', error);
      message.error('加载审计事件失败');
    }
  };

  const getSeverityColor = (severity: string) => {
    const colorMap: Record<string, string> = {
      info: 'blue',
      warning: 'orange',
      error: 'red',
      critical: 'purple',
    };
    return colorMap[severity] || 'default';
  };

  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      success: 'green',
      failure: 'red',
      warning: 'orange',
    };
    return colorMap[status] || 'default';
  };

  const eventTypeOptions = [
    { value: 'all', label: '全部类型' },
    { value: 'system.startup', label: '系统启动' },
    { value: 'system.shutdown', label: '系统关闭' },
    { value: 'system.action', label: '系统操作' },
    { value: 'user.login', label: '用户登录' },
    { value: 'user.logout', label: '用户登出' },
    { value: 'workspace.create', label: '创建工作空间' },
    { value: 'workspace.update', label: '更新工作空间' },
    { value: 'workspace.delete', label: '删除工作空间' },
  ];

  const severityOptions = [
    { value: 'all', label: '全部级别' },
    { value: 'info', label: '信息' },
    { value: 'warning', label: '警告' },
    { value: 'error', label: '错误' },
    { value: 'critical', label: '严重' },
  ];

  return (
    <Card title="审计时间线" style={{ margin: 16 }}>
      <div style={{ display: 'flex', marginBottom: 16, gap: 12 }}>
        <Select
          value={filters.eventType}
          onChange={(value) => setFilters({ ...filters, eventType: value })}
          style={{ width: 150 }}
          options={eventTypeOptions}
        />
        <Select
          value={filters.severity}
          onChange={(value) => setFilters({ ...filters, severity: value })}
          style={{ width: 120 }}
          options={severityOptions}
        />
        <Input.Search
          placeholder="搜索事件"
          style={{ width: 200 }}
          prefix={<SearchOutlined />}
          onSearch={(value) => console.log('搜索', value)}
        />
        <Button
          icon={<FilterOutlined />}
          onClick={() => console.log('高级筛选')}
        >
          筛选
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={loadEvents}
        >
          刷新
        </Button>
      </div>

      <Timeline>
        {events.map((event: AuditEvent) => (
          <Timeline.Item
            key={event.id}
            color={getStatusColor(event.result_status)}
            dot={<Tag color={getSeverityColor(event.severity)}>{event.severity}</Tag>}
          >
            <Space direction="vertical">
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <Tag color="blue">{event.event_type}</Tag>
                <Tag color={getStatusColor(event.result_status)}>{event.result_status}</Tag>
                <span style={{ fontSize: '12px', color: '#999' }}>
                  {new Date(event.timestamp).toLocaleString('zh-CN')}
                </span>
              </div>
              <div style={{ fontSize: '14px' }}>
                <strong>{event.actor_name}</strong> {event.action}
                {event.resource_type && (
                  <span> {event.resource_type} <strong>{event.resource_id}</strong></span>
                )}
              </div>
              {event.result_message && (
                <div style={{ fontSize: '12px', color: '#666' }}>
                  {event.result_message}
                </div>
              )}
            </Space>
          </Timeline.Item>
        ))}
      </Timeline>
    </Card>
  );
}