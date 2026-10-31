/**
 * Wiki HTTP 客户端（SPEC §5）
 *
 * 只使用 SPEC 已锁定的端点；合并动作由「PATCH discard → status=superseded + superseded_by」
 * 组合完成（SPEC §6 约束：合并只置 superseded，禁止物理删除），不发明新端点。
 */
import { API_BASE, WIKI_API_MOCK, WIKI_ENDPOINTS } from './wikiConfig';
import { WikiApiError, type ApiErrorPayload } from './wikiError';
import { mockGateway } from './wikiMock';

/** mock 开关随服务层一并导出：页面据此决定是否显示「演示数据」横幅（不得静默 mock） */
export { WIKI_API_MOCK } from './wikiConfig';
import type {
  DedupeCandidateList,
  ReferenceGraph,
  WikiEntry,
  WikiEntryList,
  WikiEntryStatus,
  WikiListQuery,
  WikiMergeRequest,
  WikiVersionList,
} from './wikiTypes';

function authHeader(): Record<string, string> {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem('token') : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    let payload: ApiErrorPayload = {
      error_code: `HTTP_${res.status}`,
      message: `请求 ${path} 返回 ${res.status} ${res.statusText}`,
      detail: null,
      trace_id: '',
    };
    try {
      const body = (await res.json()) as Partial<ApiErrorPayload>;
      payload = {
        error_code: body.error_code ?? payload.error_code,
        message: body.message ?? payload.message,
        detail: body.detail ?? null,
        trace_id: body.trace_id ?? '',
      };
    } catch { /* 忽略：失败时保持当前状态 */ 
      // 响应体不是 JSON —— 保留 HTTP 状态码级别的具体信息
    }
    throw new WikiApiError(payload, res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function toQueryString(query: WikiListQuery): string {
  const params = new URLSearchParams();
  if (query.status && query.status !== 'all') params.set('status', query.status);
  if (query.owner) params.set('owner', query.owner);
  if (query.tag) params.set('tag', query.tag);
  if (query.keyword) params.set('keyword', query.keyword);
  params.set('page', String(query.page ?? 1));
  params.set('page_size', String(query.page_size ?? 10));
  return params.toString();
}

export const wikiApi = {
  async listEntries(query: WikiListQuery = {}): Promise<WikiEntryList> {
    if (WIKI_API_MOCK) return mockGateway.list(query);
    return request<WikiEntryList>(`${WIKI_ENDPOINTS.list}?${toQueryString(query)}`);
  },

  async getEntry(entryId: string): Promise<WikiEntry> {
    if (WIKI_API_MOCK) return mockGateway.detail(entryId);
    return request<WikiEntry>(WIKI_ENDPOINTS.detail(entryId));
  },

  async getVersions(entryId: string): Promise<WikiVersionList> {
    if (WIKI_API_MOCK) {
      const data = await mockGateway.versions(entryId);
      return { data, total: data.length };
    }
    return request<WikiVersionList>(WIKI_ENDPOINTS.versions(entryId));
  },

  async getReferences(entryId: string): Promise<ReferenceGraph> {
    if (WIKI_API_MOCK) return mockGateway.references(entryId);
    return request<ReferenceGraph>(WIKI_ENDPOINTS.references(entryId));
  },

  async getDedupeCandidates(): Promise<DedupeCandidateList> {
    if (WIKI_API_MOCK) {
      const data = await mockGateway.dedupe();
      return { data, total: data.length };
    }
    return request<DedupeCandidateList>(WIKI_ENDPOINTS.dedupe);
  },

  /** 条目正文：mock 直读；真实环境取最新版本快照内容 */
  async getContent(entryId: string): Promise<string> {
    if (WIKI_API_MOCK) return mockGateway.content(entryId);
    const versions = await this.getVersions(entryId);
    return versions.data[0]?.content ?? '';
  },

  /** 部分更新（含乐观锁 version）—— PATCH /wiki/entries/{id} */
  async patchEntry(
    entryId: string,
    patch: { status?: WikiEntryStatus; superseded_by?: string | null; version: string },
  ): Promise<WikiEntry> {
    if (WIKI_API_MOCK) {
      await mockGateway.merge({ keep_id: patch.superseded_by ?? '', discard_id: entryId, field_choices: {}, note: '' });
      const entry = await mockGateway.detail(entryId);
      return { ...entry, status: patch.status ?? entry.status, superseded_by: patch.superseded_by ?? null };
    }
    return request<WikiEntry>(WIKI_ENDPOINTS.detail(entryId), {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  /**
   * 合并：把 discard 置为 superseded 并指向 keep（不物理删除，AC-07）。
   * mock 下走 mockGateway.merge 以复现 409 WIKI_VERSION_CONFLICT 分支。
   */
  async mergeEntries(req: WikiMergeRequest): Promise<{ kept: string; superseded: string }> {
    if (WIKI_API_MOCK) return mockGateway.merge(req);
    const discard = await this.getEntry(req.discard_id);
    await this.patchEntry(req.discard_id, {
      status: 'superseded',
      superseded_by: req.keep_id,
      version: discard.version,
    });
    return { kept: req.keep_id, superseded: req.discard_id };
  },
};

export type WikiApi = typeof wikiApi;
