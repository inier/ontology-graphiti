/**
 * EditLockIndicator 契约测试
 *
 * 该组件此前零引用。它不是伪实现——后端 WebSocket 端点真实存在：
 *   `/ws/ontology/edit-lock/{ontology_id}?user_id=`（odap/web/ws/routes.py 注册），
 *   `edit_lock_service` 落 `edit_locks.db`，服务端 30s 无心跳即释放。
 *
 * 挂载点：本体设计器页头（设计器本身就是「编辑中」）。
 *
 * 这里钉住四件事：
 *   1) 连接地址与 query 参数正确；
 *   2) lock_acquired → 「编辑中」；lock_denied → 「已锁定 - 他人」且提示带上对方；
 *   3) 未处于编辑态时不建立连接（避免只浏览也占锁）；
 *   4) 断开时发送 release —— 否则锁要等 30s 超时才释放。
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  const t = (key: string, opts?: Record<string, unknown>) =>
    opts && Object.keys(opts).length
      ? `${key}|${JSON.stringify(opts)}`
      : key;
  return { useI18n: () => ({ t }) };
});

import { EditLockIndicator } from './EditLockIndicator';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  url: string;
  readyState = 1;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
    // 连接建立推迟到微任务，模拟真实握手
    queueMicrotask(() => this.onopen?.());
  }

  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }

  /** 测试辅助：服务端推一条消息 */
  emit(payload: Record<string, unknown>) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket);
});

describe('EditLockIndicator — 编辑锁', () => {
  it('编辑态下连接 /ws/ontology/edit-lock/{id} 并带上 user_id', async () => {
    render(<EditLockIndicator ontologyId="ont-1" userId="u-9" editing />);

    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const ws = FakeWebSocket.instances[0];
    expect(ws.url).toContain('/ws/ontology/edit-lock/ont-1');
    expect(ws.url).toContain('user_id=u-9');
  });

  it('lock_acquired 后显示「编辑中」', async () => {
    render(<EditLockIndicator ontologyId="ont-1" userId="u-9" editing />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));

    act(() => {
      FakeWebSocket.instances[0].emit({ type: 'lock_acquired', data: { user_id: 'u-9' } });
    });

    await waitFor(() => expect(screen.getByText('编辑中')).toBeTruthy());
  });

  it('lock_denied 后显示占锁人，并提示是谁锁的', async () => {
    render(<EditLockIndicator ontologyId="ont-1" userId="u-9" editing />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));

    act(() => {
      FakeWebSocket.instances[0].emit({
        type: 'lock_denied',
        data: { locked_by: 'u-1', locked_at: '2026-10-19T10:00:00Z' },
      });
    });

    await waitFor(() => expect(screen.getByText(/已锁定/)).toBeTruthy());
    expect(screen.getByText(/u-1/)).toBeTruthy();
  });

  it('非编辑态不建立连接（只浏览不应占锁）', async () => {
    render(<EditLockIndicator ontologyId="ont-1" userId="u-9" editing={false} />);
    await waitFor(() => expect(screen.getByText('未锁定')).toBeTruthy());
    expect(FakeWebSocket.instances.length).toBe(0);
  });

  it('卸载时发送 release，避免锁要等 30s 超时才释放', async () => {
    const { unmount } = render(<EditLockIndicator ontologyId="ont-1" userId="u-9" editing />);
    await waitFor(() => expect(FakeWebSocket.instances.length).toBe(1));
    const ws = FakeWebSocket.instances[0];

    unmount();

    expect(ws.sent.some((s) => s.includes('"release"'))).toBe(true);
  });
});
