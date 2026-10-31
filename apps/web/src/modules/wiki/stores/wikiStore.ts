/**
 * Wiki 模块状态（zustand）
 *
 * 设计要点：
 *  - 三块独立的状态机（列表 / 详情 / 去重），各自 phase ∈ idle|loading|ready|error
 *  - 错误保存为可诊断视图模型（error_code + message + trace_id），UI 直接展示
 *  - 所有异步动作都 try/catch 并落错误态，禁止静默失败
 */
import { create } from 'zustand';
import { wikiApi } from '../services/wikiApi';
import { toErrorInfo, type WikiErrorInfo } from '../services/wikiError';
import type {
  DedupeCandidate,
  ReferenceGraph,
  WikiEntry,
  WikiEntryStatus,
  WikiListQuery,
  WikiMergeRequest,
  WikiVersion,
} from '../services/wikiTypes';

export type LoadPhase = 'idle' | 'loading' | 'ready' | 'error';

export interface WikiFilters {
  status: WikiEntryStatus | 'all';
  owner: string;
  tag: string;
  keyword: string;
}

const DEFAULT_FILTERS: WikiFilters = { status: 'all', owner: '', tag: '', keyword: '' };

interface ListSlice {
  listPhase: LoadPhase;
  entries: WikiEntry[];
  total: number;
  page: number;
  pageSize: number;
  filters: WikiFilters;
  listError: WikiErrorInfo | null;
}

interface DetailSlice {
  detailPhase: LoadPhase;
  entry: WikiEntry | null;
  content: string;
  versions: WikiVersion[];
  references: ReferenceGraph | null;
  detailError: WikiErrorInfo | null;
}

interface DedupeSlice {
  dedupePhase: LoadPhase;
  candidates: DedupeCandidate[];
  dedupeError: WikiErrorInfo | null;
  /** 当前对照的候选对索引；null 表示未选择 */
  activeIndex: number | null;
  merging: boolean;
  mergeError: WikiErrorInfo | null;
  mergeResult: { kept: string; superseded: string } | null;
}

export interface WikiStore extends ListSlice, DetailSlice, DedupeSlice {
  fetchList: (overrides?: Partial<WikiListQuery>) => Promise<void>;
  setFilters: (patch: Partial<WikiFilters>) => void;
  setPage: (page: number) => void;

  fetchDetail: (entryId: string) => Promise<void>;
  resetDetail: () => void;

  fetchDedupe: () => Promise<void>;
  setActiveCandidate: (index: number | null) => void;
  merge: (req: WikiMergeRequest) => Promise<boolean>;

  resetAll: () => void;
}

const initialState = {
  listPhase: 'idle' as LoadPhase,
  entries: [] as WikiEntry[],
  total: 0,
  page: 1,
  pageSize: 10,
  filters: DEFAULT_FILTERS,
  listError: null as WikiErrorInfo | null,

  detailPhase: 'idle' as LoadPhase,
  entry: null as WikiEntry | null,
  content: '',
  versions: [] as WikiVersion[],
  references: null as ReferenceGraph | null,
  detailError: null as WikiErrorInfo | null,

  dedupePhase: 'idle' as LoadPhase,
  candidates: [] as DedupeCandidate[],
  dedupeError: null as WikiErrorInfo | null,
  activeIndex: null as number | null,
  merging: false,
  mergeError: null as WikiErrorInfo | null,
  mergeResult: null as { kept: string; superseded: string } | null,
};

export const useWikiStore = create<WikiStore>((set, get) => ({
  ...initialState,

  async fetchList(overrides) {
    const { filters, page, pageSize } = get();
    set({ listPhase: 'loading', listError: null });
    try {
      const result = await wikiApi.listEntries({
        status: filters.status,
        owner: filters.owner || undefined,
        tag: filters.tag || undefined,
        keyword: filters.keyword || undefined,
        page,
        page_size: pageSize,
        ...overrides,
      });
      set({
        listPhase: 'ready',
        entries: result.data,
        total: result.total,
        page: result.page,
        pageSize: result.page_size,
      });
    } catch (err) {
      set({ listPhase: 'error', entries: [], total: 0, listError: toErrorInfo(err) });
    }
  },

  setFilters(patch) {
    set((state) => ({ filters: { ...state.filters, ...patch }, page: 1 }));
  },

  setPage(page) {
    set({ page });
  },

  async fetchDetail(entryId) {
    set({ detailPhase: 'loading', detailError: null, entry: null, content: '', versions: [], references: null });
    try {
      const entry = await wikiApi.getEntry(entryId);
      const [content, versions, references] = await Promise.all([
        wikiApi.getContent(entryId),
        wikiApi.getVersions(entryId),
        wikiApi.getReferences(entryId),
      ]);
      set({
        detailPhase: 'ready',
        entry,
        content,
        versions: versions.data,
        references,
      });
    } catch (err) {
      set({ detailPhase: 'error', detailError: toErrorInfo(err) });
    }
  },

  resetDetail() {
    set({
      detailPhase: 'idle',
      entry: null,
      content: '',
      versions: [],
      references: null,
      detailError: null,
    });
  },

  async fetchDedupe() {
    set({ dedupePhase: 'loading', dedupeError: null });
    try {
      const result = await wikiApi.getDedupeCandidates();
      set({ dedupePhase: 'ready', candidates: result.data, activeIndex: result.data.length > 0 ? 0 : null });
    } catch (err) {
      set({ dedupePhase: 'error', candidates: [], dedupeError: toErrorInfo(err) });
    }
  },

  setActiveCandidate(index) {
    set({ activeIndex: index, mergeError: null, mergeResult: null });
  },

  async merge(req) {
    set({ merging: true, mergeError: null, mergeResult: null });
    try {
      const result = await wikiApi.mergeEntries(req);
      set({ merging: false, mergeResult: result });
      await get().fetchDedupe();
      return true;
    } catch (err) {
      set({ merging: false, mergeError: toErrorInfo(err) });
      return false;
    }
  },

  resetAll() {
    set({ ...initialState });
  },
}));
