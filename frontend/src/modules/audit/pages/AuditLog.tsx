import { useState, useEffect } from 'react';
import { Card, Select, DatePicker, Row, Col, Tag, Statistic, Button, Space, message, Tabs } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';
import type { AuditEvent } from '@/modules/shared/services/api';
import type { Dayjs } from 'dayjs';
import dayjs from 'dayjs';
import { NLQueryAuditPanel } from '@/modules/qa/components/NLQueryAuditPanel';
import { AdvancedTable } from '@/modules/shared';

const { RangePicker } = DatePicker;

export function AuditLog() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<{
    total: number;
    by_type: Record<string, number>;
    by_severity: Record<string, number>;
    by_status: Record<string, number>;
  } | null>(null);

  const [filters, setFilters] = useState({
    event_type: undefined as string | undefined,
    severity: undefined as string | undefined,
    start_time: undefined as string | undefined,
    end_time: undefined as string | undefined,
  });

  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
  });

  useEffect(() => {
    loadStats();
    loadEvents();
  }, [pagination.current, pagination.pageSize]);

  useEffect(() => {
    loadEvents();
  }, [filters]);

  const loadStats = async () => {
    try {
      const data = await api.getAuditStats();
      setStats(data);
    } catch (error) {
      console.error('加载统计失败', error);
    }
  };

  const loadEvents = async () => {
    try {
      setLoading(true);
      const data = await api.listAuditEvents({
        ...filters,
        limit: pagination.pageSize,
        offset: (pagination.current - 1) * pagination.pageSize,
      });
      setEvents(data.events || []);
      setTotal(data.total);
    } catch (error) {
      console.error('加载审计事件失败', error);
      message.error('加载审计事件失败');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: keyof typeof filters, value: string | undefined) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPagination(prev => ({ ...prev, current: 1 }));
  };

  const handleTimeRangeChange = (dates: [Dayjs | null, Dayjs | null] | null) => {
    if (dates && dates[0] && dates[1]) {
      setFilters(prev => ({
        ...prev,
        start_time: dates[0]?.toISOString(),
        end_time: dates[1]?.toISOString(),
      }));
    } else {
      setFilters(prev => ({
        ...prev,
        start_time: undefined,
        end_time: undefined,
      }));
    }
    setPagination(prev => ({ ...prev, current: 1 }));
  };

  const handleRefresh = () => {
    loadStats();
    loadEvents();
  };

  const getSeverityColor = (severity: string) => {
    const colorMap: Record<string, string> = {
      info: 'blue',
      warn: 'orange',
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

  const columns = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 170,
      render: (timestamp: string) => dayjs(timestamp).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '事件类型',
      dataIndex: 'event_type',
      key: 'event_type',
      width: 130,
      render: (type: string) => <Tag color="blue">{type}</Tag>,
    },
    {
      title: '严重程度',
      dataIndex: 'severity',
      key: 'severity',
      width: 90,
      render: (severity: string) => (
        <Tag color={getSeverityColor(severity)}>{severity.toUpperCase()}</Tag>
      ),
    },
    {
      title: '操作者',
      dataIndex: 'actor_name',
      key: 'actor_name',
      width: 100,
      ellipsis: true,
    },
    {
      title: '动作',
      dataIndex: 'action',
      key: 'action',
      width: 140,
      ellipsis: true,
    },
    {
      title: '资源',
      dataIndex: 'resource_id',
      key: 'resource_id',
      width: 200,
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'result_status',
      key: 'result_status',
      width: 80,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{status}</Tag>
      ),
    },
    {
      title: '追踪ID',
      dataIndex: 'trace_id',
      key: 'trace_id',
      width: 130,
      ellipsis: true,
    },
  ];

  const eventTypeOptions = [
    { value: 'user.login', label: '用户登录' },
    { value: 'user.logout', label: '用户登出' },
    { value: 'workspace.create', label: '创建工作空间' },
    { value: 'workspace.switch', label: '切换工作空间' },
    { value: 'workspace.delete', label: '删除工作空间' },
    { value: 'ontology.create', label: '创建本体' },
    { value: 'data.ingest', label: '数据摄入' },
    { value: 'query.execute', label: '查询执行' },
    { value: 'system.health', label: '系统健康' },
    { value: 'system.error', label: '系统错误' },
    { value: 'skill.execute', label: '技能执行' },
    { value: 'agent.execute', label: 'Agent 执行' },
  ];

  const severityOptions = [
    { value: 'info', label: '信息' },
    { value: 'warn', label: '警告' },
    { value: 'error', label: '错误' },
    { value: 'critical', label: '严重' },
  ];

  return (
    <div>
      <Tabs
        defaultActiveKey="system"
        items={[
          {
            key: 'system',
            label: '系统审计',
            children: (
              <>
                <Row gutter={[16, 16]}>
                  <Col span={6}>
                    <Card>
                      <Statistic title="总事件数" value={stats?.total ?? 0} loading={loading} />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="成功事件"
                        value={stats?.by_status?.success ?? 0}
                        styles={{ content: { color: '#52c41a' } }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="失败事件"
                        value={stats?.by_status?.failure ?? 0}
                        styles={{ content: { color: '#ff4d4f' } }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="警告事件"
                        value={stats?.by_status?.warning ?? 0}
                        styles={{ content: { color: '#faad14' } }}
                      />
                    </Card>
                  </Col>
                </Row>

                <Card title="审计日志" style={{ marginTop: 16 }}>
                  <Space wrap style={{ marginBottom: 16 }}>
                    <Select
                      placeholder="事件类型"
                      allowClear
                      style={{ width: 150 }}
                      value={filters.event_type}
                      onChange={(value) => handleFilterChange('event_type', value)}
                      options={eventTypeOptions}
                    />
                    <Select
                      placeholder="严重程度"
                      allowClear
                      style={{ width: 120 }}
                      value={filters.severity}
                      onChange={(value) => handleFilterChange('severity', value)}
                      options={severityOptions}
                    />
                    <RangePicker
                      showTime
                      onChange={handleTimeRangeChange}
                      placeholder={['开始时间', '结束时间'] as [string, string]}
                    />
                    <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
                      刷新
                    </Button>
                  </Space>

                  <AdvancedTable
                    columns={columns}
                    dataSource={events}
                    rowKey="id"
                    loading={loading}
                    scroll={{ x: 1040 }}
                    pagination={{
                      current: pagination.current,
                      pageSize: pagination.pageSize,
                      total: total,
                      showSizeChanger: true,
                      showQuickJumper: true,
                      showTotal: (tot) => `共 ${tot} 条记录`,
                      onChange: (page, pageSize) => {
                        setPagination({ current: page, pageSize });
                      },
                    }}
                  />
                </Card>

                <Card title="事件统计" style={{ marginTop: 16 }}>
                  <Row gutter={[16, 16]}>
                    <Col span={12}>
                      <Card title="按事件类型" size="small">
                        {stats?.by_type && Object.entries(stats.by_type).length > 0 ? (
                          <Space orientation="vertical" style={{ width: '100%' }}>
                            {Object.entries(stats.by_type).map(([type, count]) => (
                              <div key={type} style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Tag>{type}</Tag>
                                <span>{count}</span>
                              </div>
                            ))}
                          </Space>
                        ) : (
                          <div style={{ textAlign: 'center', color: '#999' }}>暂无数据</div>
                        )}
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card title="按严重程度" size="small">
                        {stats?.by_severity && Object.entries(stats.by_severity).length > 0 ? (
                          <Space orientation="vertical" style={{ width: '100%' }}>
                            {Object.entries(stats.by_severity).map(([severity, count]) => (
                              <div key={severity} style={{ display: 'flex', justifyContent: 'space-between' }}>
                                <Tag color={getSeverityColor(severity)}>{severity.toUpperCase()}</Tag>
                                <span>{count}</span>
                              </div>
                            ))}
                          </Space>
                        ) : (
                          <div style={{ textAlign: 'center', color: '#999' }}>暂无数据</div>
                        )}
                      </Card>
                    </Col>
                  </Row>
                </Card>
              </>
            ),
          },
          {
            key: 'query',
            label: '查询审计',
            children: <NLQueryAuditPanel />,
          },
        ]}
      />
    </div>
  );
}