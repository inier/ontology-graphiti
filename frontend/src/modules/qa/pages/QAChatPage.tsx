import React, { useRef, useEffect, useState } from 'react';
import { Card, Typography, Button, Avatar, Spin, Tag, Badge, Empty, Tooltip, message } from 'antd';
import { SendOutlined, UserOutlined, RobotOutlined, ClearOutlined, BulbOutlined, LinkOutlined, StopOutlined, HistoryOutlined } from '@ant-design/icons';
import { useQAI } from '../hooks/useQAI';
import type { QAMessage } from '../hooks/useQAI';
import { SessionDrawer } from '../components/SessionDrawer';
import type { Session } from '../hooks/useSession';
import { useBreakpoint } from '../../shared/utils/responsive';
import { colors } from '../../shared/styles/colors';
import { css } from '@emotion/css';

const { Text, Title } = Typography;

interface ChatHeaderProps {
  sessionId: string | null;
  onClear: () => void;
  onShowHistory: () => void;
  isLoading: boolean;
}

const headerStyles = css`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px 12px 0 0;

  .header-title {
    display: flex;
    align-items: center;
    gap: 10px;
    color: white;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  @media (max-width: 576px) {
    padding: 12px 16px;

    .header-title h4 {
      font-size: 16px;
    }
  }
`;

