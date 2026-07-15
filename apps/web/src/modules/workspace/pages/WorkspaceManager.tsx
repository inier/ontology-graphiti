import { useState, useEffect, useRef, useMemo } from 'react';

import { Card, Button, Modal, Form, Input, Space, Tag, message, Row, Col, Statistic, Tabs, Popconfirm } from 'antd';

import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined, StopOutlined, BuildOutlined } from '@ant-design/icons';

import { api } from '@/modules/shared/services/api';

import { useWorkspace, useScenario } from '@/modules/shared/components/LayoutContexts';

import { DeleteConfirmModal } from '../components/DeleteConfirmModal';

import type { Workspace } from '@/modules/shared/services/api';
import { AdvancedTable, wrapRequest } from '@/modules/shared';
import type { ActionType } from '@ant-design/pro-components';



interface Scenario {

  scenario_id: string;

  name: string;

  description: string;

  workspace_id: string;

  ontology_id?: string;

  doc_count: number;

  event_count: number;

  entity_count: number;

  created_at: string;

  updated_at: string;

}



export function WorkspaceManager() {

  const { reloadWorkspaces, currentWorkspace } = useWorkspace();

  const { reloadScenarios } = useScenario();

  const workspaceActionRef = useRef<ActionType>(null);
  const scenarioActionRef = useRef<ActionType>(null);

  const [wsCount, setWsCount] = useState(0);
  const [scCount, setScCount] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [inactiveCount, setInactiveCount] = useState(0);
  const [wsMap, setWsMap] = useState<Record<string, Workspace>>({});

  const [modalVisible, setModalVisible] = useState(false);

  const [scenarioModalVisible, setScenarioModalVisible] = useState(false);

  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);

  const [editingScenario, setEditingScenario] = useState<{ workspaceId: string; scenario: Scenario | null } | null>(null);

  const [activeTab, setActiveTab] = useState<string>('workspaces');

  const [form] = Form.useForm();

  const [scenarioForm] = Form.useForm();

  const [deleteModalOpen, setDeleteModalOpen] = useState(false);

  const [deletingWorkspace, setDeletingWorkspace] = useState<Workspace | null>(null);

  const [deleteLoading, setDeleteLoading] = useState(false);

  // 工作空间请求
  const fetchWorkspaceList = async (): Promise<Workspace[]> => {
    const data = await api.listWorkspaces();
    setWsCount(data.length);
    setActiveCount(data.filter(w => w.status === 'active').length);
    setInactiveCount(data.filter(w => w.status !== 'active').length);
    const map: Record<string, Workspace> = {};
    data.forEach(w => { map[w.workspace_id] = w; });
    setWsMap(map);
    return data;
  };

  const workspaceRequest = useMemo(() => wrapRequest(fetchWorkspaceList), []);

  // 场景请求
  const fetchScenarioList = async (): Promise<Scenario[]> => {
    if (!currentWorkspace) return [];
    const data = await api.getScenariosInWorkspace(currentWorkspace);
    setScCount((data.scenarios || []).length);
    return data.scenarios || [];
  };

  const scenarioRequest = useMemo(() => wrapRequest(fetchScenarioList), [currentWorkspace]);



  const handleCreate = () => {

    setEditingWorkspace(null);

    form.resetFields();

    setModalVisible(true);

  };



  const handleEdit = (workspace: Workspace) => {

    setEditingWorkspace(workspace);

    form.setFieldsValue({

      name: workspace.name,

      description: workspace.description,

    });

    setModalVisible(true);

  };



  const handleDelete = (workspace: Workspace) => {

    setDeletingWorkspace(workspace);

    setDeleteModalOpen(true);

  };



  const handleDeleteConfirm = async () => {

    if (!deletingWorkspace) return;

    try {

      setDeleteLoading(true);

      await api.deleteWorkspace(deletingWorkspace.workspace_id);

      message.success('删除成功');

      setDeleteModalOpen(false);

      setDeletingWorkspace(null);

      workspaceActionRef.current?.reload();

      reloadWorkspaces();

    } catch (error) {

      console.error('删除失败', error);

      message.error('删除失败');

    } finally {

      setDeleteLoading(false);

    }

  };



  const handleActivate = async (workspaceId: string) => {

    try {

      await api.activateWorkspace(workspaceId);

      message.success('激活成功');

      workspaceActionRef.current?.reload();

      reloadWorkspaces();

    } catch (error) {

      console.error('激活失败', error);

      message.error('激活失败');

    }

  };



  const handleDeactivate = async (workspaceId: string) => {

    try {

      await api.deactivateWorkspace(workspaceId);

      message.success('停用成功');

      workspaceActionRef.current?.reload();

      reloadWorkspaces();

    } catch (error) {

      console.error('停用失败', error);

      message.error('停用失败');

    }

  };



  const handleSubmit = async () => {

    try {

      const values = await form.validateFields();

      if (editingWorkspace) {

        await api.updateWorkspace(editingWorkspace.workspace_id, values);

        message.success('更新成功');

      } else {

        await api.createWorkspace(values);

        message.success('创建成功');

      }

      setModalVisible(false);

      workspaceActionRef.current?.reload();

      reloadWorkspaces();

    } catch (error) {

      console.error('操作失败', error);

      message.error('操作失败');

    }

  };



  const handleCreateScenario = (workspaceId: string) => {

    setEditingScenario({ workspaceId, scenario: null });

    scenarioForm.resetFields();

    setScenarioModalVisible(true);

  };



  const handleEditScenario = (workspaceId: string, scenario: Scenario) => {

    setEditingScenario({ workspaceId, scenario });

    scenarioForm.setFieldsValue({

      name: scenario.name,

      description: scenario.description,

      ontology_id: scenario.ontology_id,

    });

    setScenarioModalVisible(true);

  };



  const handleDeleteScenario = async (workspaceId: string, scenarioId: string) => {

    try {

      await api.deleteScenario(workspaceId, scenarioId);

      message.success('删除成功');

      scenarioActionRef.current?.reload();

      reloadScenarios();

    } catch (error) {

      console.error('删除失败', error);

      message.error('删除失败');

    }

  };



  const handleBuildGraph = async (workspaceId: string, scenarioId: string) => {

    const hide = message.loading('正在构建图谱...', 0);

    try {

      const result = await api.buildGraph(workspaceId, scenarioId);

      hide();

      message.success(`构建成功！抽取了 ${result.entity_count} 个实体，${result.event_count} 个事件`);

      scenarioActionRef.current?.reload();

    } catch (error) {

      hide();

      console.error('构建图谱失败', error);

      message.error('构建图谱失败');

    }

  };



  const handleScenarioSubmit = async () => {

    try {

      const values = await scenarioForm.validateFields();

      if (!editingScenario) return;

      

      if (editingScenario.scenario) {

        await api.updateScenario(

          editingScenario.workspaceId,

          editingScenario.scenario.scenario_id,

          values.name,

          values.description,

          values.ontology_id

        );

        message.success('更新成功');

      } else {

        await api.createScenarioInWorkspace(

          editingScenario.workspaceId,

          values.name,

          values.description,

          values.ontology_id

        );

        message.success('创建成功');

      }

      setScenarioModalVisible(false);

      scenarioActionRef.current?.reload();

      reloadScenarios();

    } catch (error) {

      console.error('操作失败', error);

      message.error('操作失败');

    }

  };



  const columns = [

    {

      title: '名称',

      dataIndex: 'name',

      key: 'name',

      render: (name: string, record: Workspace) => (

        <Space>

          <span style={{ fontWeight: 500 }}>{name}</span>

          <Tag color={record.status === 'active' ? 'green' : 'red'}>

            {record.status === 'active' ? '活跃' : '停用'}

          </Tag>

        </Space>

      ),

    },

    {

      title: '描述',

      dataIndex: 'description',

      key: 'description',

      ellipsis: true,

    },

    {

      title: '类型',

      dataIndex: 'type',

      key: 'type',

      render: (type: string) => {

        const typeMap: Record<string, { color: string; text: string }> = {

          default: { color: 'blue', text: '默认' },

          project: { color: 'purple', text: '项目' },

          team: { color: 'orange', text: '团队' },

        };

        const config = typeMap[type] || { color: 'default', text: type };

        return <Tag color={config.color}>{config.text}</Tag>;

      },

    },

    {

      title: '所有者',

      dataIndex: 'owner',

      key: 'owner',

    },

    {

      title: '成员数',

      dataIndex: 'member_count',

      key: 'member_count',

      render: (count: number) => count ?? 0,

    },

    {

      title: '创建时间',

      dataIndex: 'created_at',

      key: 'created_at',

      render: (date: string) => new Date(date).toLocaleString('zh-CN'),

    },

    {

      title: '操作',

      key: 'action',

      width: 300,

      render: (_: unknown, record: Workspace) => (

        <Space size="small" wrap>

          <Button

            type="link"

            size="small"

            icon={<EditOutlined />}

            onClick={() => handleEdit(record)}

          >

            编辑

          </Button>

          {record.status === 'active' ? (

            <Button

              type="link"

              size="small"

              danger

              icon={<StopOutlined />}

              onClick={() => handleDeactivate(record.workspace_id)}

            >

              停用

            </Button>

          ) : (

            <Button

              type="link"

              size="small"

              icon={<PlayCircleOutlined />}

              onClick={() => handleActivate(record.workspace_id)}

            >

              激活

            </Button>

          )}

          <Button

            type="link"

            danger

            size="small"

            icon={<DeleteOutlined />}

            onClick={() => handleDelete(record)}

          >

            删除

          </Button>

        </Space>

      ),

    },

  ];



  const totalScenarioCount = scCount;



  const scenarioColumns = [

    {

      title: '场景名称',

      dataIndex: 'name',

      key: 'name',

      render: (name: string, record: Scenario) => (

        <Space>

          <span style={{ fontWeight: 500 }}>{name}</span>

          {record.ontology_id && <Tag color="blue">绑定本体</Tag>}

        </Space>

      ),

    },

    {

      title: '描述',

      dataIndex: 'description',

      key: 'description',

      ellipsis: true,

    },

    {

      title: '本体 ID',

      dataIndex: 'ontology_id',

      key: 'ontology_id',

      render: (ontologyId: string) => (

        <span>{ontologyId || <span style={{ color: '#999' }}>未绑定</span>}</span>

      ),

    },

    {

      title: '文档数',

      dataIndex: 'doc_count',

      key: 'doc_count',

    },

    {

      title: '事件数',

      dataIndex: 'event_count',

      key: 'event_count',

    },

    {

      title: '实体数',

      dataIndex: 'entity_count',

      key: 'entity_count',

    },

    {

      title: '创建时间',

      dataIndex: 'created_at',

      key: 'created_at',

      render: (date: string) => new Date(date).toLocaleString('zh-CN'),

    },

    {

      title: '操作',

      key: 'action',

      width: 320,

      render: (_: unknown, record: Scenario) => (

        <Space size="small" wrap>

          <Button

            type="link"

            size="small"

            icon={<EditOutlined />}

            onClick={() => handleEditScenario(record.workspace_id, record)}

          >

            编辑

          </Button>

          <Button

            type="link"

            size="small"

            icon={<BuildOutlined />}

            onClick={() => handleBuildGraph(record.workspace_id, record.scenario_id)}

          >

            构建图谱

          </Button>

          <Popconfirm

            title="确定删除此场景？"

            onConfirm={() => handleDeleteScenario(record.workspace_id, record.scenario_id)}

            okText="确定"

            cancelText="取消"

          >

            <Button type="link" danger size="small" icon={<DeleteOutlined />}>

              删除

            </Button>

          </Popconfirm>

        </Space>

      ),

    },

  ];



  return (

    <div>

      <Row gutter={[16, 16]}>

        <Col span={6}>

          <Card>

            <Statistic title="总工作空间数" value={wsCount} />

          </Card>

        </Col>

        <Col span={6}>

          <Card>

            <Statistic title="活跃工作空间" value={activeCount} styles={{ content: { color: '#52c41a' } }} />

          </Card>

        </Col>

        <Col span={6}>

          <Card>

            <Statistic title="已停用" value={inactiveCount} styles={{ content: { color: '#ff4d4f' } }} />

          </Card>

        </Col>

        <Col span={6}>

          <Card>

            <Statistic title="总场景数" value={totalScenarioCount} />

          </Card>

        </Col>

      </Row>



      <Tabs

        activeKey={activeTab}

        onChange={setActiveTab}

        style={{ marginTop: 16 }}

        items={[

          {

            key: 'scenarios',

            label: '场景管理',

            children: (

              <div>

                {currentWorkspace ? (

                  <Card

                    title={

                      <Space>

                        <span>{wsMap[currentWorkspace]?.name}</span>

                        <Tag color={wsMap[currentWorkspace]?.status === 'active' ? 'green' : 'red'}>

                          {wsMap[currentWorkspace]?.status === 'active' ? '活跃' : '停用'}

                        </Tag>

                      </Space>

                    }

                    extra={

                      <Button

                        type="primary"

                        icon={<PlusOutlined />}

                        onClick={() => handleCreateScenario(currentWorkspace)}

                      >

                        创建场景

                      </Button>

                    }

                  >

                    <AdvancedTable

                      columns={scenarioColumns}

                      request={scenarioRequest}

                      actionRef={scenarioActionRef}

                      rowKey="scenario_id"

                      pagination={{ pageSize: 10 }}

                    />

                  </Card>

                ) : (

                  <Card>

                    <div style={{ textAlign: 'center', color: '#8c8c8c', padding: '40px 0' }}>

                      请先在顶部选择一个工作空间以查看其场景

                    </div>

                  </Card>

                )}

              </div>

            ),

          },

          {

            key: 'workspaces',

            label: '工作空间管理',

            children: (

              <Card

                title="工作空间管理"

                extra={

                  <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>

                    创建工作空间

                  </Button>

                }

              >

                <AdvancedTable

                  columns={columns}

                  request={workspaceRequest}

                  actionRef={workspaceActionRef}

                  rowKey="workspace_id"

                  pagination={{ pageSize: 10 }}

                />

              </Card>

            ),

          },

        ]}

      />



      <Modal

        title={editingWorkspace ? '编辑工作空间' : '创建工作空间'}

        open={modalVisible}

        onOk={handleSubmit}

        onCancel={() => setModalVisible(false)}

        okText={editingWorkspace ? '更新' : '创建'}

        cancelText="取消"

      >

        <Form form={form} layout="vertical">

          <Form.Item

            name="name"

            label="名称"

            rules={[{ required: true, message: '请输入工作空间名称' }]}

          >

            <Input placeholder="请输入工作空间名称" />

          </Form.Item>

          <Form.Item name="description" label="描述">

            <Input.TextArea rows={3} placeholder="请输入工作空间描述" />

          </Form.Item>

          <Form.Item name="owner" label="所有者">

            <Input placeholder="请输入所有者" defaultValue="system" />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={editingScenario?.scenario ? '编辑场景' : '创建场景'}

        open={scenarioModalVisible}

        onOk={handleScenarioSubmit}

        onCancel={() => setScenarioModalVisible(false)}

        okText={editingScenario?.scenario ? '更新' : '创建'}

        cancelText="取消"

      >

        <Form form={scenarioForm} layout="vertical">

          <Form.Item

            name="name"

            label="场景名称"

            rules={[{ required: true, message: '请输入场景名称' }]}

          >

            <Input placeholder="请输入场景名称" />

          </Form.Item>

          <Form.Item name="description" label="描述">

            <Input.TextArea rows={3} placeholder="请输入场景描述" />

          </Form.Item>

          <Form.Item name="ontology_id" label="绑定本体 ID（可选）">

            <Input placeholder="请输入本体 ID" />

          </Form.Item>

        </Form>

      </Modal>



      <DeleteConfirmModal

        open={deleteModalOpen}

        workspaceId={deletingWorkspace?.workspace_id || ''}

        workspaceName={deletingWorkspace?.name || ''}

        onConfirm={handleDeleteConfirm}

        onCancel={() => { setDeleteModalOpen(false); setDeletingWorkspace(null); }}

        loading={deleteLoading}

      />

    </div>

  );

}