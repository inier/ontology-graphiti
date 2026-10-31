/**
 * HookManager 契约测试
 *
 * 该组件此前零引用，挂载即暴露三处契约虚构：
 *   1) hook_type 选项是 event/data/validation/transformation/notification/custom，
 *      而后端 HookType 只有 pre_execute/post_execute/on_error/on_timeout/pre_commit/post_commit
 *      —— 严格校验并 400，等于注册功能全废；
 *   2) 表格有 phase / priority / language 三列，列表接口根本不返回这些字段；
 *   3) 开关读 `enabled`，但后端 HookStatus 是 active/inactive/error，
 *      `checked={v !== false}` 把 undefined 当成"已启用"。
 *
 * 断言粒度：URL、body、以及**不该存在的枚举值/列**。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 保持稳定引用：组件把它放进 useCallback 依赖，否则 effect 会反复触发
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

vi.mock('@/modules/shared', async () => {
  const React = await import('react');
  return {
    wrapRequest: (fetcher: () => Promise<unknown[]>) => async () => {
      const data = await fetcher();
      return { data, success: true, total: data.length };
    },
    AdvancedTable: ({
      request,
      columns,
      rowKey,
    }: {
      request: () => Promise<{ data: Array<Record<string, unknown>> }>;
      columns: Array<{
        title: ReactNode;
        key: string;
        dataIndex?: string;
        render?: (v: unknown, r: unknown) => ReactNode;
      }>;
      rowKey: string | ((r: Record<string, unknown>) => string);
    }) => {
      const [rows, setRows] = React.useState<Array<Record<string, unknown>>>([]);
      React.useEffect(() => {
        let alive = true;
        void request().then((res) => {
          if (alive) setRows(res.data ?? []);
        });
        return () => {
          alive = false;
        };
      }, [request]);
      return React.createElement(
        'table',
        null,
        React.createElement(
          'thead',
          null,
          React.createElement(
            'tr',
            null,
            columns.map((c) => React.createElement('th', { key: c.key }, c.title)),
          ),
        ),
        React.createElement(
          'tbody',
          null,
          rows.map((row, i) => {
            const key = typeof rowKey === 'function' ? rowKey(row) : String(row[rowKey] ?? i);
            return React.createElement(
              'tr',
              { key, 'data-testid': `hook-row-${key}` },
              columns.map((col) => {
                const value = col.dataIndex ? row[col.dataIndex] : undefined;
                return React.createElement(
                  'td',
                  { key: col.key },
                  col.render ? col.render(value, row) : String(value ?? ''),
                );
              }),
            );
          }),
        ),
      );
    },
  };
});

const get = vi.fn();
const post = vi.fn();
const del = vi.fn();

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (...args: unknown[]) => get(...args),
    post: (...args: unknown[]) => post(...args),
    delete: (...args: unknown[]) => del(...args),
  },
}));

import HookManager from './HookManager';

const HOOKS = [
  { hook_id: 'h-1', name: 'audit_log', hook_type: 'post_execute', status: 'active', enabled: true },
  { hook_id: 'h-2', name: 'quota_guard', hook_type: 'pre_execute', status: 'inactive', enabled: false },
];

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
  get.mockResolvedValue({ hooks: HOOKS, total: 2, page: 1, page_size: 100 });
});

describe('HookManager — 钩子管理', () => {
  it('列表走 GET /api/hooks?page_size=100，并按 status 渲染而不是靠 undefined 猜', async () => {
    render(<HookManager />);
    await waitFor(() => expect(screen.getByTestId('hook-row-h-1')).toBeTruthy());

    expect(get).toHaveBeenCalledWith('/api/hooks?page_size=100');
    expect(screen.getByText('已启用')).toBeTruthy();
    expect(screen.getByText('已禁用')).toBeTruthy();
  });

  it('开关读服务端 enabled：inactive 的那行必须是未选中状态', async () => {
    render(<HookManager />);
    await waitFor(() => expect(screen.getByTestId('hook-row-h-2')).toBeTruthy());

    const switches = screen.getAllByRole('switch') as HTMLElement[];
    expect(switches).toHaveLength(2);
    const states = switches.map((s) => s.getAttribute('aria-checked'));
    expect(states).toEqual(['true', 'false']);
  });

  it('切换开关打 POST /api/hooks/{id}/disable（或 /enable），不是 PUT 也不是改 body', async () => {
    post.mockResolvedValue({ status: 'success', hook_id: 'h-2', enabled: true });

    render(<HookManager />);
    await waitFor(() => expect(screen.getByTestId('hook-row-h-2')).toBeTruthy());

    const switches = screen.getAllByRole('switch') as HTMLElement[];
    fireEvent.click(switches[1]);

    await waitFor(() => expect(post).toHaveBeenCalledWith('/api/hooks/h-2/enable'));
  });

  it('注销走 DELETE /api/hooks/{id}', async () => {
    del.mockResolvedValue({ status: 'success', hook_id: 'h-1', deleted: true });

    render(<HookManager />);
    await waitFor(() => expect(screen.getByTestId('hook-row-h-1')).toBeTruthy());

    const removeButtons = screen.getAllByRole('button', { name: /移除/ });
    fireEvent.click(removeButtons[0]);
    const confirm = await waitFor(() => {
      const box = document.querySelector('.ant-popconfirm');
      if (!box) throw new Error('popconfirm not opened');
      return box.querySelectorAll('button')[1] as HTMLButtonElement;
    });
    fireEvent.click(confirm);

    await waitFor(() => expect(del).toHaveBeenCalledWith('/api/hooks/h-1'));
  });

  it('注册表单的类型选项只能是后端 HookType 的 6 个枚举值', async () => {
    render(<HookManager />);
    await waitFor(() => expect(screen.getByTestId('hook-row-h-1')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /注册钩子/ }));
    // 打开 Select 才能看到选项（antd Select：mouseDown 在选择器上，选项在弹层）
    const typeSelect = await waitFor(() => screen.getByLabelText('类型'));
    fireEvent.mouseDown(typeSelect);

    await waitFor(() => expect(document.querySelectorAll('.ant-select-item-option').length).toBeGreaterThan(0));
    const options = Array.from(document.querySelectorAll('.ant-select-item-option')).map(
      (n) => n.getAttribute('title') || n.textContent || '',
    );

    expect(options).toEqual(expect.arrayContaining(['执行前', '执行后', '出错时', '超时时', '提交前', '提交后']));
    // 负向断言：这组值是后端不存在的枚举，曾经导致注册必然 400
    for (const invalid of ['event', 'data', 'validation', 'transformation', 'notification', 'custom']) {
      expect(options).not.toContain(invalid);
    }
  });

  it('表格不渲染契约里不存在的 phase / priority / language 列', async () => {
    render(<HookManager />);
    await waitFor(() => expect(screen.getByTestId('hook-row-h-1')).toBeTruthy());

    const headers = Array.from(document.querySelectorAll('th')).map((n) => n.textContent);
    expect(headers).toEqual(['名称', '类型', '状态', '启用', '操作']);
    expect(headers).not.toContain('优先级');
    expect(headers).not.toContain('阶段');
  });
});
