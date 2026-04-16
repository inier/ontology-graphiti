import { useState, useEffect } from 'react';
import { Card, Table, Tag, Button, Space, Modal, message, Spin, Timeline } from 'antd';
import { ReloadOutlined, RollbackOutlined } from '@ant-design/icons';
import { api } from '../services/api';
import type { Version } from '../types';

export function VersionHistory() {
  const [versions, setVersions] = useState<Version[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedVersion, setSelectedVersion] = useState<Version | null>(null);

  const loadVersions = async () => {
    setLoading(true);
    try {
      const data = await api.listVersions();
      setVersions(data);
    } catch (error) {
      message.error('加载版本历史失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVersions();
  }, []);

  const handleRollback = async (version: Version) => {
    Modal.confirm({
      title: '确认回滚',
      content: `确定要回滚到版本 ${version.version_id} 吗？`,
      onOk: async () => {
        try {
          await api.rollback(version.version_id);
          message.success('回滚成功');
          loadVersions();
        } catch (error) {
          message.error('回滚失败');
        }
      },
    });
  };

  const columns = [
    {
      title: '版本 ID',
      dataIndex: 'version_id',
      key: 'id',
      render: (id: string) => <Tag>{id}</Tag>,
    },
    {
      title: '提交信息',
      dataIndex: 'commit_message',
      key: 'message',
    },
    {
      title: 'Schema 版本',
      dataIndex: 'schema_version',
      key: 'schema',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created',
      render: (date: string) => new Date(date).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Version) => (
        <Space>
          <Button
            type="link"
            size="small"
            onClick={() => setSelectedVersion(record)}
          >
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<RollbackOutlined />}
            onClick={() => handleRollback(record)}
          >
            回滚
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Card
        title="版本历史"
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadVersions}>
            刷新
          </Button>
        }
      >
        {loading ? (
          <Spin tip="加载中..." style={{ width: '100%', display: 'block', margin: 40 }} />
        ) : (
          <Table
            columns={columns}
            dataSource={versions}
            rowKey="version_id"
            pagination={{ pageSize: 10 }}
          />
        )}
      </Card>

      <Modal
        title="版本详情"
        open={!!selectedVersion}
        onCancel={() => setSelectedVersion(null)}
        footer={null}
      >
        {selectedVersion && (
          <Timeline
            items={[
              { children: `版本 ID: ${selectedVersion.version_id}` },
              { children: `父版本: ${selectedVersion.parent_version || '无'}` },
              { children: `Schema: ${selectedVersion.schema_version}` },
              { children: `提交信息: ${selectedVersion.commit_message}` },
              { children: `创建时间: ${new Date(selectedVersion.created_at).toLocaleString()}` },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}
