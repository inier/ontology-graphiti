/**
 * HealthDashboardPage 契约测试 —— 本体质量健康度
 *
 * 这个页面此前是「契约虚构」：旧实现把报告维度字段（status / failure_count /
 * last_checked_at）挂在规则上，用 `rule_id` 当主键，并打两个后端不存在的端点
 * （`POST /rules/{id}/scan`、`GET /rules/{id}/violations`），还给 `/reports`
 * 发了后端不接受的 `days=30`。与此同时后端这套 router **根本没注册**
 * （health/api/routes.py 有 9 个端点，router_registry 里没有它）。
 *
 * 所以这里钉的是「双向对齐」：
 *  ① 前端不得再出现虚构端点 / 虚构字段；
 *  ② 规则主键用 `id`，状态只从「报告」读。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 必须是稳定引用：组件把它放进 useCallback 依赖，否则 effect 会反复触发
  const t = (key: string, opts?: Record<string, unknown>) =>
    opts && Object.keys(opts).length ? `${key}|${JSON.stringify(opts)}` : key;
  return { useI18n: () => ({ t }) };
});

type Call = { method: string; url: string; body?: unknown };
const calls: Call[] = [];

const RULES_URL = '/api/ontology/health/rules';
const REPORTS_URL = '/api/ontology/health/reports?limit=200';
const TYPES_URL = '/api/ontology/oms/object-types';

const RAW_RULE = {
  id: 'r-1',
  target_type_id: 'Customer',
  name: '客户必须有手机号',
  description: '',
  rule_type: 'not_null',
  check_expression: { field: 'phone' },
  severity: 'error',
  schedule: '',
  notification_channel: {},
  enabled: true,
  created_at: '2026-10-19T00:00:00Z',
  updated_at: '2026-10-19T00:00:00Z',
};

const RAW_REPORT = {
  id: 'rep-1',
  rule_id: 'r-1',
  instance_id: 'cust-42',
  target_type_id: 'Customer',
  status: 'FAIL',
  severity: 'error',
  message: 'phone 为空',
  details: {},
  scanned_at: '2026-10-19T10:00:00Z',
};

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (url: string) => {
      calls.push({ method: 'GET', url });
      if (url === RULES_URL) return Promise.resolve({ rules: [RAW_RULE], count: 1 });
      if (url === REPORTS_URL) return Promise.resolve({ reports: [RAW_REPORT], count: 1, total: 1, limit: 200, offset: 0 });
      if (url === TYPES_URL) return Promise.resolve([{ type_id: 'Customer', name: '客户' }]);
      return Promise.reject(new Error(`unexpected GET ${url}`));
    },
    post: (url: string, body?: unknown) => {
      calls.push({ method: 'POST', url, body });
      if (url === '/api/ontology/health/scan') {
        return Promise.resolve({
          scanned_count: 2,
          pass_count: 1,
          warn_count: 0,
          fail_count: 1,
          rule_id: (body as { rule_id?: string })?.rule_id ?? null,
          reports: [RAW_REPORT],
        });
      }
      if (url === RULES_URL) return Promise.resolve({ rules: [RAW_RULE], count: 1 });
      return Promise.reject(new Error(`unexpected POST ${url}`));
    },
    put: (url: string, body?: unknown) => {
      calls.push({ method: 'PUT', url, body });
      return Promise.resolve({ ...RAW_RULE, enabled: false });
    },
    delete: (url: string) => {
      calls.push({ method: 'DELETE', url });
      return Promise.resolve({ id: 'r-1', deleted: true });
    },
  },
}));

import { HealthDashboardPage } from './HealthDashboard';

const urlsOf = (method?: string) =>
  calls.filter((c) => !method || c.method === method).map((c) => c.url);

beforeEach(() => {
  calls.length = 0;
});

describe('HealthDashboardPage — 质量健康度', () => {
  it('加载规则与报告走真实端点，不给 /reports 传 days 参数', async () => {
    render(<HealthDashboardPage />);

    await waitFor(() => expect(screen.getByText('客户必须有手机号')).toBeTruthy());

    expect(urlsOf('GET')).toContain(RULES_URL);
    expect(urlsOf('GET')).toContain(REPORTS_URL);
    // 负向断言：后端 list_reports 没有 days 参数，传了会被静默忽略（= 时间过滤永不生效）
    expect(urlsOf('GET').some((u) => u.includes('days='))).toBe(false);
  });

  it('状态来自报告而不是规则：规则表不渲染 status / failure_count 列', async () => {
    render(<HealthDashboardPage />);
    await waitFor(() => expect(screen.getByText('客户必须有手机号')).toBeTruthy());

    // 规则表只应有关键列；旧实现那两列渲染出来必然是空白
    expect(screen.queryByText('失败数')).toBeNull();
    expect(screen.queryByText('最近检查')).toBeNull();
    // 目标类型来自 target_type_id
    expect(screen.getByText('Customer')).toBeTruthy();
  });

  it('运行扫描打 POST /scan，且不把 workspace_id 塞进报文', async () => {
    render(<HealthDashboardPage />);
    await waitFor(() => expect(screen.getByText('客户必须有手机号')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /运行扫描/ }));

    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.url === '/api/ontology/health/scan')).toBe(true),
    );
    const scan = calls.find((c) => c.url === '/api/ontology/health/scan')!;
    expect(scan.body).toEqual({});
  });

  it('单规则扫描仍走 POST /scan {rule_id}，不得请求不存在的 /rules/{id}/scan 或 /violations', async () => {
    render(<HealthDashboardPage />);
    await waitFor(() => expect(screen.getByText('客户必须有手机号')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /扫描此规则/ }));

    await waitFor(() =>
      expect(calls.some((c) => c.url === '/api/ontology/health/scan' && (c.body as { rule_id?: string }).rule_id === 'r-1')).toBe(true),
    );
    // 负向断言：这两个端点后端不存在，打过去必然 404
    expect(urlsOf().some((u) => /\/rules\/r-1\/scan/.test(u))).toBe(false);
    expect(urlsOf().some((u) => u.includes('/violations'))).toBe(false);
  });

  it('删除规则需二次确认，确认后走 DELETE /rules/{id}', async () => {
    render(<HealthDashboardPage />);
    await waitFor(() => expect(screen.getByText('客户必须有手机号')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: /删\s*除/ }));
    // 未确认前不得发请求
    expect(urlsOf('DELETE')).toHaveLength(0);

    await waitFor(() => expect(document.querySelector('.ant-popconfirm-buttons')).toBeTruthy());
    const confirmBtn = document.querySelector('.ant-popconfirm-buttons .ant-btn-primary') as HTMLElement;
    fireEvent.click(confirmBtn);

    await waitFor(() => expect(urlsOf('DELETE')).toContain('/api/ontology/health/rules/r-1'));
  });

  it('规则主键是 id：启停走 PUT /rules/{id} 且只提交 enabled', async () => {
    render(<HealthDashboardPage />);
    await waitFor(() => expect(screen.getByText('客户必须有手机号')).toBeTruthy());

    const toggle = document.querySelector('.ant-switch') as HTMLElement;
    expect(toggle).toBeTruthy();
    fireEvent.click(toggle);

    await waitFor(() => expect(urlsOf('PUT')).toContain('/api/ontology/health/rules/r-1'));
    const put = calls.find((c) => c.method === 'PUT')!;
    expect(put.body).toEqual({ enabled: false });
  });
});
