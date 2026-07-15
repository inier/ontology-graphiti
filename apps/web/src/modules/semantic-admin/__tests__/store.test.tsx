import { describe, it, expect, beforeEach } from 'vitest';
import { useSemanticAdminStore } from '../store/useSemanticAdminStore';

/**
 * Zustand store 单元测试：
 *  - getter/setter 正确
 *  - candidateFilters 操作 / reset 幂等
 *  - currentTopTab 设置 approvals 后可用（验收清单 FE-01 验证）
 *  关键：每次 setState 之后必须重新 getState() — Zustand 是 immutable 快照引用
 */

describe('useSemanticAdminStore: 全局 Tab/过滤/分页 store', () => {
  beforeEach(() => {
    useSemanticAdminStore.getState().resetCandidateFilters();
    useSemanticAdminStore.getState().resetPipelineRunFilters();
    useSemanticAdminStore.setState({
      currentTopTab: 'usl',
      currentUslSubTab: 'domains',
      currentDomain: null,
      selectedCandidateIds: [],
    });
  });

  it('初始值 currentTopTab=usl，可成功切换到 approvals', () => {
    expect(useSemanticAdminStore.getState().currentTopTab).toBe('usl');
    useSemanticAdminStore.getState().setCurrentTopTab('approvals');
    expect(useSemanticAdminStore.getState().currentTopTab).toBe('approvals');
  });

  it('currentUslSubTab 5 个合法值可切换', () => {
    const tabs = ['domains', 'terms', 'hierarchy', 'properties', 'constraints'] as const;
    for (const t of tabs) {
      useSemanticAdminStore.getState().setCurrentUslSubTab(t);
      expect(useSemanticAdminStore.getState().currentUslSubTab).toBe(t);
    }
  });

  it('setCandidateFilters 合并对象，resetCandidateFilters 回到默认值 { page:1, page_size:20 }', () => {
    useSemanticAdminStore.getState().setCandidateFilters({
      page: 3, page_size: 50, keyword: '应收',
    });
    expect(useSemanticAdminStore.getState().candidateFilters.page).toBe(3);
    expect(useSemanticAdminStore.getState().candidateFilters.page_size).toBe(50);
    expect(useSemanticAdminStore.getState().candidateFilters.keyword).toBe('应收');
    useSemanticAdminStore.getState().resetCandidateFilters();
    expect(useSemanticAdminStore.getState().candidateFilters).toEqual({ page: 1, page_size: 20 });
    expect(useSemanticAdminStore.getState().selectedCandidateIds).toEqual([]);
  });

  it('toggleCandidateSelect: 两次 toggle 同一个 id 回到空数组', () => {
    useSemanticAdminStore.getState().toggleCandidateSelect('cand-111');
    expect(useSemanticAdminStore.getState().selectedCandidateIds).toEqual(['cand-111']);
    useSemanticAdminStore.getState().toggleCandidateSelect('cand-111');
    expect(useSemanticAdminStore.getState().selectedCandidateIds).toEqual([]);
  });

  it('pipelineRunFilters reset 后回到 page:1 / page_size:50', () => {
    useSemanticAdminStore.getState().setPipelineRunFilters({ page: 99, status: 'failed' });
    expect(useSemanticAdminStore.getState().pipelineRunFilters.page).toBe(99);
    expect(useSemanticAdminStore.getState().pipelineRunFilters.status).toBe('failed');
    useSemanticAdminStore.getState().resetPipelineRunFilters();
    expect(useSemanticAdminStore.getState().pipelineRunFilters).toEqual({ page: 1, page_size: 50 });
  });
});
