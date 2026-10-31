/**
 * Wiki 服务层测试（mock 网关路径）
 *
 * 覆盖：筛选/分页语义、错误码具体性（禁止"加载失败"式模糊文案）、
 * 错误视图模型对冲突对象的提取（AC-04 / AC-08）。
 */
import { afterEach, describe, expect, it } from 'vitest';
import { wikiApi } from '../services/wikiApi';
import { WikiApiError, toErrorInfo } from '../services/wikiError';
import { MOCK_ENTRIES, setMockFailure } from '../services/wikiMock';

afterEach(() => {
  setMockFailure('none');
});

describe('wikiApi.listEntries', () => {
  it('默认返回第一页，页大小与总数如实回传', async () => {
    const res = await wikiApi.listEntries({ page: 1, page_size: 3 });
    expect(res.data).toHaveLength(3);
    expect(res.page).toBe(1);
    expect(res.page_size).toBe(3);
    expect(res.total).toBe(MOCK_ENTRIES.length);
  });

  it('按状态过滤：status=published 只返回已发布条目', async () => {
    const res = await wikiApi.listEntries({ status: 'published', page_size: 50 });
    expect(res.data.length).toBeGreaterThan(0);
    expect(res.data.every((e) => e.status === 'published')).toBe(true);
  });

  it('按 owner 过滤', async () => {
    const res = await wikiApi.listEntries({ owner: 'u-arch-zhang', page_size: 50 });
    expect(res.data.length).toBeGreaterThan(0);
    expect(res.data.every((e) => e.owner_id === 'u-arch-zhang')).toBe(true);
  });

  it('按标签过滤，命中「术语表」族', async () => {
    const res = await wikiApi.listEntries({ tag: '术语表', page_size: 50 });
    expect(res.data.map((e) => e.id)).toContain('01J9Z6Q2X8K3M4N5P6R7S8T9V4');
  });

  it('关键词过滤不区分大小写', async () => {
    const upper = await wikiApi.listEntries({ keyword: 'CHURN', page_size: 50 });
    const lower = await wikiApi.listEntries({ keyword: 'churn', page_size: 50 });
    expect(upper.total).toBe(lower.total);
    expect(upper.total).toBeGreaterThan(0);
  });

  it('过滤无命中时返回空数组而不是抛错（供 Empty 态渲染）', async () => {
    const res = await wikiApi.listEntries({ keyword: '不存在的术语口径-zzz' });
    expect(res.data).toEqual([]);
    expect(res.total).toBe(0);
  });

  it('超出末页返回空页，total 不变（分页不越界）', async () => {
    const res = await wikiApi.listEntries({ page: 99, page_size: 10 });
    expect(res.data).toEqual([]);
    expect(res.total).toBe(MOCK_ENTRIES.length);
  });

  it('上游超时抛出带具体错误码的 WikiApiError', async () => {
    setMockFailure('list');
    await expect(wikiApi.listEntries({})).rejects.toMatchObject({
      name: 'WikiApiError',
      errorCode: 'WIKI_LIST_UPSTREAM_TIMEOUT',
      status: 504,
    });
  });
});

