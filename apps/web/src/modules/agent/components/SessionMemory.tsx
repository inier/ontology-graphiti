/**
 * SessionMemory —— 会话记忆检视（短期上下文 / 工作记忆 / 长期记忆）。
 *
 * 契约（后端 odap/biz/platform/session_memory/api/routes.py，前缀 /api/session-memory）：
 *   GET  /sessions/{id}/context          → {context_window, messages, summary}
 *   GET  /memory/session/{id}            → {key: value} 字典（含 status 字段需过滤）
 *   GET  /memory/long-term?query=&limit= → 检索结果
 *   POST /memory/session/{id}/clear      → 清空该会话记忆
 *
 * 修复记录：
 *   - 全文英文硬编码 → 中文即键 i18n；
 *   - 三处 `catch { setX([]) }` 静默降级 → 现在把失败原因显示出来，
 *     否则"记忆为空"与"接口挂了"在界面上完全一样；
 *   - 清空用的是 POST，失败时此前只 toast 一句，现在同样落到页面错误条。
 */
import { useCallback, useEffect, useState } from 'react';
import { Tabs, List, Input, Button, Tag, Space, Typography, Empty, Spin, message, Popconfirm, Alert } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';
import { useI18n } from '@/modules/shared/hooks/useI18n';

const { Text } = Typography;

interface ChatMessage {
  id: string;
  role: string;
  content: string;
  tokens: number;
  entities: string[];
}

interface ContextWindow {
  messages: ChatMessage[];
  summary: string;
  total_tokens: number;
  max_tokens: number;
}

interface WorkingMemoryItem {
  key: string;
  value: unknown;
}

interface LongTermItem {
  key: string;
  value: unknown;
  score?: number;
}

export interface SessionMemoryProps {
  sessionId: string;
}

