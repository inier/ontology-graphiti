import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  listConfig,
  getConfig,
  setConfig,
  getDomainConfig,
  ensureBuiltinConfig,
} from '../services/saConfigApi';

const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

describe('saConfigApi.ts: 动态配置 5 个 API URL/Method 严格对齐 AGENTS.md §F', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({});
  });

  it('listConfig(scope, prefix): GET /config?scope=global&prefix=quality', async () => {
    await listConfig({ scope: 'global', prefix: 'quality' });
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/api/semantic-admin/config');
    expect(url).toContain('scope=global');
    expect(url).toContain('prefix=quality');
  });

  it('getConfig(scope, key): GET /config/{scope}/{key}', async () => {
    mockFetch.mockResolvedValueOnce({
      scope: 'quality_gate', key: 'g1_weight_name_valid', value: 0.35,
    });
    await getConfig('quality_gate', 'g1_weight_name_valid');
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/config/quality_gate/g1_weight_name_valid');
  });

  it('setConfig: PUT JSON body 含 value', async () => {
    mockFetch.mockResolvedValueOnce({
      scope: 'global', key: 'enable_auto_skip_l2', value: true,
    });
    await setConfig('global', 'enable_auto_skip_l2', true, 'admin-1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/config/global/enable_auto_skip_l2');
    expect((opts as RequestInit).method).toBe('PUT');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.value).toBe(true);
    expect(body.updated_by).toBe('admin-1');
  });

  it('getDomainConfig(code): GET /config/domain/{domain_code}', async () => {
    await getDomainConfig('finance_core');
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/config/domain/finance_core');
  });

  it('ensureBuiltinConfig(forceReset=true): POST /ensure-builtin?force=1 幂等', async () => {
    mockFetch.mockResolvedValueOnce({ inserted: 42, skipped: 8, total: 50 });
    const ret = await ensureBuiltinConfig(true);
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/ensure-builtin?force=1');
    expect((opts as RequestInit).method).toBe('POST');
    expect(ret.total).toBe(50);
    expect(ret.inserted + ret.skipped).toBe(ret.total);
  });
});
