import { useState, useEffect } from 'react';
import { Card, Tag, Space, Input, Select, Button, Row, Col, Statistic, Drawer, Descriptions, Typography } from 'antd';
import { SearchOutlined, SafetyCertificateOutlined, CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, InfoCircleOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';
import type { AuditEvent } from '@/modules/shared/services/api';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

export function AuditTimeline() {
  const { t } = useI18n();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [stats, setStats] = useState<{
    total: number;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
  } | null>(null);
  const [filters, setFilters] = useState({
    severity: undefined as string | undefined,
    event_type: undefined as string | undefined,
    keyword: ''
  });

  useEffect(() => {
    loadEvents();
    loadStats();
  }, [filters.severity, filters.event_type]);

  const loadEvents = async () => {
    setLoading(true);
    try {
      const data = await api.getAuditTimeline();
      let eventList: AuditEvent[] = [];
      if (Array.isArray(data)) {
        eventList = data as unknown as AuditEvent[];
      } else if (data && 'events' in data) {
        eventList = (data as { events: AuditEvent[]; total: number }).events || [];
      }
      setEvents(eventList);
    } catch (error) {
      console.error('加载审计事件失败', error);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    try {
      const data = await api.getAuditStats();
      setStats(data);
    } catch (error) {
      console.error('加载统计失败', error);
    }
  };

  const handleViewDetail = (event: AuditEvent) => {
    setSelectedEvent(event);
    setDrawerVisible(true);
  };

  const handleVerifyIntegrity = async () => {
    try {
      setStats(prev => prev ? { ...prev } : prev);
    } catch (error) {
      console.error('验证失败', error);
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      case 'error':
        return <WarningOutlined style={{ color: '#faad14' }} />;
      case 'warn':
      case 'warning':
        return <WarningOutlined style={{ color: '#fa8c16' }} />;
      case 'info':
        return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
      default:
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'red';
      case 'error': return 'orange';
      case 'warn':
      case 'warning': return 'gold';
      case 'info': return 'blue';
      default: return 'green';
    }
  };

  const columns = [
    {
      title: t('时间'),
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (timestamp: string) => timestamp ? new Date(timestamp).toLocaleString('zh-CN') : '-'
    },
    {
      title: t('严重级别'),
      dataIndex: 'severity',
      key: 'severity',
      width: 100,
      render: (severity: string) => (
        <Tag color={getSeverityColor(severity)} icon={getSeverityIcon(severity)}>
          {severity ? severity.toUpperCase() : '-'}
        </Tag>
      )
    },
    {
      title: t('事件类型'),
      dataIndex: 'event_type',
      key: 'event_type',
      width: 150,
      render: (type: string) => <Tag>{type ? type.replace(/_/g, ' ') : '-'}</Tag>
    },
    {
      title: t('操作'),
      dataIndex: 'action',
      key: 'action',
      width: 120
    },
    {
      title: t('用户'),
      dataIndex: 'actor_id',
      key: 'actor_id',
      width: 120
    },
    {
      title: t('资源'),
      dataIndex: 'resource_id',
      key: 'resource_id',
      width: 150,
      render: (id: string, record: AuditEvent) => (
        <Space>
          <Tag>{record.resource_type || '-'}</Tag>
          <Typography.Text code style={{ fontSize: 12 }}>{id || '-'}</Typography.Text>
        </Space>
      )
    },
    {
      title: t('结果'),
      dataIndex: 'result_status',
      key: 'result_status',
      width: 100,
      render: (status: string) => (
        <Tag color={status === 'success' ? 'green' : status === 'denied' ? 'red' : 'default'}>
          {status || '-'}
        </Tag>
      )
    },
    {
      title: t('消息'),
      dataIndex: 'result_message',
      key: 'result_message',
      ellipsis: true
    },
    {
      title: t('操作'),
      key: 'action_col',
      width: 100,
      render: (_: unknown, record: AuditEvent) => (
        <Button type="link" onClick={() => handleViewDetail(record)}>
          {t('详情')}
        </Button>
      )
    }
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic title={t('总事件数')} value={stats?.total ?? 0} prefix={<SafetyCertificateOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('成功事件')}
              value={stats?.by_status?.success ?? 0}
              styles={{ content: { color: '#52c41a' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('失败事件')}
              value={stats?.by_status?.failure ?? 0}
              styles={{ content: { color: '#ff4d4f' } }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Statistic
                title={t('严重事件')}
                value={stats?.by_severity?.critical ?? 0}
                styles={{ content: { color: '#ff4d4f' } }}
              />
              <Button size="small" onClick={handleVerifyIntegrity}>{t('验证')}</Button>
            </div>
          </Card>
        </Col>
      </Row>

      <Card
        title={t('审计日志时间线')}
        extra={
          <Space>
            <Input
              placeholder={t('搜索关键字')}
              prefix={<SearchOutlined />}
              style={{ width: 200 }}
              onChange={(e) => setFilters(prev => ({ ...prev, keyword: e.target.value }))}
            />
            <Select
              placeholder={t('严重级别')}
              allowClear
              style={{ width: 120 }}
              onChange={(value) => setFilters(prev => ({ ...prev, severity: value }))}
              options={[
                { value: 'info', label: 'INFO' },
                { value: 'warn', label: 'WARNING' },
                { value: 'error', label: 'ERROR' },
                { value: 'critical', label: 'CRITICAL' }
              ]}
            />
            <Select
              placeholder={t('事件类型')}
              allowClear
              style={{ width: 150 }}
              onChange={(value) => setFilters(prev => ({ ...prev, event_type: value }))}
              options={[
                { value: 'user.login', label: t('用户登录') },
                { value: 'user.logout', label: t('用户登出') },
                { value: 'query.execute', label: t('查询执行') },
                { value: 'data.ingest', label: t('数据摄入') },
                { value: 'workspace.create', label: t('创建工作空间') },
                { value: 'workspace.delete', label: t('删除工作空间') },
                { value: 'ontology.create', label: t('创建本体') },
                { value: 'system.health', label: t('系统健康') },
                { value: 'system.error', label: t('系统错误') },
                { value: 'skill.execute', label: t('技能执行') },
                { value: 'agent.execute', label: t('Agent 执行') }
              ]}
            />
          </Space>
        }
      >
        <AdvancedTable
          columns={columns}
          dataSource={events}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => t('共 {{count}} 条', { count: total })}}
          expandable={{
            expandedRowRender: (record) => (
              <Descriptions column={2}>
                <Descriptions.Item label={t('追踪ID')}>{record.trace_id || '-'}</Descriptions.Item>
                <Descriptions.Item label={t('耗时')}>{record.duration_ms != null ? `${record.duration_ms}ms` : '-'}</Descriptions.Item>
                <Descriptions.Item label={t('完整消息')} span={2}>{record.result_message || '-'}</Descriptions.Item>
              </Descriptions>
            )
          }}
        />
      </Card>

      <Drawer
        title={t('审计事件详情')}
        placement="right"
        size="large"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {selectedEvent && (
          <Descriptions column={1}>
            <Descriptions.Item label={t('事件ID')}>{selectedEvent.id}</Descriptions.Item>
            <Descriptions.Item label={t('时间')}>{selectedEvent.timestamp ? new Date(selectedEvent.timestamp).toLocaleString('zh-CN') : '-'}</Descriptions.Item>
            <Descriptions.Item label={t('严重级别')}>
              <Tag color={getSeverityColor(selectedEvent.severity)}>
                {selectedEvent.severity ? selectedEvent.severity.toUpperCase() : '-'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('事件类型')}>{selectedEvent.event_type || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('操作')}>{selectedEvent.action || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('用户ID')}>{selectedEvent.actor_id || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('用户名称')}>{selectedEvent.actor_name || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('资源类型')}>{selectedEvent.resource_type || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('资源ID')}>{selectedEvent.resource_id || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('结果')}>
              <Tag color={selectedEvent.result_status === 'success' ? 'green' : 'red'}>
                {selectedEvent.result_status || '-'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label={t('耗时')}>{selectedEvent.duration_ms != null ? `${selectedEvent.duration_ms}ms` : '-'}</Descriptions.Item>
            <Descriptions.Item label={t('追踪ID')}>{selectedEvent.trace_id || '-'}</Descriptions.Item>
            <Descriptions.Item label={t('消息')} span={2}>{selectedEvent.result_message || '-'}</Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
