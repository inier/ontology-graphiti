/**
 * CognitionPanel 契约测试
 *
 * 该组件此前零引用，挂载时暴露三类问题：
 *   1) 三个页签被「焊死」在三个角色上（activeKey 由 activeRole 推导、onChange 反写角色），
 *      想看解释链必须先切到 intelligence 角色；
 *   2) 角色取值 director/operations 在后端 RoleViewManager 里根本没有登记
 *      （只有 commander/intelligence/operator），恒返回空视图；
 *   3) 三处空 catch 让失败与「还没查」在界面上无法区分。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 必须是稳定引用：组件的 useEffect/useCallback 依赖它，
  // 每次渲染返回新函数会让 effect 反复触发、重复打接口。
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

const get = vi.fn();
const post = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (...a: unknown[]) => get(...a),
    post: (...a: unknown[]) => post(...a),
  },
}));

import CognitionPanel from './CognitionPanel';

const ROLE_VIEW = {
  role: 'commander',
  name: '指挥员视图',
  description: '面向指挥决策',
  capabilities: ['态势总览', '指令下发'],
};

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  get.mockResolvedValue(ROLE_VIEW);
});

describe('CognitionPanel — 认知引擎', () => {
  it('默认角色是 commander（后端登记过的角色），不是不存在的 director', async () => {
    render(<CognitionPanel workspaceId="ws-1" scenarioId="sc-1" />);

    await waitFor(() => expect(get).toHaveBeenCalledWith('/api/cognition/role-view?role=commander'));
    expect(get).not.toHaveBeenCalledWith('/api/cognition/role-view?role=director');
  });

  it('角色下拉只提供后端登记的 3 个角色', async () => {
    render(<CognitionPanel workspaceId="ws-1" scenarioId="sc-1" />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    fireEvent.mouseDown(screen.getByLabelText('当前角色'));
    const option = await waitFor(() => {
      const el = Array.from(document.querySelectorAll('.ant-select-item-option')).find((o) =>
        (o.textContent ?? '').includes('情报员'),
      );
      if (!el) throw new Error('option not found');
      return el as HTMLElement;
    });
    fireEvent.click(option);

    await waitFor(() => expect(get).toHaveBeenCalledWith('/api/cognition/role-view?role=intelligence'));
    // 负向断言：operations 从来不是后端角色
    expect(get).not.toHaveBeenCalledWith('/api/cognition/role-view?role=operations');
  });

  it('页签与角色解耦：切到解释链不会改变角色，也不会重新拉角色视图', async () => {
    render(<CognitionPanel workspaceId="ws-1" scenarioId="sc-1" />);
    await waitFor(() => expect(get).toHaveBeenCalledWith('/api/cognition/role-view?role=commander'));

    fireEvent.click(screen.getByText('解释链'));

    // 页签切换只是 UI 维度，不该触发角色视图请求
    expect(get).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('决策 ID')).toBeTruthy();
  });

  it('意图识别 POST 到 /api/cognition/recognize-intent，body 带 input_text 与当前角色', async () => {
    post.mockResolvedValue({
      primary_intent: 'query_entity',
      confidence: 0.92,
      entities: ['订单'],
      attributes: { limit: 10 },
      alternative_intents: ['query_metric'],
    });

    render(<CognitionPanel workspaceId="ws-1" scenarioId="sc-1" />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    fireEvent.change(screen.getByLabelText('待识别文本'), { target: { value: '查一下最近的订单' } });
    fireEvent.click(screen.getByRole('button', { name: /识别意图/ }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/api/cognition/recognize-intent', {
        input_text: '查一下最近的订单',
        role: 'commander',
      }),
    );
    await waitFor(() => expect(screen.getByText('query_entity')).toBeTruthy());
    expect(screen.getByText('订单')).toBeTruthy();
  });

  it('解释链 POST /api/cognition/explain，context 带 workspace/scenario', async () => {
    post.mockResolvedValue({
      decision_id: 'd-1',
      query: '为什么拒绝？',
      answer: '因为金额超限',
      confidence: 0.8,
      reasoning_chain: [{ title: '命中规则 R3', description: '金额 > 100万' }],
      sources: ['policy/limit.rego'],
    });

    render(<CognitionPanel workspaceId="ws-1" scenarioId="sc-1" />);
    await waitFor(() => expect(get).toHaveBeenCalled());

    fireEvent.click(screen.getByText('解释链'));
    fireEvent.change(screen.getByLabelText('决策 ID'), { target: { value: 'd-1' } });
    fireEvent.click(screen.getByRole('button', { name: /生成解释/ }));

    await waitFor(() =>
      expect(post).toHaveBeenCalledWith('/api/cognition/explain', {
        decision_id: 'd-1',
        context: { workspace_id: 'ws-1', scenario_id: 'sc-1' },
      }),
    );
    await waitFor(() => expect(screen.getByText('因为金额超限')).toBeTruthy());
  });

  it('调用失败时把原因显示出来，而不是只剩「暂无数据」', async () => {
    get.mockRejectedValue(new Error('503 Cognition engine unavailable'));

    render(<CognitionPanel workspaceId="ws-1" scenarioId="sc-1" />);

    await waitFor(() => expect(screen.getByText('认知引擎调用失败')).toBeTruthy());
    expect(screen.getByText(/503 Cognition engine unavailable/)).toBeTruthy();
  });
});
