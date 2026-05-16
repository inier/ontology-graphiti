import { useState, useEffect, useRef } from 'react';
import { Card, Input, Button, Avatar, Spin, Empty, Tag, message } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { agentApi } from '../services/agentApi';
import type { Agent } from '../types';

interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: string;
}

export function AgentChat() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!agentId) return;
    loadAgent();
  }, [agentId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadAgent = async () => {
    setLoading(true);
    try {
      const data = await agentApi.getAgent(agentId!);
      setAgent(data);
      setMessages([
        {
          id: 'welcome',
          role: 'agent',
          content: `你好！我是 ${data.display_name}，专注于${data.main_object}相关的问题。有什么可以帮助你的吗？`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (e) {
      message.error('加载智能体信息失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!inputText.trim() || sending) return;

    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputText.trim(),
      timestamp: new Date().toISOString(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setSending(true);

    setTimeout(() => {
      const agentMsg: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: `收到你的问题："${userMsg.content}"。我正在基于${agent?.main_object || ''}知识图谱进行分析...`,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, agentMsg]);
      setSending(false);
    }, 1500);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!agent) {
    return (
      <Empty description="智能体不存在" style={{ marginTop: 120 }}>
        <Button type="primary" onClick={() => navigate('/my-agents')}>
          返回智能体列表
        </Button>
      </Empty>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 80px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px', borderBottom: '1px solid #f0f0f0', background: '#fff' }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/my-agents')} />
        <Avatar src={agent.avatar} size={40} />
        <div>
          <div style={{ fontWeight: 600, fontSize: 16 }}>{agent.display_name}</div>
          <Tag size="small" color="blue">{agent.main_object}</Tag>
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: 16, background: '#f5f7fa' }}>
        {messages.map(msg => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginBottom: 16,
              gap: 8,
            }}
          >
            {msg.role === 'agent' && <Avatar src={agent.avatar} size={36} />}
            <div
              style={{
                maxWidth: '70%',
                padding: '10px 14px',
                borderRadius: 12,
                background: msg.role === 'user' ? '#1890ff' : '#fff',
                color: msg.role === 'user' ? '#fff' : '#333',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                lineHeight: 1.6,
              }}
            >
              {msg.content}
            </div>
            {msg.role === 'user' && <Avatar icon={<UserOutlined />} size={36} style={{ background: '#52c41a' }} />}
          </div>
        ))}
        {sending && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <Avatar src={agent.avatar} size={36} />
            <div style={{ padding: '10px 14px', background: '#fff', borderRadius: 12, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
              <Spin size="small" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0', background: '#fff', display: 'flex', gap: 8 }}>
        <Input.TextArea
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          placeholder={`向 ${agent.display_name} 提问...`}
          autoSize={{ minRows: 1, maxRows: 4 }}
          onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); handleSend(); } }}
          style={{ flex: 1 }}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={sending} disabled={!inputText.trim()}>
          发送
        </Button>
      </div>
    </div>
  );
}
