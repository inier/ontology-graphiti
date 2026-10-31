import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getQualityReport, batchEvaluateReports } from '../services/qualityApi';

const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

/**
 * 注：本文件原先还测 3 个 `getDashboard*` 函数。它们只服务于
 * `semantic-admin/pages/DashboardPage.tsx`，而后者与 `QualityDashboardPage`
 * 打同一组端点（`/api/semantic-admin/dashboard/*`），`legacyRedirects` 也已把
 * `/semantic-admin/dashboard` 收敛到 `/semantic-admin/quality` —— 页面与函数
 * 一并删除，这里同步收敛为「质量闸」两个方法的 URL 契约。
 *
 * 仪表盘三端点仍在使用（QualityDashboardPage 直接 fetch），其 URL 断言见
 * `pages/QualityDashboardPage` 相关测试。
 */
describe('qualityApi.ts: 质量闸 2 个 API URL 构造', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('getQualityReport(candId, force=true): GET /quality-gate/reports/{candId}?force=true', async () => {
    mockFetch.mockResolvedValueOnce({
      report_id: 'r-1', candidate_id: 'c-1', total_score: 0.92, tier: 'HIGH',
    });
    await getQualityReport('c-1', true);
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/quality-gate/reports/c-1');
    expect(url).toContain('force=true');
  });

  it('batchEvaluateReports: POST JSON 含 candidate_ids + sync + actor_id', async () => {
    mockFetch.mockResolvedValueOnce({ queued: 3 });
    await batchEvaluateReports(['c1', 'c2', 'c3'], true, 'admin-1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/quality-gate/reports');
    expect((opts as RequestInit).method).toBe('POST');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.candidate_ids).toEqual(['c1', 'c2', 'c3']);
    expect(body.sync).toBe(true);
    expect(body.actor_id).toBe('admin-1');
  });
});
