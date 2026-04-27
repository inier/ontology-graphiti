import { useCallback, useState, useRef, useEffect } from 'react';
import { message } from 'antd';
import { useChatStorage } from './useChatStorage';

const API_ENDPOINT = 'http://localhost:8000/api/qa/ask';

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
  onError?: (error: Error) => void;
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

export function useQAI({ sessionId: initialSessionId, onError }: UseQAIOptions = {}): UseQAIReturn {
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

  const setSessionId = useCallback((id: string | null) => {
    setSessionIdState(id);
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
    if (!content.trim() || status === 'submitting') return;

    const userMessage = createUserMessage(content);
    setMessages(prev => [...prev, userMessage]);
    setStatus('submitting');
    setError(null);

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: content,
          session_id: sessionId,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`请求失败: ${response.status}`);
      }

      const data = await response.json();

      if (data.session_id && !sessionId) {
        setSessionIdState(data.session_id);
      }

      const assistantMessage = createAssistantMessage(
        data.answer || '抱歉，我没有得到有效的回答。',
        data.sources
      );
      setMessages(prev => [...prev, assistantMessage]);
      setStatus('idle');
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
    }
  }, [sessionId, status, onError]);

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
