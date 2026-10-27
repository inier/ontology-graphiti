/**
 * 台账筛选 ↔ 查询参数映射（唯一实现点）
 *
 * 契约事实（api-spec `GET /api/decisions`）：`status` 与 `outcome` 都是可重复参数，
 * 但两者之间是 **AND** 关系，无法表达「status=executed&outcome=success OR status=failed」。
 * 因此这里做保守降级：
 * - 选中项全部落在 `executed` 变体（执行成功 / 部分成功）时，才下发 `outcome` 收窄；
 * - 混合选中时只下发 `status`，`outcome` 不下发 —— 结果是**可能多出**部分成功行，
 *   但绝不会漏行。宁可多给一条，也不静默少给（少给会被误读成「台账漏数据」）。
 */
import type { DecisionEntrySource, DecisionFilters } from '../types';

/** 台账排序字段白名单 —— 与契约 `sort` enum 逐字一致：evidence_count 本期未提供 */
export type LedgerSort = 'created_at' | 'updated_at' | 'confidence';
export type SortOrder = 'asc' | 'desc';

export interface LedgerQueryInput {
  page: number;
  pageSize: number;
  sort?: LedgerSort;
  order?: SortOrder;
  agentId?: string;
}

const CONFIDENCE_BAND: Record<
  Exclude<DecisionFilters['confidenceBand'], 'all'>,
  { min: number; max: number }
> = {
  low: { min: 0, max: 0.6 },
  medium: { min: 0.6, max: 0.8 },
  high: { min: 0.8, max: 1 },
};

/** 结果筛选选项 → 查询参数（status × outcome） */
export function resultSelectionToQuery(results: string[]): {
  statuses: string[];
  outcomes: string[];
} {
  const statuses = new Set<string>();
  const outcomes = new Set<string>();
  let allExecutedVariants = results.length > 0;

  results.forEach((value) => {
    switch (value) {
      case 'pending':
        statuses.add('pending');
        allExecutedVariants = false;
        break;
      case 'decided':
        statuses.add('decided');
        statuses.add('executing');
        allExecutedVariants = false;
        break;
      case 'executed':
        statuses.add('executed');
        outcomes.add('success');
        break;
      case 'partial_success':
        statuses.add('executed');
        outcomes.add('partial_success');
        break;
      case 'failed':
        statuses.add('failed');
        allExecutedVariants = false;
        break;
      case 'rejected':
        statuses.add('rejected');
        allExecutedVariants = false;
        break;
      default:
        allExecutedVariants = false;
    }
  });

  return {
    statuses: [...statuses],
    // 只在「全部选中项都是 executed 变体」时下发 outcome，避免 AND 语义误杀其他状态
    outcomes: allExecutedVariants ? [...outcomes] : [],
  };
}

export function buildLedgerQuery(filters: DecisionFilters, input: LedgerQueryInput): URLSearchParams {
  const params = new URLSearchParams();
  params.set('page', String(input.page));
  params.set('page_size', String(input.pageSize));
  params.set('sort', input.sort ?? 'created_at');
  params.set('order', input.order ?? 'desc');

  const { statuses, outcomes } = resultSelectionToQuery(filters.results);
  statuses.forEach((s) => params.append('status', s));
  outcomes.forEach((o) => params.append('outcome', o));

  if (filters.entrySource) params.set('entry_source', filters.entrySource);
  if (filters.q?.trim()) params.set('q', filters.q.trim());
  if (filters.createdFrom) params.set('created_from', filters.createdFrom);
  if (filters.createdTo) params.set('created_to', filters.createdTo);

  if (filters.confidenceBand !== 'all') {
    const band = CONFIDENCE_BAND[filters.confidenceBand];
    params.set('min_confidence', String(band.min));
    params.set('max_confidence', String(band.max));
  }
  // agentId 是隐藏收窄维度（不是可见筛选器），仅 Agent 页内嵌时注入
  if (input.agentId) params.set('agent_id', input.agentId);

  return params;
}

/** 筛选条件 → URL query（刷新/分享仍可复现视图，不只靠 KeepAlive 内存缓存） */
export function filtersToSearchParams(filters: DecisionFilters): URLSearchParams {
  const params = new URLSearchParams();
  filters.results.forEach((r) => params.append('result', r));
  if (filters.entrySource) params.set('entry_source', filters.entrySource);
  if (filters.confidenceBand !== 'all') params.set('confidence', filters.confidenceBand);
  if (filters.q?.trim()) params.set('q', filters.q.trim());
  if (filters.createdFrom) params.set('from', filters.createdFrom);
  if (filters.createdTo) params.set('to', filters.createdTo);
  return params;
}

export function searchParamsToFilters(params: URLSearchParams): DecisionFilters {
  const band = params.get('confidence');
  const confidenceBand: DecisionFilters['confidenceBand'] =
    band === 'low' || band === 'medium' || band === 'high' ? band : 'all';
  const entrySource = params.get('entry_source') as DecisionEntrySource | null;
  return {
    results: params.getAll('result'),
    entrySource: entrySource ?? undefined,
    confidenceBand,
    q: params.get('q') ?? undefined,
    createdFrom: params.get('from') ?? undefined,
    createdTo: params.get('to') ?? undefined,
  };
}

export function defaultFilters(): DecisionFilters {
  return { results: [], confidenceBand: 'all' };
}

/** 是否处于「有筛选」状态（决定空态用哪套文案） */
export function hasActiveFilters(filters: DecisionFilters): boolean {
  return (
    filters.results.length > 0 ||
    Boolean(filters.entrySource) ||
    filters.confidenceBand !== 'all' ||
    Boolean(filters.q?.trim()) ||
    Boolean(filters.createdFrom) ||
    Boolean(filters.createdTo)
  );
}
