import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import type { DecisionFilters, DecisionLedgerPage, DecisionRecord } from '../types';

const listDecisionLedger = vi.fn();
vi.mock('../services/decisionApi', () => ({
  listDecisionLedger: (...args: unknown[]) => listDecisionLedger(...args),
}));

// 轻量桩：按列 render 展开数据行，避免 ProTable 在 jsdom 里的开销
vi.mock('@/modules/shared', () => ({
  AdvancedTable: ({
    dataSource = [],
    columns = [],
    locale,
    onRow,
  }: {
    dataSource?: DecisionRecord[];
    columns?: Array<{ dataIndex?: string; render?: (dom: unknown, record: DecisionRecord, i: number) => unknown }>;
    locale?: { emptyText?: React.ReactNode };
    onRow?: (record: DecisionRecord) => { onClick?: () => void };
  }) => (
    <div>
      {dataSource.length === 0 && locale?.emptyText ? (
        <div data-testid="table-empty">{locale.emptyText}</div>
      ) : null}
      <table>
        <tbody>
          {dataSource.map((record, rowIndex) => (
            <tr key={record.decision_id} onClick={() => onRow?.(record)?.onClick?.()}>
              {columns.map((col, colIndex) => (
                <td key={colIndex}>
                  {col.render
                    ? (col.render(record[col.dataIndex as keyof DecisionRecord], record, rowIndex) as React.ReactNode)
                    : String(record[col.dataIndex as keyof DecisionRecord] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ),
}));

const { DecisionLedgerTable } = await import('./DecisionLedgerTable');

const baseFilters: DecisionFilters = { results: [], confidenceBand: 'all' };

function record(overrides: Partial<DecisionRecord> = {}): DecisionRecord {
  return {
    decision_id: 'dec_7f3a2b1c9d0e',
    workspace_id: 'ws_demo',
    context_summary: '华东区 A 类门店库存跌破安全线，是否继续执行自动补货？',
    constraints: {},
    reasoning: '库存周转与缺货成本权衡后选择分批补货',
    reasoning_trace: [],
    confidence: 0.42,
    evidence_episode_ids: [],
    evidence_entity_ids: ['e1', 'e2'],
    recommended_option: '按门店等级分批补货',
    alternative_options: [],
    decision_method: 'manual',
    decision_type: 'general',
    precedent_decision_ids: [],
    action_record_id: null,
    status: 'pending',
    entry_source: 'qa',
    outcome: 'pending',
    outcome_details: {},
    created_at: '2026-10-22T10:00:00Z',
    updated_at: '2026-10-22T10:00:00Z',
    valid_at: '2026-10-22T10:00:00Z',
    ...overrides,
  };
}

function page(items: DecisionRecord[], overrides: Partial<DecisionLedgerPage> = {}): DecisionLedgerPage {
  return {
    items,
    total: items.length,
    total_is_estimate: false,
    page: 1,
    page_size: 20,
    has_more: false,
    ...overrides,
  };
}

function renderTable(props: React.ComponentProps<typeof DecisionLedgerTable>) {
  return render(
    <App>
      <DecisionLedgerTable {...props} />
    </App>,
  );
}

beforeEach(() => {
  listDecisionLedger.mockReset();
});

describe('DecisionLedgerTable', () => {
  it('本空间无决策时给出「去问答发起」空态，而不是空表格', async () => {
    listDecisionLedger.mockResolvedValue(page([]));
    renderTable({ filters: baseFilters, onOpenDetail: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText('当前工作空间还没有决策记录')).toBeInTheDocument();
    });
    expect(screen.getByText('去问答发起第一个决策')).toBeInTheDocument();
  });

  it('筛选后为空时用另一套文案与「清除筛选」按钮', async () => {
    listDecisionLedger.mockResolvedValue(page([]));
    renderTable({
      filters: { ...baseFilters, results: ['pending'] },
      onOpenDetail: vi.fn(),
      onFilterReset: vi.fn(),
    });

    await waitFor(() => {
      expect(screen.getByText('当前筛选条件下没有决策')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: '清除筛选' })).toBeInTheDocument();
  });

  it('加载失败暴露 HTTP 状态与后端 detail，而不是笼统「加载失败」', async () => {
    const { DecisionApiError } = await import('../services/decisionRequest');
    listDecisionLedger.mockRejectedValue(new DecisionApiError(500, 'neo4j 连接超时'));
    renderTable({ filters: baseFilters, onOpenDetail: vi.fn() });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText('决策台账加载失败')).toBeInTheDocument();
    expect(screen.getByText('HTTP 500 · neo4j 连接超时')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重试/ })).toBeInTheDocument();
  });

  it('embedded 模式显示不可移除的语境标签与「查看全部」链接', async () => {
    listDecisionLedger.mockResolvedValue(page([record()]));
    renderTable({
      filters: baseFilters,
      onOpenDetail: vi.fn(),
      embedded: true,
      agentId: 'agent_7',
      agentName: '补货助手',
      onViewAll: vi.fn(),
    });

    await waitFor(() => {
      expect(screen.getByText('当前仅显示 补货助手 产生的决策')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: '查看全部' })).toBeInTheDocument();
  });

  it('行点击整行跳详情（不用抽屉）', async () => {
    const onOpenDetail = vi.fn();
    listDecisionLedger.mockResolvedValue(page([record()]));
    renderTable({ filters: baseFilters, onOpenDetail });

    await waitFor(() => {
      expect(screen.getByText('华东区 A 类门店库存跌破安全线，是否继续执行自动补货？')).toBeInTheDocument();
    });
    screen.getByText('华东区 A 类门店库存跌破安全线，是否继续执行自动补货？').closest('tr')?.click();
    expect(onOpenDetail).toHaveBeenCalledWith('dec_7f3a2b1c9d0e');
  });

  it('结果列走双参映射：executed + partial_success 显示「部分成功」', async () => {
    listDecisionLedger.mockResolvedValue(
      page([record({ status: 'executed', outcome: 'partial_success' })]),
    );
    renderTable({ filters: baseFilters, onOpenDetail: vi.fn() });

    await waitFor(() => {
      expect(screen.getByText('部分成功')).toBeInTheDocument();
    });
  });

  it('无关联动作显示「无动作」，与「未开始」区分', async () => {
    listDecisionLedger.mockResolvedValue(page([record({ action_record_id: null })]));
    renderTable({ filters: baseFilters, onOpenDetail: vi.fn() });
    await waitFor(() => expect(screen.getByText('无动作')).toBeInTheDocument());
  });

  it('请求参数不含 workspace_id（信任模型要求后端从 JWT 解析）', async () => {
    listDecisionLedger.mockResolvedValue(page([]));
    renderTable({ filters: baseFilters, onOpenDetail: vi.fn() });

    await waitFor(() => expect(listDecisionLedger).toHaveBeenCalled());
    const params = listDecisionLedger.mock.calls[0][0] as URLSearchParams;
    expect(params.toString()).not.toContain('workspace_id');
  });
});
