import type { FC, CSSProperties } from 'react';
import { useState, useRef, useEffect } from 'react';
import { List, Avatar as AntAvatar } from 'antd';
import adapter from '../adapter';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

interface ChatPanelProps {
  messages?: ChatMessage[];
  onSend?: (message: string) => void;
  loading?: boolean;
  placeholder?: string;
  title?: string;
  className?: string;
  style?: CSSProperties;
}

const AdapterButton = adapter.getButton();
const AdapterInput = adapter.getInput();

const ChatPanel: FC<ChatPanelProps> = ({
  messages = [],
  onSend,
  loading = false,
  placeholder = 'Type a message...',
  title,
  className,
  style,
}) => {
  const [inputValue, setInputValue] = useState('');
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      const scrollEl = listRef.current.querySelector('.ant-list-items');
      if (scrollEl) {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }
    }
  }, [messages]);

  const handleSend = () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    onSend?.(trimmed);
    setInputValue('');
  };

  const getAvatarProps = (role: ChatMessage['role']) => {
    switch (role) {
      case 'user':
        return { style: { backgroundColor: '#1677ff' }, children: 'U' };
      case 'assistant':
        return { style: { backgroundColor: '#52c41a' }, children: 'A' };
      case 'system':
        return { style: { backgroundColor: '#faad14' }, children: 'S' };
    }
  };

  return (
    <div className={className} style={{ display: 'flex', flexDirection: 'column', height: '100%', ...style }}>
      {title && (
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0', fontWeight: 600 }}>
          {title}
        </div>
      )}
      <div ref={listRef} style={{ flex: 1, overflow: 'auto', padding: '0 16px' }}>
        <List
          dataSource={messages}
          renderItem={(item) => (
            <List.Item style={{ border: 'none', padding: '8px 0' }}>
              <List.Item.Meta
                avatar={<AntAvatar {...getAvatarProps(item.role)} size="small" />}
                title={
                  <span style={{ fontSize: 12, textTransform: 'capitalize' }}>
                    {item.role}
                    {item.timestamp && (
                      <span style={{ marginLeft: 8, color: '#999', fontWeight: 'normal' }}>
                        {item.timestamp}
                      </span>
                    )}
                  </span>
                }
                description={<span style={{ whiteSpace: 'pre-wrap' }}>{item.content}</span>}
              />
            </List.Item>
          )}
        />
      </div>
      <div style={{ display: 'flex', gap: 8, padding: '12px 16px', borderTop: '1px solid #f0f0f0' }}>
        <div style={{ flex: 1 }}>
          <AdapterInput
            value={inputValue}
            onChange={setInputValue}
            placeholder={placeholder}
            disabled={loading}
          />
        </div>
        <AdapterButton type="primary" onClick={handleSend} loading={loading} disabled={!inputValue.trim()}>
          Send
        </AdapterButton>
      </div>
    </div>
  );
};

export default ChatPanel;
