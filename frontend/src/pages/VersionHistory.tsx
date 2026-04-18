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
      setVersions(Array.isArray(data) ? data : []);
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
      render: (id: string) => <Tag color="blue">{id}</Tag>,
    },
    {
      title: '提交信息',
      dataIndex: 'commit_message',
      key: 'message',
    },
    {
      title: '文档类型',
      dataIndex: 'doc_type',
      key: 'type',
      render: (type: string) => <Tag>{type}</Tag>,
    },
    {
      title: '实体数',
      dataIndex: 'entity_count',
      key: 'entities',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created',
      render: (date: string) => new Date(date).toLocaleString('zh-CN'),
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
            danger
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
    <div>
      <Card
        title="版本历史"
        extra={
          <Button icon={<ReloadOutlined />} onClick={loadVersions}>
            刷新
          </Button>
        }
        style={{ borderRadius: 8 }}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin description="加载中..." />
          </div>
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
              { children: `文档 ID: ${selectedVersion.doc_id}` },
              { children: `文档类型: ${selectedVersion.doc_type}` },
              { children: `父版本: ${selectedVersion.parent_version || '无'}` },
              { children: `提交信息: ${selectedVersion.commit_message}` },
              { children: `实体数: ${selectedVersion.entity_count || 0}` },
              { children: `关系数: ${selectedVersion.relation_count || 0}` },
              { children: `事件数: ${selectedVersion.event_count || 0}` },
              { children: `创建时间: ${new Date(selectedVersion.created_at).toLocaleString('zh-CN')}` },
            ]}
          />
        )}
      </Modal>
    </div>
  );
}
