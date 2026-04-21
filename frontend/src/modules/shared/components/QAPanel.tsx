import { useState, useRef, useEffect } from 'react';
import { Card, Input, Button, Space, Typography, List, Avatar } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { TextArea } = Input;

interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  sources?: Array<{
    node_id?: string;
    edge_id?: string;
    text?: string;
  }>;
}

interface QAPanelProps {
  workspaceId?: string;
  style?: React.CSSProperties;
}

export const QAPanel: React.FC<QAPanelProps> = ({ workspaceId, style }) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: `msg-${Date.now()}-user`,
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch(`${import.meta.env.VITE_API_BASE || 'http://localhost:8000'}/api/qa/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: input,
          workspace_id: workspaceId,
        }),
      });

      const data = await response.json();

      const assistantMessage: Message = {
        id: `msg-${Date.now()}-assistant`,
        role: 'assistant',
        content: data.answer || 'Sorry, I could not process your question.',
        timestamp: new Date().toISOString(),
        sources: data.sources || [],
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: Message = {
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: 'Failed to get answer. Please try again.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
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

  return (
    <Card style={style} bodyStyle={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 0 }}>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px' }}>
        <List
          dataSource={messages}
          renderItem={(message) => (
            <List.Item
              style={{
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                border: 'none',
              }}
            >
              <Space direction={message.role === 'user' ? 'horizontal' : 'horizontal'} align="start">
                {message.role !== 'user' && (
                  <Avatar icon={<RobotOutlined />} style={{ backgroundColor: '#1677ff' }} />
                )}
                <Card
                  size="small"
                  style={{
                    maxWidth: '70%',
                    backgroundColor: message.role === 'user' ? '#1677ff' : '#f5f5f5',
                    color: message.role === 'user' ? 'white' : 'inherit',
                  }}
                >
                  <div>{message.content}</div>
                  {message.sources && message.sources.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>Sources:</Text>
                      {message.sources.map((source, idx) => (
                        <div key={idx} style={{ fontSize: 12 }}>
                          <a href={`/graph?node=${source.node_id}`}>
                            {source.text || `Node ${source.node_id}`}
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </Card>
                {message.role === 'user' && (
                  <Avatar icon={<UserOutlined />} style={{ backgroundColor: '#52c41a' }} />
                )}
              </Space>
            </List.Item>
          )}
        />
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '16px', borderTop: '1px solid #f0f0f0' }}>
        <Space.Compact style={{ width: '100%' }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask a question... (Press Enter to send)"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            disabled={!input.trim()}
          >
            Send
          </Button>
        </Space.Compact>
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            Press Enter to send, Shift+Enter for new line
          </Text>
        </div>
      </div>
    </Card>
  );
};