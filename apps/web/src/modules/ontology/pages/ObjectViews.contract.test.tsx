/**
 * 对象视图页面契约测试（ObjectViewPage + ViewDesigner + ObjectViewsPage 组合）
 *
 * 这一组此前全是零引用：后端 `/api/ontology/views` 一整套 CRUD/查询/导出/权限都已实现，
 * 前端组件也写好了，但没有任何路由或按钮能到达。挂载时锁定三件事：
 *   1) 列表与查询打的是 `/api/ontology/views`，不是别的聚合端点；
 *   2) 编辑模式按 viewId 拉取详情，新建模式**不得**发 `GET /views/{id}`；
 *   3) 新建保存走 POST /api/ontology/views，body 必带后端要求的 name / base_type_id / role；
 *      且未选数据源时不许空发请求（后端会 422，前端应先拦）。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 保持稳定引用：组件把它放进 useCallback 依赖，否则 effect 会反复触发
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

vi.mock('@/modules/shared/components/LayoutContexts', () => ({
  useWorkspace: () => ({ currentWorkspace: 'ws-1' }),
}));

vi.mock('@/modules/shared', async () => {
  const React = await import('react');
  return {
    wrapRequest: (fetcher: () => Promise<unknown[]>) => async () => {
      const data = await fetcher();
      return { data, success: true, total: data.length };
    },
    AdvancedTable: ({
      columns,
      dataSource,
    }: {
      columns: Array<{
        title: ReactNode;
        key?: string;
        dataIndex?: string;
        render?: (v: unknown, r: unknown) => ReactNode;
      }>;
      dataSource?: Array<Record<string, unknown>>;
    }) => {
      const rows = dataSource ?? [];
      return React.createElement(
        'table',
        null,
        React.createElement(
          'thead',
          null,
          React.createElement(
            'tr',
            null,
            columns.map((c, i) => React.createElement('th', { key: c.key ?? i }, c.title)),
          ),
        ),
        React.createElement(
          'tbody',
          null,
          rows.map((row, i) =>
            React.createElement(
              'tr',
              { key: i, 'data-testid': `row-${i}` },
              columns.map((col, j) => {
                const value = col.dataIndex ? row[col.dataIndex] : undefined;
                return React.createElement(
                  'td',
                  { key: col.key ?? j },
                  col.render ? col.render(value, row) : String(value ?? ''),
                );
              }),
            ),
          ),
        ),
      );
    },
  };
});

const fetchJson = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => fetchJson(...args),
}));

import { API_BASE } from '@/config';
import { ObjectViewsPage } from './ObjectViewsPage';

const BASE = `${API_BASE}/api/ontology/views`;

const RAW_VIEW = {
  id: 'v-1',
  name: '订单明细',
  description: '',
  base_type_id: 'Order',
  role: 'viewer',
  projected_properties: ['order_id', 'amount'],
  filters: { amount: { gt: 100 } },
  row_limit: 200,
  sort_order: [{ property: 'amount', direction: 'desc' }],
  enabled: true,
  created_by: 'system',
  created_at: '',
  updated_at: '',
};

function routeFetchJson(url: string, init?: { method?: string; body?: string }) {
  const method = (init?.method || 'GET').toUpperCase();
  if (url === `${BASE}?workspace_id=ws-1`) {
    return Promise.resolve({ views: [RAW_VIEW], count: 1 });
  }
  if (url === `${BASE}` && method === 'POST') {
    return Promise.resolve({ ...RAW_VIEW, id: 'v-new', name: '新建视图A' });
  }
  if (url === `${BASE}/v-1` && method === 'PUT') {
    return Promise.resolve({ ...RAW_VIEW, enabled: false });
  }
  if (url === `${BASE}/v-1` && method === 'DELETE') {
    return Promise.resolve({ view_id: 'v-1', deleted: true });
  }
  if (url === `${BASE}/v-1`) {
    return Promise.resolve(RAW_VIEW);
  }
  if (url === `${BASE}/v-new`) {
    return Promise.resolve({ ...RAW_VIEW, id: 'v-new' });
  }
  if (url === `${BASE}/v-1/query` || url === `${BASE}/v-new/query`) {
    return Promise.resolve({ rows: [{ order_id: 'O-1', amount: 500 }], total: 1, limit: 200 });
  }
  if (url === `${BASE}/v-1/permissions`) {
    return Promise.resolve({
      permissions: [{ id: 'p-1', view_id: 'v-1', role: 'viewer', can_export: true, can_share: false, redaction_rules: {}, created_at: '' }],
      count: 1,
    });
  }
  if (url === `${API_BASE}/api/ontology/oms/object-types`) {
    // 真实端点返回的是数组（response_model=List[ObjectTypeDefinition]），
    // 属性类型字段是 property_type
    return Promise.resolve([
      {
        type_id: 'Order',
        name: '订单',
        properties: [
          { name: 'order_id', property_type: 'string' },
          { name: 'amount', property_type: 'double' },
        ],
      },
    ]);
  }
  return Promise.reject(new Error(`unexpected url: ${method} ${url}`));
}

beforeEach(() => {
  fetchJson.mockReset();
  fetchJson.mockImplementation((url: string, init?: { method?: string; body?: string }) =>
    routeFetchJson(url, init),
  );
});

describe('ObjectViewsPage — 对象视图', () => {
  it('列表按 workspace_id 走 /api/ontology/views，选中后按视图 id 查询', async () => {
    render(<ObjectViewsPage />);

    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());
    expect(fetchJson).toHaveBeenCalledWith(`${BASE}?workspace_id=ws-1`);

    await waitFor(() =>
      expect(fetchJson).toHaveBeenCalledWith(
        `${BASE}/v-1/query`,
        expect.objectContaining({ method: 'POST' }),
      ),
    );
  });

  it('编辑模式：点击「设计此视图」按 viewId 拉详情，且不发创建请求', async () => {
    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /设计此视图/ }));

    await waitFor(() => expect(screen.getByTestId('view-designer')).toBeTruthy());
    await waitFor(() => expect(fetchJson).toHaveBeenCalledWith(`${BASE}/v-1`));

    // 负向断言：编辑模式不能走 POST /views
    const postCalls = fetchJson.mock.calls.filter(
      (c) => c[1] && (c[1] as { method?: string }).method === 'POST' && c[0] === BASE,
    );
    expect(postCalls).toHaveLength(0);
  });

  it('新建模式：不发 GET /views/{id}，未选数据源时保存被前端拦下', async () => {
    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /新建视图/ }));
    await waitFor(() => expect(screen.getByTestId('view-designer')).toBeTruthy());

    // 负向断言：新建模式没有 viewId，不应去拉某个视图详情
    expect(fetchJson).not.toHaveBeenCalledWith(`${BASE}/v-1`);

    fireEvent.change(screen.getByLabelText('视图名称'), { target: { value: '新建视图A' } });
    fireEvent.click(screen.getByRole('button', { name: /保存/ }));

    // 未选数据源 → 只提示，不发请求
    await waitFor(() => expect(screen.getByText('请选择数据源类型')).toBeTruthy());
    const createCalls = fetchJson.mock.calls.filter(
      (c) => c[0] === BASE && c[1] && (c[1] as { method?: string }).method === 'POST',
    );
    expect(createCalls).toHaveLength(0);
  });

  it('新建保存走 POST /api/ontology/views，body 带 name/base_type_id/role 与投影字段', async () => {
    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /新建视图/ }));
    await waitFor(() => expect(screen.getByTestId('view-designer')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('视图名称'), { target: { value: '新建视图A' } });

    // 选数据源：点击对象类型树节点
    const treeNode = await waitFor(() => screen.getByText('订单'));
    fireEvent.click(treeNode);
    // 再点一个字段加入投影列
    fireEvent.click(screen.getByText('amount (double)'));

    fireEvent.click(screen.getByRole('button', { name: /保存/ }));

    await waitFor(() => {
      const call = fetchJson.mock.calls.find(
        (c) => c[0] === BASE && c[1] && (c[1] as { method?: string }).method === 'POST',
      );
      expect(call).toBeTruthy();
      const body = JSON.parse((call![1] as { body: string }).body);
      expect(body.name).toBe('新建视图A');
      expect(body.base_type_id).toBe('Order');
      // 后端 CreateViewRequest.role 必填
      expect(body.role).toBe('viewer');
      expect(body.projected_properties).toEqual(['amount']);
    });
  });

  it('导出走 /views/{id}/export?format=csv（不是把行数据打给后端）', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => new Blob(['a,b']),
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:x', revokeObjectURL: () => {} });

    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    const csvButtons = await waitFor(() => screen.getAllByRole('button', { name: /CSV/ }));
    fireEvent.click(csvButtons[0]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        `${BASE}/v-1/export?format=csv`,
        expect.objectContaining({ headers: expect.any(Object) }),
      );
    });
  });
});

/**
 * 视图生命周期（克隆 / 启停 / 删除）。
 *
 * 这三项原先只在零引用的 `ObjectViewList` 里，那张表与本页左侧列表是同一份数据的两套呈现。
 * 处置方式是把本页缺的能力并进来、删掉那张表 —— 因此这里必须钉住「能力没有随删除丢失」。
 */
