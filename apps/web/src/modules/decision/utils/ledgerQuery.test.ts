import { describe, expect, it } from 'vitest';
import {
  buildLedgerQuery,
  defaultFilters,
  filtersToSearchParams,
  hasActiveFilters,
  resultSelectionToQuery,
  searchParamsToFilters,
} from './ledgerQuery';
import type { DecisionFilters } from '../types';

const base: DecisionFilters = { results: [], confidenceBand: 'all' };

describe('resultSelectionToQuery —— 结果筛选 → status/outcome 参数', () => {
  it('待裁定 → status=pending', () => {
    expect(resultSelectionToQuery(['pending'])).toEqual({ statuses: ['pending'], outcomes: [] });
  });

  it('待执行确认 → status ∈ {decided, executing}', () => {
    expect(resultSelectionToQuery(['decided'])).toEqual({
      statuses: ['decided', 'executing'],
      outcomes: [],
    });
  });

  it('执行成功 + 部分成功 → status=executed 且下推 outcome 收窄', () => {
    const result = resultSelectionToQuery(['executed', 'partial_success']);
    expect(result.statuses).toEqual(['executed']);
    expect(result.outcomes.sort()).toEqual(['partial_success', 'success']);
  });

  it('混合选中时不下发 outcome（AND 语义会误杀其他状态行）', () => {
    const result = resultSelectionToQuery(['executed', 'failed']);
    expect(result.statuses.sort()).toEqual(['executed', 'failed']);
    expect(result.outcomes).toEqual([]);
  });

  it('空选择不下发任何状态', () => {
    expect(resultSelectionToQuery([])).toEqual({ statuses: [], outcomes: [] });
  });
});

describe('buildLedgerQuery —— 参数拼装', () => {
  it('默认带分页与排序，且**不出现 workspace_id**', () => {
    const params = buildLedgerQuery(base, { page: 2, pageSize: 50 });
    expect(params.get('page')).toBe('2');
    expect(params.get('page_size')).toBe('50');
    expect(params.get('sort')).toBe('created_at');
    expect(params.get('order')).toBe('desc');
    expect(params.toString()).not.toContain('workspace_id');
  });

  it('置信度区间映射到 min/max 闭区间', () => {
    const params = buildLedgerQuery({ ...base, confidenceBand: 'low' }, { page: 1, pageSize: 20 });
    expect(params.get('min_confidence')).toBe('0');
    expect(params.get('max_confidence')).toBe('0.6');
  });

  it('agentId 作为隐藏参数注入', () => {
    const params = buildLedgerQuery(base, { page: 1, pageSize: 20, agentId: 'agent_7' });
    expect(params.get('agent_id')).toBe('agent_7');
  });

  it('sort 只下发契约枚举内的值，evidence_count 不在白名单', () => {
    const params = buildLedgerQuery(base, { page: 2, pageSize: 20, sort: 'confidence' });
    expect(params.get('sort')).toBe('confidence');
    // @ts-expect-error evidence_count 已从契约 sort enum 删除，类型层不许通过
    buildLedgerQuery(base, { page: 1, pageSize: 20, sort: 'evidence_count' });
  });
});

describe('URL query 同步', () => {
  it('筛选条件往返一致', () => {
    const filters: DecisionFilters = {
      results: ['executed', 'pending'],
      entrySource: 'qa',
      confidenceBand: 'high',
      q: '库存',
      createdFrom: '2026-09-25T00:00:00.000Z',
      createdTo: '2026-10-24T00:00:00.000Z',
    };
    const roundTrip = searchParamsToFilters(filtersToSearchParams(filters));
    expect(roundTrip).toEqual(filters);
  });

  it('hasActiveFilters 能区分「无筛选为空」与「筛选后为空」', () => {
    expect(hasActiveFilters(defaultFilters())).toBe(false);
    expect(hasActiveFilters({ ...defaultFilters(), q: '库存' })).toBe(true);
  });
});
