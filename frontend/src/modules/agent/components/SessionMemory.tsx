import { useState, useEffect } from 'react';
import { Tabs, List, Input, Button, Tag, Space, Typography, Empty, Spin, message, Popconfirm } from 'antd';
import { ProCard as Card } from '@ant-design/pro-components';
import { SearchOutlined, ClearOutlined } from '@ant-design/icons';
import { apiClient } from '@/modules/shared/services/apiClient';

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

interface SessionMemoryProps {
  sessionId: string;
}

export default function SessionMemory({ sessionId }: SessionMemoryProps) {
  const [activeTab, setActiveTab] = useState('short-term');
  const [context, setContext] = useState<ContextWindow | null>(null);
  const [workingMemory, setWorkingMemory] = useState<WorkingMemoryItem[]>([]);
  const [longTermResults, setLongTermResults] = useState<LongTermItem[]>([]);
  const [ltSearchQuery, setLtSearchQuery] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await apiClient.get<{ context_window: ContextWindow; messages: ChatMessage[]; summary: string }>(
          `/api/session-memory/sessions/${sessionId}/context`,
        );
        setContext(data.context_window || null);
      } catch {
        setContext(null);
      } finally {
        setLoading(false);
      }
      try {
        const memData = await apiClient.get<Record<string, unknown>>(
          `/api/session-memory/memory/session/${sessionId}`,
        );
        if (memData && typeof memData === 'object') {
          const items = Object.entries(memData)
            .filter(([key]) => key !== 'status')
            .map(([key, value]) => ({ key, value }));
          setWorkingMemory(items);
        }
      } catch {
        setWorkingMemory([]);
      }
    };
    load();
  }, [sessionId]);

  const handleLongTermSearch = async () => {
    if (!ltSearchQuery.trim()) {
      message.warning('Please enter a search query');
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.get<{ results: LongTermItem[] }>(
        `/api/session-memory/memory/long-term?query=${encodeURIComponent(ltSearchQuery)}&limit=10`,
      );
      setLongTermResults(data.results || []);
    } catch (e) {
      message.error(`Search failed: ${(e as Error).message}`);
      setLongTermResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearSession = async () => {
    try {
      await apiClient.post(`/api/session-memory/memory/session/${sessionId}/clear`);
      message.success('Session memory cleared');
      setContext(null);
      setWorkingMemory([]);
    } catch (e) {
      message.error(`Clear failed: ${(e as Error).message}`);
    }
  };

  const renderShortTermMemory = () => {
    if (!context || !context.messages || context.messages.length === 0) {
      return <Empty description="No conversation context" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
    }
    return (
      <Space orientation="vertical" style={{ width: '100%' }} size="small">
        {context.summary && (
          <Card size="small" style={{ background: '#f6f8fa' }}>
            <Text type="secondary">Summary: </Text>
            <Text>{context.summary}</Text>
          </Card>
        )}
        <div style={{ marginBottom: 4 }}>
          <Text type="secondary">
            Tokens: {context.total_tokens || 0} / {context.max_tokens || 8000}
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
                  {msg.tokens > 0 && <Text type="secondary" style={{ fontSize: 11 }}>{msg.tokens} tokens</Text>}
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
      return <Empty description="No working memory" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
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
          placeholder="Search long-term memory..."
          value={ltSearchQuery}
          onChange={(e) => setLtSearchQuery(e.target.value)}
          style={{ width: 300 }}
          onPressEnter={handleLongTermSearch}
        />
        <Button type="primary" icon={<SearchOutlined />} onClick={handleLongTermSearch}>
          Search
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
                  {item.score !== undefined && <Text type="secondary">score: {item.score.toFixed(3)}</Text>}
                </Space>
                <Text style={{ fontSize: 13 }}>{typeof item.value === 'string' ? item.value : JSON.stringify(item.value)}</Text>
              </Space>
            </List.Item>
          )}
        />
      ) : (
        <Empty description="No results" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
    </Space>
  );

  const tabItems = [
    {
      key: 'short-term',
      label: 'Short-term',
      children: renderShortTermMemory(),
    },
    {
      key: 'working',
      label: 'Working',
      children: renderWorkingMemory(),
    },
    {
      key: 'long-term',
      label: 'Long-term',
      children: renderLongTermMemory(),
    },
  ];

  return (
    <Spin spinning={loading}>
      <Card
        title="Session Memory"
        size="small"
        extra={
          <Popconfirm title="Clear all session memory?" onConfirm={handleClearSession}>
            <Button size="small" danger icon={<ClearOutlined />}>
              Clear
            </Button>
          </Popconfirm>
        }
      >
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} />
      </Card>
    </Spin>
  );
}
