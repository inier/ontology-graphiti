import React, { useState, useEffect, useCallback } from 'react';

import {

  Card, Button, Modal, Form, Input, Select, Tag,

  Descriptions, Statistic, Progress, Tabs, Space, message, Popconfirm,

  Empty, Tooltip, Row, Col, Badge, Divider, Alert, Spin, Slider, InputNumber,

} from 'antd';

import {

  PlusOutlined, PlayCircleOutlined, DeleteOutlined,

  ExperimentOutlined, ClockCircleOutlined, ThunderboltOutlined,

  ExportOutlined, ReloadOutlined, PauseCircleOutlined,

  ForwardOutlined,

} from '@ant-design/icons';

import type { ColumnsType } from 'antd/es/table';

import type { SandboxInfo, TimelineInfo, TemplateInfo } from '../services/simulationApi';

import { useSimulationStore } from '../stores/simulationStore';

import { EmptyState } from '@/modules/shared/components/organisms';

import { useWorkspace } from '@/modules/shared/components/LayoutContexts';
import { AdvancedTable } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';



const SANDBOX_STATUS_COLORS: Record<string, string> = {

  created: 'default',

  running: 'processing',

  completed: 'green',

  failed: 'red',

  timeout: 'orange',

  destroyed: 'default',

};



const CLOCK_STATE_COLORS: Record<string, string> = {

  stopped: 'default',

  running: 'green',

  paused: 'orange',

};



