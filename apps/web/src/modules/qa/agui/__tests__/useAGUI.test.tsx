/**
 * useAGUI Hook 单元测试
 *
 * v2.0 plan T033: 4 cases (initial state, event accumulation, resume on interrupt, error handling)
 * 使用 vitest + @testing-library/react
 *
 * 注意：fetch mock 使用 vi.fn() 模拟；SSE 流通过 ReadableStream 模拟
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAGUI } from '../useAGUI';
import type { AGUIEvent } from '../agui_types';

// === Mock fetch（返回可控 SSE 流）===

function makeSSEResponse(events: AGUIEvent[]): Response {
  const encoder = new TextEncoder();
  const sseText = events
    .map((e) => `data: ${JSON.stringify(e)}\n\n`)
    .join('');
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(sseText));
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('useAGUI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // === Case 1: initial state ===
  it('returns initial idle state with empty messages', () => {
    const { result } = renderHook(() => useAGUI());
    expect(result.current.status).toBe('idle');
    expect(result.current.flatMessages).toEqual([]);
    expect(result.current.toolCalls).toEqual([]);
    expect(result.current.pendingInterrupts).toEqual([]);
    expect(result.current.error).toBeNull();
  });

  // === Case 2: event accumulation（流式文本 + tool_call） ===
  it('accumulates TEXT_MESSAGE_CONTENT events into flatMessages', async () => {
    const events: AGUIEvent[] = [
      { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
      { type: 'TEXT_MESSAGE_START', messageId: 'm1', role: 'assistant' },
      { type: 'TEXT_MESSAGE_CONTENT', messageId: 'm1', delta: 'Hello' },
      { type: 'TEXT_MESSAGE_CONTENT', messageId: 'm1', delta: ' world' },
      { type: 'TEXT_MESSAGE_END', messageId: 'm1' },
      { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
    ];
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(makeSSEResponse(events));

    const { result } = renderHook(() => useAGUI({ apiBase: 'http://test' }));

    await act(async () => {
      result.current.send('hi');
      // 等待 fetch + 解析完成
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(result.current.status).toBe('idle');
    // user 消息 + assistant 累积消息
    const assistant = result.current.flatMessages.find((m) => m.role === 'assistant');
    expect(assistant?.content).toBe('Hello world');
  });

  // === Case 3: tool_call three-piece ===
  it('captures tool_call START/ARGS/END and RESULT', async () => {
    const events: AGUIEvent[] = [
      { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
      {
        type: 'TOOL_CALL_START',
        toolCallId: 'tc1',
        toolCallName: 'bash',
        parentMessageId: 'm1',
      },
      { type: 'TOOL_CALL_ARGS', toolCallId: 'tc1', delta: '{"cmd":"ls"}' },
      { type: 'TOOL_CALL_END', toolCallId: 'tc1' },
      {
        type: 'TOOL_CALL_RESULT',
        messageId: 'm1',
        toolCallId: 'tc1',
        content: 'file.txt',
        role: 'tool',
      },
      { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
    ];
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(makeSSEResponse(events));

    const { result } = renderHook(() => useAGUI({ apiBase: 'http://test' }));

    await act(async () => {
      result.current.send('ls');
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(result.current.toolCalls).toHaveLength(1);
    const tc = result.current.toolCalls[0];
    expect(tc.id).toBe('tc1');
    expect(tc.name).toBe('bash');
    expect(tc.args).toEqual({ cmd: 'ls' });
    expect(tc.result).toBe('file.txt');
  });

  // === Case 4: interrupt + resume ===
  it('captures RunFinished.interrupts and resolves via resume()', async () => {
    // 第一次 fetch：返回 interrupt
    const interruptEvents: AGUIEvent[] = [
      { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
      {
        type: 'RUN_FINISHED',
        threadId: 't1',
        runId: 'r1',
        outcome: {
          type: 'interrupt',
          interrupts: [
            {
              id: 'int-1',
              reason: 'confirmation',
              message: '是否继续？',
            },
          ],
        },
      },
    ];
    // 第二次 fetch（resume）：返回 success
    const resumeEvents: AGUIEvent[] = [
      { type: 'RUN_STARTED', threadId: 't1', runId: 'r1' },
      { type: 'TEXT_MESSAGE_START', messageId: 'm2', role: 'assistant' },
      { type: 'TEXT_MESSAGE_CONTENT', messageId: 'm2', delta: '好的，继续。' },
      { type: 'TEXT_MESSAGE_END', messageId: 'm2' },
      { type: 'RUN_FINISHED', threadId: 't1', runId: 'r1', outcome: 'success' },
    ];

    const fetchSpy = vi
      .spyOn(global, 'fetch')
      .mockResolvedValueOnce(makeSSEResponse(interruptEvents))
      .mockResolvedValueOnce(makeSSEResponse(resumeEvents));

    const { result } = renderHook(() => useAGUI({ apiBase: 'http://test' }));

    await act(async () => {
      result.current.send('继续');
      await new Promise((r) => setTimeout(r, 100));
    });

    // 应捕获 interrupt
    expect(result.current.status).toBe('interrupted');
    expect(result.current.pendingInterrupts).toHaveLength(1);
    expect(result.current.pendingInterrupts[0].id).toBe('int-1');

    // resume
    await act(async () => {
      result.current.resume('int-1', { approved: true });
      await new Promise((r) => setTimeout(r, 100));
    });

    // 第二次 fetch 应被调用，且带 resume[]
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    const secondCall = fetchSpy.mock.calls[1];
    const body = JSON.parse(secondCall[1]?.body as string);
    expect(body.resume).toBeDefined();
    expect(body.resume[0].interruptId).toBe('int-1');
    expect(body.resume[0].response).toEqual({ approved: true });

    // 应进入 success
    expect(result.current.status).toBe('idle');
  });

  // === Case 5: error handling ===
  it('sets error state on HTTP error', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(
      new Response('Bad Request', { status: 400 }),
    );

    const { result } = renderHook(() => useAGUI({ apiBase: 'http://test' }));

    await act(async () => {
      result.current.send('hi');
      await new Promise((r) => setTimeout(r, 100));
    });

    expect(result.current.status).toBe('error');
    expect(result.current.error).toBeInstanceOf(Error);
    expect(result.current.error?.message).toContain('400');
  });

  // === Case 6: cancel ===
  it('sets cancelled status on cancel()', async () => {
    // 一个永不结束的流
    const stream = new ReadableStream({
      start(controller) {
        // 永远不 enqueue，也不 close
      },
    });
    vi.spyOn(global, 'fetch').mockResolvedValueOnce(
      new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } }),
    );

    const { result } = renderHook(() => useAGUI({ apiBase: 'http://test' }));

    await act(async () => {
      result.current.send('hi');
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(result.current.status).toBe('streaming');

    await act(async () => {
      result.current.cancel();
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(result.current.status).toBe('cancelled');
  });
});
