/**
 * Wiki 服务层测试（真实 HTTP 路径 / 错误契约解析）
 *
 * mock 关闭时（VITE_WIKI_MOCK=off）必须严格按 SPEC §5 的错误契约解析：
 * `{ error_code, message, detail, trace_id }` —— 缺字段时不得崩、不得显示 undefined。
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type WikiApiModule = typeof import('../services/wikiApi');

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'ERROR',
    json: async () => body,
  } as unknown as Response;
}

describe('wikiApi（真实 HTTP 路径）', () => {
  let wikiApi: WikiApiModule['wikiApi'];
  const fetchMock = vi.fn();

  beforeEach(async () => {
    vi.resetModules();
    vi.stubEnv('VITE_WIKI_MOCK', 'off');
    globalThis.fetch = fetchMock as unknown as typeof fetch;
    fetchMock.mockReset();
    const mod = await import('../services/wikiApi');
    wikiApi = mod.wikiApi;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('列表请求命中 SPEC 端点并携带分页/筛选 query', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: [], total: 0, page: 2, page_size: 20 }));
    await wikiApi.listEntries({ status: 'review', owner: 'u-pm-lin', tag: '术语对齐', keyword: '流失', page: 2, page_size: 20 });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/v1/wiki/entries?');
    expect(url).toContain('status=review');
    expect(url).toContain('page=2');
    expect(url).toContain('page_size=20');
    expect(decodeURIComponent(url)).toContain('keyword=流失');
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('status=all 不作为 query 下发（后端只认具体状态）', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: [], total: 0, page: 1, page_size: 10 }));
    await wikiApi.listEntries({ status: 'all' });
    expect(fetchMock.mock.calls[0][0]).not.toContain('status=');
  });

  it('404 响应解析出后端 error_code 与 message，而不是拼 HTTP 文案', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(
        { error_code: 'WIKI_ENTRY_NOT_FOUND', message: '条目 01J9 不存在', detail: null, trace_id: 'trace-abc' },
        404,
      ),
    );
    await expect(wikiApi.getEntry('01J9')).rejects.toMatchObject({
      errorCode: 'WIKI_ENTRY_NOT_FOUND',
      message: '条目 01J9 不存在',
      traceId: 'trace-abc',
      status: 404,
    });
  });

  it('响应体不是 JSON 时回落到 HTTP 状态码级信息（仍可诊断）', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => {
        throw new SyntaxError('Unexpected token <');
      },
    } as unknown as Response);

    await expect(wikiApi.getDedupeCandidates()).rejects.toMatchObject({
      errorCode: 'HTTP_502',
      status: 502,
    });
  });

  it('合并走 PATCH：只把 discard 置 superseded 并指向 keep（AC-07，不物理删除）', async () => {
    fetchMock
      .mockResolvedValueOnce(
        jsonResponse({
          id: '01J9V6',
          title: '旧版返回值语义',
          status: 'published',
          owner_id: 'u-arch-zhang',
          version: '1.3.0',
          source_ref: 'docs/x.md',
          superseded_by: null,
          content_hash: 'a'.repeat(64),
          last_verified: '2026-10-01T00:00:00.000Z',
          tags: [],
          concept_refs: [],
          workspace_id: 'ws-odap-main',
          created_at: '2026-01-01T00:00:00.000Z',
          updated_at: '2026-10-01T00:00:00.000Z',
        }),
      )
      .mockResolvedValueOnce(jsonResponse({ ok: true }));

    const result = await wikiApi.mergeEntries({
      keep_id: '01J9V1',
      discard_id: '01J9V6',
      field_choices: { version: 'left' },
      note: '合并',
    });

    expect(result).toEqual({ kept: '01J9V1', superseded: '01J9V6' });
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe('/api/v1/wiki/entries/01J9V6');
    expect(init.method).toBe('PATCH');
    const body = JSON.parse(String(init.body));
    expect(body).toEqual({ status: 'superseded', superseded_by: '01J9V1', version: '1.3.0' });
  });

  it('正文取最新版本快照（versions[0].content）', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse({
        data: [
          { id: 'wv-9', entry_id: '01J9', version: '2.0.0', content: '# 最新口径', content_hash: 'b', author_id: 'u-1', change_note: '', created_at: '2026-10-10T00:00:00.000Z' },
          { id: 'wv-8', entry_id: '01J9', version: '1.0.0', content: '# 旧口径', content_hash: 'c', author_id: 'u-1', change_note: '', created_at: '2026-01-01T00:00:00.000Z' },
        ],
        total: 2,
      }),
    );
    await expect(wikiApi.getContent('01J9')).resolves.toBe('# 最新口径');
  });

  it('无版本时正文返回空串，由页面渲染 Empty 态而不是崩溃', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ data: [], total: 0 }));
    await expect(wikiApi.getContent('01J9')).resolves.toBe('');
  });
});
