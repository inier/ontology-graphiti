import { useCallback, useState, useRef, useEffect } from 'react';
import { message } from 'antd';
import { useChatStorage } from './useChatStorage';
import { apiClient } from '@/modules/shared/services/apiClient';

export type ChartSpec = {
  chart_type: 'line' | 'bar' | 'pie' | 'scatter' | 'heatmap' | 'radar' | 'map' | 'network';
  title?: string;
  data: Record<string, unknown>;
  render_mode?: string;
};

export type TemporalCard = {
  time_type: string;
  valid_time: string;
  answer: string;
  entity_count?: number;
};

export type ReportLink = {
  report_id: string;
  title: string;
  summary?: string;
  created_at?: string;
};

export type QAMessage = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: Array<{ source: string; excerpt: string; confidence: number }>;
  intent?: { type: string; confidence: number };
  charts?: ChartSpec[];
  temporal?: TemporalCard[];
  reports?: ReportLink[];
  thinking?: string;
  clarification?: { questions: string[]; reason: string };
  reasoning?: Array<{ step: string; description: string }>;
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
  // T050-fix: 暴露 setMessages 让外部（如会话切换时）直接替换消息列表
  setMessages: React.Dispatch<React.SetStateAction<QAMessage[]>>;
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
      const data = await apiClient.get(`/api/qa/sessions/${id}`);
      
      if (data.messages && Array.isArray(data.messages)) {
        setMessages(data.messages.map((msg: any) => ({
          id: msg.id || msg.message_id || generateId(),
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          timestamp: msg.timestamp || new Date().toISOString(),
          sources: msg.sources,
          intent: msg.intent,
          charts: msg.charts,
          temporal: msg.temporal,
          reports: msg.reports,
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
      const response = await apiClient.stream('/api/qa/ask/stream', {
        question: content,
        session_id: sessionId,
        workspace_id: workspaceId,
        scenario_id: scenarioId,
        agent_id: agentId,
      }, { signal: abortControllerRef.current.signal });

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('无法读取响应流');
      }

      const decoder = new TextDecoder('utf-8');
      let accumulatedContent = '';
      let receivedSessionId = sessionId;
      let messageId = generateId();
      let sseBuffer = '';

      setMessages(prev => [...prev, {
        id: messageId,
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
      }]);

      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        sseBuffer += chunk;

        // 解析SSE事件：以 \n\n 分隔，每行以 "data: " 开头
        const eventParts = sseBuffer.split('\n\n');
        // 最后一段可能不完整，保留在buffer中
        sseBuffer = eventParts.pop() || '';

        for (const part of eventParts) {
          if (streamDone) break;
          const lines = part.split('\n');
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const jsonStr = line.slice(6);

            try {
              const data = JSON.parse(jsonStr);

              if (data.type === 'session_id') {
                receivedSessionId = data.value;
                if (!sessionId) {
                  setSessionIdState(data.value);
                }
              } else if (data.type === 'thinking') {
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    return [
                      ...prev.slice(0, lastIndex),
                      { ...prev[lastIndex], thinking: data.value },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'reasoning') {
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    const existing = prev[lastIndex].reasoning || [];
                    return [
                      ...prev.slice(0, lastIndex),
                      {
                        ...prev[lastIndex],
                        reasoning: [...existing, data.value],
                        thinking: data.value.description || prev[lastIndex].thinking,
                      },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'clarification') {
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    const questions = data.value?.questions || [];
                    const reason = data.value?.reason || '';
                    return [
                      ...prev.slice(0, lastIndex),
                      {
                        ...prev[lastIndex],
                        clarification: { questions, reason },
                        thinking: undefined,
                        content: questions.length > 0
                          ? questions.map((q: string, i: number) => `${i + 1}. ${q}`).join('\n')
                          : '请提供更多信息以便我准确回答您的问题。',
                      },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'content') {
                accumulatedContent += data.value;
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    return [
                      ...prev.slice(0, lastIndex),
                      { ...prev[lastIndex], content: accumulatedContent },
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
                      { ...prev[lastIndex], sources: data.value },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'chart') {
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    const existing = prev[lastIndex].charts || [];
                    return [
                      ...prev.slice(0, lastIndex),
                      { ...prev[lastIndex], charts: [...existing, data.value] },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'temporal') {
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    const existing = prev[lastIndex].temporal || [];
                    return [
                      ...prev.slice(0, lastIndex),
                      { ...prev[lastIndex], temporal: [...existing, data.value] },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'report') {
                setMessages(prev => {
                  const lastIndex = prev.length - 1;
                  if (lastIndex >= 0 && prev[lastIndex].role === 'assistant') {
                    const existing = prev[lastIndex].reports || [];
                    return [
                      ...prev.slice(0, lastIndex),
                      { ...prev[lastIndex], reports: [...existing, data.value] },
                    ];
                  }
                  return prev;
                });
              } else if (data.type === 'end' || data.type === 'done') {
                streamDone = true;
                break;
              }
            } catch {
              // 非JSON行，忽略
            }
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
    setMessages, // T050-fix: 让 QAChatPage 切换会话时直接替换消息
    clearMessages,
    stop,
  };
}
