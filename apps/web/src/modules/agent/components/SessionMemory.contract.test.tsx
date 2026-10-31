/**
 * SessionMemory / SessionMemoryPage 契约测试
 *
 * 组件此前零引用，且三处 `catch { setX([]) }` 让「记忆为空」与「接口挂了」在界面上完全一样。
 *
 * 契约（/api/session-memory）：
 *   GET  /sessions?workspace_id=&limit=      → {sessions: [...]}
 *   GET  /sessions/{id}/context              → {context_window, messages, summary}
 *   GET  /memory/session/{id}                → {key: value}（含 status 字段需过滤）
 *   GET  /memory/long-term?query=&limit=
 *   POST /memory/session/{id}/clear
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 保持稳定引用：组件把它放进 useCallback 依赖，否则 effect 会反复触发
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

vi.mock('@/modules/shared', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('@/modules/shared');
  return {
    ...actual,
    useWorkspace: () => ({ currentWorkspace: 'ws-1' }),
  };
});

const get = vi.fn();
const post = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
  },
}));

import SessionMemory from './SessionMemory';
import { SessionMemoryPage } from '../pages/SessionMemoryPage';

const CONTEXT_URL = '/api/session-memory/sessions/s-1/context';
const WORKING_URL = '/api/session-memory/memory/session/s-1';

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockImplementation((url: string) => {
    if (url === CONTEXT_URL) {
      return Promise.resolve({
        context_window: {
          messages: [{ id: 'm1', role: 'user', content: '查订单', tokens: 12, entities: ['订单'] }],
          summary: '用户在查订单',
          total_tokens: 12,
          max_tokens: 8000,
        },
        messages: [],
        summary: '用户在查订单',
      });
    }
    if (url === WORKING_URL) {
      return Promise.resolve({ status: 'ok', current_order: 'O-1', preference: { lang: 'zh' } });
    }
    if (url === '/api/session-memory/sessions?workspace_id=ws-1&limit=50') {
      return Promise.resolve({ sessions: [{ id: 's-1', title: '订单排查', message_count: 3 }] });
    }
    if (url.startsWith('/api/session-memory/memory/long-term')) {
      return Promise.resolve({ results: [{ key: 'o-pref', value: '偏好 A 仓', score: 0.812 }] });
    }
    return Promise.reject(new Error(`unexpected url: ${url}`));
  });
});

describe('SessionMemory — 会话记忆', () => {
  it('同时拉取 context 与工作记忆，且工作记忆过滤掉 status 元字段', async () => {
    render(<SessionMemory sessionId="s-1" />);

    await waitFor(() => expect(get).toHaveBeenCalledWith(CONTEXT_URL));
    expect(get).toHaveBeenCalledWith(WORKING_URL);

    // 默认停在「短期上下文」页签，工作记忆要切过去才会渲染（Tabs 懒渲染）
    fireEvent.click(screen.getByText('工作记忆'));
    await waitFor(() => expect(screen.getByText('current_order')).toBeTruthy());
    // status 是元字段，不应作为记忆条目展示
    expect(screen.queryByText('status')).toBeNull();
  });

  it('长期记忆检索带上 query 与 limit=10', async () => {
    render(<SessionMemory sessionId="s-1" />);
    await waitFor(() => expect(get).toHaveBeenCalledWith(CONTEXT_URL));

    fireEvent.click(screen.getByText('长期记忆'));
    fireEvent.change(screen.getByLabelText('检索长期记忆'), { target: { value: '仓库偏好' } });
    fireEvent.click(screen.getByRole('button', { name: /检索/ }));

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith(
        `/api/session-memory/memory/long-term?query=${encodeURIComponent('仓库偏好')}&limit=10`,
      ),
    );
    await waitFor(() => expect(screen.getByText('偏好 A 仓')).toBeTruthy());
  });

  it('清空记忆走 POST /memory/session/{id}/clear', async () => {
    post.mockResolvedValue({ status: 'success' });
    render(<SessionMemory sessionId="s-1" />);
    await waitFor(() => expect(get).toHaveBeenCalledWith(CONTEXT_URL));

    fireEvent.click(screen.getByRole('button', { name: /清\s*空/ }));
    const confirm = await waitFor(() => {
      const box = document.querySelector('.ant-popconfirm');
      if (!box) throw new Error('popconfirm not opened');
      return box.querySelectorAll('button')[1] as HTMLButtonElement;
    });
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/api/session-memory/memory/session/s-1/clear'),
    );
  });

  it('加载失败时把原因显示出来，而不是当成「无记忆」', async () => {
    get.mockRejectedValue(new Error('404 Session not found'));

    render(<SessionMemory sessionId="s-1" />);

    await waitFor(() => expect(screen.getByText('部分记忆数据加载失败')).toBeTruthy());
    expect(screen.getAllByText(/404 Session not found/).length).toBeGreaterThan(0);
  });
});

describe('SessionMemoryPage — 会话选择', () => {
  it('按 workspace_id 拉会话列表，选中后渲染记忆面板', async () => {
    render(<SessionMemoryPage />);

    await waitFor(() =>
      expect(get).toHaveBeenCalledWith('/api/session-memory/sessions?workspace_id=ws-1&limit=50'),
    );
    await waitFor(() => expect(screen.getByText('订单排查')).toBeTruthy());

    // 自动选中首个会话 → 触达 context 接口
    await waitFor(() => expect(get).toHaveBeenCalledWith(CONTEXT_URL));
  });
});
