import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getExtractorMode, setExtractorMode } from '../services/extractorModeApi';

const mockFetch = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (...args: unknown[]) => mockFetch(...args),
}));

describe('extractorModeApi: 提取模式 2 个 API URL/Method 对齐 ADR-089 C-D11', () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({});
  });

  it('getExtractorMode: GET /api/semantic-admin/extractor-mode', async () => {
    await getExtractorMode();
    const url = String(mockFetch.mock.calls[0][0]);
    expect(url).toContain('/api/semantic-admin/extractor-mode');
    expect(mockFetch.mock.calls[0][1]).toBeUndefined(); // GET 无 opts
  });

  it('setExtractorMode: PUT JSON body 含 mode', async () => {
    await setExtractorMode('inject', 'admin-1');
    const [url, opts] = mockFetch.mock.calls[0];
    expect(String(url)).toContain('/api/semantic-admin/extractor-mode');
    expect((opts as RequestInit).method).toBe('PUT');
    const body = JSON.parse((opts as RequestInit).body as string);
    expect(body.mode).toBe('inject');
    expect(body.updated_by).toBe('admin-1');
  });
});
