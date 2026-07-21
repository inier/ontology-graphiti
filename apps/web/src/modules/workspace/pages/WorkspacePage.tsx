import { useState, useEffect } from 'react';

import { Row, Col, Card, Tag, Modal, Form, Input, Select as AntSelect, Space, Statistic, Tabs, message, Empty } from 'antd';

import { PlusOutlined, EditOutlined, DeleteOutlined, ExportOutlined, ImportOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons';

import adapter from '@/modules/shared/components/adapter';

import { useI18n } from '@/modules/shared/hooks/useI18n';

import { PageHeader } from '@/modules/shared/components/PageHeader';

import { useWorkspace, useScenario } from '@/modules/shared/components/LayoutContexts';

import { useWorkspaceStore } from '../stores/workspaceStore';
import { DeleteConfirmModal } from '../components/DeleteConfirmModal';

import type { WorkspaceDetail, ScenarioDetail } from '../stores/workspaceStore';

import { PageTourWrapper, workspaceTourSteps, PAGE_IDS } from '@/modules/guide';
import { AdvancedTable } from '@/modules/shared';



const Button = adapter.getButton();



const ISOLATION_COLORS: Record<string, string> = {

  LOW: 'default',

  STANDARD: 'blue',

  HIGH: 'orange',

  STRICT: 'red',

};



export function WorkspacePage() {

  const { t } = useI18n();

  const ISOLATION_LABELS: Record<string, string> = {

    LOW: t('低'),

    STANDARD: t('标准'),

    HIGH: t('高'),

    STRICT: t('严格'),

  };

  const { currentWorkspace: activeWorkspaceId, reloadWorkspaces } = useWorkspace();

  const { scenarios: contextScenarios, reloadScenarios } = useScenario();

  const {

    workspaces,

    loading,

    loadWorkspaces,

    createWorkspace,

    updateWorkspace,

    deleteWorkspace,

    exportWorkspace,

    loadScenarios,

    createScenario,

    activateScenario,

  } = useWorkspaceStore();



  const [createModalVisible, setCreateModalVisible] = useState(false);

  const [editModalVisible, setEditModalVisible] = useState(false);

  const [scenarioModalVisible, setScenarioModalVisible] = useState(false);

  const [deleteModalVisible, setDeleteModalVisible] = useState(false);
  const [deletingWorkspace, setDeletingWorkspace] = useState<WorkspaceDetail | null>(null);
  const [editingWorkspace, setEditingWorkspace] = useState<WorkspaceDetail | null>(null);

  const [createForm] = Form.useForm();

  const [editForm] = Form.useForm();

  const [scenarioForm] = Form.useForm();

  const [activeTab, setActiveTab] = useState('workspaces');



  useEffect(() => {

    loadWorkspaces();

  }, []);



  useEffect(() => {

    if (activeWorkspaceId) {

      loadScenarios(activeWorkspaceId);

    }

  }, [activeWorkspaceId]);



  const handleCreate = async () => {

    try {

      const values = await createForm.validateFields();

      await createWorkspace(values);

      setCreateModalVisible(false);

      createForm.resetFields();

      adapter.getMessage().success(t('创建成功'));

    } catch {

      // validation error

    }

  };



  const handleEdit = (workspace: WorkspaceDetail) => {

    setEditingWorkspace(workspace);

    editForm.setFieldsValue({

      name: workspace.name,

      description: workspace.description,

      isolation_level: workspace.isolation_level,

    });

    setEditModalVisible(true);

  };



  const handleEditSubmit = async () => {

    if (!editingWorkspace) return;

    try {

      const values = await editForm.validateFields();

      await updateWorkspace(editingWorkspace.workspace_id, values);

      setEditModalVisible(false);

      editForm.resetFields();

      setEditingWorkspace(null);

      adapter.getMessage().success(t('更新成功'));

    } catch {

      // validation error

    }

  };



  const handleDelete = async (workspaceId: string) => {
    try {
      await deleteWorkspace(workspaceId);
      adapter.getMessage().success(t('删除成功'));
    } catch {
      adapter.getMessage().error(t('删除失败'));
    } finally {
      setDeleteModalVisible(false);
      setDeletingWorkspace(null);
    }
    reloadWorkspaces();
  };



  const handleExport = async (workspaceId: string) => {

    const result = await exportWorkspace(workspaceId);

    if (result) {

      const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });

      const url = URL.createObjectURL(blob);

      const a = document.createElement('a');

      a.href = url;

      a.download = `workspace-${workspaceId}.json`;

      a.click();

      URL.revokeObjectURL(url);

      adapter.getMessage().success(t('导出成功'));

    }

  };



  const handleCreateScenario = async () => {

    if (!activeWorkspaceId) return;

    try {

      const values = await scenarioForm.validateFields();

      await createScenario(activeWorkspaceId, values);

      setScenarioModalVisible(false);

      scenarioForm.resetFields();

      adapter.getMessage().success(t('场景创建成功'));

      reloadScenarios();

    } catch {

      // validation error

    }

  };



  const handleActivateScenario = async (scenarioId: string) => {

    if (!activeWorkspaceId) return;

    await activateScenario(activeWorkspaceId, scenarioId);

    adapter.getMessage().success(t('场景已激活'));

    reloadScenarios();

  };



  const workspaceColumns = [

    {

      title: t('名称'),

      dataIndex: 'name',

      key: 'name',

      render: (name: string, record: WorkspaceDetail) => (

        <Space>

          <span style={{ fontWeight: 500 }}>{name}</span>

          <Tag color={record.status === 'active' ? 'green' : 'red'}>

            {record.status === 'active' ? t('活跃') : t('停用')}

          </Tag>

        </Space>

      ),

    },

    {

      title: t('隔离级别'),

      dataIndex: 'isolation_level',

      key: 'isolation_level',

      render: (level: string) => (

        <Tag color={ISOLATION_COLORS[level] || 'default'}>

          {ISOLATION_LABELS[level] || level}

        </Tag>

      ),

    },

    {

      title: t('描述'),

      dataIndex: 'description',

      key: 'description',

      ellipsis: true,

    },

    {

      title: t('成员数'),

      dataIndex: 'member_count',

      key: 'member_count',

      render: (count: number) => count ?? 0,

    },

    {

      title: t('创建时间'),

      dataIndex: 'created_at',

      key: 'created_at',

      render: (date: string) => new Date(date).toLocaleString('zh-CN'),

    },

    {

      title: t('操作'),

      key: 'action',

      width: 280,

      render: (_: unknown, record: WorkspaceDetail) => (

        <Space size="small" wrap>

          <Button

            type="link"

            size="small"

            icon={<EditOutlined />}

            onClick={() => handleEdit(record)}

          >

            {t('编辑')}

          </Button>

          <Button

            type="link"

            size="small"

            icon={<ExportOutlined />}

            onClick={() => handleExport(record.workspace_id)}

          >

            {t('导出')}

          </Button>

          <Button

            type="link"

            size="small"

            icon={<DeleteOutlined />}

            onClick={() => {
              setDeletingWorkspace(record);
              setDeleteModalVisible(true);
            }}
          >
            {t('删除')}
          </Button>

        </Space>

      ),

    },

  ];



  const scenarioColumns = [

    {

      title: t('场景名称'),

      dataIndex: 'name',

      key: 'name',

      render: (name: string) => <span style={{ fontWeight: 500 }}>{name}</span>,

    },

    {

      title: t('描述'),

      dataIndex: 'description',

      key: 'description',

      ellipsis: true,

    },

    {

      title: t('状态'),

      dataIndex: 'status',

      key: 'status',

      render: (status: string) => (

        <Tag color={status === 'active' ? 'green' : 'default'}>{status}</Tag>

      ),

    },

    {

      title: t('创建时间'),

      dataIndex: 'created_at',

      key: 'created_at',

      render: (date: string) => new Date(date).toLocaleString('zh-CN'),

    },

    {

      title: t('操作'),

      key: 'action',

      width: 160,

      render: (_: unknown, record: ScenarioDetail) => (

        <Space size="small">

          <Button

            type="link"

            size="small"

            icon={<PlayCircleOutlined />}

            onClick={() => handleActivateScenario(record.scenario_id)}

          >

            {t('激活')}

          </Button>

        </Space>

      ),

    },

  ];



  const activeCount = workspaces.filter((w) => w.status === 'active').length;

  const inactiveCount = workspaces.filter((w) => w.status !== 'active').length;



  return (

    <PageTourWrapper pageId={PAGE_IDS.WORKSPACE} steps={workspaceTourSteps}>

    <div>

      <PageHeader

        title={t('工作空间管理')}

        actions={

          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalVisible(true)} data-tour="workspace-create-btn">

            {t('创建工作空间')}

          </Button>

        }

      />



      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>

        <Col span={8}>

          <Card>

            <Statistic title={t('总工作空间数')} value={workspaces.length} loading={loading} />

          </Card>

        </Col>

        <Col span={8}>

          <Card>

            <Statistic title={t('活跃工作空间')} value={activeCount} loading={loading} />

          </Card>

        </Col>

        <Col span={8}>

          <Card>

            <Statistic title={t('已停用')} value={inactiveCount} loading={loading} />

          </Card>

        </Col>

      </Row>



      <Tabs

        activeKey={activeTab}

        onChange={setActiveTab}

        items={[

          {

            key: 'workspaces',

            label: t('工作空间管理'),

            children: (

              <Card>

                <AdvancedTable

                  columns={workspaceColumns}

                  dataSource={workspaces}

                  rowKey="workspace_id"

                  loading={loading}

                  pagination={{ pageSize: 10 }}

                  onReload={() => loadWorkspaces()}

                />

              </Card>

            ),

          },

          {

            key: 'scenarios',

            label: <span data-tour="workspace-scenario-tab">{t('场景管理')}</span>,

            children: (

              <Card

                title={activeWorkspaceId ? t('场景 - {{name}}', { name: workspaces.find(w => w.workspace_id === activeWorkspaceId)?.name || '' }) : t('请选择工作空间')}

                extra={

                  activeWorkspaceId ? (

                    <Button

                      type="primary"

                      icon={<PlusOutlined />}

                      onClick={() => setScenarioModalVisible(true)}

                      data-tour="workspace-scenario-create-btn"

                    >

                      {t('创建场景')}

                    </Button>

                  ) : null

                }

              >

                {activeWorkspaceId ? (

                  <AdvancedTable

                    columns={scenarioColumns}

                    dataSource={contextScenarios}

                    rowKey="scenario_id"

                    loading={loading}

                    pagination={{ pageSize: 10 }}

                    onReload={() => { if (activeWorkspaceId) loadScenarios(activeWorkspaceId); }}

                  />

                ) : (

                  <Empty description={t('请先选择一个工作空间')} />

                )}

              </Card>

            ),

          },

        ]}

      />



      <Modal

        title={t('创建工作空间')}

        open={createModalVisible}

        onOk={handleCreate}

        onCancel={() => {

          setCreateModalVisible(false);

          createForm.resetFields();

        }}

        okText={t('创建')}

        cancelText={t('取消')}

      >

        <Form form={createForm} layout="vertical">

          <Form.Item

            name="name"

            label={t('名称')}

            rules={[{ required: true, message: t('请输入工作空间名称') }]}

          >

            <Input placeholder={t('请输入工作空间名称')} />

          </Form.Item>

          <Form.Item name="description" label={t('描述')}>

            <Input.TextArea rows={3} placeholder={t('请输入工作空间描述')} />

          </Form.Item>

          <Form.Item name="isolation_level" label={t('隔离级别')} initialValue="STANDARD">

            <AntSelect

              options={[

                { label: t('低'), value: 'LOW' },

                { label: t('标准'), value: 'STANDARD' },

                { label: t('高'), value: 'HIGH' },

                { label: t('严格'), value: 'STRICT' },

              ]}

            />

          </Form.Item>

          <Form.Item name="owner" label={t('所有者')}>

            <Input placeholder={t('请输入所有者')} />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('编辑工作空间')}

        open={editModalVisible}

        onOk={handleEditSubmit}

        onCancel={() => {

          setEditModalVisible(false);

          editForm.resetFields();

          setEditingWorkspace(null);

        }}

        okText={t('更新')}

        cancelText={t('取消')}

      >

        <Form form={editForm} layout="vertical">

          <Form.Item

            name="name"

            label={t('名称')}

            rules={[{ required: true, message: t('请输入工作空间名称') }]}

          >

            <Input placeholder={t('请输入工作空间名称')} />

          </Form.Item>

          <Form.Item name="description" label={t('描述')}>

            <Input.TextArea rows={3} placeholder={t('请输入工作空间描述')} />

          </Form.Item>

          <Form.Item name="isolation_level" label={t('隔离级别')}>

            <AntSelect

              options={[

                { label: t('低'), value: 'LOW' },

                { label: t('标准'), value: 'STANDARD' },

                { label: t('高'), value: 'HIGH' },

                { label: t('严格'), value: 'STRICT' },

              ]}

            />

          </Form.Item>

        </Form>

      </Modal>



      <Modal

        title={t('创建场景')}

        open={scenarioModalVisible}

        onOk={handleCreateScenario}

        onCancel={() => {

          setScenarioModalVisible(false);

          scenarioForm.resetFields();

        }}

        okText={t('创建')}

        cancelText={t('取消')}

      >

        <Form form={scenarioForm} layout="vertical">

          <Form.Item

            name="name"

            label={t('场景名称')}

            rules={[{ required: true, message: t('请输入场景名称') }]}

          >

            <Input placeholder={t('请输入场景名称')} />

          </Form.Item>

          <Form.Item name="description" label={t('描述')}>

            <Input.TextArea rows={3} placeholder={t('请输入场景描述')} />

          </Form.Item>

          <Form.Item name="ontology_id" label={t('绑定本体 ID（可选）')}>

            <Input placeholder={t('请输入本体 ID')} />

          </Form.Item>

        </Form>

      </Modal>

      <DeleteConfirmModal
        open={deleteModalVisible}
        workspaceId={deletingWorkspace?.workspace_id || ''}
        workspaceName={deletingWorkspace?.name || ''}
        onConfirm={() => handleDelete(deletingWorkspace?.workspace_id || '')}
        onCancel={() => {
          setDeleteModalVisible(false);
          setDeletingWorkspace(null);
        }}
      />

    </div>

    </PageTourWrapper>

  );

}

