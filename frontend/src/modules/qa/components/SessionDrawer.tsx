import React, { useEffect } from 'react';
import { Drawer, Spin, Empty, Button, Popconfirm, Tag, Typography, Space } from 'antd';
import { DeleteOutlined, LoadingOutlined, HistoryOutlined } from '@ant-design/icons';
import { useSession } from '../hooks/useSession';
import type { Session } from '../hooks/useSession';
import { css } from '@emotion/css';
import { useWorkspace, useScenario } from '../../shared';

const { Text } = Typography;

interface SessionDrawerProps {
  open: boolean;
  onClose: () => void;
  onSelectSession: (session: Session) => void;
}

const drawerStyles = css`
  .session-list {
    .session-item {
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 8px;
      cursor: pointer;
      transition: all 0.2s;
      border: 1px solid #f0f0f0;

      &:hover {
        background: #f5f5f5;
        border-color: #1890ff;
      }

      .session-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 8px;
      }

      .session-summary {
        font-size: 14px;
        color: #262626;
        line-height: 1.4;
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .session-meta {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
      }

      .session-time {
        font-size: 12px;
        color: #8c8c8c;
      }

      .session-actions {
        opacity: 0;
        transition: opacity 0.2s;
      }
    }

    .session-item:hover .session-actions {
      opacity: 1;
    }
  }
`;

function formatTime(timestamp: string | number): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : new Date(timestamp * 1000);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  } else if (days === 1) {
    return '昨天';
  } else if (days < 7) {
    return `${days}天前`;
  } else {
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  }
}

export function SessionDrawer({ open, onClose, onSelectSession }: SessionDrawerProps) {
  const { currentWorkspace } = useWorkspace();
  const { currentScenario } = useScenario();
  
  const { sessions, loading, fetchSessions, deleteSession } = useSession({
    workspaceId: currentWorkspace,
    scenarioId: currentScenario,
  });

  useEffect(() => {
    if (open) {
      fetchSessions(currentWorkspace, currentScenario);
    }
  }, [open, fetchSessions, currentWorkspace, currentScenario]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    await deleteSession(sessionId);
  };

  const handleSelect = (session: Session) => {
    onSelectSession(session);
    onClose();
  };

  return (
    <Drawer
      title={
        <Space>
          <HistoryOutlined />
          <span>历史会话</span>
        </Space>
      }
      placement="right"
      size="large"
      onClose={onClose}
      open={open}
      className={drawerStyles}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
          <Text type="secondary" style={{ display: 'block', marginTop: 16 }}>
            加载中...
          </Text>
        </div>
      ) : sessions.length === 0 ? (
        <Empty
          description="暂无历史会话"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <div className="session-list">
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className="session-item"
              onClick={() => handleSelect(session)}
            >
              <div className="session-header">
                <div className="session-summary">
                  {session.summary || '(无摘要)'}
                </div>
                <div className="session-actions">
                  <Popconfirm
                    title="确定删除此会话？"
                    description="删除后无法恢复"
                    onConfirm={(e) => handleDelete(e!, session.session_id)}
                    onCancel={(e) => e?.stopPropagation()}
                    okText="删除"
                    cancelText="取消"
                    placement="left"
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              </div>
              <div className="session-meta">
                <Tag color="blue">{session.message_count} 条消息</Tag>
                {session.model && <Tag>{session.model}</Tag>}
                <Text className="session-time">{formatTime(session.created_at)}</Text>
              </div>
            </div>
          ))}
        </div>
      )}
    </Drawer>
  );
}