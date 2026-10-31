/**
 * Wiki 状态机测试
 *
 * 断言三块状态机（列表 / 详情 / 去重）在成功、失败、边界下的推进，
 * 以及失败时错误码被完整保留（供 UI 直接展示 error_code）。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { useWikiStore } from '../stores/wikiStore';
import { setMockFailure } from '../services/wikiMock';

const ENTRY_ID = '01J9Z6Q2X8K3M4N5P6R7S8T9V1';

beforeEach(() => {
  useWikiStore.getState().resetAll();
  setMockFailure('none');
});

afterEach(() => {
  setMockFailure('none');
});

describe('列表状态机', () => {
  it('idle → loading → ready，并写入条目与总数', async () => {
    expect(useWikiStore.getState().listPhase).toBe('idle');
    const promise = useWikiStore.getState().fetchList();
    expect(useWikiStore.getState().listPhase).toBe('loading');
    await promise;
    const state = useWikiStore.getState();
    expect(state.listPhase).toBe('ready');
    expect(state.entries.length).toBeGreaterThan(0);
    expect(state.total).toBeGreaterThanOrEqual(state.entries.length);
  });

  it('上游失败落到 error 态，保留 error_code 且清空旧数据', async () => {
    await useWikiStore.getState().fetchList();
    expect(useWikiStore.getState().entries.length).toBeGreaterThan(0);

    setMockFailure('list');
    await useWikiStore.getState().fetchList();

    const state = useWikiStore.getState();
    expect(state.listPhase).toBe('error');
    expect(state.listError?.errorCode).toBe('WIKI_LIST_UPSTREAM_TIMEOUT');
    expect(state.entries).toEqual([]);
    expect(state.total).toBe(0);
  });

  it('改筛选条件会回到第 1 页（避免停在越界页看到空列表）', () => {
    useWikiStore.getState().setPage(4);
    expect(useWikiStore.getState().page).toBe(4);
    useWikiStore.getState().setFilters({ keyword: '退货率' });
    expect(useWikiStore.getState().page).toBe(1);
    expect(useWikiStore.getState().filters.keyword).toBe('退货率');
  });

  it('筛选只改传入字段，其他条件保留', () => {
    useWikiStore.getState().setFilters({ status: 'published', tag: '指标口径' });
    useWikiStore.getState().setFilters({ owner: 'u-arch-zhang' });
    const { filters } = useWikiStore.getState();
    expect(filters).toMatchObject({ status: 'published', tag: '指标口径', owner: 'u-arch-zhang' });
  });

  it('空结果是 ready 态而非 error 态（Empty 与 Error 必须区分）', async () => {
    useWikiStore.getState().setFilters({ keyword: '完全不存在-zzz' });
    await useWikiStore.getState().fetchList();
    const state = useWikiStore.getState();
    expect(state.listPhase).toBe('ready');
    expect(state.entries).toEqual([]);
    expect(state.listError).toBeNull();
  });
});

describe('详情状态机', () => {
  it('拉取详情时并发取正文/版本/引用，全部落位', async () => {
    await useWikiStore.getState().fetchDetail(ENTRY_ID);
    const state = useWikiStore.getState();
    expect(state.detailPhase).toBe('ready');
    expect(state.entry?.id).toBe(ENTRY_ID);
    expect(state.content.length).toBeGreaterThan(0);
    expect(state.versions.length).toBeGreaterThanOrEqual(3);
    expect(state.references?.outgoing.length).toBeGreaterThan(0);
  });

  it('条目不存在时是 error 态并带 404，不是空 ready', async () => {
    await useWikiStore.getState().fetchDetail('01J9-NOT-EXIST');
    const state = useWikiStore.getState();
    expect(state.detailPhase).toBe('error');
    expect(state.detailError?.errorCode).toBe('WIKI_ENTRY_NOT_FOUND');
    expect(state.detailError?.status).toBe(404);
    expect(state.entry).toBeNull();
  });

  it('切换条目时先清空上一条内容，避免串条目', async () => {
    await useWikiStore.getState().fetchDetail(ENTRY_ID);
    const promise = useWikiStore.getState().fetchDetail('01J9Z6Q2X8K3M4N5P6R7S8T9V2');
    expect(useWikiStore.getState().entry).toBeNull();
    expect(useWikiStore.getState().content).toBe('');
    await promise;
    expect(useWikiStore.getState().entry?.id).toBe('01J9Z6Q2X8K3M4N5P6R7S8T9V2');
  });

  it('resetDetail 回到 idle', async () => {
    await useWikiStore.getState().fetchDetail(ENTRY_ID);
    useWikiStore.getState().resetDetail();
    expect(useWikiStore.getState().detailPhase).toBe('idle');
    expect(useWikiStore.getState().versions).toEqual([]);
  });
});

describe('去重状态机', () => {
  it('默认选中第一条候选', async () => {
    await useWikiStore.getState().fetchDedupe();
    const state = useWikiStore.getState();
    expect(state.dedupePhase).toBe('ready');
    expect(state.candidates.length).toBeGreaterThan(1);
    expect(state.activeIndex).toBe(0);
  });

  it('切换候选会清掉上一次的合并结果与错误', async () => {
    await useWikiStore.getState().fetchDedupe();
    await useWikiStore.getState().merge({
      keep_id: useWikiStore.getState().candidates[0].left_id,
      discard_id: useWikiStore.getState().candidates[0].right_id,
      field_choices: {},
      note: '',
    });
    expect(useWikiStore.getState().mergeResult).not.toBeNull();

    useWikiStore.getState().setActiveCandidate(1);
    expect(useWikiStore.getState().activeIndex).toBe(1);
    expect(useWikiStore.getState().mergeResult).toBeNull();
    expect(useWikiStore.getState().mergeError).toBeNull();
  });

  it('合并成功：写入 kept/superseded 并刷新候选列表', async () => {
    await useWikiStore.getState().fetchDedupe();
    const target = useWikiStore.getState().candidates[0];
    const ok = await useWikiStore.getState().merge({
      keep_id: target.left_id,
      discard_id: target.right_id,
      field_choices: { version: 'left' },
      note: '合并重复条目',
    });
    const state = useWikiStore.getState();
    expect(ok).toBe(true);
    expect(state.merging).toBe(false);
    expect(state.mergeResult).toEqual({ kept: target.left_id, superseded: target.right_id });
    expect(state.dedupePhase).toBe('ready');
  });

  it('合并冲突：返回 false 并保留可诊断错误码，界面不误报成功', async () => {
    await useWikiStore.getState().fetchDedupe();
    const target = useWikiStore.getState().candidates[0];
    setMockFailure('merge');
    const ok = await useWikiStore.getState().merge({
      keep_id: target.left_id,
      discard_id: target.right_id,
      field_choices: {},
      note: '',
    });
    const state = useWikiStore.getState();
    expect(ok).toBe(false);
    expect(state.merging).toBe(false);
    expect(state.mergeResult).toBeNull();
    expect(state.mergeError?.errorCode).toBe('WIKI_VERSION_CONFLICT');
    expect(state.mergeError?.conflictingId).toBe(target.right_id);
  });

  it('候选拉取失败时是 error 态，不再残留旧候选', async () => {
    await useWikiStore.getState().fetchDedupe();
    setMockFailure('dedupe');
    await useWikiStore.getState().fetchDedupe();
    const state = useWikiStore.getState();
    expect(state.dedupePhase).toBe('error');
    expect(state.candidates).toEqual([]);
    expect(state.dedupeError?.errorCode).toBe('DOCS_DEDUPE_INDEX_MISSING');
  });
});
