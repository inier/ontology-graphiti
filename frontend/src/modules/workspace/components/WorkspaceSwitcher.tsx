import { useState, useEffect } from 'react';
import { Select, Space, Tag, Button } from 'antd';
import { PlusOutlined, SettingOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import type { Workspace } from '../../shared/services/api';

export function WorkspaceSwitcher({ currentWorkspace, onWorkspaceChange }: {
  currentWorkspace: string;
  onWorkspaceChange: (workspaceId: string) => void;
}) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

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
    console.log('创建工作空间');
  };

  const handleWorkspaceSettings = () => {
    console.log('工作空间设置');
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
    </Space>
  );
}