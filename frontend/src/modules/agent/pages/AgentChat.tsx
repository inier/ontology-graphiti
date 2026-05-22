import React, { useState, useEffect, useRef } from 'react';
import { Layout, Typography, Button, Avatar, Empty, Tooltip, message, Divider, Tag, Space } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, DeleteOutlined, ArrowLeftOutlined, StarOutlined, LeftOutlined, RightOutlined, HistoryOutlined, ThunderboltOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { agentApi } from '../services/agentApi';
import { useQAI } from '../../qa/hooks/useQAI';
import { useWorkspace, useScenario, useRightPanel } from '../../shared';
import { css } from '@emotion/css';
import type { Agent } from '../types';
import type { QAMessage } from '../../qa/hooks/useQAI';

const { Sider, Content } = Layout;
const { Text } = Typography;

const pageStyles = css`
  height: 100%;
  background: #ffffff;
  overflow: hidden;
  margin: 0;
  padding: 0;
`;

const chatHeaderStyles = css`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  min-height: 56px;
  border-bottom: 1px solid #f0f0f0;
  background: white;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-title {
    font-size: 16px;
    font-weight: 600;
    color: #1f2937;
  }

  .header-subtitle {
    font-size: 12px;
    color: #9ca3af;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }
`;

const messageListStyles = css`
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #fefefe;

  .message-wrapper {
    max-width: 900px;
    margin: 0 auto;
  }

  .message-item {
    display: flex;
    margin-bottom: 20px;
    animation: fadeIn 0.3s ease;

    &.user { flex-direction: row-reverse; }
    &.assistant { flex-direction: row; }
  }

  .message-avatar { flex-shrink: 0; width: 40px; height: 40px; }

  .message-content { max-width: 65%; margin: 0 12px; }

  .message-bubble {
    padding: 14px 18px;
    border-radius: 16px;
    position: relative;

    &.user {
      background: linear-gradient(135deg, #1890ff 0%, #4096ff 100%);
      color: white;
      border-bottom-right-radius: 4px;
      box-shadow: 0 4px 12px rgba(24, 144, 255, 0.2);
    }

    &.assistant {
      background: white;
      border: 1px solid #e5e7eb;
      border-bottom-left-radius: 4px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }
  }

  .message-text {
    line-height: 1.7;
    font-size: 14px;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .message-time {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 6px;
  }

  .message-sources {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(0, 0, 0, 0.06);
  }

  .source-card {
    background: #f9fafb;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    border: 1px solid #f3f4f6;
    font-size: 13px;
    color: #374151;
    line-height: 1.6;
  }

  .source-info {
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    color: #9ca3af;
  }

  .loading-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 18px;
    background: white;
    border-radius: 16px;
    border-bottom-left-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    max-width: 220px;
  }

  .thinking-dots {
    display: flex;
    gap: 4px;

    span {
      width: 6px;
      height: 6px;
      background: #9ca3af;
      border-radius: 50%;
      animation: dotPulse 1.4s infinite ease-in-out;

      &:nth-child(1) { animation-delay: 0s; }
      &:nth-child(2) { animation-delay: 0.2s; }
      &:nth-child(3) { animation-delay: 0.4s; }
    }
  }

  .welcome-section {
    text-align: center;
    padding: 48px 20px;
  }

  .welcome-title {
    font-size: 22px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 8px;
  }

  .welcome-desc {
    color: #6b7280;
    font-size: 14px;
    margin-bottom: 16px;
  }

  .welcome-tags {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 6px;
    margin-bottom: 24px;
  }

  .welcome-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 12px;
  }

  .welcome-btn {
    padding: 10px 20px;
    background: #f3f4f6;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    color: #374151;
    cursor: pointer;
    transition: all 0.2s ease;

    &:hover { background: #e5e7eb; }
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  @keyframes dotPulse {
    0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
    40% { transform: scale(1); opacity: 1; }
  }
`;

const chatInputStyles = css`
  padding: 16px 24px;
  border-top: 1px solid #f0f0f0;
  background: white;

  .input-container {
    max-width: 900px;
    margin: 0 auto;
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }

  .input-wrapper {
    flex: 1;
    display: flex;
    gap: 10px;
    background: #f9fafb;
    border-radius: 16px;
    padding: 8px 16px;
    border: 2px solid transparent;
    transition: all 0.3s ease;

    &:focus-within {
      border-color: #1890ff;
      background: white;
      box-shadow: 0 0 0 4px rgba(24, 144, 255, 0.1);
    }
  }

  .chat-input {
    flex: 1;
    border: none;
    background: transparent;
    resize: none;
    font-size: 14px;
    line-height: 1.6;
    max-height: 150px;
    padding: 6px 0;

    &:focus { outline: none; }
    &::placeholder { color: #9ca3af; }
  }

  .send-button {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;

    &:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
    }
  }

  .input-hint {
    max-width: 900px;
    margin: 8px auto 0;
    font-size: 12px;
    color: #9ca3af;
    text-align: center;
  }
`;

