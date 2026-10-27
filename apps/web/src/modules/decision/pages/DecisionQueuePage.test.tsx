import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { renderWithProviders } from '@/test/helpers/renderWithProviders';
import type { DecisionRecord, PendingDecisionItem, PendingQueuePage } from '../types';
import { splitSections } from '../utils/queueSections';

const listPendingDecisions = vi.fn();
const resolveDecision = vi.fn();
vi.mock('../services/decisionApi', () => ({
  listPendingDecisions: (...args: unknown[]) => listPendingDecisions(...args),
  resolveDecision: (...args: unknown[]) => resolveDecision(...args),
  executeDecision: vi.fn().mockResolvedValue({ idempotent_replay: false }),
}));

const { default: DecisionQueuePage } = await import('./DecisionQueuePage');

function record(overrides: Partial<DecisionRecord> = {}): DecisionRecord {
  return {
    decision_id: 'dec_aaaaaaaaaaaa',
    workspace_id: 'ws_demo',
    context_summary: '华东区 A 类门店库存跌破安全线，是否继续执行自动补货？',
    constraints: {},
    reasoning: '',
    reasoning_trace: [],
    confidence: 0.42,
    evidence_episode_ids: [],
    evidence_entity_ids: ['e1'],
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
    created_at: '2026-10-20T10:00:00Z',
    updated_at: '2026-10-20T10:00:00Z',
    valid_at: '2026-10-20T10:00:00Z',
    ...overrides,
  };
}

function item(overrides: Partial<PendingDecisionItem> = {}): PendingDecisionItem {
  return {
    decision: record(),
    group: 'to_resolve',
    waited_minutes: 4560,
    decided_waited_minutes: null,
    sla_state: 'breached',
    available_operations: ['approve', 'reject'],
    executable: true,
    ...overrides,
  };
}

function queuePage(items: PendingDecisionItem[]): PendingQueuePage {
  return {
    items,
    total: items.length,
    counts: { to_resolve: 1, to_execute: 2, sla_warning: 1, sla_breached: 1 },
    page: 1,
    page_size: 50,
    has_more: false,
  };
}

function renderPage() {
  // renderWithProviders 已内置 MemoryRouter + i18n；只需再套 antd App（useApp 上下文）
  return renderWithProviders(
    <App>
      <DecisionQueuePage />
    </App>,
    { route: '/decisions/queue' },
  );
}

beforeEach(() => {
  listPendingDecisions.mockReset();
  resolveDecision.mockReset();
  resolveDecision.mockResolvedValue({});
});

describe('splitSections —— 三段而不是两段', () => {
  it('to_execute 内再按 status 拆成「已裁决待执行」与「执行中」', () => {
    const sections = splitSections([
      item(),
      item({ group: 'to_execute', decision: record({ status: 'decided' }), available_operations: ['execute'] }),
      item({ group: 'to_execute', decision: record({ status: 'executing' }), available_operations: [] }),
    ]);
    expect(sections.map((s) => s.title)).toEqual(['待我拍板', '已裁决，待执行', '执行中']);
  });

  it('空分组不渲染标题（不出现空分组）', () => {
    const sections = splitSections([item()]);
    expect(sections).toHaveLength(1);
  });
});

