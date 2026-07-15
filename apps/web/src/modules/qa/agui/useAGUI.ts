/**
 * useAGUI — AG-UI 协议 React Hook
 *
 * 用途：组件级使用 AG-UI 协议（无需 Provider 直接使用）。
 * 与 AGUIProvider 区别：
 * - AGUIProvider 适合在全局挂载一次
 * - useAGUI 适合每个组件独立订阅（更轻量）
 *
 * 零依赖：仅使用 fetch + EventSource 等浏览器 API
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { AGUIEvent, Interrupt, Message, RunAgentInput } from './agui_types';

export interface UseAGUIOptions {
  apiBase?: string;
  token?: string;
  workspaceId?: string;
}

export interface UseAGUIReturn {
  status: 'idle' | 'streaming' | 'interrupted' | 'error' | 'cancelled';
  /** 平铺的对话消息（assistant 累积文本 + user 原始 + tool 结果） */
  flatMessages: Array<{ id: string; role: string; content: string }>;
  /** tool_call 三件套信息 */
  toolCalls: Array<{ id: string; name: string; args: unknown; result?: string }>;
  /** 挂起 interrupt（用户需响应） */
  pendingInterrupts: Interrupt[];
  error: Error | null;
  /** 发送一条消息（自动构造 RunAgentInput） */
  send: (content: string, options?: { threadId?: string }) => void;
  /** 响应 interrupt */
  resume: (interruptId: string, response: Record<string, unknown>) => void;
  /** 取消 */
  cancel: () => void;
}

const DEFAULT_API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) || '';

function generateId(): string {
  return `id_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export function useAGUI(options: UseAGUIOptions = {}): UseAGUIReturn {
  const { apiBase = DEFAULT_API_BASE, token, workspaceId } = options;
  const [status, setStatus] = useState<UseAGUIReturn['status']>('idle');
  const [flatMessages, setFlatMessages] = useState<UseAGUIReturn['flatMessages']>([]);
  const [toolCalls, setToolCalls] = useState<UseAGUIReturn['toolCalls']>([]);
  const [pendingInterrupts, setPendingInterrupts] = useState<Interrupt[]>([]);
  const [error, setError] = useState<Error | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const lastInputRef = useRef<RunAgentInput | null>(null);
  const messageBufferRef = useRef<Map<string, { role: string; content: string }>>(new Map());
  const toolBufferRef = useRef<Map<string, { name: string; args: unknown; result?: string }>>(new Map());

  // 内部：应用事件到状态
  const applyEvent = useCallback((event: AGUIEvent) => {
    if (event.type === 'TEXT_MESSAGE_START') {
      messageBufferRef.current.set(event.messageId, { role: event.role, content: '' });
    } else if (event.type === 'TEXT_MESSAGE_CONTENT') {
      const existing = messageBufferRef.current.get(event.messageId);
      if (existing) {
        existing.content += event.delta;
        // 同步到 flatMessages
        setFlatMessages(
          Array.from(messageBufferRef.current.entries()).map(([id, m]) => ({
            id,
            role: m.role,
            content: m.content,
          })),
        );
      }
    } else if (event.type === 'TOOL_CALL_START') {
      toolBufferRef.current.set(event.toolCallId, { name: event.toolCallName, args: undefined });
    } else if (event.type === 'TOOL_CALL_ARGS') {
      const existing = toolBufferRef.current.get(event.toolCallId);
      if (existing) {
        try {
          existing.args = JSON.parse(event.delta);
        } catch {
          existing.args = event.delta;
        }
      }
    } else if (event.type === 'TOOL_CALL_END') {
      setToolCalls(
        Array.from(toolBufferRef.current.entries()).map(([id, t]) => ({
          id,
          name: t.name,
          args: t.args,
          result: t.result,
        })),
      );
    } else if (event.type === 'TOOL_CALL_RESULT') {
      const existing = toolBufferRef.current.get(event.toolCallId);
      if (existing) {
        existing.result = event.content;
        setToolCalls(
          Array.from(toolBufferRef.current.entries()).map(([id, t]) => ({
            id,
            name: t.name,
            args: t.args,
            result: t.result,
          })),
        );
      }
    } else if (event.type === 'MESSAGES_SNAPSHOT') {
      const buf = new Map<string, { role: string; content: string }>();
      for (const m of event.messages) {
        if (m.content) buf.set(m.id, { role: m.role, content: m.content });
      }
      messageBufferRef.current = buf;
      setFlatMessages(
        Array.from(buf.entries()).map(([id, m]) => ({ id, role: m.role, content: m.content })),
      );
    } else if (event.type === 'RUN_STARTED') {
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
  }, []);

  // 内部：流式调用
  const streamRun = useCallback(
    async (input: RunAgentInput) => {
      const controller = new AbortController();
      abortControllerRef.current = controller;
      try {
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const enriched: RunAgentInput = { ...input, workspaceId: input.workspaceId || workspaceId };
        const response = await fetch(`${apiBase}/api/ag-ui/run`, {
          method: 'POST',
          headers,
          body: JSON.stringify(enriched),
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        if (!response.body) throw new Error('No response body');
        // 连接已建立，立即进入 streaming 状态（不等待 RUN_STARTED 事件）。
        // 这样即使后端流尚未发送任何事件，UI 也能反映"请求进行中"，
        // 且 cancel() 能正确将状态从 streaming 转为 cancelled。
        setStatus('streaming');
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split('\n\n');
          buffer = events.pop() || '';
          for (const evt of events) {
            const dataLines = evt
              .split('\n')
              .filter((l) => l.startsWith('data: '))
              .map((l) => l.slice('data: '.length))
              .join('');
            if (!dataLines) continue;
            try {
              applyEvent(JSON.parse(dataLines) as AGUIEvent);
            } catch {
              /* 忽略 */
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          setStatus('cancelled');
          return;
        }
        setError(err instanceof Error ? err : new Error(String(err)));
        setStatus('error');
      }
    },
    [apiBase, token, workspaceId, applyEvent],
  );

  const send = useCallback(
    (content: string, opts: { threadId?: string } = {}) => {
      const threadId = opts.threadId || generateId();
      const runId = generateId();
      const userMsg: Message = {
        id: generateId(),
        role: 'user',
        content,
        createdAt: new Date().toISOString(),
      };
      const input: RunAgentInput = {
        threadId,
        runId,
        messages: [userMsg],
      };
      // 立即把 user 消息加进去
      setFlatMessages((prev) => [...prev, { id: userMsg.id, role: 'user', content }]);
      lastInputRef.current = input;
      void streamRun(input);
    },
    [streamRun],
  );

  const resume = useCallback(
    (interruptId: string, response: Record<string, unknown>) => {
      if (!lastInputRef.current) return;
      const next: RunAgentInput = {
        ...lastInputRef.current,
        resume: [
          ...(lastInputRef.current.resume || []),
          { interruptId, status: 'resolved', response },
        ],
      };
      setPendingInterrupts((prev) => prev.filter((i) => i.id !== interruptId));
      void streamRun(next);
    },
    [streamRun],
  );

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort();
    setStatus('cancelled');
  }, []);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  return {
    status,
    flatMessages,
    toolCalls,
    pendingInterrupts,
    error,
    send,
    resume,
    cancel,
  };
}
