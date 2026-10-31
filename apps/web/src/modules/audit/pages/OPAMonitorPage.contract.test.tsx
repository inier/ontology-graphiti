/**
 * OPAMonitorPage 契约测试
 *
 * 该页此前零引用，同时有两处缺陷：
 *   1) 指标拉取是空 catch —— 后端不可用时页面静默停在 0，
 *      看上去像"策略从未被调用"，与真实原因完全无关；
 *   2) `<Alert message={...}>` 是 AntD 6 已弃用属性（应为 title）。
 *
 * 断言粒度：端点与查询参数、关键指标渲染、失败原因可见性。
 */
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 保持稳定引用：组件把它放进 useCallback 依赖，否则 effect 会反复触发
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

const get = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: { get: (...args: unknown[]) => get(...args) },
}));

import { OPAMonitorPage } from './OPAMonitorPage';

const METRICS = {
  total_decisions: 120,
  allow_count: 90,
  deny_count: 30,
  deny_rate_percent: 25,
  latency_ms: { p50: 3, p95: 9, p99: 12, avg: 4.5 },
  by_package: { domain: { allow: 90, deny: 30 } },
  top_deny_reasons: [{ reason: 'cleared_below_secret', count: 30 }],
  audit_failures: 0,
  opa_unavailable_count: 1,
};

beforeEach(() => {
  get.mockReset();
});

describe('OPAMonitorPage — 策略运行时监控', () => {
  it('拉取 /api/opa/metrics?window=300 并渲染核心指标', async () => {
    get.mockResolvedValue(METRICS);

    render(<OPAMonitorPage />);

    await waitFor(() => expect(get).toHaveBeenCalledWith('/api/opa/metrics?window=300'));
    await waitFor(() => expect(screen.getByText('cleared_below_secret')).toBeTruthy());
    expect(screen.getByText('120')).toBeTruthy();
    expect(screen.getByText('25%')).toBeTruthy();
  });

  it('拉取失败时把失败原因显示出来，而不是静默停在 0', async () => {
    get.mockRejectedValue(new Error('503 Service Unavailable'));

    render(<OPAMonitorPage />);

    await waitFor(() => expect(screen.getByText('策略运行时指标拉取失败')).toBeTruthy());
    expect(screen.getByText(/503 Service Unavailable/)).toBeTruthy();
  });

  it('DENY 率超过阈值时给出异常告警（AntD 6 title 属性，不是已弃用的 message）', async () => {
    get.mockResolvedValue({ ...METRICS, deny_count: 80, allow_count: 20, deny_rate_percent: 80 });

    render(<OPAMonitorPage />);

    await waitFor(() => expect(screen.getByText('DENY 率异常')).toBeTruthy());
    // Alerts 的 message 属性在 AntD 6 已废弃，会渲染不出来；这里确认描述也真的渲染了
    expect(screen.getByText('{{rate}}% 的请求被拒绝，请检查策略配置')).toBeTruthy();
  });
});