describe('DecisionQueuePage', () => {
  it('渲染三段分组与双计数', async () => {
    listPendingDecisions.mockResolvedValue(
      queuePage([
        item({ decision: record({ decision_id: 'dec_111111111111' }) }),
        item({
          group: 'to_execute',
          decision: record({ decision_id: 'dec_222222222222', status: 'decided', action_record_id: null }),
          available_operations: ['execute'],
        }),
        item({
          group: 'to_execute',
          decision: record({ decision_id: 'dec_333333333333', status: 'executing', action_record_id: 'act_1' }),
          available_operations: [],
        }),
      ]),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('待我拍板')).toBeInTheDocument());
    expect(screen.getByText('已裁决，待执行')).toBeInTheDocument();
    expect(screen.getByText('执行中')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /待裁定 1 条/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /待执行确认 2 条/ })).toBeInTheDocument();
  });

  it('executing 卡片不渲染任何操作按钮，改渲染进度说明', async () => {
    listPendingDecisions.mockResolvedValue(
      queuePage([
        item({
          group: 'to_execute',
          decision: record({ status: 'executing', action_record_id: 'act_1' }),
          available_operations: [],
        }),
      ]),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('执行中')).toBeInTheDocument());
    expect(screen.getByText(/执行中，等待完成/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '采纳' })).toBeNull();
    expect(screen.queryByRole('button', { name: '驳回' })).toBeNull();
    expect(screen.queryByRole('button', { name: '发起执行' })).toBeNull();
  });

  it('decided 卡片按 available_operations 渲染「发起执行」（否则 execute 不可达）', async () => {
    listPendingDecisions.mockResolvedValue(
      queuePage([
        item({
          group: 'to_execute',
          decision: record({ status: 'decided' }),
          available_operations: ['execute'],
        }),
      ]),
    );
    renderPage();

    await waitFor(() => expect(screen.getByRole('button', { name: /发起执行/ })).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: '采纳' })).toBeNull();
  });

  it('待裁定卡片渲染采纳 / 驳回 / 查看详情', async () => {
    listPendingDecisions.mockResolvedValue(queuePage([item()]));
    renderPage();

    await waitFor(() => expect(screen.getByRole('button', { name: /采纳/ })).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /驳回/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /查看详情/ })).toBeInTheDocument();
  });

  it('队列清空时给出具体空态文案，不用空洞语气', async () => {
    listPendingDecisions.mockResolvedValue(queuePage([]));
    renderPage();

    await waitFor(() => expect(screen.getByText('待决策队列已清空')).toBeInTheDocument());
    expect(screen.getByText('当前没有等你拍板的决策。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /去台账看看最近的决策/ })).toBeInTheDocument();
  });

  it('加载失败暴露 HTTP 状态与后端 detail', async () => {
    const { DecisionApiError } = await import('../services/decisionRequest');
    listPendingDecisions.mockRejectedValue(new DecisionApiError(422, 'JWT 缺少 workspace 声明'));
    renderPage();

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText('待决策队列加载失败')).toBeInTheDocument();
    expect(screen.getByText('HTTP 422 · JWT 缺少 workspace 声明')).toBeInTheDocument();
    expect(screen.getByText('数据可能过期')).toBeInTheDocument();
  });

  it('409 实际渲染文案：用户看到「已被 张三 处理」，不是「HTTP 409」', async () => {
    const { DecisionApiError } = await import('../services/decisionRequest');
    listPendingDecisions.mockResolvedValue(queuePage([item({ decision: record({ confidence: 0.82 }) })]));
    resolveDecision.mockRejectedValue(
      new DecisionApiError(409, {
        error: {
          code: 'illegal_transition',
          message: 'decision already resolved',
          details: { handler_name: '张三' },
        },
      }),
    );
    renderPage();

    const approve = await screen.findByRole('button', { name: /采纳/ });
    fireEvent.click(approve);

    await waitFor(() =>
      expect(screen.getByText('该决策已被张三处理，请刷新后查看最新状态')).toBeInTheDocument(),
    );
    expect(screen.queryByText(/HTTP 409/)).toBeNull();
  });

  it('to_execute 卡片用 decided_waited_minutes，不拿 waited_minutes 顶替', async () => {
    listPendingDecisions.mockResolvedValue(
      queuePage([
        item({
          group: 'to_execute',
          decision: record({ status: 'decided' }),
          available_operations: ['execute'],
          waited_minutes: 4560, // 自创建起算：76 小时
          decided_waited_minutes: 90, // 自裁决起算：1 小时
        }),
      ]),
    );
    renderPage();

    await waitFor(() => expect(screen.getByText('等待 1 小时')).toBeInTheDocument());
    expect(screen.queryByText('等待 76 小时')).toBeNull();
  });
});
