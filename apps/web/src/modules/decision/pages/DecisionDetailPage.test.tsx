import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { App } from 'antd';
import { render } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { DecisionChain, DecisionRecord } from '../types';
import { DecisionApiError } from '../services/decisionRequest';

const getDecisionChain = vi.fn();
const analyzeDecisionImpact = vi.fn();
const findSimilarDecisions = vi.fn();
vi.mock('../services/decisionApi', () => ({
  getDecisionChain: (...args: unknown[]) => getDecisionChain(...args),
  analyzeDecisionImpact: (...args: unknown[]) => analyzeDecisionImpact(...args),
  findSimilarDecisions: (...args: unknown[]) => findSimilarDecisions(...args),
  resolveDecision: vi.fn().mockResolvedValue({}),
}));

// G6 依赖 canvas，jsdom 下不渲染真实图
vi.mock('@antv/g6', () => ({
  Graph: class {
    render() {
      return undefined;
    }
    destroy() {
      return undefined;
    }
  },
}));

const { default: DecisionDetailPage } = await import('./DecisionDetailPage');

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

function chain(overrides: Partial<DecisionRecord> = {}): DecisionChain {
  return {
    decision: record(overrides),
    evidence_entities: [{ uuid: 'e1', name: 'A 类门店库存' }],
    evidence_episodes: [],
    parent_chain: [],
    precedents: [],
    reasoning_trace: [{ step_id: 's1', phase: 'decide', description: '选择分批补货', timestamp: '2026-10-22T10:00:00Z' }],
  };
}

function renderPage() {
  // 必须真实挂载路由：`useParams` 只有在匹配到 :decisionId 时才有值
  return render(
    <App>
      <MemoryRouter initialEntries={['/decisions/detail/dec_7f3a2b1c9d0e']}>
        <Routes>
          <Route path="/decisions/detail/:decisionId" element={<DecisionDetailPage />} />
        </Routes>
      </MemoryRouter>
    </App>,
  );
}

beforeEach(() => {
  getDecisionChain.mockReset();
  analyzeDecisionImpact.mockReset();
  findSimilarDecisions.mockReset();
  findSimilarDecisions.mockResolvedValue([]);
  analyzeDecisionImpact.mockResolvedValue({
    decision_id: 'dec_7f3a2b1c9d0e',
    derived_decisions: [],
    target_changes: [],
    co_evidence_decisions: [],
    impact_completeness: 'partial',
  });
});

describe('DecisionDetailPage', () => {
  it('404 用统一文案，不暴露「存在但无权限」', async () => {
    getDecisionChain.mockRejectedValue(new DecisionApiError(404, '决策不存在'));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('决策不存在或无权访问')).toBeInTheDocument();
    });
    expect(screen.getByText('它可能属于其他工作空间，或已被删除。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '返回决策台账' })).toBeInTheDocument();
  });

  it('403 与 404 文案分开，且不渲染任何决策字段', async () => {
    getDecisionChain.mockRejectedValue(new DecisionApiError(403, '无查看权限'));
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('你没有查看这条决策的权限')).toBeInTheDocument();
    });
    expect(screen.queryByText('推荐方案')).toBeNull();
  });

  it('impact_completeness=partial 显示三态之一的具体文案（含「0 不代表没有」澄清）', async () => {
    getDecisionChain.mockResolvedValue(chain());
    renderPage();

    await waitFor(() => {
      expect(screen.getByText('影响分析不完整')).toBeInTheDocument();
    });
    expect(
      screen.getByText(/下游决策数为 0 不代表没有下游决策/),
    ).toBeInTheDocument();
  });

  it('详情页展示推理路径区块（来自 /chain 的 reasoning_trace，零额外请求）', async () => {
    getDecisionChain.mockResolvedValue(chain());
    renderPage();

    await waitFor(() => expect(screen.getByText('推理路径')).toBeInTheDocument());
    expect(screen.getByText('选择分批补货')).toBeInTheDocument();
  });

  it('状态标签走双参映射，待裁定显示「待定（待裁定）」', async () => {
    getDecisionChain.mockResolvedValue(chain());
    renderPage();

    // 头部与 Descriptions「可见状态」各一处，都必须是双参映射结果
    await waitFor(() => expect(screen.getAllByText('待定（待裁定）').length).toBeGreaterThan(0));
  });

  it('无关联执行动作时给出说明，而不是空白', async () => {
    getDecisionChain.mockResolvedValue(chain());
    renderPage();

    await waitFor(() => expect(screen.getByText('无关联执行动作')).toBeInTheDocument());
    expect(screen.getByText('该决策尚未派发执行')).toBeInTheDocument();
  });

  it('非待裁定状态不渲染裁决按钮（不适用 ≠ 无权限）', async () => {
    getDecisionChain.mockResolvedValue(chain({ status: 'executed', outcome: 'success' }));
    renderPage();

    await waitFor(() =>
      expect(screen.getByText(/该决策当前状态不可裁决/)).toBeInTheDocument(),
    );
    expect(screen.queryByRole('button', { name: '采纳' })).toBeNull();
  });
});