export default function SessionMemory({ sessionId }: SessionMemoryProps) {
  const { t } = useI18n('agent');
  const [activeTab, setActiveTab] = useState('short-term');
  const [context, setContext] = useState<ContextWindow | null>(null);
  const [workingMemory, setWorkingMemory] = useState<WorkingMemoryItem[]>([]);
  const [longTermResults, setLongTermResults] = useState<LongTermItem[]>([]);
  const [ltSearchQuery, setLtSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    const nextErrors: string[] = [];
    try {
      const data = await apiClient.get<{ context_window?: ContextWindow; messages?: ChatMessage[]; summary?: string }>(
        `/api/session-memory/sessions/${encodeURIComponent(sessionId)}/context`,
      );
      setContext(
        data.context_window ?? {
          messages: data.messages ?? [],
          summary: data.summary ?? '',
          total_tokens: 0,
          max_tokens: 0,
        },
      );
    } catch (e) {
      setContext(null);
      nextErrors.push(`${t('加载会话上下文失败')}: ${(e as Error).message}`);
    }

    try {
      const memData = await apiClient.get<Record<string, unknown>>(
        `/api/session-memory/memory/session/${encodeURIComponent(sessionId)}`,
      );
      if (memData && typeof memData === 'object') {
        setWorkingMemory(
          Object.entries(memData)
            .filter(([key]) => key !== 'status')
            .map(([key, value]) => ({ key, value })),
        );
      } else {
        setWorkingMemory([]);
      }
    } catch (e) {
      setWorkingMemory([]);
      nextErrors.push(`${t('加载工作记忆失败')}: ${(e as Error).message}`);
    }

    setErrors(nextErrors);
    setLoading(false);
  }, [sessionId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleLongTermSearch = async () => {
    if (!ltSearchQuery.trim()) {
      message.warning(t('请输入检索词'));
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.get<{ results?: LongTermItem[] }>(
        `/api/session-memory/memory/long-term?query=${encodeURIComponent(ltSearchQuery)}&limit=10`,
      );
      setLongTermResults(data.results ?? []);
      setErrors((prev) => prev.filter((e) => !e.startsWith(t('检索长期记忆失败'))));
    } catch (e) {
      setLongTermResults([]);
      setErrors((prev) => [...prev, `${t('检索长期记忆失败')}: ${(e as Error).message}`]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearSession = async () => {
    try {
      await apiClient.post(`/api/session-memory/memory/session/${encodeURIComponent(sessionId)}/clear`);
      message.success(t('会话记忆已清空'));
      setContext(null);
      setWorkingMemory([]);
    } catch (e) {
      setErrors((prev) => [...prev, `${t('清空会话记忆失败')}: ${(e as Error).message}`]);
    }
  };

  const renderShortTermMemory = () => {
    if (!context || !context.messages || context.messages.length === 0) {
      return <Empty description={t('暂无会话上下文')} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        {context.summary && (
          <Card size="small" style={{ background: 'var(--ant-color-fill-quaternary)' }}>
            <Text type="secondary">{t('摘要')}：</Text>
            <Text>{context.summary}</Text>
          </Card>
        )}
        <div style={{ marginBottom: 4 }}>
          <Text type="secondary">
            {t('Token 用量')}：{context.total_tokens || 0} / {context.max_tokens || 8000}
          </Text>
        </div>
        <List
          size="small"
          dataSource={context.messages}
          renderItem={(msg: ChatMessage) => (
            <List.Item>
              <Space orientation="vertical" style={{ width: '100%' }} size={2}>
                <Space>
                  <Tag color={msg.role === 'user' ? 'blue' : msg.role === 'assistant' ? 'green' : 'default'}>
                    {msg.role}
                  </Tag>
                  {msg.tokens > 0 && (
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {msg.tokens} {t('token')}
                    </Text>
                  )}
                </Space>
                <Text style={{ fontSize: 13 }}>{msg.content}</Text>
                {msg.entities && msg.entities.length > 0 && (
                  <Space size={4}>
                    {msg.entities.map((e) => <Tag key={e} style={{ fontSize: 11 }}>{e}</Tag>)}
                  </Space>
                )}
              </Space>
            </List.Item>
          )}
        />
      </Space>
    );
  };

  const renderWorkingMemory = () => {
    if (workingMemory.length === 0) {
      return <Empty description={t('暂无工作记忆')} image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <List
        size="small"
        dataSource={workingMemory}
        renderItem={(item) => (
          <List.Item>
            <Space>
              <Tag color="orange">{item.key}</Tag>
              <Text>{typeof item.value === 'string' ? item.value : JSON.stringify(item.value)}</Text>
            </Space>
          </List.Item>
        )}
      />
    );
  };

  const renderLongTermMemory = () => (
    <Space orientation="vertical" style={{ width: '100%' }} size="middle">
      <Space>
        <Input
          aria-label={t('检索长期记忆')}
          placeholder={t('检索长期记忆...')}
          value={ltSearchQuery}
          onChange={(e) => setLtSearchQuery(e.target.value)}
          style={{ width: 300 }}
          onPressEnter={() => void handleLongTermSearch()}
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={() => void handleLongTermSearch()}>
          {t('检索')}
        </Button>
      </Space>
      {longTermResults.length > 0 ? (
        <List
          size="small"
          dataSource={longTermResults}
          renderItem={(item) => (
            <List.Item>
              <Space orientation="vertical" style={{ width: '100%' }} size={2}>
                <Space>
                  <Tag color="purple">{item.key}</Tag>
                  {item.score !== undefined && (
                    <Text type="secondary">
                      {t('相关度')}：{item.score.toFixed(3)}
                    </Text>
                  )}
                </Space>
                <Text style={{ fontSize: 13 }}>
                  {typeof item.value === 'string' ? item.value : JSON.stringify(item.value)}
                </Text>
              </Space>
            </List.Item>
          )}
        />
      ) : (
        <Empty description={t('暂无检索结果')} image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Space>
  );

  const tabItems = [
    { key: 'short-term', label: t('短期上下文'), children: renderShortTermMemory() },
    { key: 'working', label: t('工作记忆'), children: renderWorkingMemory() },
    { key: 'long-term', label: t('长期记忆'), children: renderLongTermMemory() },
  ];

  return (
    <Spin spinning={loading}>
      <Card
        title={t('会话记忆')}
        size="small"
        extra={
          <Popconfirm title={t('确定清空该会话的全部记忆？')} onConfirm={() => void handleClearSession()}>
            <Button size="small" danger icon={<ClearOutlined />}>
              {t('清空')}
            </Button>
          </Popconfirm>
        }
      >
        {errors.length > 0 && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            title={t('部分记忆数据加载失败')}
            description={
              <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                {errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            }
            action={
              <Button size="small" onClick={() => void load()}>
                {t('重试')}
              </Button>
            }
          />
        )}
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>
    </Spin>
  );
}
