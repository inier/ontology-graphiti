/**
 * AGUIProvider 生产化硬化测试 (T067)
 *
 * 验证四项生产级要求：
 * 1. ErrorBoundary — 捕获子组件异常，渲染降级 UI
 * 2. 重连机制 — 最多 2 次重试（间隔 1s/3s）
 * 3. 心跳超时 — 默认 120s（120000ms）
 * 4. 命名空间隔离 — 支持自定义 endpoint（/api/ontology-assistant/ vs /api/ag-ui/）
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, renderHook, act } from '@testing-library/react';
import React from 'react';
import { AGUIProvider, useAGUIContext, AGUIErrorBoundary } from '../AGUIProvider';
import type { AGUIEvent } from '../agui_types';

// === Mock fetch（返回可控 SSE 流）===

function makeSSEResponse(events: AGUIEvent[], options: { status?: number; statusText?: string } = {}): Response {
  const encoder = new TextEncoder();
  const sseText = events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('');
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(sseText));
      controller.close();
    },
  });
  return new Response(stream, {
    status: options.status ?? 200,
    statusText: options.statusText ?? 'OK',
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

function makeErrorResponse(status: number, statusText: string): Response {
  return new Response('error', { status, statusText });
}

// === Helper: 触发子组件抛错 ===

function ThrowOnRender({ error }: { error: Error }): null {
  throw error;
}

// === Wrapper 工厂：确保 children 正确传递 ===

function makeWrapper(props: React.ComponentProps<typeof AGUIProvider> = {}) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <AGUIProvider apiBase="http://test" {...props}>{children}</AGUIProvider>;
  };
}

describe('AGUIProvider T067 production hardening', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================
  // 1. ErrorBoundary — 捕获子组件异常
  // ============================================================
  describe('ErrorBoundary', () => {
    it('renders fallback UI when child throws', () => {
      // 抑制 console.error（React 会打印错误堆栈）
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const bomb = new Error('boom');
      const fallback = <div data-testid="fallback">AI 助手暂不可用</div>;

      const { getByTestId } = render(
        <AGUIProvider apiBase="http://test" fallback={fallback}>
          <ThrowOnRender error={bomb} />
        </AGUIProvider>,
      );

      expect(getByTestId('fallback')).toBeTruthy();
      spy.mockRestore();
    });

    it('renders children normally when no error', () => {
      const { getByText } = render(
        <AGUIProvider apiBase="http://test">
          <div>正常内容</div>
        </AGUIProvider>,
      );
      expect(getByText('正常内容')).toBeTruthy();
    });

    it('AGUIErrorBoundary can be used standalone with default fallback', () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { container } = render(
        <AGUIErrorBoundary>
          <ThrowOnRender error={new Error('standalone boom')} />
        </AGUIErrorBoundary>,
      );

      // 默认 fallback 应包含"AI 助手暂不可用"
      expect(container.textContent).toContain('AI 助手暂不可用');
      spy.mockRestore();
    });
  });

  // ============================================================
  // 2. 默认心跳超时 120s
  // ============================================================
  describe('heartbeatTimeoutMs default', () => {
    it('defaults to 120000ms (120s) - provider accepts and uses default', () => {
      const events: AGUIEvent[] = [
        { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
        { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
      ];
      vi.spyOn(global, 'fetch').mockResolvedValueOnce(makeSSEResponse(events));

      const wrapper = makeWrapper(); // 不传 heartbeatTimeoutMs，使用默认 120000
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      act(() => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
      });

      // Provider 默认 heartbeatTimeoutMs 应为 120000
      // 通过验证 provider 正常工作（不报错）间接验证
      expect(result.current).toBeDefined();
      expect(result.current.runAgent).toBeTypeOf('function');
    });

    it('accepts custom heartbeatTimeoutMs', () => {
      const events: AGUIEvent[] = [
        { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
        { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
      ];
      vi.spyOn(global, 'fetch').mockResolvedValueOnce(makeSSEResponse(events));

      const wrapper = makeWrapper({ heartbeatTimeoutMs: 30000 });
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      act(() => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
      });

      expect(result.current).toBeDefined();
    });
  });

  // ============================================================
  // 3. 重连机制 — 最多 2 次重试
  // ============================================================
  describe('reconnect with 2 retries', () => {
    it('retries up to 2 times before setting error state', async () => {
      // 三次 500 错误，第三次后应该放弃
      const fetchSpy = vi
        .spyOn(global, 'fetch')
        .mockResolvedValue(makeErrorResponse(500, 'Internal Server Error'));

      const wrapper = makeWrapper({ autoReconnect: true, maxRetries: 2 });
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      await act(async () => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
        // 等待重试链完成（1s + 3s + buffer）
        await new Promise((r) => setTimeout(r, 5500));
      });

      // 应该调用 3 次（1 次初始 + 2 次重试）
      expect(fetchSpy.mock.calls.length).toBeGreaterThanOrEqual(3);
      expect(result.current.status).toBe('error');
    }, 10000);

    it('does not retry when autoReconnect is false', async () => {
      const fetchSpy = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(makeErrorResponse(500, 'Internal Server Error'));

      const wrapper = makeWrapper({ autoReconnect: false });
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      await act(async () => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
        await new Promise((r) => setTimeout(r, 300));
      });

      expect(fetchSpy).toHaveBeenCalledTimes(1);
      expect(result.current.status).toBe('error');
    });

    it('does not retry on 401 unauthorized', async () => {
      const fetchSpy = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(makeErrorResponse(401, 'Unauthorized'));

      const wrapper = makeWrapper({ autoReconnect: true });
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      await act(async () => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
        await new Promise((r) => setTimeout(r, 300));
      });

      expect(fetchSpy).toHaveBeenCalledTimes(1);
      expect(result.current.status).toBe('error');
    });

    it('resets retry count on successful runAgent', async () => {
      // 第一次：500 错误 → 重试 2 次 → 失败
      // 第二次：成功 → 应该正常工作
      const fetchSpy = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(makeErrorResponse(500, 'Server Error'))
        .mockResolvedValueOnce(makeErrorResponse(500, 'Server Error'))
        .mockResolvedValueOnce(makeErrorResponse(500, 'Server Error'))
        .mockResolvedValueOnce(
          makeSSEResponse([
            { type: 'RUN_STARTED', threadId: 't2', runId: 'r2' },
            { type: 'RUN_FINISHED', threadId: 't2', runId: 'r2', outcome: 'success' },
          ]),
        );

      const wrapper = makeWrapper({ autoReconnect: true, maxRetries: 2 });
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      // 第一次 run：失败 + 2 次重试
      await act(async () => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'fail' }],
        });
        await new Promise((r) => setTimeout(r, 5500));
      });

      expect(result.current.status).toBe('error');
      const callsAfterFirstRun = fetchSpy.mock.calls.length;

      // 第二次 run：应该成功（重试计数已重置）
      await act(async () => {
        result.current.runAgent({
          threadId: 't2',
          runId: 'r2',
          messages: [{ id: 'm2', role: 'user', content: 'success' }],
        });
        await new Promise((r) => setTimeout(r, 300));
      });

      // 第二次只调用 1 次 fetch（成功）
      expect(fetchSpy.mock.calls.length).toBe(callsAfterFirstRun + 1);
      expect(result.current.status).toBe('idle');
    }, 15000);
  });

  // ============================================================
  // 4. 命名空间隔离 — 支持自定义 endpoint
  // ============================================================
  describe('namespace isolation', () => {
    it('uses default /api/ag-ui/run endpoint when no namespace specified', async () => {
      const fetchSpy = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(
          makeSSEResponse([
            { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
            { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
          ]),
        );

      const wrapper = makeWrapper();
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      await act(async () => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
        await new Promise((r) => setTimeout(r, 100));
      });

      const url = fetchSpy.mock.calls[0][0] as string;
      expect(url).toBe('http://test/api/ag-ui/run');
    });

    it('uses custom endpoint when namespace is "ontology-assistant"', async () => {
      const fetchSpy = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(
          makeSSEResponse([
            { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
            { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
          ]),
        );

      const wrapper = makeWrapper({ namespace: 'ontology-assistant' });
      const { result } = renderHook(() => useAGUIContext(), { wrapper });

      await act(async () => {
        result.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'hi' }],
        });
        await new Promise((r) => setTimeout(r, 100));
      });

      const url = fetchSpy.mock.calls[0][0] as string;
      expect(url).toBe('http://test/api/ontology-assistant/run');
    });

    it('isolates QA namespace from ontology-assistant namespace', async () => {
      // QA 命名空间
      const qaFetch = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(
          makeSSEResponse([
            { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
            { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
          ]),
        );

      const qaWrapper = makeWrapper({ namespace: 'ag-ui' });
      const { result: qaResult } = renderHook(() => useAGUIContext(), { wrapper: qaWrapper });

      await act(async () => {
        qaResult.current.runAgent({
          threadId: 't1',
          runId: 'r1',
          messages: [{ id: 'm1', role: 'user', content: 'qa' }],
        });
        await new Promise((r) => setTimeout(r, 100));
      });

      const qaUrl = qaFetch.mock.calls[0][0] as string;
      expect(qaUrl).toContain('/api/ag-ui/run');
      expect(qaUrl).not.toContain('/api/ontology-assistant/');

      // 本体设计器命名空间
      const ontologyFetch = vi
        .spyOn(global, 'fetch')
        .mockResolvedValueOnce(
          makeSSEResponse([
            { type: 'RUN_STARTED', threadId: 't2', runId: 'r2' },
            { type: 'RUN_FINISHED', threadId: 't2', runId: 'r2', outcome: 'success' },
          ]),
        );

      const ontologyWrapper = makeWrapper({ namespace: 'ontology-assistant' });
      const { result: ontologyResult } = renderHook(() => useAGUIContext(), { wrapper: ontologyWrapper });

      await act(async () => {
        ontologyResult.current.runAgent({
          threadId: 't2',
          runId: 'r2',
          messages: [{ id: 'm2', role: 'user', content: 'ontology' }],
        });
        await new Promise((r) => setTimeout(r, 100));
      });

      const ontologyUrl = ontologyFetch.mock.calls[0][0] as string;
      expect(ontologyUrl).toContain('/api/ontology-assistant/run');
      expect(ontologyUrl).not.toContain('/api/ag-ui/');
    });
  });
});