export function AgentChat() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');

  const { currentWorkspace } = useWorkspace();
  const { currentScenario } = useScenario();
  const { setShowRightPanel, setRightPanelContent, setRightPanelTitle } = useRightPanel();

  const { messages, sendMessage, isLoading, sessionId, setSessionId, clearMessages, stop } = useQAI({
    workspaceId: currentWorkspace,
    scenarioId: currentScenario,
    agentId: agentId,
    onSessionUpdate: () => {},
  });

  useEffect(() => {
    if (!agentId) return;
    loadAgent();
  }, [agentId]);

  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant' && lastMessage.content) {
        const suggestions = generateAgentSuggestions(lastMessage.content, agent);
        if (suggestions.length > 0) {
          setRightPanelTitle('执行建议');
          setRightPanelContent(
            <div>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                基于当前问答，推荐以下执行动作：
              </Typography.Text>
              <div style={{ marginTop: 12 }}>
                {suggestions.map((s, i) => (
                  <div key={i} style={{ padding: '8px 0', borderBottom: i < suggestions.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <ThunderboltOutlined style={{ color: '#1890ff', fontSize: 12 }} />
                      <Text strong style={{ fontSize: 13 }}>{s.action}</Text>
                    </div>
                    <div style={{ marginTop: 4, display: 'flex', gap: 6 }}>
                      <Tag color="processing" style={{ fontSize: 11, margin: 0 }}>{s.skill}</Tag>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
          setShowRightPanel(true);
        }
      }
    }
  }, [messages, agent]);

  const loadAgent = async () => {
    setLoading(true);
    try {
      const data = await agentApi.getAgent(agentId!);
      setAgent(data);
    } catch (e) {
      message.error('加载智能体信息失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input);
    setInput('');
  };

  const handleClear = () => {
    clearMessages();
    message.success('对话已清除');
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '60vh' }}>
        <Text type="secondary">加载中...</Text>
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

  const agentContextTags = [
    ...(agent.related_processes || []).map(p => ({ label: p, color: 'green' })),
    ...(agent.related_rules || []).map(r => ({ label: r, color: 'orange' })),
    ...(agent.related_business_logic || []).map(l => ({ label: l, color: 'cyan' })),
    ...(agent.related_indicators || []).map(i => ({ label: i, color: 'volcano' })),
    ...(agent.related_skills || []).map(s => ({ label: s, color: 'purple' })),
  ];

  const suggestedQuestions = generateSuggestedQuestions(agent);

  return (
    <Layout className={pageStyles}>
      <Content style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className={chatHeaderStyles}>
          <div className="header-left">
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/my-agents')} />
            <Avatar src={agent.avatar} size={40} />
            <div>
              <div className="header-title">{agent.display_name}</div>
              <div className="header-subtitle">
                主对象: {agent.main_object}
                {agentContextTags.length > 0 && (
                  <span> · 关联 {agentContextTags.length} 项业务配置</span>
                )}
              </div>
            </div>
          </div>
          <div className="header-actions">
            <Tooltip title="清除对话">
              <Button type="text" icon={<DeleteOutlined />} onClick={handleClear} danger>
                清除
              </Button>
            </Tooltip>
          </div>
        </div>

        <MessageList
          messages={messages}
          isLoading={isLoading}
          agent={agent}
          contextTags={agentContextTags}
          suggestedQuestions={suggestedQuestions}
          onAskQuestion={(q) => { setInput(q); sendMessage(q); }}
        />

        <div className={chatInputStyles}>
          <div className="input-container">
            <div className="input-wrapper">
              <textarea
                className="chat-input"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyPress={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder={`向 ${agent.display_name} 提问...`}
                rows={1}
                disabled={isLoading}
              />
            </div>
            <Button
              className="send-button"
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
            />
          </div>
          <div className="input-hint">
            按 Enter 发送，Shift + Enter 换行
          </div>
        </div>
      </Content>
    </Layout>
  );
}

function MessageList({
  messages,
  isLoading,
  agent,
  contextTags,
  suggestedQuestions,
  onAskQuestion,
}: {
  messages: QAMessage[];
  isLoading: boolean;
  agent: Agent;
  contextTags: Array<{ label: string; color: string }>;
  suggestedQuestions: string[];
  onAskQuestion: (q: string) => void;
}) {
  const listRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  if (messages.length === 0 && !isLoading) {
    return (
      <div ref={listRef} className={messageListStyles}>
        <div className="welcome-section">
          <Avatar src={agent.avatar} size={72} style={{ border: '3px solid #f0f0f0', marginBottom: 16 }} />
          <div className="welcome-title">{agent.display_name}</div>
          <div className="welcome-desc">
            {agent.description || `专注于${agent.main_object}相关问题的智能助手`}
          </div>
          {contextTags.length > 0 && (
            <div className="welcome-tags">
              {contextTags.slice(0, 8).map((tag, i) => (
                <Tag key={i} color={tag.color} style={{ fontSize: 12 }}>{tag.label}</Tag>
              ))}
              {contextTags.length > 8 && <Tag>+{contextTags.length - 8}</Tag>}
            </div>
          )}
          <div className="welcome-actions">
            {suggestedQuestions.map((q, idx) => (
              <button key={idx} className="welcome-btn" onClick={() => onAskQuestion(q)}>
                {q}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={listRef} className={messageListStyles}>
      <div className="message-wrapper">
        {messages.map((msg) => (
          <div key={msg.id} className={`message-item ${msg.role}`}>
            <Avatar
              className="message-avatar"
              icon={msg.role === 'user' ? <UserOutlined /> : undefined}
              src={msg.role === 'assistant' ? agent.avatar : undefined}
              style={{
                background: msg.role === 'user' ? '#1890ff' : undefined,
              }}
            />
            <div className="message-content">
              <div className={`message-bubble ${msg.role}`}>
                <div className="message-text">{msg.content}</div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources">
                    {msg.sources.slice(0, 3).map((source, idx) => (
                      <div key={idx} className="source-card">
                        <div>{source.excerpt}</div>
                        <div className="source-info">
                          <span>来源: {source.source || '未知'}</span>
                          <span>置信度: {(source.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="message-time">{formatTime(msg.timestamp)}</div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message-item assistant">
            <Avatar className="message-avatar" src={agent.avatar} />
            <div className="message-content">
              <div className="loading-indicator">
                <div className="thinking-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <Text type="secondary">正在思考...</Text>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function generateSuggestedQuestions(agent: Agent): string[] {
  const questions: string[] = [];
  const mainObj = agent.main_object || '业务';

  questions.push(`介绍一下${mainObj}的基本情况`);

  if (agent.related_processes && agent.related_processes.length > 0) {
    questions.push(`${agent.related_processes[0]}的执行流程是什么？`);
  }
  if (agent.related_rules && agent.related_rules.length > 0) {
    questions.push(`${agent.related_rules[0]}有哪些关键规则？`);
  }
  if (agent.related_indicators && agent.related_indicators.length > 0) {
    questions.push(`如何分析${agent.related_indicators[0]}？`);
  }
  if (agent.related_skills && agent.related_skills.length > 0) {
    questions.push(`使用${agent.related_skills[0]}技能帮我分析`);
  }

  if (questions.length < 3) {
    questions.push(`${mainObj}相关的最新动态有哪些？`);
  }

  return questions.slice(0, 4);
}

function generateAgentSuggestions(
  content: string,
  agent: Agent | null,
): Array<{ action: string; skill: string }> {
  const suggestions: Array<{ action: string; skill: string }> = [];

  if (!agent) return suggestions;

  if (agent.related_skills && agent.related_skills.length > 0) {
    suggestions.push({
      action: `使用 ${agent.related_skills[0]} 技能`,
      skill: agent.related_skills[0],
    });
  }

  if (content.includes('分析') || content.includes('评估')) {
    if (agent.related_indicators && agent.related_indicators.length > 0) {
      suggestions.push({
        action: `查看 ${agent.related_indicators[0]} 指标`,
        skill: 'indicator_analysis',
      });
    }
  }

  if (content.includes('流程') || content.includes('过程')) {
    if (agent.related_processes && agent.related_processes.length > 0) {
      suggestions.push({
        action: `查看 ${agent.related_processes[0]} 流程`,
        skill: 'process_detail',
      });
    }
  }

  if (content.includes('规则') || content.includes('条件')) {
    if (agent.related_rules && agent.related_rules.length > 0) {
      suggestions.push({
        action: `查看 ${agent.related_rules[0]} 规则`,
        skill: 'rule_detail',
      });
    }
  }

  suggestions.push({
    action: '查询本体图谱',
    skill: 'ontology_search',
  });

  return suggestions.slice(0, 4);
}
