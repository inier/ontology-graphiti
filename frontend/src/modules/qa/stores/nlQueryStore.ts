/**
 * NL 查询服务 - Zustand Store
 */
import { create } from 'zustand';
import type {
  QueryMode,
  QueryResponse,
  NLSearchResponse,
  NLExplainResponse,
  PillarStatusResponse,
  AuditRecord,
  AuditStatsResponse,
  EvalResponse,
} from '../services/nlQueryApi';
import {
  nlQuery,
  nlSearch,
  nlExplain,
  getPillarStatus,
  listAuditRecords,
  getAuditStats,
  runEvaluation,
} from '../services/nlQueryApi';

interface NLQueryState {
  // 查询状态
  queryLoading: boolean;
  queryResult: QueryResponse | null;
  queryError: string | null;

  // 检索状态
  searchLoading: boolean;
  searchResult: NLSearchResponse | null;
  searchError: string | null;

  // 解释状态
  explainLoading: boolean;
  explainResult: NLExplainResponse | null;
  explainError: string | null;

  // 支柱状态
  pillarStatus: PillarStatusResponse | null;

  // 审计状态
  auditRecords: AuditRecord[];
  auditTotal: number;
  auditStats: AuditStatsResponse | null;
  auditLoading: boolean;

  // 评估状态
  evalLoading: boolean;
  evalResult: EvalResponse | null;
  evalError: string | null;

  // 当前查询参数
  currentMode: QueryMode;
  topK: number;

  // 操作
  executeQuery: (query: string, workspaceId?: string, scenarioId?: string) => Promise<void>;
  executeSearch: (query: string, workspaceId?: string, scenarioId?: string) => Promise<void>;
  executeExplain: (query: string, workspaceId?: string, scenarioId?: string) => Promise<void>;
  fetchPillarStatus: () => Promise<void>;
  fetchAuditRecords: (params?: { workspace_id?: string; user_id?: string; limit?: number; offset?: number }) => Promise<void>;
  fetchAuditStats: (workspaceId?: string) => Promise<void>;
  executeEvaluation: () => Promise<void>;
  setMode: (mode: QueryMode) => void;
  setTopK: (k: number) => void;
  clearResults: () => void;
}

export const useNLQueryStore = create<NLQueryState>((set, get) => ({
  queryLoading: false,
  queryResult: null,
  queryError: null,

  searchLoading: false,
  searchResult: null,
  searchError: null,

  explainLoading: false,
  explainResult: null,
  explainError: null,

  pillarStatus: null,

  auditRecords: [],
  auditTotal: 0,
  auditStats: null,
  auditLoading: false,

  evalLoading: false,
  evalResult: null,
  evalError: null,

  currentMode: 'auto',
  topK: 10,

  executeQuery: async (query, workspaceId, scenarioId) => {
    set({ queryLoading: true, queryError: null });
    try {
      const { currentMode, topK } = get();
      const result = await nlQuery({
        query,
        workspace_id: workspaceId,
        scenario_id: scenarioId,
        mode: currentMode,
        top_k: topK,
      });
      set({ queryResult: result, queryLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : '查询失败';
      set({ queryError: message, queryLoading: false });
    }
  },

  executeSearch: async (query, workspaceId, scenarioId) => {
    set({ searchLoading: true, searchError: null });
    try {
      const { currentMode, topK } = get();
      const result = await nlSearch({
        query,
        workspace_id: workspaceId,
        scenario_id: scenarioId,
        mode: currentMode,
        top_k: topK,
      });
      set({ searchResult: result, searchLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : '检索失败';
      set({ searchError: message, searchLoading: false });
    }
  },

  executeExplain: async (query, workspaceId, scenarioId) => {
    set({ explainLoading: true, explainError: null });
    try {
      const { currentMode, topK } = get();
      const result = await nlExplain({
        query,
        workspace_id: workspaceId,
        scenario_id: scenarioId,
        mode: currentMode,
        top_k: topK,
      });
      set({ explainResult: result, explainLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : '解释失败';
      set({ explainError: message, explainLoading: false });
    }
  },

  fetchPillarStatus: async () => {
    try {
      const result = await getPillarStatus();
      set({ pillarStatus: result });
    } catch {
      // 静默失败
    }
  },

  fetchAuditRecords: async (params) => {
    set({ auditLoading: true });
    try {
      const result = await listAuditRecords(params);
      set({ auditRecords: result.records, auditTotal: result.total, auditLoading: false });
    } catch {
      set({ auditLoading: false });
    }
  },

  fetchAuditStats: async (workspaceId) => {
    try {
      const result = await getAuditStats(workspaceId);
      set({ auditStats: result });
    } catch {
      // 静默失败
    }
  },

  executeEvaluation: async () => {
    set({ evalLoading: true, evalError: null });
    try {
      const result = await runEvaluation();
      set({ evalResult: result, evalLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : '评估失败';
      set({ evalError: message, evalLoading: false });
    }
  },

  setMode: (mode) => set({ currentMode: mode }),
  setTopK: (k) => set({ topK: k }),

  clearResults: () =>
    set({
      queryResult: null,
      queryError: null,
      searchResult: null,
      searchError: null,
      explainResult: null,
      explainError: null,
    }),
}));
