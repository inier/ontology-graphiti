import { describe, it, expect, vi, beforeEach } from 'vitest';
import { gapApi } from '../services/gapApi';

// 拦截 fetchJson 调用（不发起真实 HTTP）
const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

describe('gapApi.ts: 缺口池 6 个方法与 URL 构造', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ items: [], total: 0 });
  });

  it('list: GET /api/semantic-admin/gaps/ 且 querystring 含 status=open & page=1', async () => {
    await gapApi.list({ status: 'open', page: 1, page_size: 20 });
    expect(mockFetch).toHaveBeenCalledTimes(1);
    const called = mockFetch.mock.calls[0][0] as string;
    expect(called).toContain('/api/semantic-admin/gaps/');
    expect(called).toContain('status=open');
    expect(called).toContain('page=1');
    expect(called).toContain('page_size=20');
  });

  it('list: 过滤掉 null/undefined 参数，不进 querystring', async () => {
    await gapApi.list({ status: 'open', source: undefined, page: 2 });
    const called = mockFetch.mock.calls[0][0] as string;
    const qs = called.slice(called.indexOf('?') + 1);
    const params = new URLSearchParams(qs);
    expect(params.get('status')).toBe('open');
    expect(params.get('page')).toBe('2');
    expect(called).not.toContain('source=');
    expect(called.match(/\?/g)).toHaveLength(1);
  });

  it('get: GET /api/semantic-admin/gaps/{id}', async () => {
    await gapApi.get('gap-1');
    const called = mockFetch.mock.calls[0][0] as string;
    expect(called).toContain('/api/semantic-admin/gaps/gap-1');
  });

  it('promote: POST .../{id}/promote 且 body 含 domain_id/workspace_id', async () => {
    mockFetch.mockResolvedValueOnce({ candidate_id: 'cand-9' });
    await gapApi.promote('gap-2', { domain_id: 'd-1', workspace_id: 'ws-1' });
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/api/semantic-admin/gaps/gap-2/promote');
    expect((opts as RequestInit).method).toBe('POST');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.domain_id).toBe('d-1');
    expect(body.workspace_id).toBe('ws-1');
  });

  it('dismiss: POST .../{id}/dismiss 且 body 含 reason', async () => {
    mockFetch.mockResolvedValueOnce({ status: 'rejected' });
    await gapApi.dismiss('gap-3', '重复说法');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/api/semantic-admin/gaps/gap-3/dismiss');
    expect((opts as RequestInit).method).toBe('POST');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.reason).toBe('重复说法');
  });

  it('resolveCheck: GET .../{id}/resolve-check', async () => {
    mockFetch.mockResolvedValueOnce({ resolvable: true, via: 'usl', detail: 'ok' });
    await gapApi.resolveCheck('gap-4');
    const called = mockFetch.mock.calls[0][0] as string;
    expect(called).toContain('/api/semantic-admin/gaps/gap-4/resolve-check');
  });

  it('stats: GET .../stats', async () => {
    await gapApi.stats();
    const called = mockFetch.mock.calls[0][0] as string;
    expect(called).toContain('/api/semantic-admin/gaps/stats');
  });
});
