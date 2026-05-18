import React, { useState, useEffect } from 'react';
import { Layout, Typography, Button, Avatar, Empty, Tooltip, message, Divider, Modal, List, Tag } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, PlusOutlined, DeleteOutlined, SettingOutlined, LeftOutlined, RightOutlined, StarOutlined, HistoryOutlined, ThunderboltOutlined, ArrowRightOutlined } from '@ant-design/icons';
import { useQAI } from '../hooks/useQAI';
import type { QAMessage } from '../hooks/useQAI';
import { useSession } from '../hooks/useSession';
import type { Session } from '../hooks/useSession';
import { colors } from '../../shared/styles/colors';
import { useWorkspace, useScenario, useRightPanel } from '../../shared';
import { css } from '@emotion/css';

const { Sider, Content } = Layout;
const { Text } = Typography;

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

    &:hover {
      background: #f3f4f6;
    }

    &.active {
      background: rgba(99, 102, 241, 0.1);
      border-color: rgba(99, 102, 241, 0.2);
    }
  }

  .session-avatar {
    width: 20px;
    height: 20px;
    border-radius: 10px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 14px;
  }

  .session-info {
    flex: 1;
    min-width: 0;
  }

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

    &:hover {
      color: #ff4d4f;
    }
  }

  .session-item:hover .session-delete {
    opacity: 1;
  }

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

  .sidebar-footer {
    padding: 16px;
    border-top: 1px solid #e5e7eb;
  }

  .quick-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .quick-action-btn {
    padding: 6px 12px;
    font-size: 12px;
    background: #f3f4f6;
    border: none;
    color: #4b5563;
    border-radius: 16px;
    transition: all 0.2s ease;

    &:hover {
      background: #e5e7eb;
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

    &:hover {
      background: #f9fafb;
    }
  }
`;

function Sidebar({ 
  sessions, 
  activeSessionId, 
  onSelectSession, 
  onNewSession, 
  onDeleteSession,
  isCollapsed,
  onToggleCollapse 
}: {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (session: Session) => void;
  onNewSession: () => void;
  onDeleteSession: (sessionId: string) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
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
            <StarOutlined style={{ fontSize: 20, color: '#667eea' }} />
            <Text style={{ fontSize: 16, fontWeight: 600, color: '#1f2937' }}>智能问答</Text>
          </div>
        )}
        {!isCollapsed && (
          <div className="sidebar-actions">
            <Tooltip title="设置">
              <Button type="text" icon={<SettingOutlined />} style={{ color: '#6b7280' }} />
            </Tooltip>
          </div>
        )}
      </div>

      <div className="sidebar-menu">
        {!isCollapsed && (
          <Button 
            className="new-chat-btn" 
            icon={<PlusOutlined />} 
            onClick={onNewSession}
          >
            新对话
          </Button>
        )}
        {isCollapsed && (
          <Button 
            icon={<PlusOutlined />} 
            onClick={onNewSession}
            style={{ 
              width: '100%', 
              background: 'rgba(255,255,255,0.1)',
              border: 'none',
              color: 'white',
              marginTop: 16
            }}
          />
        )}

        <Divider style={{ margin: '6px 0', borderColor: 'rgba(255,255,255,0.08)' }} />

        <div className="session-list">
          {sessions.length === 0 ? (
            !isCollapsed && (
              <Empty 
                description={
                  <Text style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12 }}>
                    暂无对话记录
                  </Text>
                }
                image={null}
              />
            )
          ) : (
            sessions.map((session) => (
              <div
                key={session.session_id}
                className={`session-item ${activeSessionId === session.session_id ? 'active' : ''}`}
                onClick={() => onSelectSession(session)}
              >
                {/* <div className="session-avatar">
                  <StarOutlined style={{ fontSize: 16 }} />
                </div> */}
                {!isCollapsed && (
                  <>
                    <div className="session-info">
                      <div className="session-title">
                        {session.summary || '未命名对话'}
                      </div>
                      <div className="session-meta">
                        {session.message_count} 条消息 · {formatDate(session.created_at)}
                      </div>
                    </div>
                    <button
                      className="session-delete"
                      onClick={(e) => handleDelete(e, session.session_id)}
                    >
                      <DeleteOutlined />
                    </button>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {!isCollapsed && (
        <div className="sidebar-footer">
          <Text style={{ color: 'rgba(255,255,255,0.5)', fontSize: 11, display: 'block', marginBottom: 8 }}>
            快捷操作
          </Text>
          <div className="quick-actions">
            <button className="quick-action-btn">写邮件</button>
            <button className="quick-action-btn">写报告</button>
            <button className="quick-action-btn">翻译</button>
            <button className="quick-action-btn">总结</button>
          </div>
        </div>
      )}

      <button className="collapse-btn" onClick={onToggleCollapse}>
        {isCollapsed ? <RightOutlined /> : <LeftOutlined />}
      </button>
    </Sider>
  );
}

const chatHeaderStyles = css`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 10px;
  min-height: 50px;
  border-bottom: 1px solid #f0f0f0;
  background: white;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .header-title {
    text-align: left;
    font-size: 16px;
    font-weight: 600;
    color: #1f2937;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  @media (max-width: 576px) {
    padding: 16px;
  }
`;

function ChatHeader({ 
  sessionId, 
  sessionTitle,
  onClear, 
  isLoading 
}: { 
  sessionId: string | null;
  sessionTitle: string;
  onClear: () => void; 
  isLoading: boolean; 
}) {
  return (
    <div className={chatHeaderStyles}>
      <div className="header-left">
        <Avatar 
          icon={<StarOutlined />} 
          style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }} 
        />
        <div>
          <div className="header-title">{sessionTitle || '新对话'}</div>
          {sessionId && (
            <Text style={{ fontSize: 12, color: '#9ca3af' }}>
              会话 ID: {sessionId}
            </Text>
          )}
        </div>
      </div>
      <div className="header-actions">
        <Tooltip title="清除对话">
          <Button 
            type="text" 
            icon={<DeleteOutlined />} 
            onClick={onClear}
            loading={isLoading}
            danger
          >
            清除
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

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

    &.user {
      flex-direction: row-reverse;
    }

    &.assistant {
      flex-direction: row;
    }
  }

  .message-avatar {
    flex-shrink: 0;
    width: 40px;
    height: 40px;
  }

  .message-content {
    max-width: 65%;
    margin: 0 12px;

    @media (max-width: 576px) {
      max-width: 80%;
    }
  }

  .message-bubble {
    padding: 14px 18px;
    border-radius: 16px;
    position: relative;

    &.user {
      background: linear-gradient(135deg, ${colors.primary} 0%, #4096ff 100%);
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

  .message-meta {
    margin-top: 8px;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .message-time {
    font-size: 11px;
    color: #9ca3af;
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
  }

  .source-excerpt {
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
    padding: 60px 20px;
  }

  .welcome-icon {
    width: 80px;
    height: 80px;
    margin: 0 auto 20px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 40px;
  }

  .welcome-title {
    font-size: 24px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 8px;
  }

  .welcome-desc {
    color: #6b7280;
    font-size: 14px;
    margin-bottom: 32px;
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
    transition: all 0.2s ease;

    &:hover {
      background: #e5e7eb;
    }
  }

  @keyframes fadeIn {
    from {
      opacity: 0;
      transform: translateY(10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  @keyframes dotPulse {
    0%, 80%, 100% {
      transform: scale(0.6);
      opacity: 0.5;
    }
    40% {
      transform: scale(1);
      opacity: 1;
    }
  }
`;

function MessageList({ messages, isLoading }: { messages: QAMessage[]; isLoading: boolean }) {
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

  const sampleQuestions = [
    '解释一下量子计算的基本原理',
    '写一篇关于人工智能的短文',
    '如何学习 Python 编程',
    '推荐一些经典电影',
  ];

  if (messages.length === 0 && !isLoading) {
    return (
      <div className={messageListStyles}>
        <div className="welcome-section">
          <div className="welcome-icon">
            <StarOutlined />
          </div>
          <div className="welcome-title">智能问答助手</div>
          <div className="welcome-desc">
            有什么我可以帮助您的吗？
          </div>
          <div className="welcome-actions">
            {sampleQuestions.map((q, idx) => (
              <button 
                key={idx} 
                className="welcome-btn"
                onClick={() => {
                  const event = new CustomEvent('askQuestion', { detail: q });
                  window.dispatchEvent(event);
                }}
              >
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
              icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
              style={{
                background: msg.role === 'user' ? colors.primary : '#6b7280',
              }}
            />
            <div className="message-content">
              <div className={`message-bubble ${msg.role}`}>
                <div className="message-text">{msg.content}</div>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="message-sources">
                    <div className="sources-title">参考来源</div>
                    {msg.sources.slice(0, 3).map((source, idx) => (
                      <div key={idx} className="source-card">
                        <div className="source-excerpt">{source.excerpt}</div>
                        <div className="source-info">
                          <span>来源: {source.source || '未知'}</span>
                          <span>置信度: {(source.confidence * 100).toFixed(0)}%</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="message-meta">
                <span className="message-time">{formatTime(msg.timestamp)}</span>
              </div>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="message-item assistant">
            <Avatar
              className="message-avatar"
              icon={<RobotOutlined />}
              style={{ background: '#6b7280' }}
            />
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

const chatInputStyles = css`
  padding: 20px 24px;
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
      border-color: ${colors.primary};
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

    &:focus {
      outline: none;
    }

    &::placeholder {
      color: #9ca3af;
    }
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

  .stop-button {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .input-hint {
    max-width: 900px;
    margin: 10px auto 0;
    font-size: 12px;
    color: #9ca3af;
    text-align: center;
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

    &:hover {
      background-color: #f3f4f6;
    }
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

    &:hover {
      color: #6b7280;
      background-color: #f3f4f6;
    }

    svg {
      width: 16px;
      height: 16px;
    }
  }

  @media (max-width: 576px) {
    padding: 16px;

    .input-hint {
      display: none;
    }
  }
`;

function useInputHistory() {
  const [history, setHistory] = React.useState<string[]>(() => {
    const stored = localStorage.getItem('qa_input_history');
    return stored ? JSON.parse(stored) : [];
  });
  const [historyIndex, setHistoryIndex] = React.useState(-1);

  React.useEffect(() => {
    localStorage.setItem('qa_input_history', JSON.stringify(history));
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
    
    let newIndex: number;
    if (historyIndex === -1) {
      newIndex = 0;
    } else if (historyIndex < history.length - 1) {
      newIndex = historyIndex + 1;
    } else {
      newIndex = historyIndex;
    }
    setHistoryIndex(newIndex);
    return history[newIndex];
  };

  const getNext = (currentValue: string): string => {
    if (historyIndex === -1) return currentValue;
    
    let newIndex: number;
    if (historyIndex > 0) {
      newIndex = historyIndex - 1;
    } else {
      newIndex = -1;
      return '';
    }
    setHistoryIndex(newIndex);
    return history[newIndex];
  };

  const clearHistory = () => {
    setHistory([]);
    setHistoryIndex(-1);
  };

  return {
    history,
    historyIndex,
    addToHistory,
    getPrevious,
    getNext,
    clearHistory,
  };
}

function ChatInput({ 
  value, 
  onChange, 
  onSend, 
  onStop, 
  isLoading 
}: { 
  value: string; 
  onChange: (value: string) => void; 
  onSend: () => void; 
  onStop?: () => void;
  isLoading: boolean; 
}) {
  const inputRef = React.useRef<HTMLTextAreaElement>(null);
  const [showHistoryDropdown, setShowHistoryDropdown] = React.useState(false);
  const { history, addToHistory, getPrevious, getNext } = useInputHistory();

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      const newValue = getPrevious(value);
      onChange(newValue);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      const newValue = getNext(value);
      onChange(newValue);
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

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
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
            <Button 
              type="text" 
              size="small" 
              onClick={() => setShowHistoryDropdown(false)}
            >
              关闭
            </Button>
          </div>
          <div className="history-list">
            {history.slice(0, 20).map((item, index) => (
              <div
                key={index}
                className="history-item"
                onClick={() => handleSelectHistory(item)}
              >
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
            onChange={handleChange}
            onKeyPress={handleKeyPress}
            onKeyDown={handleKeyDown}
            placeholder="输入您的问题..."
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
          <Button
            className="stop-button"
            danger
            icon={<SendOutlined />}
            onClick={onStop}
          />
        ) : (
          <Button
            className="send-button"
            type="primary"
            icon={<SendOutlined />}
            onClick={() => {
              addToHistory(value);
              onSend();
            }}
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

const pageStyles = css`
  height: 100%;
  background: #ffffff;
  overflow: hidden;
  margin: 0;
  padding: 0;
`;

export function QAChatPage({ className, style }: { className?: string; style?: React.CSSProperties }) {
  const [input, setInput] = useState('');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [selectedSessionTitle, setSelectedSessionTitle] = useState('');
  const [, setSuggestions] = useState<Array<{ action: string; skill: string; confidence: number }>>([]);
  
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
    onSessionUpdate: () => {
      fetchSessions(currentWorkspace, currentScenario);
    },
  });

  // 当收到 AI 回复时，更新右栏内容
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant' && lastMessage.content) {
        // 生成示例建议（实际应该从 AI 回复中解析）
        const mockSuggestions = generateSuggestions(lastMessage.content);
        setSuggestions(mockSuggestions);
        
        // 更新右栏内容
        if (mockSuggestions.length > 0) {
          setRightPanelTitle('执行建议');
          setRightPanelContent(
            <SuggestionPanel 
              suggestions={mockSuggestions} 
              onExecute={(skill) => {
                message.info(`执行 Skill: ${skill}`);
              }}
            />
          );
          setShowRightPanel(true);
        }
      }
    }
  }, [messages]);

  // 生成建议的函数（应该根据 AI 回复内容智能生成）
  const generateSuggestions = (content: string): Array<{ action: string; skill: string; confidence: number }> => {
    const suggestions: Array<{ action: string; skill: string; confidence: number }> = [];
    
    // 简单的关键词匹配生成建议
    if (content.includes('部队') || content.includes('单位')) {
      suggestions.push({
        action: '查询部队位置信息',
        skill: 'location_query',
        confidence: 0.9
      });
    }
    if (content.includes('分析') || content.includes('评估')) {
      suggestions.push({
        action: '生成态势分析报告',
        skill: 'analysis_report',
        confidence: 0.85
      });
    }
    if (content.includes('威胁') || content.includes('风险')) {
      suggestions.push({
        action: '威胁评估',
        skill: 'threat_assessment',
        confidence: 0.88
      });
    }
    if (content.includes('推荐') || content.includes('建议')) {
      suggestions.push({
        action: '获取行动建议',
        skill: 'action_recommendation',
        confidence: 0.82
      });
    }
    
    // 始终添加一个通用查询建议
    if (suggestions.length < 3) {
      suggestions.push({
        action: '查询本体图谱',
        skill: 'ontology_search',
        confidence: 0.75
      });
    }
    
    return suggestions.slice(0, 4); // 最多返回 4 条建议
  };

  React.useEffect(() => {
    const handleAskQuestion = (e: Event) => {
      const event = e as CustomEvent<string>;
      setInput(event.detail);
    };
    window.addEventListener('askQuestion', handleAskQuestion);
    return () => window.removeEventListener('askQuestion', handleAskQuestion);
  }, []);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    sendMessage(input);
    setInput('');
  };

  const handleStop = () => {
    stop();
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
    setSelectedSessionTitle(session.summary || '智能问答');
  };

  const handleDeleteSession = (deletedSessionId: string) => {
    deleteSession(deletedSessionId);
    if (deletedSessionId === sessionId) {
      clearMessages();
      setSelectedSessionTitle('');
    }
  };

  return (
    <Layout className={`${pageStyles} ${className || ''}`} style={style}>
      <Sidebar
        sessions={sessions}
        activeSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />
      <Content style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <ChatHeader
          sessionId={sessionId}
          sessionTitle={selectedSessionTitle}
          onClear={handleClear}
          isLoading={isLoading}
        />
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onStop={handleStop}
          isLoading={isLoading}
        />
      </Content>
    </Layout>
  );
}

// 建议面板组件
interface SuggestionPanelProps {
  suggestions: Array<{ action: string; skill: string; confidence: number }>;
  onExecute: (skill: string) => void;
}

function SuggestionPanel({ suggestions, onExecute }: SuggestionPanelProps) {
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
                <Button 
                  type="link" 
                  size="small" 
                  icon={<ArrowRightOutlined />}
                  style={{ padding: 0, height: 'auto' }}
                >
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