describe('ObjectViewPage — 视图生命周期', () => {
  it('克隆用 POST /views 复制，不请求不存在的 /{id}/clone 端点', async () => {
    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: '克隆视图 订单明细' }));

    await waitFor(() => {
      const call = fetchJson.mock.calls.find(
        (c) => c[0] === BASE && c[1] && (c[1] as { method?: string }).method === 'POST',
      );
      expect(call).toBeTruthy();
      const body = JSON.parse((call![1] as { body: string }).body);
      expect(body.name).toBe('订单明细 (copy)');
      expect(body.base_type_id).toBe('Order');
      expect(body.projected_properties).toEqual(['order_id', 'amount']);
      // 后端没有 clone 端点，不能臆造
      expect(body.sort_order).toEqual([{ property: 'amount', direction: 'desc' }]);
    });

    // 负向断言：不得请求 /views/{id}/clone
    const bogus = fetchJson.mock.calls.filter((c) => String(c[0]).includes('/clone'));
    expect(bogus).toHaveLength(0);
  });

  it('启停走 PUT /views/{id} 且 body 只带 enabled', async () => {
    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    // 视图当前 enabled=true → 按钮语义是「停用」
    fireEvent.click(screen.getByRole('button', { name: '停用 订单明细' }));

    await waitFor(() => {
      const call = fetchJson.mock.calls.find(
        (c) => c[0] === `${BASE}/v-1` && c[1] && (c[1] as { method?: string }).method === 'PUT',
      );
      expect(call).toBeTruthy();
      expect(JSON.parse((call![1] as { body: string }).body)).toEqual({ enabled: false });
    });
  });

  it('删除走 DELETE /views/{id}，需二次确认，且删的是被点的那一个', async () => {
    render(<ObjectViewsPage />);
    await waitFor(() => expect(screen.getByText('订单明细')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: '删除视图 订单明细' }));

    const confirm = await waitFor(() => {
      const box = document.querySelector('.ant-popconfirm');
      if (!box) throw new Error('popconfirm not opened');
      const buttons = box.querySelectorAll('button');
      if (buttons.length < 2) throw new Error('popconfirm buttons not found');
      return buttons[1] as HTMLButtonElement;
    });
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(fetchJson).toHaveBeenCalledWith(`${BASE}/v-1`, { method: 'DELETE' }),
    );
  });
});