function ChatHeader({ sessionId, onClear, onShowHistory, isLoading }: ChatHeaderProps) {
  const breakpoint = useBreakpoint();

  return (
    <div className={headerStyles}>
      <div className="header-title">
        <BulbOutlined style={{ fontSize: 20 }} />
        <Title level={4} style={{ margin: 0, color: 'white' }}>
          智能问答
        </Title>
        {sessionId && (
          <Tag color="gold" style={{ marginLeft: 8 }}>
            会话: {sessionId.slice(0, 8)}...
          </Tag>
        )}
      </div>
      <div className="header-actions">
        <Tooltip title="查看历史会话">
          <Button
            type="text"
            icon={<HistoryOutlined />}
            onClick={onShowHistory}
            style={{ color: 'white' }}
          >
            {!breakpoint.isMobile && '历史'}
          </Button>
        </Tooltip>
        <Tooltip title="清除对话历史">
          <Button
            type="text"
            icon={<ClearOutlined />}
            onClick={onClear}
            loading={isLoading}
            style={{ color: 'white' }}
          >
            {!breakpoint.isMobile && '清除'}
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

interface MessageListProps {
  messages: QAMessage[];
  isLoading: boolean;
}

const messageListStyles = css`
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  background: #fafafa;

  .message-item {
    display: flex;
    margin-bottom: 16px;
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
  }

  .message-content {
    max-width: 70%;
    margin: 0 12px;

    @media (max-width: 576px) {
      max-width: 85%;
    }
  }

  .message-bubble {
    padding: 12px 16px;
    border-radius: 12px;
    position: relative;

    &.user {
      background: linear-gradient(135deg, ${colors.primary} 0%, #4096ff 100%);
      color: white;
      border-bottom-right-radius: 4px;
    }

    &.assistant {
      background: white;
      border: 1px solid #e8e8e8;
      border-bottom-left-radius: 4px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    }
  }

  .message-text {
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .message-meta {
    margin-top: 6px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .message-time {
    font-size: 11px;
    opacity: 0.7;
  }

  .message-sources {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.2);
  }

  .message-sources-title {
    font-size: 11px;
    margin-bottom: 6px;
    opacity: 0.8;
  }

  .source-tag {
    margin: 4px 4px 4px 0;
    font-size: 11px;
  }

  .loading-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: white;
    border-radius: 12px;
    border-bottom-left-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
    max-width: 200px;
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
`;

function MessageList({ messages, isLoading }: MessageListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  };

  const renderSources = (sources: QAMessage['sources']) => {
    if (!sources || sources.length === 0) return null;

    return (
      <div className="message-sources">
        <div className="message-sources-title">参考来源:</div>
        {sources.slice(0, 3).map((source, idx) => (
          <Tag key={idx} className="source-tag" icon={<LinkOutlined />}>
            {source.source}: {source.excerpt?.slice(0, 40)}...
          </Tag>
        ))}
      </div>
    );
  };

  return (
    <div ref={listRef} className={messageListStyles}>
      {messages.length === 0 && !isLoading ? (
        <Empty
          description="开始对话吧！问我任何问题。"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <>
          {messages.map((msg) => (
            <div key={msg.id} className={`message-item ${msg.role}`}>
              <Avatar
                className="message-avatar"
                icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                style={{
                  background: msg.role === 'user' ? colors.primary : colors.secondary,
                }}
              />
              <div className="message-content">
                <div className={`message-bubble ${msg.role}`}>
                  <div className="message-text">{msg.content}</div>
                  {msg.sources && renderSources(msg.sources)}
                </div>
                <div className="message-meta">
                  <span className="message-time">{formatTime(msg.timestamp)}</span>
                  {msg.intent && (
                    <Tag color="blue" style={{ fontSize: 10 }}>
                      意图: {msg.intent.type}
                    </Tag>
                  )}
                  {msg.sources && msg.sources.length > 0 && (
                    <Badge count={msg.sources.length} size="small" style={{ fontSize: 10 }} />
                  )}
                </div>
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message-item assistant">
              <Avatar
                className="message-avatar"
                icon={<RobotOutlined />}
                style={{ background: colors.secondary }}
              />
              <div className="message-content">
                <div className="loading-indicator">
                  <Spin size="small" />
                  <Text type="secondary">思考中...</Text>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  isLoading: boolean;
}

const chatInputStyles = css`
  padding: 16px 20px;
  border-top: 1px solid #f0f0f0;
  background: white;

  .input-container {
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }

  .input-wrapper {
    flex: 1;
    display: flex;
    gap: 8px;
    background: #f5f5f5;
    border-radius: 12px;
    padding: 8px 12px;
    border: 2px solid transparent;
    transition: all 0.3s ease;

    &:focus-within {
      border-color: ${colors.primary};
      background: white;
      box-shadow: 0 0 0 3px rgba(24, 144, 255, 0.1);
    }
  }

  .chat-input {
    flex: 1;
    border: none;
    background: transparent;
    resize: none;
    font-size: 14px;
    line-height: 1.5;
    max-height: 120px;
    padding: 4px 0;

    &:focus {
      box-shadow: none;
    }
  }

  .send-button {
    flex-shrink: 0;
    height: 40px;
    width: 40px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s ease;
  }

  .input-hint {
    margin-top: 8px;
    font-size: 11px;
    color: #8c8c8c;
    text-align: center;
  }

  @media (max-width: 576px) {
    padding: 12px 16px;

    .input-hint {
      display: none;
    }
  }
`;

function ChatInput({ value, onChange, onSend, onStop, isLoading }: ChatInputProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading) {
        onSend();
      }
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value);
  };

  useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isLoading]);

  return (
    <div className={chatInputStyles}>
      <div className="input-container">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={value}
            onChange={handleChange}
            onKeyPress={handleKeyPress}
            placeholder="输入您的问题，按 Enter 发送..."
            rows={1}
            disabled={isLoading}
          />
        </div>
        {isLoading ? (
          <Button
            className="send-button"
            danger
            icon={<StopOutlined />}
            onClick={onStop}
          />
        ) : (
          <Button
            className="send-button"
            type="primary"
            icon={<SendOutlined />}
            onClick={onSend}
            disabled={!value.trim()}
          />
        )}
      </div>
      <div className="input-hint">
        按 Enter 发送，Shift + Enter 换行
      </div>
    </div>
  );
}

interface QAChatPageProps {
  className?: string;
  style?: React.CSSProperties;
}

const pageStyles = css`
  display: flex;
  flex-direction: column;
  height: 100%;
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  overflow: hidden;

  .page-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
`;

export function QAChatPage({ className, style }: QAChatPageProps) {
  const [input, setInput] = React.useState('');
  const [sessionDrawerOpen, setSessionDrawerOpen] = useState(false);
  const { messages, sendMessage, isLoading, sessionId, setSessionId, clearMessages, stop } = useQAI();

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
    message.success('对话历史已清除');
  };

  const handleShowHistory = () => {
    setSessionDrawerOpen(true);
  };

  const handleSelectSession = (session: Session) => {
    setSessionId(session.session_id);
    message.success(`已加载会话: ${session.summary || session.session_id}`);
  };

  return (
    <Card className={`${pageStyles} ${className || ''}`} style={style} styles={{ body: { padding: 0, height: '100%', display: 'flex', flexDirection: 'column' } }}>
      <ChatHeader
        sessionId={sessionId}
        onClear={handleClear}
        onShowHistory={handleShowHistory}
        isLoading={isLoading}
      />
      <div className="page-content">
        <MessageList messages={messages} isLoading={isLoading} />
        <ChatInput
          value={input}
          onChange={setInput}
          onSend={handleSend}
          onStop={handleStop}
          isLoading={isLoading}
        />
      </div>
      <SessionDrawer
        open={sessionDrawerOpen}
        onClose={() => setSessionDrawerOpen(false)}
        onSelectSession={handleSelectSession}
      />
    </Card>
  );
}
