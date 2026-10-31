/**
 * MCPManager 契约测试
 *
 * 真实契约：
 *   GET    /api/mcp/servers                            → { servers: [...] }
 *   POST   /api/mcp/servers                            body: { name, url, description? }
 *   DELETE /api/mcp/servers/{server_id}
 *   GET    /api/mcp/servers/{server_id}/tools          → { tools: [{ name, description, inputSchema }] }
 *   POST   /api/mcp/servers/{server_id}/tools/{name}   body: { arguments }
 *
 * 旧实现四处虚构：
 *  ① 注册打 `POST /api/mcp/servers/register` —— 后端只有 `POST /servers`；
 *  ② 调工具打 `POST /api/mcp/tools/{tool_id}/invoke` —— 真实路由按 server 分组，
 *     路径里根本没有工具 id 这一段；
 *  ③ 工具用 `tool_id` 当主键 —— MCP 协议里工具的唯一标识是 `name`；
 *  ④ 调用参数键叫 `parameters` —— 后端读的是 `arguments`。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => {
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
      dataSource,
      columns,
      rowKey,
    }: {
      request?: () => Promise<{ data: Array<Record<string, unknown>> }>;
      dataSource?: Array<Record<string, unknown>>;
      columns: Array<{
        title: ReactNode;
        key: string;
        dataIndex?: string;
        render?: (v: unknown, r: unknown) => ReactNode;
      }>;
      rowKey: string | ((r: Record<string, unknown>) => string);
    }) => {
      const [rows, setRows] = React.useState<Array<Record<string, unknown>>>(dataSource ?? []);
      React.useEffect(() => {
        if (!request) {
          setRows(dataSource ?? []);
          return;
        }
        let alive = true;
        void request().then((res) => {
          if (alive) setRows(res.data ?? []);
        });
        return () => {
          alive = false;
        };
      }, [request, dataSource]);
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
              { key, 'data-testid': `mcp-row-${key}` },
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

type Call = { method: string; url: string; body?: unknown };
const calls: Call[] = [];

const SERVERS = [
  {
    server_id: 'srv-1',
    name: 'graph-tools',
    url: 'http://localhost:9000/mcp',
    status: 'connected',
    tools_count: 2,
    description: '图谱工具',
    last_ping: '2026-10-19T10:00:00Z',
  },
];

const TOOLS = [
  { name: 'query_graph', description: '按 Cypher 查询', inputSchema: { type: 'object' } },
  { name: 'upsert_node', description: '写入节点', inputSchema: { type: 'object' } },
];

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (url: string) => {
      calls.push({ method: 'GET', url });
      if (url === '/api/mcp/servers') return Promise.resolve({ servers: SERVERS });
      if (url === '/api/mcp/servers/srv-1/tools') return Promise.resolve({ tools: TOOLS });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    },
    post: (url: string, body?: unknown) => {
      calls.push({ method: 'POST', url, body });
      if (url === '/api/mcp/servers') return Promise.resolve({ server_id: 'srv-2' });
      if (url === '/api/mcp/servers/srv-1/tools/query_graph') return Promise.resolve({ rows: [] });
      return Promise.reject(new Error(`unexpected POST ${url}`));
    },
    delete: (url: string) => {
      calls.push({ method: 'DELETE', url });
      return Promise.resolve({ deleted: true });
    },
  },
}));

import MCPManager from './MCPManager';

const urlsOf = (method?: string) =>
  calls.filter((c) => !method || c.method === method).map((c) => c.url);

beforeEach(() => {
  calls.length = 0;
});

describe('MCPManager — MCP 服务器管理', () => {
  it('列表读 data.servers，按 server_id 作行键', async () => {
    render(<MCPManager />);

    await waitFor(() => expect(screen.getByText('graph-tools')).toBeTruthy());
    expect(urlsOf('GET')).toContain('/api/mcp/servers');
    expect(screen.getByText('http://localhost:9000/mcp')).toBeTruthy();
  });

  it('注册走 POST /api/mcp/servers，不得打 /servers/register', async () => {
    render(<MCPManager />);
    await waitFor(() => expect(screen.getByText('graph-tools')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /注册/ }));

    await waitFor(() => expect(document.querySelector('.ant-modal-body')).toBeTruthy());
    const inputs = document.querySelectorAll('.ant-modal-body input');
    fireEvent.change(inputs[0], { target: { value: 'new-server' } });
    fireEvent.change(inputs[1], { target: { value: 'http://localhost:9100/mcp' } });

    const okBtn = document.querySelector('.ant-modal-footer .ant-btn-primary') as HTMLElement;
    fireEvent.click(okBtn);

    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.url === '/api/mcp/servers')).toBe(true),
    );
    const post = calls.find((c) => c.method === 'POST')!;
    expect(post.body).toMatchObject({ name: 'new-server', url: 'http://localhost:9100/mcp' });

    // 负向断言：/servers/register 后端不存在
    expect(urlsOf().some((u) => u.includes('/servers/register'))).toBe(false);
  });

  it('工具列表走 GET /servers/{id}/tools，并以 name 作工具主键', async () => {
    render(<MCPManager />);
    await waitFor(() => expect(screen.getByText('graph-tools')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /mcp\.tools/ }));

    await waitFor(() => expect(urlsOf('GET')).toContain('/api/mcp/servers/srv-1/tools'));
    await waitFor(() => expect(screen.getByText('query_graph')).toBeTruthy());
    expect(screen.getByText('upsert_node')).toBeTruthy();
  });

  it('调用工具走 POST /servers/{server_id}/tools/{name}，body 键是 arguments', async () => {
    render(<MCPManager />);
    await waitFor(() => expect(screen.getByText('graph-tools')).toBeTruthy());

    // 先打开工具列表（调用路径依赖 server_id，必须先记住归属）
    fireEvent.click(screen.getByRole('button', { name: /mcp\.tools/ }));
    await waitFor(() => expect(screen.getByText('query_graph')).toBeTruthy());

    const invokeBtns = screen.getAllByRole('button', { name: /mcp\.invoke/ });
    fireEvent.click(invokeBtns[0]);

    await waitFor(() => expect(document.querySelector('textarea')).toBeTruthy());
    const textarea = document.querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: '{"limit": 5}' } });

    // 调用弹窗的确认按钮（页面上有多个 modal-footer，取最后一个=最上层）
    const footers = document.querySelectorAll('.ant-modal-footer');
    const okBtn = footers[footers.length - 1].querySelector('.ant-btn-primary') as HTMLElement;
    fireEvent.click(okBtn);

    await waitFor(() =>
      expect(
        calls.some(
          (c) =>
            c.method === 'POST' &&
            c.url === '/api/mcp/servers/srv-1/tools/query_graph' &&
            JSON.stringify(c.body) === JSON.stringify({ arguments: { limit: 5 } }),
        ),
      ).toBe(true),
    );

    // 负向断言：两处虚构路径都不得出现
    expect(urlsOf().some((u) => /\/api\/mcp\/tools\/[^/]+\/invoke/.test(u))).toBe(false);
    expect(calls.some((c) => c.method === 'POST' && 'parameters' in ((c.body ?? {}) as object))).toBe(false);
  });

  it('注销需二次确认，确认后走 DELETE /servers/{id}', async () => {
    render(<MCPManager />);
    await waitFor(() => expect(screen.getByText('graph-tools')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /mcp\.remove/ }));
    expect(urlsOf('DELETE')).toHaveLength(0);

    await waitFor(() => expect(document.querySelector('.ant-popconfirm-buttons')).toBeTruthy());
    const confirmBtn = document.querySelector('.ant-popconfirm-buttons .ant-btn-primary') as HTMLElement;
    fireEvent.click(confirmBtn);

    await waitFor(() => expect(urlsOf('DELETE')).toContain('/api/mcp/servers/srv-1'));
  });
});
