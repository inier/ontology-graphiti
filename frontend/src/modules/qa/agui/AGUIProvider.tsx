/**
 * AGUIProvider — AG-UI Protocol SSE 客户端
 *
 * v2.0 架构：纯薄适配层（不引入 @ag-ui/core）
 * - 使用浏览器原生 EventSource 订阅后端 SSE
 * - 解析 AG-UI 17 类 Event 为 React 状态
 * - 提供 runAgent() / resume() 方法
 *
 * 后端 endpoint: POST /api/ag-ui/run (SSE response)
 *
 * 关键不变量：
 * - 0 修改现有 useQAI / QAIProvider（共存）
 * - 0 新增 npm 依赖
 * - 0 修改 OpenHarness
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import type { AGUIEvent, Interrupt, Message, ResumeEntry, RunAgentInput } from './agui_types';

export interface AGUIProviderConfig {
  /** API 基础 URL（如 http://localhost:8000）默认从 VITE_API_BASE 取 */
  apiBase?: string;
  /** Bearer token（JWT） */
  token?: string;
  /** 工作空间 ID（用于 OPA 鉴权） */
  workspaceId?: string;
  /** 客户端发出的所有事件（订阅此 stream 接收 AG-UI 事件） */
  onEvent?: (event: AGUIEvent) => void;
  /** 自动重连（默认 true） */
  autoReconnect?: boolean;
  /** SSE 心跳超时（默认 60s） */
  heartbeatTimeoutMs?: number;
}

export interface AGUIContextValue {
  /** 当前 run 状态 */
  status: 'idle' | 'streaming' | 'interrupted' | 'error' | 'cancelled';
  /** 累积的事件流（最近 1000 个） */
  events: AGUIEvent[];
  /** 当前 messageId → 已累积文本 */
  messages: Map<string, { role: string; content: string; toolCalls?: Array<{ id: string; name: string; result?: string }> }>;
  /** 当前挂起的 interrupts（等待用户响应） */
  pendingInterrupts: Interrupt[];
  /** 错误 */
  error: Error | null;
  /** 发起新 run（可携带 resume） */
  runAgent: (input: RunAgentInput) => void;
  /** 响应 interrupt（自动构造下一个 run 携带 resume） */
  resume: (interruptId: string, response: Record<string, unknown>) => void;
  /** 取消当前 run */
  cancel: () => void;
  /** 清空状态 */
  clear: () => void;
}

const AGUIContext = createContext<AGUIContextValue | null>(null);

export function useAGUIContext(): AGUIContextValue {
  const ctx = useContext(AGUIContext);
  if (!ctx) {
    throw new Error('useAGUIContext must be used within AGUIProvider');
  }
  return ctx;
}

export interface AGUIProviderProps extends AGUIProviderConfig {
  children: ReactNode;
}

const DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '';
const ENDPOINT = '/api/ag-ui/run';
const MAX_EVENTS = 1000;
const MAX_MESSAGES = 500;

