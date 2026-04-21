import { useState, useEffect } from 'react';
import { Table, Card, Button, Modal, Form, Input, Space, Tag, Popconfirm, message, Row, Col, Statistic } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import { useWorkspace } from '../../shared/components/AppLayout';
import type { Workspace } from '../../shared/services/api';

export function WorkspaceManager() {
  const { reloadWorkspaces } = useWorkspace();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadWorkspaces();
  }, []);

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
      width: 200,
      render: (_: unknown, record: Workspace) => (
        <Space size="small">
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          {record.status === 'active' ? (
            <Button
              type="link"
              danger
              icon={<StopOutlined />}
              onClick={() => handleDeactivate(record.workspace_id)}
            >
              停用
            </Button>
          ) : (
            <Button
              type="link"
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
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const activeCount = workspaces.filter(w => w.status === 'active').length;
  const inactiveCount = workspaces.filter(w => w.status !== 'active').length;

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
            <Statistic title="活跃工作空间" value={activeCount} valueStyle={{ color: '#52c41a' }} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已停用" value={inactiveCount} valueStyle={{ color: '#ff4d4f' }} loading={loading} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="总成员数" value={workspaces.reduce((sum, w) => sum + (w.member_count ?? 0), 0)} loading={loading} />
          </Card>
        </Col>
      </Row>

      <Card
        title="工作空间管理"
        style={{ marginTop: 16 }}
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
    </div>
  );
}