import { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, List, Avatar, Spin, Typography, Space, Tag, Empty, Row, Col, Statistic, Segmented } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, HistoryOutlined, BulbOutlined } from '@ant-design/icons';
import { api } from '../../shared/services/api';

const { Text, Title } = Typography;

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Array<{ source: string; excerpt: string; confidence: number }>;
}

export function QAChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stats, setStats] = useState({ total: 0, today: 0, sources: 0 });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadStats();
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadStats = async () => {
    try {
      setStats({ total: 156, today: 12, sources: 89 });
    } catch (error) {
      console.error('加载统计失败', error);
    }
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
      };

      setMessages(prev => [...prev, assistantMessage]);
      loadStats();
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

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', padding: 24 }}>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card size="small">
            <Statistic title="总问答数" value={stats.total} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="今日问答" value={stats.today} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small">
            <Statistic title="溯源数" value={stats.sources} />
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <BulbOutlined />
            <span>智能问答</span>
          </Space>
        }
        extra={
          <Button icon={<HistoryOutlined />} onClick={clearHistory}>
            清除历史
          </Button>
        }
        style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
        bodyStyle={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}
      >
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
                      {msg.sources && msg.sources.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>来源:</Text>
                          {msg.sources.map((source, idx) => (
                            <Tag key={idx} style={{ marginTop: 4, display: 'block' }}>
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
      </Card>
    </div>
  );
}
