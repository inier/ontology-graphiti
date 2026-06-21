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

      message.success(`沙箱 ${sandboxId} 创建成功`);

      setSandboxModalOpen(false);

      sandboxForm.resetFields();

    }

  };



  const handleRunSimulation = async (values: Record<string, unknown>) => {

    await store.runSimulation(values);

    if (store.simulationResult) {

      message.success('推演完成');

      setRunModalOpen(false);

      runForm.resetFields();

    }

  };



  const handleDestroySandbox = async (sandboxId: string) => {

    try {

      await store.destroySandbox(sandboxId);

      message.success('沙箱已销毁');

    } catch (error) {

      message.error(`销毁失败: ${error}`);

    }

  };



  const handleExport = async (sandboxId: string) => {

    try {

      await store.exportResults(sandboxId, 'admin');

      message.success('结果已导出');

    } catch (error) {

      message.error(`导出失败: ${error}`);

    }

  };



  const handleRunParallel = async (values: Record<string, unknown>) => {

    try {

      const scenariosStr = values.scenarios as string;

      const scenarios = JSON.parse(scenariosStr);

      await store.runParallel(scenarios);

      if (store.parallelResult) {

        message.success('并行推演完成');

        setParallelModalOpen(false);

        parallelForm.resetFields();

      }

    } catch {

      message.error('方案 JSON 格式错误');

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

        message.success('What-if 分析完成');

        setWhatIfModalOpen(false);

        whatIfForm.resetFields();

      }

    } catch {

      message.error('参数 JSON 格式错误');

    }

  };



  const handleCreateTimeline = async (values: Record<string, unknown>) => {

    const timelineId = await store.createTimeline(values);

    if (timelineId) {

      message.success(`时间线 ${timelineId} 创建成功`);

      setTimelineModalOpen(false);

      timelineForm.resetFields();

    }

  };



  const handleClockControl = async (timelineId: string, action: string, speed?: number) => {

    try {

      const params: Record<string, unknown> = { timeline_id: timelineId, action };

      if (speed !== undefined) params.speed = speed;

      await store.controlClock(params);

      message.success(`时钟${action === 'start' ? '启动' : action === 'pause' ? '暂停' : action === 'resume' ? '恢复' : '调整'}成功`);

    } catch (error) {

      message.error(`时钟控制失败: ${error}`);

    }

  };



  const handleCreateTemplate = async (values: Record<string, unknown>) => {

    try {

      await store.createTemplate(values);

      message.success('模板创建成功');

      setTemplateModalOpen(false);

      templateForm.resetFields();

    } catch (error) {

      message.error(`创建模板失败: ${error}`);

    }

  };



  const handleGenerateEvents = async (templateId: string) => {

    await store.generateEventSequence({ template_id: templateId, count: 5 });

    if (store.eventSequence) {

      message.success(`生成 ${store.eventSequence.total_events} 个事件`);

    }

  };



  const handleInjectEvent = async (values: Record<string, unknown>) => {

    try {

      await store.injectEvent(values);

      message.success('事件已注入');

      setInjectModalOpen(false);

      injectForm.resetFields();

    } catch (error) {

      message.error(`注入事件失败: ${error}`);

    }

  };



  const sandboxColumns: ColumnsType<SandboxInfo> = [

    {

      title: '沙箱 ID',

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

      title: '状态',

      dataIndex: 'status',

      key: 'status',

      width: 90,

      render: (status) => (

        <Tag color={SANDBOX_STATUS_COLORS[status as string] || 'default'}>{status as string}</Tag>

      ),

    },

    {

      title: '创建时间',

      dataIndex: 'created_at',

      key: 'created_at',

      width: 160,

      ellipsis: true,

    },

    {

      title: '操作',

      key: 'action',

      width: 180,

      render: (_, record) => (

        <Space size="small">

          <Tooltip title="运行推演">

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

          <Tooltip title="导出结果">

            <Button

              size="small"

              icon={<ExportOutlined />}

              onClick={() => handleExport(record.sandbox_id)}

              disabled={record.status !== 'completed'}

            />

          </Tooltip>

          <Popconfirm

            title="确认销毁此沙箱？"

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

      title: '时间线 ID',

      dataIndex: 'timeline_id',

      key: 'timeline_id',

      ellipsis: true,

    },

    {

      title: '时钟状态',

      dataIndex: 'clock_state',

      key: 'clock_state',

      width: 90,

      render: (state) => (

        <Tag color={CLOCK_STATE_COLORS[state as string] || 'default'}>{state as string}</Tag>

      ),

    },

    {

      title: '速度',

      dataIndex: 'simulation_speed',

      key: 'simulation_speed',

      width: 70,

      render: (speed) => `${speed}x`,

    },

    {

      title: '当前时间',

      dataIndex: 'current_time',

      key: 'current_time',

      width: 160,

      ellipsis: true,

    },

    {

      title: '操作',

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

      title: '模板名称',

      dataIndex: 'name',

      key: 'name',

      ellipsis: true,

    },

    {

      title: '分类',

      dataIndex: 'category',

      key: 'category',

      width: 100,

      render: (cat) => <Tag>{cat as string}</Tag>,

    },

    {

      title: '事件类型',

      dataIndex: 'event_types',

      key: 'event_types',

      width: 200,

      render: (types) => (

        <Space size={2} wrap>

          {(types as string[]).slice(0, 3).map(t => <Tag key={t}>{t}</Tag>)}

          {(types as string[]).length > 3 && <Tag>+{(types as string[]).length - 3}</Tag>}

        </Space>

      ),

    },

    {

      title: '操作',

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

            生成

          </Button>

          <Popconfirm

            title="确认删除此模板？"

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

        title="沙箱管理"

        size="small"

        extra={

          <Space size="small">

            <Button size="small" icon={<ReloadOutlined />} onClick={() => store.fetchSandboxes()}>

              刷新

            </Button>

            <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setSandboxModalOpen(true)}>

              创建沙箱

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

          locale={{ emptyText: (

            <EmptyState

              icon={<ExperimentOutlined />}

              title="暂无沙箱"

              description="创建沙箱以进行推演仿真，或加载示例数据快速体验"

              actionLabel="创建沙箱"

              onAction={() => setSandboxModalOpen(true)}

              showSampleData

              onLoadSampleData={async () => {

                if (!currentWorkspace) { message.warning('请先选择工作空间'); return; }

                try {

                  const { api } = await import('@/modules/shared/services/api');

                  await api.generateSampleData(currentWorkspace);

                  message.success('示例数据已加载');

                  store.fetchSandboxes();

                } catch (e) { message.error('加载示例数据失败'); }

              }}

            />

          ) }}

        />

      </Card>



      {store.sandboxStatus && (

        <Card title="沙箱状态" size="small">

          <Descriptions size="small" column={2} variant="bordered">

            <Descriptions.Item label="沙箱 ID">{store.sandboxStatus.sandbox_id}</Descriptions.Item>

            <Descriptions.Item label="状态">

              <Tag color={SANDBOX_STATUS_COLORS[store.sandboxStatus.status] || 'default'}>

                {store.sandboxStatus.status}

              </Tag>

            </Descriptions.Item>

            <Descriptions.Item label="隔离级别">{store.sandboxStatus.isolation_level}</Descriptions.Item>

            <Descriptions.Item label="创建时间">{store.sandboxStatus.created_at}</Descriptions.Item>

          </Descriptions>

        </Card>

      )}



      {store.simulationResult && (

        <Card title="推演结果" size="small">

          {store.simulationResult.status === 'timeout' ? (

            <Alert type="warning" showIcon message="推演超时" description={store.simulationResult.message} />

          ) : (

            <Space orientation="vertical" style={{ width: '100%' }}>

              {store.simulationResult.risk_assessment && (

                <Row gutter={16}>

                  <Col span={8}>

                    <Statistic

                      title="风险等级"

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

                    <Statistic title="置信度" value={(store.simulationResult.confidence || 0) as number * 100} precision={1} suffix="%" />

                  </Col>

                </Row>

              )}

              {store.simulationResult.recommendation && (

                <Alert type="info" message="推荐" description={store.simulationResult.recommendation} />

              )}

              {store.simulationResult.metric_changes && store.simulationResult.metric_changes.length > 0 && (

                <AdvancedTable

                  dataSource={store.simulationResult.metric_changes}

                  columns={[

                    { title: '指标', dataIndex: 'metric_name', key: 'metric_name' },

                    { title: '变化前', dataIndex: 'before', key: 'before' },

                    { title: '变化后', dataIndex: 'after', key: 'after' },

                    {

                      title: '变化量',

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

        title="并行推演 & What-if 分析"

        size="small"

        extra={

          <Space size="small">

            <Button size="small" icon={<ThunderboltOutlined />} onClick={() => setParallelModalOpen(true)}>

              并行推演

            </Button>

            <Button size="small" icon={<ExperimentOutlined />} onClick={() => setWhatIfModalOpen(true)}>

              What-if 分析

            </Button>

          </Space>

        }

      >

        <Empty description="配置并行推演或 What-if 分析" image={Empty.PRESENTED_IMAGE_SIMPLE} />

      </Card>



      {store.parallelResult && (

        <Card title="并行推演结果" size="small">

          <Descriptions size="small" column={2} variant="bordered">

            <Descriptions.Item label="运行 ID">{store.parallelResult.run_id}</Descriptions.Item>

            <Descriptions.Item label="方案数量">{store.parallelResult.total_scenarios}</Descriptions.Item>

            <Descriptions.Item label="最优方案">

              <Tag color="gold">{store.parallelResult.best_scenario_id || '无'}</Tag>

            </Descriptions.Item>

          </Descriptions>

          {store.parallelResult.results?.map((r, idx) => (

            <Card key={idx} size="small" type="inner" title={`方案 ${idx + 1}: ${(r as Record<string, unknown>).scenario_id as string || ''}`} style={{ marginTop: 8 }}>

              <Space>

                <Tag color={((r as Record<string, unknown>).status as string) === 'completed' ? 'green' : 'red'}>

                  {(r as Record<string, unknown>).status as string}

                </Tag>

                {(r as Record<string, unknown>).risk_assessment ? (

                  <Tag color={((r as Record<string, unknown>).risk_assessment as Record<string, unknown>).overall_risk === 'high' ? 'red' : 'green'}>

                    {`风险: ${((r as Record<string, unknown>).risk_assessment as Record<string, unknown>).overall_risk as string}`}

                  </Tag>

                ) : null}

              </Space>

            </Card>

          ))}

        </Card>

      )}



      {store.whatIfResult && (

        <Card title="What-if 分析结果" size="small">

          <Descriptions size="small" column={2} variant="bordered">

            <Descriptions.Item label="运行 ID">{store.whatIfResult.run_id}</Descriptions.Item>

            <Descriptions.Item label="变异数量">{store.whatIfResult.total_variations}</Descriptions.Item>

          </Descriptions>

          {store.whatIfResult.sensitivity_analysis ? (

            <Card size="small" type="inner" title="敏感性分析" style={{ marginTop: 8 }}>

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

        title="事件模拟器"

        size="small"

        extra={

          <Space size="small">

            <Button size="small" icon={<PlusOutlined />} onClick={() => setInjectModalOpen(true)}>

              注入事件

            </Button>

          </Space>

        }

      >

        {store.eventSequence ? (

          <Space orientation="vertical" style={{ width: '100%' }}>

            <Descriptions size="small" column={2} variant="bordered">

              <Descriptions.Item label="序列 ID">{store.eventSequence.sequence_id}</Descriptions.Item>

              <Descriptions.Item label="事件数量">

                <Badge count={store.eventSequence.total_events} showZero color="blue" />

              </Descriptions.Item>

            </Descriptions>

            <AdvancedTable

              dataSource={store.eventSequence.events}

              columns={[

                { title: '事件 ID', dataIndex: 'event_id', key: 'event_id', ellipsis: true },

                { title: '类型', dataIndex: 'event_type', key: 'event_type', render: (t) => <Tag>{t as string}</Tag> },

                { title: '目标类型', dataIndex: 'target_entity_type', key: 'target_entity_type', render: (t) => <Tag color="blue">{t as string}</Tag> },

                { title: '时间', dataIndex: 'timestamp', key: 'timestamp', ellipsis: true, width: 160 },

                {

                  title: '相关性',

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

          <Empty description="选择模板生成事件序列" image={Empty.PRESENTED_IMAGE_SIMPLE} />

        )}

      </Card>



      <Card

        title="事件模板"

        size="small"

        extra={

          <Button size="small" icon={<PlusOutlined />} onClick={() => setTemplateModalOpen(true)}>

            新建模板

          </Button>

        }

      >

        <AdvancedTable

          dataSource={store.templates}

          columns={templateColumns}

          rowKey="template_id"

          size="small"

          pagination={false}

          locale={{ emptyText: <Empty description="暂无模板" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}

        />

      </Card>



      <Card

        title="时间线控制"

        size="small"

        extra={

          <Button size="small" icon={<PlusOutlined />} onClick={() => setTimelineModalOpen(true)}>

            新建时间线

          </Button>

        }

      >

        <AdvancedTable

          dataSource={store.timelines}

          columns={timelineColumns}

          rowKey="timeline_id"

          size="small"

          pagination={false}

          locale={{ emptyText: <Empty description="暂无时间线" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}

        />

      </Card>

    </Space>

  );



  return (

    <Spin spinning={store.loading} description="推演进行中...">

      <Tabs

        activeKey={store.activeTab}

        onChange={store.setActiveTab}

        items={[

          {

            key: 'sandbox',

            label: (

              <span>

                <ExperimentOutlined />

                沙箱推演

              </span>

            ),

            children: renderSandboxPanel(),

          },

          {

            key: 'parallel',

            label: (

              <span>

                <ThunderboltOutlined />

                并行推演

              </span>

            ),

            children: renderParallelPanel(),

          },

          {

            key: 'event',

            label: (

              <span>

                <ClockCircleOutlined />

                事件模拟器

              </span>

            ),

            children: renderEventSimulatorPanel(),

          },

        ]}

      />



      <Modal

        title="创建沙箱"

        open={sandboxModalOpen}

        onCancel={() => { setSandboxModalOpen(false); sandboxForm.resetFields(); }}

        onOk={() => sandboxForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={sandboxForm} layout="vertical" onFinish={handleCreateSandbox}>

          <Form.Item name="max_memory_mb" label="最大内存 (MB)" initialValue={512}>

            <InputNumber min={128} max={4096} style={{ width: '100%' }} />

          </Form.Item>

          <Form.Item name="max_time_seconds" label="最大时间 (秒)" initialValue={300}>

            <InputNumber min={30} max={3600} style={{ width: '100%' }} />

          </Form.Item>

          <Form.Item name="workspace_id" label="工作空间 ID">

            <Input placeholder="default" />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="运行推演"

        open={runModalOpen}

        onCancel={() => { setRunModalOpen(false); runForm.resetFields(); }}

        onOk={() => runForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={runForm} layout="vertical" onFinish={handleRunSimulation}>

          <Form.Item name="action_type_id" label="动作类型" rules={[{ required: true }]}>

            <Select

              options={[

                { value: 'move', label: '移动' },

                { value: 'engage', label: '交锋' },

                { value: 'hold', label: '坚守' },

                { value: 'support', label: '支援' },

                { value: 'withdraw', label: '撤离' },

                { value: 'observe', label: '观察' },

              ]}

            />

          </Form.Item>

          <Form.Item name="target_object_id" label="目标对象 ID" rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="target_object_type" label="目标对象类型" rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="parameters" label="参数 (JSON)">

            <Input.TextArea rows={3} placeholder='{"key": "value"}' />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="并行推演"

        open={parallelModalOpen}

        onCancel={() => { setParallelModalOpen(false); parallelForm.resetFields(); }}

        onOk={() => parallelForm.submit()}

        confirmLoading={store.loading}

        width={640}

      >

        <Form form={parallelForm} layout="vertical" onFinish={handleRunParallel}>

          <Form.Item name="scenarios" label="方案列表 (JSON)" rules={[{ required: true }]}>

            <Input.TextArea

              rows={8}

              placeholder='[{"action_type_id":"engage","target_object_id":"unit_1","target_object_type":"entity","parameters":{}}]'

            />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="What-if 分析"

        open={whatIfModalOpen}

        onCancel={() => { setWhatIfModalOpen(false); whatIfForm.resetFields(); }}

        onOk={() => whatIfForm.submit()}

        confirmLoading={store.loading}

        width={640}

      >

        <Form form={whatIfForm} layout="vertical" onFinish={handleRunWhatIf}>

          <Form.Item name="base_scenario" label="基础方案 (JSON)" rules={[{ required: true }]}>

            <Input.TextArea rows={4} placeholder='{"action_type_id":"move","target_object_id":"unit_1","target_object_type":"entity","parameters":{}}' />

          </Form.Item>

          <Form.Item name="param_variations" label="参数变异 (JSON)" rules={[{ required: true }]}>

            <Input.TextArea rows={4} placeholder='[{"speed": 0.5}, {"speed": 1.0}, {"speed": 2.0}]' />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="创建时间线"

        open={timelineModalOpen}

        onCancel={() => { setTimelineModalOpen(false); timelineForm.resetFields(); }}

        onOk={() => timelineForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={timelineForm} layout="vertical" onFinish={handleCreateTimeline}>

          <Form.Item name="speed" label="模拟速度" initialValue={1.0}>

            <Slider min={0.1} max={10} step={0.1} marks={{ 0.1: '0.1x', 1: '1x', 5: '5x', 10: '10x' }} />

          </Form.Item>

          <Form.Item name="start_time" label="起始时间">

            <Input placeholder="ISO 时间（可选）" />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="新建事件模板"

        open={templateModalOpen}

        onCancel={() => { setTemplateModalOpen(false); templateForm.resetFields(); }}

        onOk={() => templateForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={templateForm} layout="vertical" onFinish={handleCreateTemplate}>

          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="description" label="描述">

            <Input.TextArea rows={2} />

          </Form.Item>

          <Form.Item name="category" label="分类">

            <Select

              options={[

                { value: 'conflict', label: '冲突' },

                { value: 'logistics', label: '物流' },

                { value: 'survey', label: '监测' },

                { value: 'communication', label: '通信' },

                { value: 'management', label: '管理' },

                { value: 'custom', label: '自定义' },

              ]}

            />

          </Form.Item>

          <Form.Item name="event_types" label="事件类型 (逗号分隔)">

            <Input placeholder="engage,hold,withdraw" />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title="注入事件"

        open={injectModalOpen}

        onCancel={() => { setInjectModalOpen(false); injectForm.resetFields(); }}

        onOk={() => injectForm.submit()}

        confirmLoading={store.loading}

      >

        <Form form={injectForm} layout="vertical" onFinish={handleInjectEvent}>

          <Form.Item name="event_type" label="事件类型" rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="target_entity_type" label="目标实体类型" rules={[{ required: true }]}>

            <Input />

          </Form.Item>

          <Form.Item name="data" label="事件数据 (JSON)">

            <Input.TextArea rows={3} placeholder='{"key": "value"}' />

          </Form.Item>

        </Form>

      </Modal>

    </Spin>

  );

};



export default SimulationPage;

