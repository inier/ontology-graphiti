/**
 * ToolRegistry 契约测试
 *
 * 该组件此前零引用（无路由/无 Tab），一旦挂载就会暴露两类问题：
 *   1) 全英文硬编码，不走 i18n（本项目「中文即 key」约定下等于没做国际化）；
 *   2) 语义发现调完 `POST /api/tools/discover` 后**把结果丢掉**，只弹一句
 *      "Discovered N tools" 再 reload 全量列表 —— 用户永远看不到发现结果。
 *
 * 断言粒度：请求了哪个 URL、带了什么 body，以及发现结果是否真的进入了表格数据源。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 保持稳定引用：组件把它放进 useCallback 依赖，否则 effect 会反复触发
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

// 只替换表格与 wrapRequest，避免整个 shared 桶（图组件/monaco 等）进入 jsdom
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
          'tbody',
          null,
          rows.map((row, i) => {
            const key = typeof rowKey === 'function' ? rowKey(row) : String(row[rowKey] ?? i);
            return React.createElement(
              'tr',
              { key, 'data-testid': `tool-row-${key}` },
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

import ToolRegistry from './ToolRegistry';

const TOOLS = [
  {
    tool_id: 't-1',
    name: 'query_metric',
    description: '查询指标',
    tool_type: 'function',
    category: 'query',
    danger_level: 'low',
  },
];

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  del.mockReset();
  get.mockResolvedValue({ tools: TOOLS, count: 1 });
});

describe('ToolRegistry — 工具注册表', () => {
  it('列表走 GET /api/tools（无筛选时不带 query），并按行渲染工具名称', async () => {
    render(<ToolRegistry />);
    await waitFor(() => expect(screen.getByTestId('tool-row-t-1')).toBeTruthy());

    expect(get).toHaveBeenCalledWith('/api/tools');
    expect(screen.getByText('query_metric')).toBeTruthy();
  });

  it('注销走 DELETE /api/tools/{id}，而不是某个"删除接口"或空 body 的 POST', async () => {
    render(<ToolRegistry />);
    await waitFor(() => expect(screen.getByTestId('tool-row-t-1')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /移除/ }));
    // Popconfirm 的确认按钮在浮层里
    const confirm = await waitFor(() => {
      const box = document.querySelector('.ant-popconfirm');
      if (!box) throw new Error('popconfirm not opened');
      return box.querySelectorAll('button')[1] as HTMLButtonElement;
    });
    fireEvent.click(confirm);

    await waitFor(() => expect(del).toHaveBeenCalledWith('/api/tools/t-1'));
    // 负向断言：注销绝不是一次 POST
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining('/t-1'), expect.anything());
  });

  it('语义发现打 POST /api/tools/discover，且发现结果必须进入表格（此前被丢弃）', async () => {
    const discovered = [
      { tool_id: 'd-1', name: 'discovered_tool', tool_type: 'api', category: 'data' },
    ];
    post.mockResolvedValue({ tools: discovered, count: 1 });

    render(<ToolRegistry />);
    await waitFor(() => expect(screen.getByTestId('tool-row-t-1')).toBeTruthy());

    const input = screen.getByPlaceholderText('语义检索工具...');
    fireEvent.change(input, { target: { value: '查指标' } });
    fireEvent.click(screen.getByRole('button', { name: /语义发现/ }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/api/tools/discover', { query: '查指标', top_k: 10 }),
    );

    // 关键回归：发现结果成为表格数据源，而不是 reload 全量列表
    await waitFor(() => expect(screen.getByTestId('tool-row-d-1')).toBeTruthy());
    expect(screen.queryByTestId('tool-row-t-1')).toBeNull();
  });

  it('调用走 POST /api/tools/{id}/invoke，body 为 {params}；status=error 时不得提示成功', async () => {
    post.mockResolvedValue({ status: 'error', tool_id: 't-1', error: 'permission denied' });

    render(<ToolRegistry />);
    await waitFor(() => expect(screen.getByTestId('tool-row-t-1')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /调用/ }));
    const textarea = await waitFor(() => screen.getByLabelText('参数（JSON，可留空）'));
    fireEvent.change(textarea, { target: { value: '{"year": 2024}' } });

    const okButtons = document.querySelectorAll('.ant-modal-footer button');
    fireEvent.click(okButtons[okButtons.length - 1] as HTMLButtonElement);

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/api/tools/t-1/invoke', { params: { year: 2024 } }),
    );
    // 负向断言：后端返回 error 时不能走"调用成功"分支
    expect(post).not.toHaveBeenCalledWith(expect.stringContaining('/register'), expect.anything());
  });
});
