import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  getQualityReport,
  batchEvaluateReports,
  getDashboardSummary,
  getDashboardTermsTrend,
  getDashboardApprovalsBreakdown,
} from '../services/qualityApi';

const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

describe('qualityApi.ts: 质量闸 & 仪表盘 5 个 API URL 构造', () => {
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

  it('getDashboardSummary / getDashboardTermsTrend / getDashboardApprovalsBreakdown 存在并返回 Promise', async () => {
    mockFetch.mockResolvedValue({
      total_candidates: 0, by_status: {}, by_tier: {}, avg_gate_scores: {
        gate1_avg: 0, gate2_avg: 0, gate3_avg: 0, total_avg: 0,
      }, approval_times: {
        l1_avg_secs: 0, l2_avg_secs: 0, total_avg_secs: 0, l1_samples: 0, l2_samples: 0, total_samples: 0,
      },
    });
    const [s, t, b] = await Promise.all([
      getDashboardSummary('ws-1'),
      getDashboardTermsTrend(7, 'domain-x'),
      getDashboardApprovalsBreakdown('ws-1'),
    ]);
    expect(mockFetch).toHaveBeenCalledTimes(3);
    expect(s).toBeDefined();
    expect(t).toBeDefined();
    expect(b).toBeDefined();
    // 3 次调用 url 分别正确
    expect(String(mockFetch.mock.calls[0][0])).toContain('/dashboard/summary');
    expect(String(mockFetch.mock.calls[1][0])).toContain('/dashboard/terms-trend');
    expect(String(mockFetch.mock.calls[2][0])).toContain('/dashboard/approvals-breakdown');
  });
});
