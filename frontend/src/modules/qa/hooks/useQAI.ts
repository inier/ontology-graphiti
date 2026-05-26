import { useCallback, useState, useRef, useEffect } from 'react';
import { message } from 'antd';
import { useChatStorage } from './useChatStorage';

const API_BASE = import.meta.env.VITE_API_BASE || '';
const API_ENDPOINT = `${API_BASE}/api/qa/ask`;
const SESSIONS_ENDPOINT = `${API_BASE}/api/qa/sessions`;
const STREAM_API_ENDPOINT = `${API_BASE}/api/qa/ask/stream`;

export type QAMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Array<{ source: string; excerpt: string; confidence: number }>;
  intent?: { type: string; confidence: number };
}

export type UseQAIOptions = {
  sessionId?: string;
  workspaceId?: string;
  scenarioId?: string;
  agentId?: string;
  onError?: (error: Error) => void;
  onSessionUpdate?: () => void;
}

export type UseQAIReturn = {
  messages: QAMessage[];
  sendMessage: (content: string) => void;
  status: 'idle' | 'submitting' | 'streaming' | 'error' | 'waiting_for_input';
  isLoading: boolean;
  error: Error | null;
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  clearMessages: () => void;
  stop: () => void;
}

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function createUserMessage(content: string): QAMessage {
  return {
    id: generateId(),
    role: 'user',
    content,
    timestamp: new Date().toISOString(),
  };
}

function createAssistantMessage(
  content: string,
  sources?: Array<{ source: string; excerpt: string; confidence: number }>
): QAMessage {
  return {
    id: generateId(),
    role: 'assistant',
    content,
    timestamp: new Date().toISOString(),
    sources,
  };
}

export function useQAI({ sessionId: initialSessionId, workspaceId, scenarioId, agentId, onError, onSessionUpdate }: UseQAIOptions = {}): UseQAIReturn {
  const [sessionId, setSessionIdState] = useState<string | null>(initialSessionId || null);
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [status, setStatus] = useState<'idle' | 'submitting' | 'streaming' | 'error' | 'waiting_for_input'>('idle');
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isRestoredRef = useRef(false);

  const { loadState, persistMessages, clearState } = useChatStorage(sessionId);

  useEffect(() => {
    if (isRestoredRef.current) return;
    isRestoredRef.current = true;

    const stored = loadState();
    if (stored && stored.messages.length > 0) {
      setMessages(stored.messages);
      if (stored.sessionId) {
        setSessionIdState(stored.sessionId);
      }
    }
  }, [loadState]);

  useEffect(() => {
    if (!isRestoredRef.current) return;
    if (messages.length === 0) return;
    persistMessages(messages, sessionId);
  }, [messages, sessionId, persistMessages]);

  const setSessionId = useCallback(async (id: string | null) => {
    if (!id) {
      setSessionIdState(null);
      setMessages([]);
      return;
    }

    setStatus('submitting');
    try {
      const response = await fetch(`${SESSIONS_ENDPOINT}/${id}`);
      if (!response.ok) {
        throw new Error(`加载会话失败: ${response.status}`);
      }
      const data = await response.json();
      
      if (data.messages && Array.isArray(data.messages)) {
        setMessages(data.messages.map((msg: any) => ({
          id: msg.id || msg.message_id || generateId(),
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: msg.timestamp || new Date().toISOString(),
          sources: msg.sources,
          intent: msg.intent,
        })));
      } else {
        setMessages([]);
      }
      setSessionIdState(id);
      message.success('会话已加载');
    } catch (err) {
      const error = err instanceof Error ? err : new Error('加载会话失败');
      message.error(error.message);
    } finally {
      setStatus('idle');
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setSessionIdState(null);
    setError(null);
    setStatus('idle');
    clearState();
  }, [clearState]);

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setStatus('idle');
    }
  }, []);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || status === 'submitting' || status === 'streaming') return;

    const userMessage = createUserMessage(content);
    setMessages(prev => [...prev, userMessage]);
    setStatus('streaming');
    setError(null);

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(STREAM_API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: content,
          session_id: sessionId,
          workspace_id: workspaceId,
          scenario_id: scenarioId,
          agent_id: agentId,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法读取响应流');
      }

      const decoder = new TextDecoder('utf-8');
      let accumulatedContent = '';
      let receivedSessionId = sessionId;
      let messageId = generateId();

      setMessages(prev => [...prev, {
        id: messageId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      }]);

      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        
        const lines = chunk.split('\n');
        for (const line of lines) {
          if (line.trim() === '') continue;
          
          try {
            const data = JSON.parse(line);
            
            if (data.type === 'session_id') {
              receivedSessionId = data.value;
              if (!sessionId) {
                setSessionIdState(data.value);
              }
            } else if (data.type === 'content') {
              accumulatedContent += data.value;
              setMessages(prev => {
                const lastIndex = prev.length - 1;
                if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                  return [
                    ...prev.slice(0, lastIndex),
                    {
                      ...prev[lastIndex],
                      content: accumulatedContent,
                    },
                  ];
                }
                return prev;
              });
            } else if (data.type === 'sources') {
              setMessages(prev => {
                const lastIndex = prev.length - 1;
                if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                  return [
                    ...prev.slice(0, lastIndex),
                    {
                      ...prev[lastIndex],
                      sources: data.value,
                    },
                  ];
                }
                return prev;
              });
            } else if (data.type === 'end') {
              break;
            }
          } catch (e) {
            accumulatedContent += line;
            setMessages(prev => {
              const lastIndex = prev.length - 1;
              if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                return [
                  ...prev.slice(0, lastIndex),
                  {
                    ...prev[lastIndex],
                    content: accumulatedContent,
                  },
                ];
              }
              return prev;
            });
          }
        }
      }

      setStatus('idle');
      
      if (!sessionId && receivedSessionId) {
        setSessionIdState(receivedSessionId);
        onSessionUpdate?.();
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setStatus('idle');
        return;
      }
      
      const error = err instanceof Error ? err : new Error('发送消息失败');
      setError(error);
      setStatus('error');
      onError?.(error);
      message.error(error.message || '发生错误，请重试');
      
      setMessages(prev => {
        const lastIndex = prev.length - 1;
        if (lastIndex >= 0 && prev[lastIndex].role === 'assistant' && !prev[lastIndex].content) {
          return [...prev.slice(0, lastIndex), createAssistantMessage('抱歉，请求失败，请重试')];
        }
        return prev;
      });
    }
  }, [sessionId, status, onError, workspaceId, scenarioId, agentId]);

  return {
    messages,
    sendMessage,
    status,
    isLoading: status === 'submitting' || status === 'streaming',
    error,
    sessionId,
    setSessionId,
    clearMessages,
    stop,
  };
}