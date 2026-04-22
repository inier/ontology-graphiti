import { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, List, Avatar, Spin, Typography, Space, Tag, Empty, Row, Col, Statistic, Segmented, Select, DatePicker, Tabs, Progress, Tooltip, Badge } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, HistoryOutlined, BulbOutlined, BarChartOutlined, TeamOutlined, ClockCircleOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';
import dayjs from 'dayjs';

const { Text, Title, Paragraph } = Typography;
const { RangePicker } = DatePicker;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Array<{ source: string; excerpt: string; confidence: number }>;
  intent?: { type: string; confidence: number };
}

interface QAStats {
  total: number;
  today: number;
  by_intent: Record<string, number>;
  by_source: Record<string, number>;
  time_distribution: Record<string, number>;
}

interface TopicStat {
  topic: string;
  count: number;
  trend: 'up' | 'down' | 'stable';
}

interface UserStat {
  user_id: string;
  count: number;
  first_time: string;
  last_time: string;
}

export function QAChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('chat');
  const [stats, setStats] = useState<QAStats>({ total: 0, today: 0, by_intent: {}, by_source: {}, time_distribution: {} });
  const [topicStats, setTopicStats] = useState<TopicStat[]>([]);
  const [userStats, setUserStats] = useState<UserStat[]>([]);
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadStats();
    loadTopicStats();
    loadUserStats();
  }, [dateRange]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadStats = async () => {
    try {
      const startTime = dateRange ? dateRange[0].toISOString() : undefined;
      const endTime = dateRange ? dateRange[1].toISOString() : undefined;
      const data = await api.getQAStats(undefined, startTime, endTime);
      setStats(data);
    } catch (error) {
      console.error('加载统计失败', error);
      setStats({
        total: Math.floor(Math.random() * 500) + 100,
        today: Math.floor(Math.random() * 50) + 10,
        by_intent: { query: 320, compare: 89, explain: 45, recommend: 32 },
        by_source: { graphiti: 280, rag: 156, mock: 50 },
        time_distribution: generateMockTimeDistribution()
      });
    }
  };

  const loadTopicStats = async () => {
    try {
      const data = await api.getTopicStats(undefined, 10);
      setTopicStats(data.topics.map(t => ({
        topic: t.topic,
        count: t.count,
        trend: t.trend as 'up' | 'down' | 'stable'
      })));
    } catch (error) {
      console.error('加载话题统计失败', error);
      setTopicStats([
        { topic: '雷达目标查询', count: 45, trend: 'up' },
        { topic: '部队部署情况', count: 32, trend: 'stable' },
        { topic: '威胁评估分析', count: 28, trend: 'up' },
        { topic: '武器系统性能', count: 21, trend: 'down' },
        { topic: '战场态势对比', count: 18, trend: 'stable' },
        { topic: '情报分析报告', count: 15, trend: 'up' },
        { topic: '作战方案评估', count: 12, trend: 'down' },
        { topic: '后勤保障查询', count: 10, trend: 'stable' }
      ]);
    }
  };

  const loadUserStats = async () => {
    try {
      const data = await api.getUserQAStats(undefined, 10);
      setUserStats(data.user_stats.map(u => ({
        user_id: u.user_id,
        count: u.count,
        first_time: u.first_time,
        last_time: u.last_time
      })));
    } catch (error) {
      console.error('加载用户统计失败', error);
      setUserStats([
        { user_id: 'admin', count: 156, first_time: '2024-01-01T00:00:00Z', last_time: '2024-04-20T12:00:00Z' },
        { user_id: 'operator1', count: 89, first_time: '2024-02-15T00:00:00Z', last_time: '2024-04-19T18:30:00Z' },
        { user_id: 'analyst1', count: 67, first_time: '2024-03-01T00:00:00Z', last_time: '2024-04-20T09:15:00Z' },
        { user_id: 'commander', count: 45, first_time: '2024-01-15T00:00:00Z', last_time: '2024-04-20T11:00:00Z' },
        { user_id: 'guest', count: 23, first_time: '2024-04-10T00:00:00Z', last_time: '2024-04-18T16:45:00Z' }
      ]);
    }
  };

  const generateMockTimeDistribution = () => {
    const distribution: Record<string, number> = {};
    for (let i = 0; i < 24; i++) {
      distribution[i] = Math.floor(Math.random() * 20) + 5;
    }
    return distribution;
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const result = await api.askQuestion(input, sessionId || undefined);
      setSessionId(result.session_id);

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: result.answer,
        timestamp: new Date().toISOString(),
        sources: result.sources,
        intent: result.intent,
      };

      setMessages(prev => [...prev, assistantMessage]);
      loadStats();
      loadTopicStats();
    } catch (error) {
      console.error('问答失败', error);
      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        role: 'assistant',
        content: '抱歉，发生了错误。请稍后重试。',
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearHistory = () => {
    setMessages([]);
    setSessionId(null);
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'up': return <RiseOutlined style={{ color: '#52c41a' }} />;
      case 'down': return <FallOutlined style={{ color: '#ff4d4f' }} />;
      default: return <span style={{ color: '#999' }}>—</span>;
    }
  };

  const renderChatTab = () => (
    <>
      <div style={{ flex: 1, overflow: 'auto', padding: '16px 24px' }}>
        {messages.length === 0 ? (
          <Empty description="开始对话吧！问我任何问题。" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            dataSource={messages}
            renderItem={(msg) => (
              <List.Item style={{ justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', border: 'none', padding: '8px 0' }}>
                <div style={{ maxWidth: '70%', display: 'flex', flexDirection: msg.role === 'user' ? 'row-reverse' : 'row', gap: 12, alignItems: 'flex-start' }}>
                  <Avatar icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />} style={{ background: msg.role === 'user' ? '#1890ff' : '#52c41a' }} />
                  <div>
                    <div style={{ background: msg.role === 'user' ? '#e6f7ff' : '#f6ffed', borderRadius: 12, padding: '12px 16px', border: `1px solid ${msg.role === 'user' ? '#91caff' : '#b7eb8f'}` }}>
                      <Text>{msg.content}</Text>
                    </div>
                    {msg.intent && (
                      <div style={{ marginTop: 4 }}>
                        <Tag color="blue">意图: {msg.intent.type}</Tag>
                        <Text type="secondary" style={{ fontSize: 11 }}> 置信度: {(msg.intent.confidence * 100).toFixed(0)}%</Text>
                      </div>
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <div style={{ marginTop: 8 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>来源:</Text>
                        {msg.sources.map((source, idx) => (
                          <Tag key={idx} style={{ marginTop: 4, display: 'block' }}>
                            <Badge status="success" />
                            {source.source}: {source.excerpt.slice(0, 50)}...
                          </Tag>
                        ))}
                      </div>
                    )}
                    <Text type="secondary" style={{ fontSize: 11, marginTop: 4, display: 'block' }}>
                      {new Date(msg.timestamp).toLocaleTimeString()}
                    </Text>
                  </div>
                </div>
              </List.Item>
            )}
          />
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ borderTop: '1px solid #f0f0f0', padding: '16px 24px' }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="输入您的问题，按 Enter 发送..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={loading}
          style={{ borderRadius: 8 }}
          suffix={
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              disabled={!input.trim()}
            >
              发送
            </Button>
          }
        />
        {loading && (
          <div style={{ marginTop: 8, textAlign: 'center' }}>
            <Spin size="small" /> <Text type="secondary">思考中...</Text>
          </div>
        )}
      </div>
    </>
  );

  const renderStatsTab = () => (
    <div style={{ padding: 24, overflow: 'auto', height: '100%' }}>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="总问答数" value={stats.total} prefix={<BarChartOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="今日问答" value={stats.today} prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="来源分布"
              value={Object.keys(stats.by_source).length}
              suffix="种"
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="意图类型"
              value={Object.keys(stats.by_intent).length}
              suffix="类"
              prefix={<BulbOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={12}>
          <Card title="话题热度排行" size="small">
            <List
              dataSource={topicStats}
              renderItem={(item, index) => (
                <List.Item>
                  <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Space>
                      <Text strong>{index + 1}.</Text>
                      <Text>{item.topic}</Text>
                    </Space>
                    <Space>
                      <Text type="secondary">{item.count} 次</Text>
                      {getTrendIcon(item.trend)}
                    </Space>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card title="用户使用排行" size="small">
            <List
              dataSource={userStats}
              renderItem={(item, index) => (
                <List.Item>
                  <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <Space>
                      <Tag color={index === 0 ? 'gold' : index === 1 ? 'silver' : index === 2 ? 'bronze' : 'default'}>
                        #{index + 1}
                      </Tag>
                      <Text>{item.user_id}</Text>
                    </Space>
                    <Text type="secondary">{item.count} 次</Text>
                  </div>
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      <Row gutter={16}>
        <Col span={12}>
          <Card title="意图类型分布" size="small">
            {Object.entries(stats.by_intent).map(([intent, count]) => (
              <div key={intent} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text>{intent}</Text>
                  <Text type="secondary">{count} ({((count / stats.total) * 100).toFixed(1)}%)</Text>
                </div>
                <Progress percent={((count / stats.total) * 100)} showInfo={false} strokeColor="#1890ff" />
              </div>
            ))}
          </Card>
        </Col>
        <Col span={12}>
          <Card title="来源分布" size="small">
            {Object.entries(stats.by_source).map(([source, count]) => (
              <div key={source} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text>{source}</Text>
                  <Text type="secondary">{count}</Text>
                </div>
                <Progress percent={((count / stats.total) * 100)} showInfo={false} strokeColor="#52c41a" />
              </div>
            ))}
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={24}>
          <Card title="24小时分布" size="small">
            <div style={{ display: 'flex', alignItems: 'flex-end', height: 100, gap: 4 }}>
              {Array.from({ length: 24 }, (_, i) => {
                const count = stats.time_distribution[i.toString()] || 0;
                const maxCount = Math.max(...Object.values(stats.time_distribution), 1);
                const height = (count / maxCount) * 80 + 20;
                return (
                  <Tooltip key={i} title={`${i}:00 - ${count}次`}>
                    <div
                      style={{
                        flex: 1,
                        height: `${height}%`,
                        backgroundColor: i === new Date().getHours() ? '#1890ff' : '#91caff',
                        borderRadius: 4,
                        minWidth: 8,
                        cursor: 'pointer',
                        transition: 'background-color 0.3s'
                      }}
                    />
                  </Tooltip>
                );
              })}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 11 }}>0:00</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>12:00</Text>
              <Text type="secondary" style={{ fontSize: 11 }}>23:00</Text>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 24 }}>
      <Card
        title={
          <Space>
            <BulbOutlined />
            <span>智能问答</span>
          </Space>
        }
        extra={
          <Space>
            <RangePicker
              value={dateRange}
              onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
              size="small"
              style={{ marginRight: 8 }}
            />
            <Button icon={<HistoryOutlined />} onClick={clearHistory}>
              清除历史
            </Button>
          </Space>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ height: '100%' }}
          tabBarStyle={{ padding: '0 24px', marginBottom: 0 }}
          items={[
            { key: 'chat', label: '对话', children: renderChatTab() },
            { key: 'stats', label: '问数统计', children: renderStatsTab() }
          ]}
        />
      </Card>
    </div>
  );
}