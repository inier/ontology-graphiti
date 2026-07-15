import { create } from 'zustand';
import type { UslDomain } from '../types';
import type { CandidateStatus, PipelineRunStatus } from '../services/pipelineApi';

const DASHBOARD_TTL_MS = 5 * 60 * 1000;

export type AdminTopTab = 'usl' | 'pipeline' | 'candidates' | 'quality' | 'dashboard' | 'approvals';

export type UslSubTab =
  | 'domains'
  | 'terms'
  | 'hierarchy'
  | 'properties'
  | 'constraints';

export interface CandidateFilters {
  pipeline_run_id?: string;
  domain_id?: string;
  status?: CandidateStatus | '';
  semantic_type?: string;
  min_confidence?: number;
  keyword?: string;
  page: number;
  page_size: number;
}

export interface PipelineRunFilters {
  workspace_id?: string;
  status?: PipelineRunStatus | '';
  page: number;
  page_size: number;
}

/**
 * Quality Dashboard 全局缓存（5 分钟 TTL）
 * 3 视图：summary / terms-trend / approvals-breakdown
 */
export interface DashboardSummaryCache {
  summary: Record<string, unknown> | null;
  trend: Record<string, unknown> | null;
  approvals: Record<string, unknown> | null;
  fetchedAt: number;
}

interface SemanticAdminState {
  currentTopTab: AdminTopTab;
  setCurrentTopTab: (tab: AdminTopTab) => void;

  currentUslSubTab: UslSubTab;
  setCurrentUslSubTab: (tab: UslSubTab) => void;

  currentDomain: UslDomain | null;
  setCurrentDomain: (domain: UslDomain | null) => void;

  filters: {
    termSemanticType: string;
    termKeyword: string;
    termStoplist: boolean | null;
  };
  setTermSemanticType: (v: string) => void;
  setTermKeyword: (v: string) => void;
  setTermStoplist: (v: boolean | null) => void;

  termPage: number;
  termPageSize: number;
  setTermPage: (page: number) => void;
  setTermPageSize: (size: number) => void;

  candidateFilters: CandidateFilters;
  setCandidateFilters: (patch: Partial<CandidateFilters>) => void;
  resetCandidateFilters: () => void;
  selectedCandidateIds: string[];
  toggleCandidateSelect: (id: string) => void;
  setAllCandidateSelected: (ids: string[]) => void;
  clearCandidateSelected: () => void;

  pipelineRunFilters: PipelineRunFilters;
  setPipelineRunFilters: (patch: Partial<PipelineRunFilters>) => void;
  resetPipelineRunFilters: () => void;

  dashboardSummary: DashboardSummaryCache | null;
  setDashboardSummary: (
    updater:
      | DashboardSummaryCache
      | null
      | ((prev: DashboardSummaryCache | null) => DashboardSummaryCache | null),
  ) => void;
}

export const useSemanticAdminStore = create<SemanticAdminState>((set) => {
  let ttlTimer: ReturnType<typeof setTimeout> | null = null;

  const clearTimer = () => {
    if (ttlTimer) {
      clearTimeout(ttlTimer);
      ttlTimer = null;
    }
  };

  const scheduleExpire = () => {
    clearTimer();
    ttlTimer = setTimeout(() => {
      set({ dashboardSummary: null });
      ttlTimer = null;
    }, DASHBOARD_TTL_MS);
  };

  return {
    currentTopTab: 'usl',
    setCurrentTopTab: (tab) => set({ currentTopTab: tab }),

    currentUslSubTab: 'domains',
    setCurrentUslSubTab: (tab) => set({ currentUslSubTab: tab }),

    currentDomain: null,
    setCurrentDomain: (domain) => set({ currentDomain: domain, termPage: 1 }),

    filters: {
      termSemanticType: '',
      termKeyword: '',
      termStoplist: null,
    },
    setTermSemanticType: (v) =>
      set((prev) => ({ filters: { ...prev.filters, termSemanticType: v }, termPage: 1 })),
    setTermKeyword: (v) => set((prev) => ({ filters: { ...prev.filters, termKeyword: v } })),
    setTermStoplist: (v) =>
      set((prev) => ({ filters: { ...prev.filters, termStoplist: v }, termPage: 1 })),

    termPage: 1,
    termPageSize: 10,
    setTermPage: (page) => set({ termPage: page }),
    setTermPageSize: (size) => set({ termPageSize: size, termPage: 1 }),

    candidateFilters: { page: 1, page_size: 20 },
    setCandidateFilters: (patch) =>
      set((s) => ({ candidateFilters: { ...s.candidateFilters, ...patch } })),
    resetCandidateFilters: () =>
      set({ candidateFilters: { page: 1, page_size: 20 }, selectedCandidateIds: [] }),
    selectedCandidateIds: [],
    toggleCandidateSelect: (id) =>
      set((s) => ({
        selectedCandidateIds: s.selectedCandidateIds.includes(id)
          ? s.selectedCandidateIds.filter((x) => x !== id)
          : [...s.selectedCandidateIds, id],
      })),
    setAllCandidateSelected: (ids) => set({ selectedCandidateIds: ids }),
    clearCandidateSelected: () => set({ selectedCandidateIds: [] }),

    pipelineRunFilters: { page: 1, page_size: 50 },
    setPipelineRunFilters: (patch) =>
      set((s) => ({ pipelineRunFilters: { ...s.pipelineRunFilters, ...patch } })),
    resetPipelineRunFilters: () => set({ pipelineRunFilters: { page: 1, page_size: 50 } }),

    dashboardSummary: null,
    setDashboardSummary: (updater) => {
      set((s) => {
        const newValue =
          typeof updater === 'function'
            ? (updater as (p: DashboardSummaryCache | null) => DashboardSummaryCache | null)(
                s.dashboardSummary,
              )
            : updater;
        if (newValue) {
          scheduleExpire();
        } else {
          clearTimer();
        }
        return { dashboardSummary: newValue };
      });
    },
  };
});
