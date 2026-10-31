/**
 * SessionMemoryPage —— 会话记忆检视页面。
 *
 * `SessionMemory` 以 sessionId 为入参，因此页面负责"选会话"这一步：
 *   GET /api/session-memory/sessions?workspace_id=&limit=  → {sessions: [...]}
 * 选中的会话交给 SessionMemory 展示短期 / 工作 / 长期三层记忆。
 *
 * 说明：会话数据来自 session_memory 存储（与问答面板同一份 store 的数据来源），
 * 不是凭空的 id 输入框 —— 否则用户无从知道该填什么。
 */
import { useCallback, useEffect, useState } from 'react';
import { Card, List, Empty, Spin, Tag, Typography, Button, Alert, Space } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useWorkspace } from '@/modules/shared';
import { useI18n } from '@/modules/shared/hooks/useI18n';
import SessionMemory from '../components/SessionMemory';

const { Text } = Typography;

interface SessionSummary {
  id: string;
  title?: string;
  message_count?: number;
  is_active?: boolean;
  updated_at?: string;
}

export function SessionMemoryPage() {
  const { t } = useI18n('agent');
  const { currentWorkspace } = useWorkspace();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | undefined>();
  // 「加载中」不靠 effect 里同步 setLoading(true)：那会触发级联渲染
  // （react-hooks/set-state-in-effect）。改为「最近一次成功/失败请求的 key ≠ 当前 key」
  // 推导，再叠加一个只由按钮事件置位的手动刷新标记。
  const [refreshing, setRefreshing] = useState(false);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const workspaceKey = currentWorkspace || 'default';
  const loading = refreshing || loadedKey !== workspaceKey;

  /** 只做 I/O、不写状态（避免 effect 内同步 setState 触发级联渲染） */
  const requestSessions = useCallback(() => {
    const qs = new URLSearchParams({ workspace_id: workspaceKey, limit: '50' });
    return apiClient.get<{ sessions?: SessionSummary[] }>(
      `/api/session-memory/sessions?${qs.toString()}`,
    );
  }, [workspaceKey]);

  const applySessions = useCallback((data: { sessions?: SessionSummary[] }) => {
    const list = data.sessions ?? [];
    setSessions(list);
    setError(null);
    setSelectedId((prev) => prev ?? list[0]?.id);
  }, []);

  const failSessions = useCallback((e: Error) => { setError(e.message); }, []);

  const settle = useCallback(() => {
    setRefreshing(false);
    // 失败也落 key，否则 spinner 永久转
    setLoadedKey(workspaceKey);
  }, [workspaceKey]);

  useEffect(() => {
    let ignore = false;
    requestSessions()
      .then((data) => { if (!ignore) applySessions(data); })
      .catch((e: Error) => { if (!ignore) failSessions(e); })
      .finally(() => { if (!ignore) settle(); });
    return () => { ignore = true; };
  }, [requestSessions, applySessions, failSessions, settle]);

  /** 手动刷新来自按钮事件，不属于 effect，可以直接置位 refreshing 让按钮转圈 */
  const handleRefresh = () => {
    setRefreshing(true);
    requestSessions().then(applySessions).catch(failSessions).finally(settle);
  };

  return (
    <div style={{ padding: 4 }}>
      {error && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 12 }}
          title={t('加载会话列表失败')}
          description={error}
          action={
            <Button size="small" onClick={handleRefresh}>
              {t('重试')}
            </Button>
          }
        />
      )}
      <Space orientation="vertical" style={{ width: '100%' }} size="middle">
        <Card
          size="small"
          title={t('会话列表 ({{count}})', { count: sessions.length })}
          extra={
            <Button size="small" icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
              {t('刷新')}
            </Button>
          }
        >
          <Spin spinning={loading}>
            {sessions.length === 0 ? (
              <Empty description={t('暂无会话记录')} />
            ) : (
              <List
                size="small"
                dataSource={sessions}
                renderItem={(s) => (
                  <List.Item
                    style={{
                      cursor: 'pointer',
                      padding: '8px 12px',
                      background: s.id === selectedId ? 'var(--ant-color-primary-bg)' : undefined,
                    }}
                    onClick={() => setSelectedId(s.id)}
                  >
                    <Space>
                      <Text strong={s.id === selectedId}>{s.title || t('未命名会话')}</Text>
                      <Text type="secondary">{s.id}</Text>
                      {typeof s.message_count === 'number' && (
                        <Tag>
                          {t('{{n}} 条消息', { n: s.message_count })}
                        </Tag>
                      )}
                    </Space>
                  </List.Item>
                )}
              />
            )}
          </Spin>
        </Card>

        {selectedId ? (
          <SessionMemory key={selectedId} sessionId={selectedId} />
        ) : (
          <Empty description={t('请选择一个会话查看记忆')} />
        )}
      </Space>
    </div>
  );
}

export default SessionMemoryPage;