export function AGUIProvider({
  children,
  apiBase = DEFAULT_API_BASE,
  token,
  workspaceId,
  onEvent,
  autoReconnect = true,
  heartbeatTimeoutMs = 60000,
}: AGUIProviderProps) {
  const [status, setStatus] = useState<AGUIContextValue['status']>('idle');
  const [events, setEvents] = useState<AGUIEvent[]>([]);
  const [messages, setMessages] = useState<AGUIContextValue['messages']>(new Map());
  const [pendingInterrupts, setPendingInterrupts] = useState<Interrupt[]>([]);
  const [error, setError] = useState<Error | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastInputRef = useRef<RunAgentInput | null>(null);

  // === 内部：应用单个 AG-UI 事件到状态 ===
  const applyEvent = useCallback(
    (event: AGUIEvent) => {
      // 调用外部 onEvent 回调
      onEvent?.(event);

      // 更新 events 流（限长）
      setEvents((prev) => {
        const next = [...prev, event];
        return next.length > MAX_EVENTS ? next.slice(-MAX_EVENTS) : next;
      });

      // 更新 messages
      if (event.type === 'TEXT_MESSAGE_CONTENT') {
        setMessages((prev) => {
          const next = new Map(prev);
          const existing = next.get(event.messageId) || { role: 'assistant', content: '' };
          next.set(event.messageId, { ...existing, content: existing.content + event.delta });
          return next;
        });
      } else if (event.type === 'TOOL_CALL_RESULT') {
        setMessages((prev) => {
          const next = new Map(prev);
          const existing = next.get(event.toolCallId) || { role: 'tool', content: '' };
          next.set(event.toolCallId, { ...existing, content: event.content });
          return next;
        });
      } else if (event.type === 'MESSAGES_SNAPSHOT') {
        // 用快照覆盖（一般是 run 开始时）
        const map = new Map<string, { role: string; content: string }>();
        for (const msg of event.messages) {
          if (msg.content) {
            map.set(msg.id, { role: msg.role, content: msg.content });
          }
        }
        setMessages(map);
      }

      // 处理 run 状态
      if (event.type === 'RUN_STARTED') {
        setStatus('streaming');
        setError(null);
      } else if (event.type === 'RUN_FINISHED') {
        if (typeof event.outcome === 'object' && event.outcome.type === 'interrupt') {
          setStatus('interrupted');
          setPendingInterrupts(event.outcome.interrupts);
        } else if (typeof event.outcome === 'object' && event.outcome.type === 'error') {
          setStatus('error');
          setError(new Error(event.outcome.error));
        } else {
          setStatus('idle');
          setPendingInterrupts([]);
        }
      } else if (event.type === 'RUN_ERROR') {
        setStatus('error');
        setError(new Error(event.message));
      }
    },
    [onEvent],
  );

  // === 内部：发起 POST + 解析 SSE ===
  const streamRun = useCallback(
    async (input: RunAgentInput) => {
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const enrichedInput: RunAgentInput = {
          ...input,
          workspaceId: input.workspaceId || workspaceId || undefined,
        };

        const response = await fetch(`${apiBase}${ENDPOINT}`, {
          method: 'POST',
          headers,
          body: JSON.stringify(enrichedInput),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`AG-UI endpoint returned ${response.status}: ${response.statusText}`);
        }
        if (!response.body) {
          throw new Error('No response body for SSE');
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        // 心跳重置
        const resetHeartbeat = () => {
          if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current);
          heartbeatTimerRef.current = setTimeout(() => {
            controller.abort();
            setError(new Error('SSE heartbeat timeout'));
            setStatus('error');
          }, heartbeatTimeoutMs);
        };
        resetHeartbeat();

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            resetHeartbeat();

            buffer += decoder.decode(value, { stream: true });

            // SSE 事件以 \n\n 分隔
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';

            for (const evt of events) {
              // 跳过注释行
              const dataLines = evt
                .split('\n')
                .filter((l) => l.startsWith('data: '))
                .map((l) => l.slice('data: '.length))
                .join('');
              if (!dataLines) continue;
              try {
                const parsed = JSON.parse(dataLines) as AGUIEvent;
                applyEvent(parsed);
              } catch (e) {
                console.error('[AGUI] failed to parse SSE event:', e, dataLines);
              }
            }
          }
        } finally {
          if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current);
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setStatus('cancelled');
          return;
        }
        if (autoReconnect && lastInputRef.current && !(err instanceof Error && err.message.includes('401'))) {
          // 自动重连（仅 1 次）
          setTimeout(() => {
            if (lastInputRef.current) {
              void streamRun(lastInputRef.current);
            }
          }, 1000);
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
        setStatus('error');
      }
    },
    [apiBase, token, workspaceId, heartbeatTimeoutMs, autoReconnect, applyEvent],
  );

  // === 公开方法 ===

  const runAgent = useCallback(
    (input: RunAgentInput) => {
      // 清理旧状态
      setEvents([]);
      setMessages(new Map());
      setError(null);
      lastInputRef.current = input;
      void streamRun(input);
    },
    [streamRun],
  );

  const resume = useCallback(
    (interruptId: string, response: Record<string, unknown>) => {
      if (!lastInputRef.current) return;
      const resumeEntry: ResumeEntry = {
        interruptId,
        status: 'resolved',
        response,
      };
      const next: RunAgentInput = {
        ...lastInputRef.current,
        // 移除已 resolved 的 interrupt
        resume: [
          ...(lastInputRef.current.resume || []),
          resumeEntry,
        ],
      };
      // 从 pendingInterrupts 移除已响应
      setPendingInterrupts((prev) => prev.filter((i) => i.id !== interruptId));
      void streamRun(next);
    },
    [streamRun],
  );

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    setStatus('cancelled');
  }, []);

  const clear = useCallback(() => {
    setEvents([]);
    setMessages(new Map());
    setPendingInterrupts([]);
    setError(null);
    setStatus('idle');
  }, []);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
      if (heartbeatTimerRef.current) clearTimeout(heartbeatTimerRef.current);
    };
  }, []);

  const value = useMemo<AGUIContextValue>(
    () => ({
      status,
      events,
      messages,
      pendingInterrupts,
      error,
      runAgent,
      resume,
      cancel,
      clear,
    }),
    [status, events, messages, pendingInterrupts, error, runAgent, resume, cancel, clear],
  );

  return <AGUIContext.Provider value={value}>{children}</AGUIContext.Provider>;
}