describe('wikiApi 详情/版本/引用', () => {
  const ENTRY_ID = '01J9Z6Q2X8K3M4N5P6R7S8T9V1';

  it('详情返回条目本体', async () => {
    const entry = await wikiApi.getEntry(ENTRY_ID);
    expect(entry.id).toBe(ENTRY_ID);
    expect(entry.owner_id).toBe('u-arch-zhang');
  });

  it('条目不存在时抛 WIKI_ENTRY_NOT_FOUND，而不是返回空对象', async () => {
    await expect(wikiApi.getEntry('missing-entry')).rejects.toMatchObject({
      errorCode: 'WIKI_ENTRY_NOT_FOUND',
      status: 404,
    });
  });

  it('版本按时间倒序，最新在前', async () => {
    const res = await wikiApi.getVersions(ENTRY_ID);
    expect(res.data.length).toBeGreaterThanOrEqual(3);
    const times = res.data.map((v) => v.created_at);
    expect([...times].sort().reverse()).toEqual(times);
    expect(res.total).toBe(res.data.length);
  });

  it('引用关系区分出边与入边，并回填当前条目 id', async () => {
    const graph = await wikiApi.getReferences(ENTRY_ID);
    expect(graph.entry_id).toBe(ENTRY_ID);
    expect(graph.outgoing.length).toBeGreaterThan(0);
    expect(graph.incoming.length).toBeGreaterThan(0);
    expect(graph.outgoing.some((ref) => ref.ref === 'Metric:ReturnRate')).toBe(true);
  });

  it('正文可读，且不是空字符串', async () => {
    const content = await wikiApi.getContent(ENTRY_ID);
    expect(content).toContain('退货率');
    expect(content.length).toBeGreaterThan(40);
  });
});

describe('wikiApi 去重与合并', () => {
  it('候选列表至少包含一组高相似度条目', async () => {
    const res = await wikiApi.getDedupeCandidates();
    expect(res.total).toBe(res.data.length);
    expect(res.data.length).toBeGreaterThan(0);
    expect(res.data[0].similarity).toBeGreaterThan(0.9);
    expect(res.data[0].conflicting_fields.length).toBeGreaterThan(0);
  });

  it('合并只返回 kept/superseded 两个 id（不返回"已删除"语义）', async () => {
    const result = await wikiApi.mergeEntries({
      keep_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
      discard_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V6',
      field_choices: { version: 'left' },
      note: '合并旧版口径说明',
    });
    expect(result).toEqual({
      kept: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
      superseded: '01J9Z6Q2X8K3M4N5P6R7S8T9V6',
    });
  });

  it('版本冲突抛出 WIKI_VERSION_CONFLICT 并带上冲突条目 id', async () => {
    setMockFailure('merge');
    try {
      await wikiApi.mergeEntries({
        keep_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V1',
        discard_id: '01J9Z6Q2X8K3M4N5P6R7S8T9V6',
        field_choices: {},
        note: '',
      });
      throw new Error('应当抛出冲突错误');
    } catch (err) {
      expect(err).toBeInstanceOf(WikiApiError);
      const info = toErrorInfo(err);
      expect(info.errorCode).toBe('WIKI_VERSION_CONFLICT');
      expect(info.conflictingId).toBe('01J9Z6Q2X8K3M4N5P6R7S8T9V6');
      expect(info.traceId).not.toBe('');
    }
  });

  it('去重索引未建立时给出可执行指引的 409', async () => {
    setMockFailure('dedupe');
    await expect(wikiApi.getDedupeCandidates()).rejects.toMatchObject({
      errorCode: 'DOCS_DEDUPE_INDEX_MISSING',
      status: 409,
    });
  });
});

describe('toErrorInfo', () => {
  it('WikiApiError 保留错误码、状态码与 trace_id', () => {
    const info = toErrorInfo(new WikiApiError({ error_code: 'WIKI_OWNER_REQUIRED', message: '条目必须指定 owner', detail: null, trace_id: 'trace-9f2' }, 422));
    expect(info).toEqual({
      errorCode: 'WIKI_OWNER_REQUIRED',
      message: '条目必须指定 owner',
      traceId: 'trace-9f2',
      status: 422,
      conflictingId: undefined,
    });
  });

  it('普通 Error 落到兜底码，但仍保留原始 message', () => {
    const info = toErrorInfo(new Error('网络连接被重置'));
    expect(info.errorCode).toBe('WIKI_CLIENT_NETWORK_ERROR');
    expect(info.message).toBe('网络连接被重置');
    expect(info.status).toBe(0);
  });

  it('非 Error 输入也能给出 message，不显示 undefined', () => {
    expect(toErrorInfo('上游 502').message).toBe('上游 502');
  });
});
