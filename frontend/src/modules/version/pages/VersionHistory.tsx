import { useState, useEffect } from 'react';
import { Table, Card, Button, Space, Tag, Popconfirm, message } from 'antd';
import { RollbackOutlined, DeleteOutlined, ReloadOutlined, FileTextOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import type { Version } from '../../shared/types';

export function VersionHistory() {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVersions, setSelectedVersions] = useState<string[]>([]);

  useEffect(() => {
    loadVersions();
  }, []);

  const loadVersions = async () => {
    try {
      setLoading(true);
      const data = await api.listVersions();
      setVersions(data);
    } catch (error) {
      console.error('加载版本历史失败', error);
      message.error('加载版本历史失败');
    } finally {
      setLoading(false);
    }
  };

  const handleRollback = async (versionId: string) => {
    try {
      await api.rollback(versionId);
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
      // 显示对比结果
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
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (timestamp: string) => new Date(timestamp).toLocaleString('zh-CN'),
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => {
        const typeMap: Record<string, { color: string; text: string }> = {
          full: { color: 'blue', text: '全量' },
          incremental: { color: 'green', text: '增量' },
        };
        const config = typeMap[type] || { color: 'default', text: type };
        return <Tag color={config.color}>{config.text}</Tag>;
      },
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '变化',
      dataIndex: 'changes',
      key: 'changes',
      render: (changes: { entities: number; relations: number }) => (
        <Space>
          <span>实体: {changes.entities}</span>
          <span>关系: {changes.relations}</span>
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Version) => (
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