import { useState, useEffect } from 'react';
import { Table, Card, Button, Modal, Form, Input, Space, Tag, Popconfirm, message, Row, Col, Statistic, Tabs, Spin } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined, StopOutlined, BuildOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import { useWorkspace, useScenario } from '../../shared/components/AppLayout';
import type { Workspace } from '../../shared/services/api';

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
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [scenarios, setScenarios] = useState<Record<string, Scenario[]>>({});
  const [loading, setLoading] = useState(true);
  const [scenarioLoading, setScenarioLoading] = useState<Record<string, boolean>>({});
  const [modalVisible, setModalVisible] = useState(false);
  const [scenarioModalVisible, setScenarioModalVisible] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);
  const [editingScenario, setEditingScenario] = useState<{ workspaceId: string; scenario: Scenario | null } | null>(null);
  const [activeTab, setActiveTab] = useState<string>('workspaces');
  const [form] = Form.useForm();
  const [scenarioForm] = Form.useForm();

  useEffect(() => {
    loadWorkspaces();
  }, []);

  useEffect(() => {
    if (activeTab === 'scenarios' && currentWorkspace) {
      // 当切换到场景管理 tab 时，加载当前工作空间的场景
      // 每次 currentWorkspace 变化时都重新加载
      loadScenarios(currentWorkspace);
    }
  }, [activeTab, currentWorkspace]);

  const loadWorkspaces = async () => {
    try {
      setLoading(true);
      const data = await api.listWorkspaces();
      setWorkspaces(data);
    } catch (error) {
      console.error('加载工作空间失败', error);
      message.error('加载工作空间失败');
    } finally {
      setLoading(false);
    }
  };

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

  const handleDelete = async (workspaceId: string) => {
    try {
      await api.deleteWorkspace(workspaceId);
      message.success('删除成功');
      loadWorkspaces();
      reloadWorkspaces();
    } catch (error) {
      console.error('删除失败', error);
      message.error('删除失败');
    }
  };

  const handleActivate = async (workspaceId: string) => {
    try {
      await api.activateWorkspace(workspaceId);
      message.success('激活成功');
      loadWorkspaces();
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
      loadWorkspaces();
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
      loadWorkspaces();
      reloadWorkspaces();
    } catch (error) {
      console.error('操作失败', error);
      message.error('操作失败');
    }
  };

  // 场景相关函数
  const loadScenarios = async (workspaceId: string) => {
    try {
      setScenarioLoading(prev => ({ ...prev, [workspaceId]: true }));
      const data = await api.getScenariosInWorkspace(workspaceId);
      setScenarios(prev => ({ ...prev, [workspaceId]: data.scenarios }));
    } catch (error) {
      console.error('加载场景失败', error);
      message.error('加载场景失败');
    } finally {
      setScenarioLoading(prev => ({ ...prev, [workspaceId]: false }));
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
      loadScenarios(workspaceId);
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
      loadScenarios(workspaceId);
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
      loadScenarios(editingScenario.workspaceId);
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
          <Popconfirm
            title="确定删除此工作空间？"
            onConfirm={() => handleDelete(record.workspace_id)}
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

  const activeCount = workspaces.filter(w => w.status === 'active').length;
  const inactiveCount = workspaces.filter(w => w.status !== 'active').length;
  const totalScenarioCount = Object.values(scenarios).reduce((sum, s) => sum + s.length, 0);

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
    <div style={{ padding: 24 }}>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card>
            <Statistic title="总工作空间数" value={workspaces.length} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="活跃工作空间" value={activeCount} styles={{ content: { color: '#52c41a' } }} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已停用" value={inactiveCount} styles={{ content: { color: '#ff4d4f' } }} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总场景数" value={totalScenarioCount} loading={loading} />
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
                        <span>{workspaces.find(w => w.workspace_id === currentWorkspace)?.name}</span>
                        <Tag color={workspaces.find(w => w.workspace_id === currentWorkspace)?.status === 'active' ? 'green' : 'red'}>
                          {workspaces.find(w => w.workspace_id === currentWorkspace)?.status === 'active' ? '活跃' : '停用'}
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
                    <Table
                      columns={scenarioColumns}
                      dataSource={scenarios[currentWorkspace] || []}
                      rowKey="scenario_id"
                      loading={scenarioLoading[currentWorkspace]}
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
                <Table
                  columns={columns}
                  dataSource={workspaces}
                  rowKey="workspace_id"
                  loading={loading}
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
    </div>
  );
}