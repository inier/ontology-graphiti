import { useState, useEffect } from 'react';
import { Table, Card, Button, Space, Tag, Popconfirm, message } from 'antd';
import { RollbackOutlined, DeleteOutlined, ReloadOutlined, FileTextOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import { useScenario, useWorkspace } from '../../shared/components/AppLayout';

interface VersionItem {
  version_id: string;
  ontology_id?: string;
  parent_version?: string;
  commit_message?: string;
  created_at: string;
  status?: string;
  is_current?: boolean;
  entity_count?: number;
  relation_count?: number;
  event_count?: number;
}

export function VersionHistory() {
  const [versions, setVersions] = useState<VersionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);
  const { currentScenario } = useScenario();
  const { currentWorkspace } = useWorkspace();

  useEffect(() => {
    loadVersions();
  }, [currentScenario, currentWorkspace]);

  const loadVersions = async () => {
    try {
      setLoading(true);
      if (currentWorkspace && currentScenario) {
        const data = await api.getScenarioOntologyVersions(currentWorkspace, currentScenario);
        setVersions(data);
      } else {
        const data = await api.listVersions();
        setVersions(data);
      }
    } catch (error) {
      console.error('加载版本历史失败', error);
      message.error('加载版本历史失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRollback = async (versionId: string) => {
    try {
      if (currentWorkspace && currentScenario) {
        await api.switchScenarioOntologyVersion(currentWorkspace, currentScenario, versionId);
      } else {
        await api.rollback(versionId);
      }
      message.success('回滚成功');
      loadVersions();
    } catch (error) {
      console.error('回滚失败', error);
      message.error('回滚失败');
    }
  };

  const handleDiff = async () => {
    if (selectedVersions.length !== 2) {
      message.warning('请选择两个版本进行对比');
      return;
    }
    try {
      const diff = await api.diffVersions(selectedVersions[0], selectedVersions[1]);
      console.log('版本对比结果:', diff);
    } catch (error) {
      console.error('版本对比失败', error);
      message.error('版本对比失败');
    }
  };

  const columns = [
    {
      title: '版本号',
      dataIndex: 'version_id',
      key: 'version_id',
      render: (versionId: string) => (
        <Space>
          <FileTextOutlined />
          <span>{versionId}</span>
        </Space>
      ),
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (timestamp: string) => timestamp ? new Date(timestamp).toLocaleString('zh-CN') : '-',
    },
    {
      title: '提交信息',
      dataIndex: 'commit_message',
      key: 'commit_message',
      ellipsis: true,
      render: (msg: string) => msg || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string, record: VersionItem) => {
        if (record.is_current) return <Tag color="blue">当前</Tag>;
        const colorMap: Record<string, string> = {
          draft: 'default', released: 'green', deprecated: 'red', archived: 'orange',
        };
        return <Tag color={colorMap[status] || 'default'}>{status || '未知'}</Tag>;
      },
    },
    {
      title: '数据量',
      key: 'counts',
      render: (_: unknown, record: VersionItem) => (
        <Space>
          <span>{record.entity_count ?? 0}E</span>
          <span>{record.relation_count ?? 0}R</span>
          <span>{record.event_count ?? 0}V</span>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: VersionItem) => (
        <Space size="small">
          <Button
            type="link"
            icon={<RollbackOutlined />}
            onClick={() => handleRollback(record.version_id)}
          >
            回滚
          </Button>
          <Popconfirm
            title="确定删除此版本？"
            onConfirm={() => console.log('删除版本', record.version_id)}
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

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="版本历史"
        extra={
          <Space>
            <Button
              type="primary"
              disabled={selectedVersions.length !== 2}
              onClick={handleDiff}
            >
              对比版本
            </Button>
            <Button icon={<ReloadOutlined />} onClick={loadVersions}>
              刷新
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={versions}
          rowKey="version_id"
          loading={loading}
          pagination={{ pageSize: 10 }}
          rowSelection={{
            selectedRowKeys: selectedVersions,
            onChange: (selectedKeys) => setSelectedVersions(selectedKeys as string[]),
            selections: [
              {
                key: 'all-data',
                text: '全选',
                onSelect: () => setSelectedVersions(versions.map(v => v.version_id)),
              },
            ],
          }}
        />
      </Card>
    </div>
  );
}
