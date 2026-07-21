import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  Button,
  Space,
  Tag,
  Modal,
  Form,
  Input,
  Select,
  InputNumber,
  message,
  Switch,
  Descriptions,
  Statistic,
  Row,
  Col,
  Timeline,
  Tabs,
  Badge,
  Popconfirm,
  Tooltip,
  Progress,
  Spin,
  Empty,
  Divider,
  Result,
} from 'antd';
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  StopOutlined,
  ReloadOutlined,
  ThunderboltOutlined,
  FieldTimeOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  SettingOutlined,
  ExperimentOutlined,
  DashboardOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import { apiService } from '@/modules/shared/services/api';
import type { ColumnsType } from 'antd/es/table';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Option } = Select;

interface SimulationEvent {
  event_id: string;
  type: string;
  description: string;
  timestamp: string;
  status: string;
  source: string;
}

interface EventTemplate {
  template_id: string;
  name: string;
  description: string;
  event_type: string;
  parameters: Record<string, unknown>;
}

interface SimulationStatus {
  status: string;
  current_time: string;
  speed: number;
  events_generated: number;
  events_adopted: number;
  events_pending: number;
}

const EVENT_TYPES = [
  'operational_movement',
  'diplomatic_signal',
  'economic_sanction',
  'cyber_operation',
  'intelligence_report',
  'supply_chain_disruption',
  'political_statement',
  'strategic_deployment',
];

