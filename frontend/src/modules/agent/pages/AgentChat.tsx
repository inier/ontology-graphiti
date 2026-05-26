import React, { useState, useEffect, useRef } from 'react';
import { Layout, Typography, Button, Avatar, Empty, Tooltip, message, Divider, Tag, Space, List, Modal } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, PlusOutlined, DeleteOutlined, SettingOutlined, LeftOutlined, RightOutlined, StarOutlined, HistoryOutlined, ThunderboltOutlined, ArrowLeftOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import { agentApi } from '../services/agentApi';
import { useQAI } from '../../qa/hooks/useQAI';
import { useSession } from '../../qa/hooks/useSession';
import type { Session } from '../../qa/hooks/useSession';
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

const sidebarStyles = css`
  background: #ffffff !important;
  border-right: 1px solid #e5e7eb;
  overflow: hidden;
  display: flex;
  flex-direction: column;

  .sidebar-header {
    padding: 0 10px;
    min-height: 50px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid #e5e7eb;
  }

  .sidebar-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: #1f2937;
  }

  .sidebar-actions {
    display: flex;
    gap: 8px;
  }

  .sidebar-menu {
    flex: 1;
    overflow-y: auto;
    padding: 8px 12px;
  }

  .session-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .session-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 4px;
    border-radius: 3px;
    cursor: pointer;
    transition: all 0.2s ease;
    border: 1px solid transparent;

    &:hover { background: #f3f4f6; }
    &.active {
      background: rgba(99, 102, 241, 0.1);
      border-color: rgba(99, 102, 241, 0.2);
    }
  }

  .session-info { flex: 1; min-width: 0; }

  .session-title {
    font-size: 13px;
    color: #1f2937;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .session-meta {
    font-size: 11px;
    color: #9ca3af;
    margin-top: 2px;
  }

  .session-delete {
    opacity: 0;
    border-style: none;
    transition: opacity 0.2s ease;
    color: #9ca3af;
    &:hover { color: #ff4d4f; }
  }

  .session-item:hover .session-delete { opacity: 1; }

  .new-chat-btn {
    width: 100%;
    margin-top: 8px;
    border: 1px dashed #d1d5db;
    color: #4b5563;
    background: transparent;
    &:hover {
      background: #f3f4f6;
      border-color: #9ca3af;
    }
  }

  .collapse-btn {
    position: absolute;
    right: -12px;
    top: 50%;
    transform: translateY(-50%);
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: white;
    border: 1px solid #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
    z-index: 100;
    color: #6b7280;
    &:hover { background: #f9fafb; }
  }
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

  .sources-title {
    font-size: 12px;
    font-weight: 500;
    color: #6b7280;
    margin-bottom: 8px;
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
    position: relative;

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

  .send-button, .stop-button {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
  }

  .send-button:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
  }

  .history-button {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: #9ca3af;
    cursor: pointer;
    padding: 4px;
    border-radius: 6px;
    transition: all 0.2s;
    &:hover { color: #6b7280; background-color: #f3f4f6; }
    svg { width: 16px; height: 16px; }
  }

  .history-dropdown {
    position: absolute;
    bottom: 100%;
    left: 16px;
    right: 16px;
    margin-bottom: 8px;
    background: #ffffff;
    border-radius: 12px;
    box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
    border: 1px solid #e5e7eb;
    max-height: 300px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .history-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #e5e7eb;
    font-weight: 600;
    color: #1f2937;
    font-size: 14px;
  }

  .history-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
  }

  .history-item {
    padding: 10px 12px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    color: #374151;
    transition: background-color 0.2s;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    &:hover { background-color: #f3f4f6; }
  }

  .input-hint {
    max-width: 900px;
    margin: 8px auto 0;
    font-size: 12px;
    color: #9ca3af;
    text-align: center;
  }
`;

function useInputHistory() {
  const [history, setHistory] = React.useState<string[]>(() => {
    const stored = localStorage.getItem('agent_input_history');
    return stored ? JSON.parse(stored) : [];
  });
  const [historyIndex, setHistoryIndex] = React.useState(-1);

  React.useEffect(() => {
    localStorage.setItem('agent_input_history', JSON.stringify(history));
  }, [history]);

  const addToHistory = (text: string) => {
    if (!text.trim()) return;
    setHistory(prev => {
      const filtered = prev.filter(h => h !== text.trim());
      return [text.trim(), ...filtered].slice(0, 50);
    });
    setHistoryIndex(-1);
  };

  const getPrevious = (currentValue: string): string => {
    if (history.length === 0) return currentValue;
    const newIndex = historyIndex === -1 ? 0 : historyIndex < history.length - 1 ? historyIndex + 1 : historyIndex;
    setHistoryIndex(newIndex);
    return history[newIndex];
  };

  const getNext = (currentValue: string): string => {
    if (historyIndex === -1) return currentValue;
    if (historyIndex > 0) {
      const newIndex = historyIndex - 1;
      setHistoryIndex(newIndex);
      return history[newIndex];
    }
    setHistoryIndex(-1);
    return '';
  };

  return { history, addToHistory, getPrevious, getNext };
}

function AgentSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  isCollapsed,
  onToggleCollapse,
  agent,
}: {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (session: Session) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  agent: Agent;
}) {
  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    if (hours < 1) return '刚刚';
    if (hours < 24) return `${hours}小时前`;
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  const handleDelete = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    Modal.confirm({
      title: '确认删除',
      content: '确定要删除这个会话吗？',
      onOk: () => {
        onDeleteSession(sessionId);
        message.success('会话已删除');
      },
    });
  };

  return (
    <Sider
      className={sidebarStyles}
      width={isCollapsed ? 0 : 220}
      collapsed={isCollapsed}
      style={{ position: 'relative' }}
    >
      <div className="sidebar-header">
        {!isCollapsed && (
          <div className="sidebar-title">
            <Avatar src={agent.avatar} size={24} />
            <Text style={{ fontSize: 14, fontWeight: 600, color: '#1f2937' }}>{agent.display_name}</Text>
          </div>
        )}
        {!isCollapsed && (
          <div className="sidebar-actions">
            <Tooltip title="新对话">
              <Button type="text" icon={<PlusOutlined />} style={{ color: '#6b7280' }} onClick={onNewSession} />
            </Tooltip>
          </div>
        )}
      </div>

      <div className="sidebar-menu">
        {!isCollapsed && (
          <Button className="new-chat-btn" icon={<PlusOutlined />} onClick={onNewSession}>
            新对话
          </Button>
        )}

        <Divider style={{ margin: '6px 0', borderColor: '#e5e7eb' }} />

        <div className="session-list">
          {sessions.length === 0 ? (
            !isCollapsed && (
              <Empty
                description={<Text style={{ color: '#9ca3af', fontSize: 12 }}>暂无对话记录</Text>}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            )
          ) : (
            sessions.map((session) => (
              <div
                key={session.session_id}
                className={`session-item ${activeSessionId === session.session_id ? 'active' : ''}`}
                onClick={() => onSelectSession(session)}
              >
                {!isCollapsed && (
                  <>
                    <div className="session-info">
                      <div className="session-title">{session.summary || '未命名对话'}</div>
                      <div className="session-meta">
                        {session.message_count} 条消息 · {formatDate(session.created_at)}
                      </div>
                    </div>
                    <button className="session-delete" onClick={(e) => handleDelete(e, session.session_id)}>
                      <DeleteOutlined />
                    </button>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <button className="collapse-btn" onClick={onToggleCollapse}>
        {isCollapsed ? <RightOutlined /> : <LeftOutlined />}
      </button>
    </Sider>
  );
}

function AgentChatHeader({
  agent,
  sessionId,
  sessionTitle,
  onClear,
  isLoading,
  onBack,
}: {
  agent: Agent;
  sessionId: string | null;
  sessionTitle: string;
  onClear: () => void;
  isLoading: boolean;
  onBack: () => void;
}) {
  const contextCount = (agent.related_processes?.length || 0) +
    (agent.related_rules?.length || 0) +
    (agent.related_skills?.length || 0) +
    (agent.related_indicators?.length || 0);

  return (
    <div className={chatHeaderStyles}>
      <div className="header-left">
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={onBack} />
        <Avatar src={agent.avatar} size={40} />
        <div>
          <div className="header-title">{sessionTitle || agent.display_name}</div>
          <div className="header-subtitle">
            主对象: {agent.main_object}
            {contextCount > 0 && <span> · 关联 {contextCount} 项业务配置</span>}
            {sessionId && <span> · {sessionId.slice(0, 8)}</span>}
          </div>
        </div>
      </div>
      <div className="header-actions">
        <Tooltip title="清除对话">
          <Button type="text" icon={<DeleteOutlined />} onClick={onClear} loading={isLoading} danger>
            清除
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

function AgentMessageList({
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
              style={{ background: msg.role === 'user' ? '#1890ff' : undefined }}
            />
            <div className="message-content">
              <div className={`message-bubble ${msg.role}`}>
                <div className="message-text">{msg.content}</div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources">
                    <div className="sources-title">参考来源</div>
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
                  <span></span><span></span><span></span>
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

function AgentChatInput({
  value,
  onChange,
  onSend,
  onStop,
  isLoading,
  agent,
}: {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  isLoading: boolean;
  agent: Agent;
}) {
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const [showHistoryDropdown, setShowHistoryDropdown] = React.useState(false);
  const { history, addToHistory, getPrevious, getNext } = useInputHistory();

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      onChange(getPrevious(value));
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      onChange(getNext(value));
    } else if (e.key === 'Escape') {
      setShowHistoryDropdown(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) {
        addToHistory(value);
        onSend();
      }
    }
  };

  const handleSelectHistory = (text: string) => {
    onChange(text);
    setShowHistoryDropdown(false);
    inputRef.current?.focus();
  };

  React.useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]);

  return (
    <div className={chatInputStyles}>
      {showHistoryDropdown && history.length > 0 && (
        <div className="history-dropdown">
          <div className="history-header">
            <span>历史记录</span>
            <Button type="text" size="small" onClick={() => setShowHistoryDropdown(false)}>关闭</Button>
          </div>
          <div className="history-list">
            {history.slice(0, 20).map((item, index) => (
              <div key={index} className="history-item" onClick={() => handleSelectHistory(item)}>
                {item}
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="input-container">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={value}
            onChange={e => onChange(e.target.value)}
            onKeyPress={handleKeyPress}
            onKeyDown={handleKeyDown}
            placeholder={`向 ${agent.display_name} 提问...`}
            rows={1}
            disabled={isLoading}
          />
          <button
            className="history-button"
            onClick={() => setShowHistoryDropdown(!showHistoryDropdown)}
            title="历史记录"
          >
            <HistoryOutlined />
          </button>
        </div>
        {isLoading ? (
          <Button className="stop-button" danger icon={<SendOutlined />} onClick={onStop} />
        ) : (
          <Button
            className="send-button"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => { addToHistory(value); onSend(); }}
            disabled={!value.trim()}
          />
        )}
      </div>
      <div className="input-hint">
        按 Enter 发送，Shift + Enter 换行，↑↓ 切换历史
      </div>
    </div>
  );
}

function SuggestionPanel({
  suggestions,
  onExecute,
}: {
  suggestions: Array<{ action: string; skill: string; confidence: number }>;
  onExecute: (skill: string) => void;
}) {
  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return 'green';
    if (confidence >= 0.8) return 'blue';
    if (confidence >= 0.7) return 'orange';
    return 'default';
  };

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          基于当前问答，推荐以下执行动作：
        </Typography.Text>
      </div>
      <List
        size="small"
        dataSource={suggestions}
        renderItem={(item, index) => (
          <List.Item
            key={index}
            style={{
              padding: '12px 8px',
              cursor: 'pointer',
              borderRadius: 8,
              marginBottom: 8,
              border: '1px solid #f0f0f0',
              transition: 'all 0.2s',
            }}
            onClick={() => onExecute(item.skill)}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = '#f5f5f5';
              e.currentTarget.style.borderColor = '#1890ff';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent';
              e.currentTarget.style.borderColor = '#f0f0f0';
            }}
          >
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <ThunderboltOutlined style={{ color: '#1890ff' }} />
                <Typography.Text strong style={{ fontSize: 13 }}>{item.action}</Typography.Text>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                <Tag color="processing" style={{ fontSize: 11, marginRight: 0 }}>{item.skill}</Tag>
                <Tag color={getConfidenceColor(item.confidence)} style={{ fontSize: 11, marginRight: 0 }}>
                  {(item.confidence * 100).toFixed(0)}% 置信度
                </Tag>
              </div>
              <div style={{ marginTop: 8 }}>
                <Button type="link" size="small" icon={<ArrowRightOutlined />} style={{ padding: 0, height: 'auto' }}>
                  执行
                </Button>
              </div>
            </div>
          </List.Item>
        )}
      />
      <Divider style={{ margin: '16px 0' }} />
      <div>
        <Typography.Text type="secondary" style={{ fontSize: 11 }}>
          点击建议可直接执行对应 Skill 操作
        </Typography.Text>
      </div>
    </div>
  );
}

function generateSuggestedQuestions(agent: Agent): string[] {
  const questions: string[] = [];
  const mainObj = agent.main_object || '业务';
  const rl = (id: string) => agent.ref_labels?.[id] || id;
  questions.push(`介绍一下${mainObj}的基本情况`);
  if (agent.related_processes && agent.related_processes.length > 0) {
    questions.push(`${rl(agent.related_processes[0])}的执行流程是什么？`);
  }
  if (agent.related_rules && agent.related_rules.length > 0) {
    questions.push(`${rl(agent.related_rules[0])}有哪些关键规则？`);
  }
  if (agent.related_indicators && agent.related_indicators.length > 0) {
    questions.push(`如何分析${rl(agent.related_indicators[0])}？`);
  }
  if (agent.related_skills && agent.related_skills.length > 0) {
    questions.push(`使用${rl(agent.related_skills[0])}技能帮我分析`);
  }
  if (questions.length < 3) {
    questions.push(`${mainObj}相关的最新动态有哪些？`);
  }
  return questions.slice(0, 4);
}

function generateAgentSuggestions(
  content: string,
  agent: Agent | null,
): Array<{ action: string; skill: string; confidence: number }> {
  const suggestions: Array<{ action: string; skill: string; confidence: number }> = [];
  if (!agent) return suggestions;

  const rl = (id: string) => agent.ref_labels?.[id] || id;

  if (agent.related_skills && agent.related_skills.length > 0) {
    suggestions.push({
      action: `使用 ${rl(agent.related_skills[0])} 技能`,
      skill: agent.related_skills[0],
      confidence: 0.9,
    });
  }

  if (content.includes('分析') || content.includes('评估')) {
    if (agent.related_indicators && agent.related_indicators.length > 0) {
      suggestions.push({
        action: `查看 ${rl(agent.related_indicators[0])} 指标`,
        skill: 'indicator_analysis',
        confidence: 0.85,
      });
    }
  }

  if (content.includes('流程') || content.includes('过程')) {
    if (agent.related_processes && agent.related_processes.length > 0) {
      suggestions.push({
        action: `查看 ${rl(agent.related_processes[0])} 流程`,
        skill: 'process_detail',
        confidence: 0.88,
      });
    }
  }

  if (content.includes('规则') || content.includes('条件')) {
    if (agent.related_rules && agent.related_rules.length > 0) {
      suggestions.push({
        action: `查看 ${rl(agent.related_rules[0])} 规则`,
        skill: 'rule_detail',
        confidence: 0.82,
      });
    }
  }

  if (suggestions.length < 3) {
    suggestions.push({
      action: '查询本体图谱',
      skill: 'ontology_search',
      confidence: 0.75,
    });
  }

  return suggestions.slice(0, 4);
}

export function AgentChat() {
  const { agentId } = useParams<{ agentId: string }>();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [input, setInput] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [selectedSessionTitle, setSelectedSessionTitle] = useState('');

  const { currentWorkspace } = useWorkspace();
  const { currentScenario } = useScenario();
  const { setShowRightPanel, setRightPanelContent, setRightPanelTitle } = useRightPanel();

  const { sessions, fetchSessions, deleteSession } = useSession({
    workspaceId: currentWorkspace,
    scenarioId: currentScenario,
  });

  const { messages, sendMessage, isLoading, sessionId, setSessionId, clearMessages, stop } = useQAI({
    workspaceId: currentWorkspace,
    scenarioId: currentScenario,
    agentId: agentId,
    onSessionUpdate: () => {
      fetchSessions(currentWorkspace, currentScenario);
    },
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
            <SuggestionPanel
              suggestions={suggestions}
              onExecute={(skill) => { message.info(`执行 Skill: ${skill}`); }}
            />
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
    setSelectedSessionTitle('');
    message.success('对话历史已清除');
  };

  const handleNewSession = () => {
    clearMessages();
    setSelectedSessionTitle('');
    setSessionId(null);
    message.info('已创建新对话');
  };

  const handleSelectSession = (session: Session) => {
    setSessionId(session.session_id);
    setSelectedSessionTitle(session.summary || agent?.display_name || '智能问答');
  };

  const handleDeleteSession = (deletedSessionId: string) => {
    deleteSession(deletedSessionId);
    if (deletedSessionId === sessionId) {
      clearMessages();
      setSelectedSessionTitle('');
    }
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

  const rl = (id: string) => agent.ref_labels?.[id] || id;

  const agentContextTags = [
    ...(agent.related_processes || []).map(p => ({ label: rl(p), color: 'green' })),
    ...(agent.related_rules || []).map(r => ({ label: rl(r), color: 'orange' })),
    ...(agent.related_business_logic || []).map(l => ({ label: rl(l), color: 'cyan' })),
    ...(agent.related_indicators || []).map(i => ({ label: rl(i), color: 'volcano' })),
    ...(agent.related_skills || []).map(s => ({ label: rl(s), color: 'purple' })),
  ];

  const suggestedQuestions = generateSuggestedQuestions(agent);

  return (
    <Layout className={pageStyles}>
      <AgentSidebar
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        agent={agent}
      />
      <Content style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <AgentChatHeader
          agent={agent}
          sessionId={sessionId}
          sessionTitle={selectedSessionTitle}
          onClear={handleClear}
          isLoading={isLoading}
          onBack={() => navigate('/my-agents')}
        />
        <AgentMessageList
          messages={messages}
          isLoading={isLoading}
          agent={agent}
          contextTags={agentContextTags}
          suggestedQuestions={suggestedQuestions}
          onAskQuestion={(q) => { setInput(q); sendMessage(q); }}
        />
        <AgentChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onStop={stop}
          isLoading={isLoading}
          agent={agent}
        />
      </Content>
    </Layout>
  );
}