const SimulationPage: React.FC = () => {

  const { t } = useI18n();

  const store = useSimulationStore();

  const { currentWorkspace } = useWorkspace();

  const [sandboxModalOpen, setSandboxModalOpen] = useState(false);

  const [runModalOpen, setRunModalOpen] = useState(false);

  const [parallelModalOpen, setParallelModalOpen] = useState(false);

  const [whatIfModalOpen, setWhatIfModalOpen] = useState(false);

  const [timelineModalOpen, setTimelineModalOpen] = useState(false);

  const [templateModalOpen, setTemplateModalOpen] = useState(false);

  const [injectModalOpen, setInjectModalOpen] = useState(false);

  const [sandboxForm] = Form.useForm();

  const [runForm] = Form.useForm();

  const [parallelForm] = Form.useForm();

  const [whatIfForm] = Form.useForm();

  const [timelineForm] = Form.useForm();

  const [templateForm] = Form.useForm();

  const [injectForm] = Form.useForm();



  useEffect(() => {

    store.fetchSandboxes();

    store.fetchTemplates();

    store.fetchTimelines();

  }, []);



  const handleCreateSandbox = async (values: Record<string, unknown>) => {

    const sandboxId = await store.createSandbox(values);

    if (sandboxId) {

      message.success(t('沙箱 {{id}} 创建成功', { id: sandboxId }));

      setSandboxModalOpen(false);

      sandboxForm.resetFields();

    }

  };



  const handleRunSimulation = async (values: Record<string, unknown>) => {

    await store.runSimulation(values);

    if (store.simulationResult) {

      message.success(t('推演完成'));

      setRunModalOpen(false);

      runForm.resetFields();

    }

  };



  const handleDestroySandbox = async (sandboxId: string) => {

    try {

      await store.destroySandbox(sandboxId);

      message.success(t('沙箱已销毁'));

    } catch (error) {

      message.error(t('销毁失败: {{error}}', { error: String(error) }));

    }

  };



  const handleExport = async (sandboxId: string) => {

    try {

      await store.exportResults(sandboxId, 'admin');

      message.success(t('结果已导出'));

    } catch (error) {

      message.error(t('导出失败: {{error}}', { error: String(error) }));

    }

  };



  const handleRunParallel = async (values: Record<string, unknown>) => {

    try {

      const scenariosStr = values.scenarios as string;

      const scenarios = JSON.parse(scenariosStr);

      await store.runParallel(scenarios);

      if (store.parallelResult) {

        message.success(t('并行推演完成'));

        setParallelModalOpen(false);

        parallelForm.resetFields();

      }

    } catch {

      message.error(t('方案 JSON 格式错误'));

    }

  };



  const handleRunWhatIf = async (values: Record<string, unknown>) => {

    try {

      const baseStr = values.base_scenario as string;

      const varsStr = values.param_variations as string;

      const baseScenario = JSON.parse(baseStr);

      const paramVariations = JSON.parse(varsStr);

      await store.runWhatIf(baseScenario, paramVariations);

      if (store.whatIfResult) {

        message.success(t('What-if 分析完成'));

        setWhatIfModalOpen(false);

        whatIfForm.resetFields();

      }

    } catch {

      message.error(t('参数 JSON 格式错误'));

    }

  };



  const handleCreateTimeline = async (values: Record<string, unknown>) => {

    const timelineId = await store.createTimeline(values);

    if (timelineId) {

      message.success(t('时间线 {{id}} 创建成功', { id: timelineId }));

      setTimelineModalOpen(false);

      timelineForm.resetFields();

    }

  };



  const handleClockControl = async (timelineId: string, action: string, speed?: number) => {

    try {

      const params: Record<string, unknown> = { timeline_id: timelineId, action };

      if (speed !== undefined) params.speed = speed;

      await store.controlClock(params);

      const actionLabel = action === 'start' ? t('启动') : action === 'pause' ? t('暂停') : action === 'resume' ? t('恢复') : t('调整');

      message.success(t('时钟{{action}}成功', { action: actionLabel }));

    } catch (error) {

      message.error(t('时钟控制失败: {{error}}', { error: String(error) }));

    }

  };



  const handleCreateTemplate = async (values: Record<string, unknown>) => {

    try {

      await store.createTemplate(values);

      message.success(t('模板创建成功'));

      setTemplateModalOpen(false);

      templateForm.resetFields();

    } catch (error) {

      message.error(t('创建模板失败: {{error}}', { error: String(error) }));

    }

  };



  const handleGenerateEvents = async (templateId: string) => {

    await store.generateEventSequence({ template_id: templateId, count: 5 });

    if (store.eventSequence) {

      message.success(t('生成 {{n}} 个事件', { n: store.eventSequence.total_events }));

    }

  };



  const handleInjectEvent = async (values: Record<string, unknown>) => {

    try {

      await store.injectEvent(values);

      message.success(t('事件已注入'));

      setInjectModalOpen(false);

      injectForm.resetFields();

    } catch (error) {

      message.error(t('注入事件失败: {{error}}', { error: String(error) }));

    }

  };



  const sandboxColumns: ColumnsType<SandboxInfo> = [

    {

      title: t('沙箱 ID'),

      dataIndex: 'sandbox_id',

      key: 'sandbox_id',

      ellipsis: true,

      render: (id) => (

        <Button type="link" size="small" onClick={() => store.selectSandbox(id as string)}>

          {id as string}

        </Button>

      ),

    },

    {

      title: t('状态'),

      dataIndex: 'status',

      key: 'status',

      width: 90,

      render: (status) => (

        <Tag color={SANDBOX_STATUS_COLORS[status as string] || 'default'}>{status as string}</Tag>

      ),

    },

    {

      title: t('创建时间'),

      dataIndex: 'created_at',

      key: 'created_at',

      width: 160,

      ellipsis: true,

    },

    {

      title: t('操作'),

      key: 'action',

      width: 180,

      render: (_, record) => (

        <Space size="small">

          <Tooltip title={t('运行推演')}>

            <Button

              type="primary"

              size="small"

              icon={<PlayCircleOutlined />}

              onClick={() => {

                store.selectSandbox(record.sandbox_id);

                setRunModalOpen(true);

              }}

              disabled={record.status === 'running' || record.status === 'destroyed'}

            />

          </Tooltip>

          <Tooltip title={t('导出结果')}>

            <Button

              size="small"

              icon={<ExportOutlined />}

              onClick={() => handleExport(record.sandbox_id)}

              disabled={record.status !== 'completed'}

            />

          </Tooltip>

          <Popconfirm

            title={t('确认销毁此沙箱？')}

            onConfirm={() => handleDestroySandbox(record.sandbox_id)}

          >

            <Button type="text" danger size="small" icon={<DeleteOutlined />} />

          </Popconfirm>

        </Space>

      ),

    },

  ];



  const timelineColumns: ColumnsType<TimelineInfo> = [

    {

      title: t('时间线 ID'),

      dataIndex: 'timeline_id',

      key: 'timeline_id',

      ellipsis: true,

    },

    {

      title: t('时钟状态'),

      dataIndex: 'clock_state',

      key: 'clock_state',

      width: 90,

      render: (state) => (

        <Tag color={CLOCK_STATE_COLORS[state as string] || 'default'}>{state as string}</Tag>

      ),

    },

    {

      title: t('速度'),

      dataIndex: 'simulation_speed',

      key: 'simulation_speed',

      width: 70,

      render: (speed) => `${speed}x`,

    },

    {

      title: t('当前时间'),

      dataIndex: 'current_time',

      key: 'current_time',

      width: 160,

      ellipsis: true,

    },

    {

      title: t('操作'),

      key: 'action',

      width: 200,

      render: (_, record) => (

        <Space size="small">

          <Button

            size="small"

            icon={<PlayCircleOutlined />}

            onClick={() => handleClockControl(record.timeline_id, 'start', 1.0)}

            disabled={record.clock_state === 'running'}

          />

          <Button

            size="small"

            icon={<PauseCircleOutlined />}

            onClick={() => handleClockControl(record.timeline_id, 'pause')}

            disabled={record.clock_state !== 'running'}

          />

          <Button

            size="small"

            icon={<ForwardOutlined />}

            onClick={() => handleClockControl(record.timeline_id, 'advance')}

          />

          <Button

            size="small"

            icon={<ReloadOutlined />}

            onClick={() => handleClockControl(record.timeline_id, 'set_speed', 2.0)}

          />

        </Space>

      ),

    },

  ];



  const templateColumns: ColumnsType<TemplateInfo> = [

    {

      title: t('模板名称'),

      dataIndex: 'name',

      key: 'name',

      ellipsis: true,

    },

    {

      title: t('分类'),

      dataIndex: 'category',

      key: 'category',

      width: 100,

      render: (cat) => <Tag>{cat as string}</Tag>,

    },

    {

      title: t('事件类型'),

      dataIndex: 'event_types',

      key: 'event_types',

      width: 200,

      render: (types) => (

        <Space size={2} wrap>

          {(types as string[]).slice(0, 3).map(tp => <Tag key={tp}>{tp}</Tag>)}

          {(types as string[]).length > 3 && <Tag>+{(types as string[]).length - 3}</Tag>}

        </Space>

      ),

    },

    {

      title: t('操作'),

      key: 'action',

      width: 120,

      render: (_, record) => (

        <Space size="small">

          <Button

            type="primary"

            size="small"

            icon={<ThunderboltOutlined />}

            onClick={() => handleGenerateEvents(record.template_id)}

          >

            {t('生成')}

          </Button>

          <Popconfirm

            title={t('确认删除此模板？')}

            onConfirm={() => store.deleteTemplate(record.template_id)}

          >

            <Button type="text" danger size="small" icon={<DeleteOutlined />} />

          </Popconfirm>

        </Space>

      ),

    },

  ];



  const renderSandboxPanel = () => (

    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>

      <Card

        title={t('沙箱管理')}

        size="small"

        extra={

          <Space size="small">

            <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setSandboxModalOpen(true)}>

              {t('创建沙箱')}

            </Button>

          </Space>

        }

      >

        <AdvancedTable

          dataSource={store.sandboxes}

          columns={sandboxColumns}

          rowKey="sandbox_id"

          size="small"

          pagination={false}

          onReload={() => store.fetchSandboxes()}

          locale={{ emptyText: (

            <EmptyState

              icon={<ExperimentOutlined />}

              title={t('暂无沙箱')}

              description={t('创建沙箱以进行推演仿真，或加载示例数据快速体验')}

              actionLabel={t('创建沙箱')}

              onAction={() => setSandboxModalOpen(true)}

              showSampleData

              onLoadSampleData={async () => {

                if (!currentWorkspace) { message.warning(t('请先选择工作空间')); return; }

                try {

                  const { api } = await import('@/modules/shared/services/api');

                  await api.generateSampleData(currentWorkspace);

                  message.success(t('示例数据已加载'));

                  store.fetchSandboxes();

                } catch (e) { message.error(t('加载示例数据失败')); }

              }}

            />

          ) }}

        />

      </Card>



      {store.sandboxStatus && (

        <Card title={t('沙箱状态')} size="small">

          <Descriptions column={2}>

            <Descriptions.Item label={t('沙箱 ID')}>{store.sandboxStatus.sandbox_id}</Descriptions.Item>

            <Descriptions.Item label={t('状态')}>

              <Tag color={SANDBOX_STATUS_COLORS[store.sandboxStatus.status] || 'default'}>

                {store.sandboxStatus.status}

              </Tag>

            </Descriptions.Item>

            <Descriptions.Item label={t('隔离级别')}>{store.sandboxStatus.isolation_level}</Descriptions.Item>

            <Descriptions.Item label={t('创建时间')}>{store.sandboxStatus.created_at}</Descriptions.Item>

          </Descriptions>

        </Card>

      )}



      {store.simulationResult && (

        <Card title={t('推演结果')} size="small">

          {store.simulationResult.status === 'timeout' ? (

            <Alert type="warning" showIcon title={t('推演超时')} description={store.simulationResult.message} />

          ) : (

            <Space orientation="vertical" style={{ width: '100%' }}>

              {store.simulationResult.risk_assessment && (

                <Row gutter={16}>

                  <Col span={8}>

                    <Statistic

                      title={t('风险等级')}

                      value={(store.simulationResult.risk_assessment as Record<string, unknown>).overall_risk as string || 'unknown'}

                      styles={{

                        content: {

                          color: (store.simulationResult.risk_assessment as Record<string, unknown>).overall_risk === 'high' ? '#ff4d4f'

                            : (store.simulationResult.risk_assessment as Record<string, unknown>).overall_risk === 'medium' ? '#faad14' : '#52c41a',

                        },

                      }}

                    />

                  </Col>

                  <Col span={8}>

                    <Statistic title={t('置信度')} value={(store.simulationResult.confidence || 0) as number * 100} precision={1} suffix="%" />

                  </Col>

                </Row>

              )}

              {store.simulationResult.recommendation && (

                <Alert type="info" title={t('推荐')} description={store.simulationResult.recommendation} />

              )}

              {store.simulationResult.metric_changes && store.simulationResult.metric_changes.length > 0 && (

                <AdvancedTable

                  dataSource={store.simulationResult.metric_changes}

                  columns={[

                    { title: t('指标'), dataIndex: 'metric_name', key: 'metric_name' },

                    { title: t('变化前'), dataIndex: 'before', key: 'before' },

                    { title: t('变化后'), dataIndex: 'after', key: 'after' },

                    {

                      title: t('变化量'),

                      dataIndex: 'delta',

                      key: 'delta',

                      render: (v) => v != null ? (

                        <span style={{ color: (v as number) >= 0 ? '#52c41a' : '#ff4d4f' }}>

                          {(v as number) >= 0 ? '+' : ''}{(v as number).toFixed(3)}

                        </span>

                      ) : '-',

                    },

                  ]}

                  rowKey="metric_name"

                  size="small"

                  pagination={false}

                />

              )}

            </Space>

          )}

        </Card>

      )}

    </Space>

  );



  const renderParallelPanel = () => (

    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>

      <Card

        title={t('并行推演 & What-if 分析')}

        size="small"

        extra={

          <Space size="small">

            <Button size="small" icon={<ThunderboltOutlined />} onClick={() => setParallelModalOpen(true)}>

              {t('并行推演')}

            </Button>

            <Button size="small" icon={<ExperimentOutlined />} onClick={() => setWhatIfModalOpen(true)}>

              {t('What-if 分析')}

            </Button>

          </Space>

        }

      >

        <Empty description={t('配置并行推演或 What-if 分析')} image={Empty.PRESENTED_IMAGE_SIMPLE} />

      </Card>



      {store.parallelResult && (

        <Card title={t('并行推演结果')} size="small">

          <Descriptions column={2}>

            <Descriptions.Item label={t('运行 ID')}>{store.parallelResult.run_id}</Descriptions.Item>

            <Descriptions.Item label={t('方案数量')}>{store.parallelResult.total_scenarios}</Descriptions.Item>

            <Descriptions.Item label={t('最优方案')}>

              <Tag color="gold">{store.parallelResult.best_scenario_id || t('无')}</Tag>

            </Descriptions.Item>

          </Descriptions>

          {store.parallelResult.results?.map((r, idx) => (

            <Card key={idx} size="small" type="inner" title={t('方案 {{n}}: {{id}}', { n: idx + 1, id: (r as Record<string, unknown>).scenario_id as string || '' })} style={{ marginTop: 8 }}>

              <Space>

                <Tag color={((r as Record<string, unknown>).status as string) === 'completed' ? 'green' : 'red'}>

                  {(r as Record<string, unknown>).status as string}

                </Tag>

                {(r as Record<string, unknown>).risk_assessment ? (

                  <Tag color={((r as Record<string, unknown>).risk_assessment as Record<string, unknown>).overall_risk === 'high' ? 'red' : 'green'}>

                    {t('风险: {{risk}}', { risk: ((r as Record<string, unknown>).risk_assessment as Record<string, unknown>).overall_risk as string })}

                  </Tag>

                ) : null}

              </Space>

            </Card>

          ))}

        </Card>

      )}



      {store.whatIfResult && (

        <Card title={t('What-if 分析结果')} size="small">

          <Descriptions column={2}>

            <Descriptions.Item label={t('运行 ID')}>{store.whatIfResult.run_id}</Descriptions.Item>

            <Descriptions.Item label={t('变异数量')}>{store.whatIfResult.total_variations}</Descriptions.Item>

          </Descriptions>

          {store.whatIfResult.sensitivity_analysis ? (

            <Card size="small" type="inner" title={t('敏感性分析')} style={{ marginTop: 8 }}>

              {Object.entries(store.whatIfResult.sensitivity_analysis).map(([metric, values]) => (

                <div key={metric} style={{ marginBottom: 4 }}>

                  <strong>{metric}:</strong>{' '}

                  {(values as Array<Record<string, unknown>>).map((v, i) => (

                    <Tag key={i}>

                      {`Δ=${(v.delta as number)?.toFixed(3) ?? 'N/A'}`}

                    </Tag>

                  ))}

                </div>

              ))}

            </Card>

          ) : null}

        </Card>

      )}

    </Space>

  );



  const renderEventSimulatorPanel = () => (

    <Space orientation="vertical" size="middle" style={{ width: '100%' }}>

      <Card

        title={t('事件模拟器')}

        size="small"

        extra={

          <Space size="small">

            <Button size="small" icon={<PlusOutlined />} onClick={() => setInjectModalOpen(true)}>

              {t('注入事件')}

            </Button>

          </Space>

        }

      >

        {store.eventSequence ? (

          <Space orientation="vertical" style={{ width: '100%' }}>

            <Descriptions column={2}>

              <Descriptions.Item label={t('序列 ID')}>{store.eventSequence.sequence_id}</Descriptions.Item>

              <Descriptions.Item label={t('事件数量')}>

                <Badge count={store.eventSequence.total_events} showZero color="blue" />

              </Descriptions.Item>

            </Descriptions>

            <AdvancedTable

              dataSource={store.eventSequence.events}

              columns={[

                { title: t('事件 ID'), dataIndex: 'event_id', key: 'event_id', ellipsis: true },

                { title: t('类型'), dataIndex: 'event_type', key: 'event_type', render: (tp) => <Tag>{tp as string}</Tag> },

                { title: t('目标类型'), dataIndex: 'target_entity_type', key: 'target_entity_type', render: (tp) => <Tag color="blue">{tp as string}</Tag> },

                { title: t('时间'), dataIndex: 'timestamp', key: 'timestamp', ellipsis: true, width: 160 },

                {

                  title: t('相关性'),

                  dataIndex: 'ontology_relevance',

                  key: 'ontology_relevance',

                  width: 100,

                  render: (v) => (

                    <Progress percent={Math.round((v as number) * 100)} size="small" strokeColor={(v as number) > 0.7 ? '#52c41a' : (v as number) > 0.4 ? '#faad14' : '#ff4d4f'} />

                  ),

                },

              ]}

              rowKey="event_id"

              size="small"

              pagination={false}

            />

          </Space>

        ) : (

          <Empty description={t('选择模板生成事件序列')} image={Empty.PRESENTED_IMAGE_SIMPLE} />

        )}

      </Card>



      <Card

        title={t('事件模板')}

        size="small"

        extra={

          <Button size="small" icon={<PlusOutlined />} onClick={() => setTemplateModalOpen(true)}>

            {t('新建模板')}

          </Button>

        }

      >

        <AdvancedTable

          dataSource={store.templates}

          columns={templateColumns}

          rowKey="template_id"

          size="small"

          pagination={false}

          onReload={() => store.fetchTemplates()}

          locale={{ emptyText: <Empty description={t('暂无模板')} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}

        />

      </Card>



      <Card

        title={t('时间线控制')}

        size="small"

        extra={

          <Button size="small" icon={<PlusOutlined />} onClick={() => setTimelineModalOpen(true)}>

            {t('新建时间线')}

          </Button>

        }

      >

        <AdvancedTable

          dataSource={store.timelines}

          columns={timelineColumns}

          rowKey="timeline_id"

          size="small"

          pagination={false}

          onReload={() => store.fetchTimelines()}

          locale={{ emptyText: <Empty description={t('暂无时间线')} image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}

        />

      </Card>

    </Space>

  );



  return (

    <Spin spinning={store.loading} description={t('推演进行中...')}>

      <Tabs

        activeKey={store.activeTab}

        onChange={store.setActiveTab}

        items={[

          {

            key: 'sandbox',

            label: (

              <span>

                <ExperimentOutlined />

                {t('沙箱推演')}

              </span>

            ),

            children: renderSandboxPanel(),

          },

          {

            key: 'parallel',

            label: (

              <span>

                <ThunderboltOutlined />

                {t('并行推演')}

              </span>

            ),

            children: renderParallelPanel(),

          },

          {

            key: 'event',

            label: (

              <span>

                <ClockCircleOutlined />

                {t('事件模拟器')}

              </span>

            ),

            children: renderEventSimulatorPanel(),

          },

        ]}

      />



      <Modal

        title={t('创建沙箱')}

        open={sandboxModalOpen}

        onCancel={() => { setSandboxModalOpen(false); sandboxForm.resetFields(); }}

        onOk={() => sandboxForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={sandboxForm} layout="vertical" onFinish={handleCreateSandbox}>

          <Form.Item name="max_memory_mb" label={t('最大内存 (MB)')} initialValue={512}>

            <InputNumber min={128} max={4096} style={{ width: '100%' }} />

          </Form.Item>

          <Form.Item name="max_time_seconds" label={t('最大时间 (秒)')} initialValue={300}>

            <InputNumber min={30} max={3600} style={{ width: '100%' }} />

          </Form.Item>

          <Form.Item name="workspace_id" label={t('工作空间 ID')}>

            <Input placeholder="default" />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('运行推演')}

        open={runModalOpen}

        onCancel={() => { setRunModalOpen(false); runForm.resetFields(); }}

        onOk={() => runForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={runForm} layout="vertical" onFinish={handleRunSimulation}>

          <Form.Item name="action_type_id" label={t('动作类型')} rules={[{ required: true }]}>

            <Select

              options={[

                { value: 'move', label: t('移动') },

                { value: 'engage', label: t('交锋') },

                { value: 'hold', label: t('坚守') },

                { value: 'support', label: t('支援') },

                { value: 'withdraw', label: t('撤离') },

                { value: 'observe', label: t('观察') },

              ]}

            />

          </Form.Item>

          <Form.Item name="target_object_id" label={t('目标对象 ID')} rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="target_object_type" label={t('目标对象类型')} rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="parameters" label={t('参数 (JSON)')}>

            <Input.TextArea rows={3} placeholder='{"key": "value"}' />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('并行推演')}

        open={parallelModalOpen}

        onCancel={() => { setParallelModalOpen(false); parallelForm.resetFields(); }}

        onOk={() => parallelForm.submit()}

        confirmLoading={store.loading}

        width={640}

      >

        <Form form={parallelForm} layout="vertical" onFinish={handleRunParallel}>

          <Form.Item name="scenarios" label={t('方案列表 (JSON)')} rules={[{ required: true }]}>

            <Input.TextArea

              rows={8}

              placeholder='[{"action_type_id":"engage","target_object_id":"unit_1","target_object_type":"entity","parameters":{}}]'

            />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('What-if 分析')}

        open={whatIfModalOpen}

        onCancel={() => { setWhatIfModalOpen(false); whatIfForm.resetFields(); }}

        onOk={() => whatIfForm.submit()}

        confirmLoading={store.loading}

        width={640}

      >

        <Form form={whatIfForm} layout="vertical" onFinish={handleRunWhatIf}>

          <Form.Item name="base_scenario" label={t('基础方案 (JSON)')} rules={[{ required: true }]}>

            <Input.TextArea rows={4} placeholder='{"action_type_id":"move","target_object_id":"unit_1","target_object_type":"entity","parameters":{}}' />

          </Form.Item>

          <Form.Item name="param_variations" label={t('参数变异 (JSON)')} rules={[{ required: true }]}>

            <Input.TextArea rows={4} placeholder='[{"speed": 0.5}, {"speed": 1.0}, {"speed": 2.0}]' />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('创建时间线')}

        open={timelineModalOpen}

        onCancel={() => { setTimelineModalOpen(false); timelineForm.resetFields(); }}

        onOk={() => timelineForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={timelineForm} layout="vertical" onFinish={handleCreateTimeline}>

          <Form.Item name="speed" label={t('模拟速度')} initialValue={1.0}>

            <Slider min={0.1} max={10} step={0.1} marks={{ 0.1: '0.1x', 1: '1x', 5: '5x', 10: '10x' }} />

          </Form.Item>

          <Form.Item name="start_time" label={t('起始时间')}>

            <Input placeholder={t('ISO 时间（可选）')} />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('新建事件模板')}

        open={templateModalOpen}

        onCancel={() => { setTemplateModalOpen(false); templateForm.resetFields(); }}

        onOk={() => templateForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={templateForm} layout="vertical" onFinish={handleCreateTemplate}>

          <Form.Item name="name" label={t('模板名称')} rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="description" label={t('描述')}>

            <Input.TextArea rows={2} />

          </Form.Item>

          <Form.Item name="category" label={t('分类')}>

            <Select

              options={[

                { value: 'conflict', label: t('冲突') },

                { value: 'logistics', label: t('物流') },

                { value: 'survey', label: t('监测') },

                { value: 'communication', label: t('通信') },

                { value: 'management', label: t('管理') },

                { value: 'custom', label: t('自定义') },

              ]}

            />

          </Form.Item>

          <Form.Item name="event_types" label={t('事件类型 (逗号分隔)')}>

            <Input placeholder="engage,hold,withdraw" />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('注入事件')}

        open={injectModalOpen}

        onCancel={() => { setInjectModalOpen(false); injectForm.resetFields(); }}

        onOk={() => injectForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={injectForm} layout="vertical" onFinish={handleInjectEvent}>

          <Form.Item name="event_type" label={t('事件类型')} rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="target_entity_type" label={t('目标实体类型')} rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="data" label={t('事件数据 (JSON)')}>

            <Input.TextArea rows={3} placeholder='{"key": "value"}' />

          </Form.Item>

        </Form>

      </Modal>

    </Spin>

  );

};



export default SimulationPage;
