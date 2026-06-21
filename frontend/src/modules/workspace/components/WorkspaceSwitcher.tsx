import { useState, useEffect } from 'react';
import { Select, Space, Tag, Button, Modal, Input, message } from 'antd';
import { ProForm as Form } from '@ant-design/pro-components';
import { PlusOutlined, SettingOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';
import type { Workspace } from '@/modules/shared/services/api';
import { useNavigate } from 'react-router-dom';

export function WorkspaceSwitcher({ currentWorkspace, onWorkspaceChange }: {
  currentWorkspace: string;
  onWorkspaceChange: (workspaceId: string) => void;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [createForm] = Form.useForm();
  const navigate = useNavigate();

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
    } finally {
      setLoading(false);
    }
  };

  const handleWorkspaceChange = (value: string) => {
    onWorkspaceChange(value);
  };

  const handleCreateWorkspace = () => {
    setCreateModalVisible(true);
  };

  const handleCreateSubmit = async () => {
    try {
      const values = await createForm.validateFields();
      await api.createWorkspace(values);
      message.success('工作空间创建成功');
      setCreateModalVisible(false);
      createForm.resetFields();
      loadWorkspaces();
    } catch (error) {
      message.error(`创建失败: ${error}`);
    }
  };

  const handleWorkspaceSettings = () => {
    navigate('/workspace/manage');
  };

  return (
    <Space>
      <Select
        value={currentWorkspace}
        onChange={handleWorkspaceChange}
        loading={loading}
        style={{ width: 200 }}
        placeholder="选择工作空间"
        options={workspaces.map(workspace => ({
          value: workspace.workspace_id,
          label: (
            <Space>
              <span>{workspace.name}</span>
              {workspace.status === 'active' && (
                <Tag color="green">活跃</Tag>
              )}
            </Space>
          ),
        }))}
      />
      <Button
        type="dashed"
        icon={<PlusOutlined />}
        size="small"
        onClick={handleCreateWorkspace}
      >
        新建
      </Button>
      <Button
        icon={<SettingOutlined />}
        size="small"
        onClick={handleWorkspaceSettings}
      >
        设置
      </Button>
      <Modal
        title="新建工作空间"
        open={createModalVisible}
        onOk={handleCreateSubmit}
        onCancel={() => { setCreateModalVisible(false); createForm.resetFields(); }}
        okText="创建"
        cancelText="取消"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入工作空间名称' }]}>
            <Input placeholder="输入工作空间名称" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="输入描述" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}