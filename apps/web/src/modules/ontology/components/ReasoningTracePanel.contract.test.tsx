/**
 * ReasoningTracePanel 契约测试
 *
 * 该组件此前零引用。契约是真的（`POST /api/reasoning/deduce`），但没有任何入口，
 * 且全文中文硬编码、`Alert` 用了 AntD 6 已弃用的 `message` 属性。
 *
 * 这里钉住四件事：
 *   1) 请求打到 /api/reasoning/deduce，goal / ontology_id / workspace_id 走 query 参数；
 *   2) rule_trace 有则逐条渲染，无则给出解释性空态（不能说成「没命中」）；
 *   3) 失败原因原样暴露，不吞成「推理失败」；
 *   4) 没选本体时按钮不可点 —— 空 ontology_id 打过去只会得到无意义结果。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // t 保持稳定引用：组件把它放进 useCallback 依赖
  const t = (key: string) => key;
  return { useI18n: () => ({ t }) };
});

const post = vi.fn();
vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: { post: (...a: unknown[]) => post(...a) },
}));

import ReasoningTracePanel from './ReasoningTracePanel';

const OUTCOME = {
  source: 'deterministic',
  rows: [['a', 'b'], ['b', 'c']],
  confidence: 0.93,
  explanation: 'Datalog 推导成功',
  truncated: false,
  fallback_reason: '',
};

beforeEach(() => {
  post.mockReset();
});

describe('ReasoningTracePanel — 推理追踪', () => {
  it('goal / ontology_id / workspace_id 走 query 参数打 /api/reasoning/deduce', async () => {
    post.mockResolvedValue({ ...OUTCOME, rule_trace: [] });

    render(<ReasoningTracePanel ontologyId="ont-1" workspaceId="ws-1" />);
    fireEvent.change(screen.getByLabelText('推理目标'), { target: { value: 'ancestor("a", X)' } });
    fireEvent.click(screen.getByRole('button', { name: /推\s*理/ }));

    await waitFor(() => {
      const url = String(post.mock.calls[0][0]);
      expect(url.startsWith('/api/reasoning/deduce?')).toBe(true);
      const qs = new URLSearchParams(url.split('?')[1]);
      expect(qs.get('goal')).toBe('ancestor("a", X)');
      expect(qs.get('ontology_id')).toBe('ont-1');
      expect(qs.get('workspace_id')).toBe('ws-1');
    });
  });

  it('渲染置信度与推理来源，rows 里的对象值不会直接塞进 JSX', async () => {
    post.mockResolvedValue({
      ...OUTCOME,
      rows: [['a', { nested: true }]],
      rule_trace: [],
    });

    render(<ReasoningTracePanel ontologyId="ont-1" />);
    fireEvent.change(screen.getByLabelText('推理目标'), { target: { value: 'path("a", X)' } });
    fireEvent.click(screen.getByRole('button', { name: /推\s*理/ }));

    await waitFor(() => expect(screen.getByText('93.0%')).toBeTruthy());
    expect(screen.getByText('确定性推理')).toBeTruthy();
    expect(screen.getByText('a, {"nested":true}')).toBeTruthy();
  });

  it('rule_trace 有值则逐条渲染规则轨迹', async () => {
    post.mockResolvedValue({
      ...OUTCOME,
      rule_trace: [
        {
          goal: 'ancestor("a", X)',
          rule_id: 'R1',
          rule_text: 'ancestor(X,Y) :- parent(X,Y)',
          matched_rows: 2,
          elapsed_ms: 1.25,
          truncated: false,
          fired_at: '2026-10-19T00:00:00Z',
          bindings: { X: 'a' },
        },
      ],
    });

    render(<ReasoningTracePanel ontologyId="ont-1" />);
    fireEvent.change(screen.getByLabelText('推理目标'), { target: { value: 'ancestor("a", X)' } });
    fireEvent.click(screen.getByRole('button', { name: /推\s*理/ }));

    await waitFor(() => expect(screen.getByText('R1')).toBeTruthy());
    expect(screen.getByText('ancestor(X,Y) :- parent(X,Y)')).toBeTruthy();
  });

  it('rule_trace 缺省时给出解释性空态，而不是当成「没有命中」', async () => {
    post.mockResolvedValue({ ...OUTCOME, rule_trace: undefined });

    render(<ReasoningTracePanel ontologyId="ont-1" />);
    fireEvent.change(screen.getByLabelText('推理目标'), { target: { value: 'path("a", X)' } });
    fireEvent.click(screen.getByRole('button', { name: /推\s*理/ }));

    await waitFor(() =>
      expect(screen.getByText('本次推理未返回规则轨迹（rule_trace 缺省）')).toBeTruthy(),
    );
  });

  it('失败原因原样显示，不吞成通用文案', async () => {
    post.mockRejectedValue(new Error('500 deducer timeout: graph backend unavailable'));

    render(<ReasoningTracePanel ontologyId="ont-1" />);
    fireEvent.change(screen.getByLabelText('推理目标'), { target: { value: 'path("a", X)' } });
    fireEvent.click(screen.getByRole('button', { name: /推\s*理/ }));

    await waitFor(() => expect(screen.getByText('推理请求失败')).toBeTruthy());
    expect(screen.getByText(/500 deducer timeout/)).toBeTruthy();
  });

  it('未选本体时按钮禁用并说明原因（空 ontology_id 推不出有意义的结果）', () => {
    render(<ReasoningTracePanel ontologyId="" />);

    expect(screen.getByText('请先选择本体，推理需要 ontology_id')).toBeTruthy();
    const btn = screen.getByRole('button', { name: /推\s*理/ }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });
});
