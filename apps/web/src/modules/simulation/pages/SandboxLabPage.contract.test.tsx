/**
 * SandboxLabPage 契约测试 —— 仿真推演工作台
 *
 * 这个页面的存在意义是「动线」：沙箱试跑 → 参数 what-if → 反馈闭环，
 * 三段是同一条链路。此前三块能力分散在三个未挂载的组件里（其中两个还是
 * 契约虚构），用户要跳三个不存在的地方才能走完一条链路。
 *
 * 所以这里钉的不是某个端点，而是**三块能力在同页可达**，且默认落点是沙箱。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

vi.mock('@/modules/ontology/stores/ontologyStore', () => ({
  useOntologyStore: (selector: (s: { ontologies: unknown[]; currentOntology: unknown }) => unknown) =>
    selector({
      ontologies: [{ ontology_id: 'ont-1', name: '供应链本体' }],
      currentOntology: { ontology_id: 'ont-1', name: '供应链本体' },
    }),
}));

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
    }: {
      request?: () => Promise<{ data: Array<Record<string, unknown>> }>;
      dataSource?: Array<Record<string, unknown>>;
      columns: Array<{ title: ReactNode; key: string; dataIndex?: string; render?: (v: unknown, r: unknown) => ReactNode }>;
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
          rows.map((row, i) =>
            React.createElement(
              'tr',
              { key: i },
              columns.map((col) =>
                React.createElement(
                  'td',
                  { key: col.key },
                  col.render
                    ? col.render(col.dataIndex ? row[col.dataIndex] : undefined, row)
                    : String((col.dataIndex ? row[col.dataIndex] : '') ?? ''),
                ),
              ),
            ),
          ),
        ),
      );
    },
  };
});

type Call = { method: string; url: string; body?: unknown };
const calls: Call[] = [];

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (url: string) => {
      calls.push({ method: 'GET', url });
      if (url === '/api/simulation/sandbox') {
        return Promise.resolve({
          sandboxes: [
            {
              sandbox_id: 'sb-1',
              ontology_id: 'ont-1',
              status: 'running',
              created_at: '2026-10-19T09:00:00Z',
              resources: {},
            },
          ],
        });
      }
      return Promise.resolve({});
    },
    post: (url: string, body?: unknown) => {
      calls.push({ method: 'POST', url, body });
      return Promise.resolve({ sandbox_id: 'sb-2', status: 'created' });
    },
    delete: (url: string) => {
      calls.push({ method: 'DELETE', url });
      return Promise.resolve({ deleted: true });
    },
  },
}));

import { SandboxLabPage } from './SandboxLabPage';

beforeEach(() => {
  calls.length = 0;
});

describe('SandboxLabPage — 仿真推演工作台', () => {
  it('三个能力在同页可达：沙箱 / 假设推演 / 反馈闭环', async () => {
    render(<SandboxLabPage />);

    await waitFor(() => expect(screen.getByRole('tab', { name: /沙箱/ })).toBeTruthy());
    expect(screen.getByRole('tab', { name: /假设推演/ })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /反馈闭环/ })).toBeTruthy();
  });

  it('默认落点是沙箱页签，且会拉沙箱列表', async () => {
    render(<SandboxLabPage />);

    await waitFor(() => expect(calls.some((c) => c.method === 'GET' && c.url === '/api/simulation/sandbox')).toBe(true));
    const activeTab = document.querySelector('.ant-tabs-tab-active');
    expect(activeTab?.textContent).toContain('沙箱');
  });

  it('切到「假设推演」后出现参数变体表单（WhatIfPanel 真的挂上了）', async () => {
    render(<SandboxLabPage />);
    await waitFor(() => expect(screen.getByRole('tab', { name: /假设推演/ })).toBeTruthy());

    fireEvent.click(screen.getByRole('tab', { name: /假设推演/ }));

    await waitFor(() => expect(screen.getByPlaceholderText('参数名')).toBeTruthy());
    expect(screen.getByRole('button', { name: /开始推演/ })).toBeTruthy();
  });
});
