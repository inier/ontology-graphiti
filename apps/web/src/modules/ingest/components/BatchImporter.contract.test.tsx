/**
 * BatchImporter 契约测试
 *
 * 该组件此前零引用，而且一旦挂载就会踩三个硬错误：
 *   1) 打到 `/api/ingest/batch?scenario_id=...` —— 该路径不存在（/api/ingest 只有
 *      /unified 与 /source-types），真实端点是 `/api/ontology/ingestion/batch`；
 *   2) 把 `scenarioId` 当 `entity_type_id` 传到 body —— 语义错位，即使路径对了也会导错类型；
 *   3) 构造了 FormData 但从未使用（死代码）。
 *
 * 断言粒度：URL、body 字段语义、以及"没有目标类型时不发请求"的负向约束。
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
    AdvancedTable: ({
      columns,
      dataSource,
    }: {
      columns: Array<{ title: ReactNode; key?: string; dataIndex?: string; render?: (v: unknown, r: unknown) => ReactNode }>;
      dataSource?: Array<Record<string, unknown>>;
    }) =>
      React.createElement(
        'table',
        { 'data-testid': 'error-table' },
        React.createElement(
          'tbody',
          null,
          (dataSource ?? []).map((row, i) =>
            React.createElement(
              'tr',
              { key: i, 'data-testid': `error-row-${i}` },
              columns.map((col, j) => {
                const value = col.dataIndex ? row[col.dataIndex] : undefined;
                return React.createElement('td', { key: col.key ?? j }, col.render ? col.render(value, row) : String(value ?? ''));
              }),
            ),
          ),
        ),
      ),
  };
});

const fetchJson = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => fetchJson(...args),
}));

import { API_BASE } from '@/config';
import BatchImporter from './BatchImporter';

const OBJECT_TYPES_URL = `${API_BASE}/api/ontology/oms/object-types`;
const BATCH_URL = `${API_BASE}/api/ontology/ingestion/batch`;

function mockRoutes(overrides: Record<string, unknown> = {}) {
  fetchJson.mockImplementation((url: string, init?: { method?: string }) => {
    if (url === OBJECT_TYPES_URL) {
      return Promise.resolve(overrides[url] ?? [
        { type_id: 'Order', name: '订单', properties: [{ name: 'order_id' }, { name: 'amount' }] },
      ]);
    }
    if (url === BATCH_URL) {
      return Promise.resolve(
        overrides[url] ?? {
          status: 'success',
          success_count: 2,
          fail_count: 1,
          errors: [{ row: 3, error: 'amount 不是合法数字' }],
          format: 'csv',
          entity_type_id: 'Order',
          workspace_id: 'ws-1',
        },
      );
    }
    return Promise.reject(new Error(`unexpected: ${init?.method ?? 'GET'} ${url}`));
  });
}

function uploadCsv(content = 'order_id,amount\nO-1,100') {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  expect(input).toBeTruthy();
  const file = new File([content], 'orders.csv', { type: 'text/csv' });
  Object.defineProperty(input, 'files', { value: [file], configurable: true });
  fireEvent.change(input);
  return file;
}

async function selectObjectType() {
  fireEvent.mouseDown(screen.getByLabelText('目标对象类型'));
  const option = await waitFor(() => {
    const el = Array.from(document.querySelectorAll('.ant-select-item-option')).find((o) =>
      (o.textContent ?? '').includes('Order'),
    );
    if (!el) throw new Error('option not found');
    return el as HTMLElement;
  });
  fireEvent.click(option);
}

beforeEach(() => {
  fetchJson.mockReset();
  mockRoutes();
});

describe('BatchImporter — 结构化批量导入', () => {
  it('对象类型下拉走 /api/ontology/oms/object-types（不是不存在的 /api/ontology/object-types）', async () => {
    render(<BatchImporter workspaceId="ws-1" />);

    await waitFor(() => expect(fetchJson).toHaveBeenCalledWith(OBJECT_TYPES_URL));
    // 负向断言：历史路径不存在
    expect(fetchJson).not.toHaveBeenCalledWith(`${API_BASE}/api/ontology/object-types`);
  });

  it('未选择目标类型时「开始导入」不可用，不会空发请求', async () => {
    render(<BatchImporter workspaceId="ws-1" />);
    await waitFor(() => expect(fetchJson).toHaveBeenCalledWith(OBJECT_TYPES_URL));
    uploadCsv();

    const button = screen.getByRole('button', { name: /开始导入/ }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(fetchJson).not.toHaveBeenCalledWith(BATCH_URL, expect.anything());
  });

  it('导入打 POST /api/ontology/ingestion/batch，body 的 entity_type_id 来自选择项', async () => {
    render(<BatchImporter workspaceId="ws-1" />);
    await waitFor(() => expect(fetchJson).toHaveBeenCalledWith(OBJECT_TYPES_URL));

    await selectObjectType();
    uploadCsv('order_id,amount\nO-1,100');

    fireEvent.click(screen.getByRole('button', { name: /开始导入/ }));

    await waitFor(() => {
      const call = fetchJson.mock.calls.find((c) => c[0] === BATCH_URL);
      expect(call).toBeTruthy();
      const body = JSON.parse((call![1] as { body: string }).body);
      expect(body.entity_type_id).toBe('Order');
      expect(body.format).toBe('csv');
      expect(body.workspace_id).toBe('ws-1');
      expect(body.data).toContain('order_id,amount');
    });

    // 负向断言：绝不能再打到 /api/ingest/batch
    expect(fetchJson).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/ingest/batch'),
      expect.anything(),
    );
  });

  it('逐行失败回执被渲染（行号 + 原因）', async () => {
    render(<BatchImporter workspaceId="ws-1" />);
    await waitFor(() => expect(fetchJson).toHaveBeenCalledWith(OBJECT_TYPES_URL));

    await selectObjectType();
    uploadCsv();
    fireEvent.click(screen.getByRole('button', { name: /开始导入/ }));

    await waitFor(() => expect(screen.getByTestId('error-table')).toBeTruthy());
    expect(screen.getByText('amount 不是合法数字')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('对象类型拉取失败时显示失败原因与重试入口', async () => {
    fetchJson.mockReset();
    fetchJson.mockImplementation((url: string) => {
      if (url === OBJECT_TYPES_URL) return Promise.reject(new Error('403 Forbidden'));
      return Promise.resolve({});
    });

    render(<BatchImporter workspaceId="ws-1" />);

    await waitFor(() => expect(screen.getByText('对象类型列表拉取失败')).toBeTruthy());
    expect(screen.getByText('403 Forbidden')).toBeTruthy();
    // AntD 的 autoInsertSpace 会在两个 CJK 字符间插空格（"重试" → "重 试"）
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeTruthy();
  });
});