const Simulator: React.FC = () => {
  const { t } = useI18n();
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [templates, setTemplates] = useState<EventTemplate[]>([]);
  const [simStatus, setSimStatus] = useState<SimulationStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [selectedEventType, setSelectedEventType] = useState<string | null>(null);
  const [simulationLog, setSimulationLog] = useState<Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  const [generateForm] = Form.useForm();
  const [templateForm] = Form.useForm();

  const fetchEvents = useCallback(async () => {
    try {
      const response = await apiService.listSimulationEvents({ limit: 100 });
      setEvents(response.events);
    } catch (error) {
      console.error('获取模拟事件失败', error);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const response = await apiService.getEventTemplates();
      setTemplates(response.templates);
    } catch (error) {
      console.error('获取事件模板失败', error);
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await apiService.getSimulationStatus();
      setSimStatus(response);
    } catch (error) {
      console.error('获取模拟状态失败', error);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
    fetchTemplates();
    fetchStatus();
    const interval = setInterval(fetchStatus, 3000);
    return () => clearInterval(interval);
  }, [fetchEvents, fetchTemplates, fetchStatus]);

  const addLog = (message: string, type: 'info' | 'success' | 'error' = 'info') => {
    const time = new Date().toLocaleTimeString();
    setSimulationLog(prev => [...prev.slice(-50), { time, message, type }]);
    setTimeout(() => {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  };

  const handleTimeControl = async (action: 'start' | 'pause' | 'resume' | 'stop') => {
    try {
      setLoading(true);
      const response = await apiService.controlSimulationTime({ action });
      addLog(t('时间控制: {{action}}', { action }), 'info');
      const actionMsg = action === 'start' ? t('已开始') : action === 'pause' ? t('已暂停') : action === 'resume' ? t('已恢复') : t('已停止');
      message.success(t('模拟{{state}}', { state: actionMsg }));
      fetchStatus();
    } catch (error) {
      message.error(t('操作失败: {{error}}', { error: String(error) }));
      addLog(t('时间控制失败: {{action}}', { action }), 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleSpeedChange = async (speed: number) => {
    try {
      await apiService.controlSimulationTime({ action: 'set_speed', speed });
      message.success(t('模拟速度已设置为 {{speed}}x', { speed }));
      addLog(t('速度调整为 {{speed}}x', { speed }), 'info');
      fetchStatus();
    } catch (error) {
      message.error(t('速度调整失败: {{error}}', { error: String(error) }));
    }
  };

  const handleGenerateEvents = async (values: Record<string, unknown>) => {
    try {
      setLoading(true);
      const response = await apiService.generateEvents({
        template_id: values.template_id as string | undefined,
        count: values.count as number,
        region: values.region as string | undefined,
        event_types: values.event_types as string[] | undefined,
        scenario_id: values.scenario_id as string | undefined,
      });
      addLog(t('成功生成 {{count}} 个事件', { count: response.events_generated }), 'success');
      message.success(t('成功生成 {{count}} 个事件', { count: response.events_generated }));
      setGenerateModalOpen(false);
      generateForm.resetFields();
      fetchEvents();
      fetchStatus();
    } catch (error) {
      addLog(t('事件生成失败: {{error}}', { error: String(error) }), 'error');
      message.error(t('事件生成失败: {{error}}', { error: String(error) }));
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTemplate = async (values: Record<string, unknown>) => {
    try {
      await apiService.createEventTemplate({
        name: values.name as string,
        description: values.description as string,
        event_type: values.event_type as string,
        parameters: (values.parameters || {}) as Record<string, unknown>,
      });
      addLog(t('创建模板: {{name}}', { name: String(values.name) }), 'success');
      message.success(t('模板创建成功'));
      setTemplateModalOpen(false);
      templateForm.resetFields();
      fetchTemplates();
    } catch (error) {
      message.error(t('模板创建失败: {{error}}', { error: String(error) }));
    }
  };

  const handleAdoptEvent = async (eventId: string) => {
    try {
      await apiService.adoptEvent(eventId);
      addLog(t('采纳事件: {{eventId}}', { eventId }), 'success');
      message.success(t('事件已采纳'));
      fetchEvents();
      fetchStatus();
    } catch (error) {
      message.error(t('事件采纳失败: {{error}}', { error: String(error) }));
    }
  };

  const handleAdoptAll = async () => {
    const pendingEvents = events.filter(e => e.status === 'pending').map(e => e.event_id);
    if (pendingEvents.length === 0) {
      message.info(t('没有待采纳的事件'));
      return;
    }
    try {
      const response = await apiService.adoptEventsBulk(pendingEvents);
      addLog(t('批量采纳: {{adopted}} 成功 / {{failed}} 失败', { adopted: response.adopted_count, failed: response.failed_count }), 'success');
      message.success(t('成功采纳 {{count}} 个事件', { count: response.adopted_count }));
      fetchEvents();
      fetchStatus();
    } catch (error) {
      message.error(t('批量采纳失败: {{error}}', { error: String(error) }));
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'adopted': return 'green';
      case 'pending': return 'gold';
      case 'processing': return 'blue';
      case 'rejected': return 'red';
      default: return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'adopted': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
      case 'pending': return <ClockCircleOutlined style={{ color: '#faad14' }} />;
      case 'processing': return <ThunderboltOutlined style={{ color: '#1890ff' }} />;
      case 'rejected': return <StopOutlined style={{ color: '#ff4d4f' }} />;
      default: return null;
    }
  };

  const getEventTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      operational_movement: 'red',
      diplomatic_signal: 'blue',
      economic_sanction: 'orange',
      cyber_operation: 'volcano',
      intelligence_report: 'purple',
      supply_chain_disruption: 'gold',
      political_statement: 'cyan',
      strategic_deployment: 'magenta',
    };
    return colors[type] || 'default';
  };

  const getEventTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      operational_movement: t('业务调动'),
      diplomatic_signal: t('外交信号'),
      economic_sanction: t('经济制裁'),
      cyber_operation: t('网络行动'),
      intelligence_report: t('情报报告'),
      supply_chain_disruption: t('供应链中断'),
      political_statement: t('政治声明'),
      strategic_deployment: t('战略部署'),
    };
    return labels[type] || type;
  };

  const eventColumns: ColumnsType<SimulationEvent> = [
    {
      title: t('状态'),
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tooltip title={status}>
          {getStatusIcon(status)}
        </Tooltip>
      ),
    },
    {
      title: t('事件ID'),
      dataIndex: 'event_id',
      key: 'event_id',
      width: 120,
      ellipsis: true,
    },
    {
      title: t('类型'),
      dataIndex: 'type',
      key: 'type',
      width: 110,
      render: (type: string) => (
        <Tag color={getEventTypeColor(type)}>{getEventTypeLabel(type)}</Tag>
      ),
    },
    {
      title: t('描述'),
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: t('时间'),
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 170,
      sorter: (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
    },
    {
      title: t('来源'),
      dataIndex: 'source',
      key: 'source',
      width: 80,
    },
    {
      title: t('操作'),
      key: 'actions',
      width: 100,
      render: (_, record) => (
        <Space>
          {record.status === 'pending' && (
            <Button
              type="primary"
              size="small"
              icon={<CheckCircleOutlined />}
              onClick={() => handleAdoptEvent(record.event_id)}
            >
              {t('采纳')}
            </Button>
          )}
          {record.status === 'adopted' && (
            <Tag color="green">{t('已采纳')}</Tag>
          )}
        </Space>
      ),
    },
  ];

  const templateColumns: ColumnsType<EventTemplate> = [
    {
      title: t('模板名称'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('事件类型'),
      dataIndex: 'event_type',
      key: 'event_type',
      render: (type: string) => (
        <Tag color={getEventTypeColor(type)}>{getEventTypeLabel(type)}</Tag>
      ),
    },
    {
      title: t('描述'),
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ];

  const pendingCount = events.filter(e => e.status === 'pending').length;
  const adoptedCount = events.filter(e => e.status === 'adopted').length;

  return (
    <div style={{ padding: '0 0 24px 0' }}>
      {/* 模拟控制面板 */}
      <Card
        title={
          <Space>
            <ExperimentOutlined />
            <span>{t('模拟推演引擎')}</span>
          </Space>
        }
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Tooltip title={t('刷新')}>
              <Button icon={<ReloadOutlined />} onClick={() => { fetchEvents(); fetchStatus(); }} />
            </Tooltip>
          </Space>
        }
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title={t('模拟状态')}
                value={simStatus?.status || 'unknown'}
                styles={{
                  content: {
                    color: simStatus?.status === 'running' ? '#52c41a' : '#faad14',
                  },
                }}
                prefix={
                  simStatus?.status === 'running'
                    ? <Badge status="processing" />
                    : <Badge status="default" />
                }
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title={t('模拟速度')}
                value={simStatus?.speed || 1}
                suffix="x"
                prefix={<FieldTimeOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title={t('生成事件')}
                value={simStatus?.events_generated || 0}
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
          <Col xs={24} sm={12} md={6}>
            <Card size="small">
              <Statistic
                title={t('待采纳')}
                value={simStatus?.events_pending || pendingCount}
                prefix={<ClockCircleOutlined />}
                styles={{ content: { color: pendingCount > 0 ? '#faad14' : undefined } }}
              />
            </Card>
          </Col>
        </Row>

        <Divider style={{ margin: '16px 0' }} />

        <Row justify="space-between" align="middle">
          <Col>
            <Space size="middle">
              <Button
                type="primary"
                icon={<PlayCircleOutlined />}
                onClick={() => handleTimeControl('start')}
                disabled={simStatus?.status === 'running'}
                loading={loading}
              >
                {t('开始')}
              </Button>
              <Button
                icon={<PauseCircleOutlined />}
                onClick={() => handleTimeControl('pause')}
                disabled={simStatus?.status !== 'running'}
              >
                {t('暂停')}
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => handleTimeControl('resume')}
                disabled={simStatus?.status !== 'paused'}
              >
                {t('恢复')}
              </Button>
              <Button
                danger
                icon={<StopOutlined />}
                onClick={() => handleTimeControl('stop')}
              >
                {t('停止')}
              </Button>
            </Space>
          </Col>
          <Col>
            <Space>
              <span style={{ color: '#666' }}>{t('速度:')}</span>
              <Select
                value={simStatus?.speed || 1}
                onChange={handleSpeedChange}
                style={{ width: 80 }}
                size="small"
              >
                <Option value={1}>1x</Option>
                <Option value={2}>2x</Option>
                <Option value={5}>5x</Option>
                <Option value={10}>10x</Option>
                <Option value={20}>20x</Option>
              </Select>
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                onClick={() => setGenerateModalOpen(true)}
              >
                {t('生成事件')}
              </Button>
              <Button
                icon={<CheckCircleOutlined />}
                onClick={handleAdoptAll}
                disabled={pendingCount === 0}
              >
                {t('全部采纳')}
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 主要内容区域 */}
      <Row gutter={16}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space>
                <DashboardOutlined />
                <span>{t('模拟事件列表')}</span>
                <Badge count={events.length} style={{ backgroundColor: '#1890ff' }} />
              </Space>
            }
            style={{ marginBottom: 16 }}
          >
            <Tabs
              defaultActiveKey="all"
              items={[
                {
                  key: 'all',
                  label: t('全部 ({{count}})', { count: events.length }),
                  children: (
                    <AdvancedTable
                      columns={eventColumns}
                      dataSource={events}
                      rowKey="event_id"
                      size="small"
                      pagination={{ pageSize: 15, showSizeChanger: true, showTotal: (total) => t('共 {{count}} 个事件', { count: total }) }}
                      loading={loading}
                      locale={{ emptyText: <Empty description={t('暂无模拟事件，请先生成事件')} /> }}
                    />
                  ),
                },
                {
                  key: 'pending',
                  label: t('待采纳 ({{count}})', { count: pendingCount }),
                  children: (
                    <AdvancedTable
                      columns={eventColumns}
                      dataSource={events.filter(e => e.status === 'pending')}
                      rowKey="event_id"
                      size="small"
                      pagination={{ pageSize: 15 }}
                      loading={loading}
                    />
                  ),
                },
                {
                  key: 'adopted',
                  label: t('已采纳 ({{count}})', { count: adoptedCount }),
                  children: (
                    <AdvancedTable
                      columns={eventColumns}
                      dataSource={events.filter(e => e.status === 'adopted')}
                      rowKey="event_id"
                      size="small"
                      pagination={{ pageSize: 15 }}
                      loading={loading}
                    />
                  ),
                },
              ]}
            />
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card
            title={
              <Space>
                <SettingOutlined />
                <span>{t('事件模板')}</span>
              </Space>
            }
            extra={
              <Button
                type="link"
                icon={<PlusOutlined />}
                onClick={() => setTemplateModalOpen(true)}
                size="small"
              >
                {t('新建')}
              </Button>
            }
            style={{ marginBottom: 16 }}
          >
            {templates.length === 0 ? (
              <Empty description={t('暂无模板')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
            ) : (
              <AdvancedTable
                columns={templateColumns}
                dataSource={templates}
                rowKey="template_id"
                size="small"
                pagination={false}
                scroll={{ y: 200 }}
              />
            )}
          </Card>

          <Card
            title={
              <Space>
                <RocketOutlined />
                <span>{t('模拟日志')}</span>
              </Space>
            }
            styles={{ body: { padding: '8px', maxHeight: 320, overflow: 'auto' } }}
          >
            {simulationLog.length === 0 ? (
              <div style={{ color: '#999', textAlign: 'center', padding: '24px 0' }}>
                {t('暂无日志，开始模拟后查看')}
              </div>
            ) : (
              <Timeline
                style={{ marginTop: 8 }}
                items={simulationLog.map(log => ({
                  color: log.type === 'success' ? 'green' : log.type === 'error' ? 'red' : 'blue',
                  children: (
                    <div>
                      <div style={{ fontSize: 12, color: '#999' }}>{log.time}</div>
                      <div>{log.message}</div>
                    </div>
                  ),
                }))}
              />
            )}
            <div ref={logEndRef} />
          </Card>
        </Col>
      </Row>

      {/* 生成事件模态框 */}
      <Modal
        title={
          <Space>
            <ThunderboltOutlined />
            <span>{t('生成模拟事件')}</span>
          </Space>
        }
        open={generateModalOpen}
        onCancel={() => setGenerateModalOpen(false)}
        onOk={() => generateForm.submit()}
        confirmLoading={loading}
        okText={t('生成')}
        cancelText={t('取消')}
      >
        <Form
          form={generateForm}
          layout="vertical"
          onFinish={handleGenerateEvents}
          initialValues={{ count: 5 }}
        >
          <Form.Item name="template_id" label={t('事件模板')}>
            <Select allowClear placeholder={t('选择模板（可选）')}>
              {templates.map(t => (
                <Option key={t.template_id} value={t.template_id}>
                  {t.name} - {getEventTypeLabel(t.event_type)}
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="count" label={t('生成数量')}>
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="event_types" label={t('事件类型筛选')}>
            <Select mode="multiple" allowClear placeholder={t('选择类型（可选）')}>
              {EVENT_TYPES.map(et => (
                <Option key={et} value={et}>
                  <Tag color={getEventTypeColor(et)}>{getEventTypeLabel(et)}</Tag>
                </Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item name="region" label={t('区域')}>
            <Input placeholder={t('例如: 中东、亚太')} />
          </Form.Item>
          <Form.Item name="scenario_id" label={t('目标场景ID')}>
            <Input placeholder={t('关联场景ID（可选）')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 创建模板模态框 */}
      <Modal
        title={
          <Space>
            <PlusOutlined />
            <span>{t('创建事件模板')}</span>
          </Space>
        }
        open={templateModalOpen}
        onCancel={() => setTemplateModalOpen(false)}
        onOk={() => templateForm.submit()}
        okText={t('创建')}
        cancelText={t('取消')}
      >
        <Form
          form={templateForm}
          layout="vertical"
          onFinish={handleCreateTemplate}
        >
          <Form.Item
            name="name"
            label={t('模板名称')}
            rules={[{ required: true, message: t('请输入模板名称') }]}
          >
            <Input placeholder={t('例如: 标准业务冲突模板')} />
          </Form.Item>
          <Form.Item
            name="event_type"
            label={t('事件类型')}
            rules={[{ required: true, message: t('请选择事件类型') }]}
          >
            <Select placeholder={t('选择事件类型')}>
              {EVENT_TYPES.map(et => (
                <Option key={et} value={et}>{getEventTypeLabel(et)}</Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="description"
            label={t('模板描述')}
            rules={[{ required: true, message: t('请输入描述') }]}
          >
            <Input.TextArea rows={3} placeholder={t('描述该模板的用途')} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Simulator;