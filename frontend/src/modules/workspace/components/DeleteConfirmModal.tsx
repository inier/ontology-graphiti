import { useState, useEffect } from 'react';
import { Modal, Table, Typography, Space, Alert, Spin } from 'antd';
import { ExclamationCircleOutlined, DeleteOutlined } from '@ant-design/icons';
import { api } from '@/modules/shared/services/api';

const { Text } = Typography;

interface DeletionResource {
  type: string;
  label: string;
  count: number;
}

interface DeletionPreview {
  workspace_id: string;
  workspace_name: string;
  resources: DeletionResource[];
  total_count: number;
}

interface DeleteConfirmModalProps {
  open: boolean;
  workspaceId: string;
  workspaceName: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export function DeleteConfirmModal({
  open,
  workspaceId,
  workspaceName,
  onConfirm,
  onCancel,
  loading = false,
}: DeleteConfirmModalProps) {
  const [preview, setPreview] = useState<DeletionPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (open && workspaceId) {
      setConfirmed(false);
      loadPreview();
    } else {
      setPreview(null);
      setConfirmed(false);
    }
  }, [open, workspaceId]);

  const loadPreview = async () => {
    setPreviewLoading(true);
    try {
      const result = await api.getWorkspaceDeletionPreview(workspaceId);
      setPreview(result);
    } catch (error) {
      console.error('加载删除预览失败:', error);
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleConfirm = () => {
    if (!confirmed) {
      setConfirmed(true);
      return;
    }
    onConfirm();
    setConfirmed(false);
  };

  const handleCancel = () => {
    setConfirmed(false);
    onCancel();
  };

  const columns = [
    {
      title: '资源类型',
      dataIndex: 'label',
      key: 'label',
      render: (label: string) => <Text strong>{label}</Text>,
    },
    {
      title: '数量',
      dataIndex: 'count',
      key: 'count',
      width: 80,
      align: 'center' as const,
      render: (count: number) => <Text type="danger">{count}</Text>,
    },
  ];

  return (
    <Modal
      title={
        <Space>
          <ExclamationCircleOutlined style={{ color: '#faad14' }} />
          确认删除工作空间
        </Space>
      }
      open={open}
      onOk={handleConfirm}
      onCancel={handleCancel}
      okText={confirmed ? '确认删除' : '我已了解，继续'}
      okButtonProps={{
        danger: confirmed,
        type: confirmed ? 'primary' : 'default',
      }}
      cancelText="取消"
      width={560}
      confirmLoading={loading}
    >
      {previewLoading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin description="加载删除预览..." />
        </div>
      ) : (
        <Space orientation="vertical" style={{ width: '100%' }} size="middle">
          <Alert
            type="warning"
            showIcon
            message={`即将删除工作空间「${workspaceName}」及其所有关联数据`}
            description="此操作不可恢复，删除后所有关联的场景、智能体、会话等数据将被永久清除。"
          />

          {preview && preview.resources.length > 0 && (
            <>
              <Text type="secondary">
                以下资源将被级联删除（共 {preview.total_count} 项）：
              </Text>
              <Table
                dataSource={preview.resources}
                columns={columns}
                rowKey="type"
                size="small"
                pagination={false}
                style={{ maxHeight: 300, overflow: 'auto' }}
              />
            </>
          )}

          {confirmed && (
            <Alert
              type="error"
              showIcon
              icon={<DeleteOutlined />}
              message="二次确认"
              description="请再次点击「确认删除」按钮以执行删除操作。"
            />
          )}
        </Space>
      )}
    </Modal>
  );
}
