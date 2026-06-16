import { useState, useEffect, useCallback } from 'react';
import {
  Drawer,
  Timeline,
  Button,
  Space,
  Typography,
  Popconfirm,
  Tag,
  Empty,
  Spin,
  message,
} from 'antd';
import {
  RollbackOutlined,
  UserOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { configApi } from '../services/configApi';
import type { ConfigRevision, ConfigChange } from '../types';

const { Text, Paragraph } = Typography;

interface ConfigHistoryDrawerProps {
  open: boolean;
  onClose: () => void;
  onRollback?: () => void;
}

export function ConfigHistoryDrawer({
  open,
  onClose,
  onRollback,
}: ConfigHistoryDrawerProps) {
  const [revisions, setRevisions] = useState<ConfigRevision[]>([]);
  const [loading, setLoading] = useState(false);
  const [rollingBack, setRollingBack] = useState<number | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const data = await configApi.getConfigHistory({ page: 1, page_size: 50 });
      setRevisions(data.revisions || []);
    } catch {
      message.error('加载变更历史失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (open) {
      fetchHistory();
    }
  }, [open, fetchHistory]);

  const handleRollback = async (revisionNumber: number) => {
    setRollingBack(revisionNumber);
    try {
      await configApi.rollbackConfig(revisionNumber);
      message.success(`已回滚至版本 #${revisionNumber}`);
      onRollback?.();
      fetchHistory();
    } catch {
      message.error('回滚失败');
    } finally {
      setRollingBack(null);
    }
  };

  const renderChangeItem = (change: ConfigChange, idx: number) => {
    const oldValueDisplay = change.is_sensitive
      ? '******'
      : change.old_value ?? '(空)';
    const newValueDisplay = change.is_sensitive
      ? '******'
      : change.new_value ?? '(空)';

    return (
      <div key={idx} style={{ marginBottom: 4 }}>
        <Text strong>{change.key}</Text>
        <br />
        <Text type="secondary" style={{ fontSize: 12 }}>
          {oldValueDisplay}
        </Text>
        <Text style={{ margin: '0 6px', fontSize: 12 }}>→</Text>
        <Text style={{ fontSize: 12 }}>{newValueDisplay}</Text>
      </div>
    );
  };

  const formatTime = (isoStr: string) => {
    try {
      return new Date(isoStr).toLocaleString('zh-CN');
    } catch {
      return isoStr;
    }
  };

  return (
    <Drawer
      title="配置变更历史"
      placement="right"
      width={560}
      open={open}
      onClose={onClose}
    >
      {loading ? (
        <Spin spinning description="加载中..." style={{ width: '100%' }}>
          <div style={{ minHeight: 100 }} />
        </Spin>
      ) : revisions.length === 0 ? (
        <Empty description="暂无变更记录" />
      ) : (
        <Timeline
          items={revisions.map((rev) => ({
            color: 'blue' as const,
            children: (
              <div
                style={{
                  padding: '8px 12px',
                  background: '#fafafa',
                  borderRadius: 6,
                  border: '1px solid #f0f0f0',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}
                >
                  <Space>
                    <Tag color="blue">#{rev.revision_number}</Tag>
                    <Text>
                      <UserOutlined style={{ marginRight: 4 }} />
                      {rev.operator_name}
                    </Text>
                  </Space>
                  <Space>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      <ClockCircleOutlined style={{ marginRight: 4 }} />
                      {formatTime(rev.changed_at)}
                    </Text>
                    <Popconfirm
                      title={`确认回滚至版本 #${rev.revision_number}？`}
                      description="回滚后当前配置将被替换为该版本的配置"
                      onConfirm={() => handleRollback(rev.revision_number)}
                      okText="确认回滚"
                      cancelText="取消"
                    >
                      <Button
                        type="link"
                        icon={<RollbackOutlined />}
                        size="small"
                        loading={rollingBack === rev.revision_number}
                        danger
                      >
                        回滚
                      </Button>
                    </Popconfirm>
                  </Space>
                </div>
                <div>
                  {rev.changes.map((change, idx) => renderChangeItem(change, idx))}
                </div>
              </div>
            ),
          }))}
        />
      )}
    </Drawer>
  );
}
