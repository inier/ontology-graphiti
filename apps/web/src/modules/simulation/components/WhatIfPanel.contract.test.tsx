/**
 * WhatIfPanel 契约测试 —— 假设推演
 *
 * 真实契约（odap/biz/simulation/simulation_sandbox/api/parallel_routes.py）：
 *   POST /api/simulation/what-if
 *   body: { base_scenario: {...必填...}, param_variations: [{ <param>: <value> }] }
 *   resp.sensitivity_analysis: { <metric>: [{ variation, delta }] }
 *
 * 旧实现三处硬伤，这里各钉一条：
 *  ① 不发 base_scenario → 后端拿到空场景，仿真等于跑空壳；
 *  ② 发 sandbox_id / scenario_id → 后端不读，纯噪声；
 *  ③ 读 sensitivity_analysis[x].impact / .direction → 后端只给 variation / delta，
 *     对 undefined 调 .toFixed() 会直接抛 TypeError 白屏。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  const t = (key: string, opts?: Record<string, unknown>) =>
    opts && Object.keys(opts).length ? `${key}|${JSON.stringify(opts)}` : key;
  return { useI18n: () => ({ t }) };
});

type Call = { method: string; url: string; body?: unknown };
const calls: Call[] = [];

const WHAT_IF_URL = '/api/simulation/what-if';

const OK_RESPONSE = {
  run_id: 'run-1',
  status: 'completed',
  total_variations: 2,
  base_scenario: { action_type_id: 'rebalance', target_object_id: 'n-1', target_object_type: 'Node' },
  results: [
    {
      scenario_id: 'sc-1',
      status: 'completed',
      metric_changes: [{ metric_name: 'throughput', before: 100, after: 112, delta: 12 }],
      risk_assessment: { level: 'low' },
      recommendation: '可执行',
      confidence: 0.82,
      variation: { intensity: 1 },
    },
    {
      scenario_id: 'sc-2',
      status: 'completed',
      metric_changes: [],
      risk_assessment: { level: 'mid' },
      recommendation: '需复核',
      confidence: 0.64,
      variation: { intensity: 2 },
    },
  ],
  sensitivity_analysis: {
    throughput: [
      { variation: { intensity: 1 }, delta: 12 },
      { variation: { intensity: 2 }, delta: -3.5 },
    ],
  },
  completed_at: '2026-10-19T10:00:00Z',
};

vi.mock('@/modules/shared/services/apiClient', () => ({
  apiClient: {
    get: (url: string) => {
      calls.push({ method: 'GET', url });
      return Promise.reject(new Error(`unexpected GET ${url}`));
    },
    post: (url: string, body?: unknown) => {
      calls.push({ method: 'POST', url, body });
      if (url === WHAT_IF_URL) return Promise.resolve(OK_RESPONSE);
      return Promise.reject(new Error(`unexpected POST ${url}`));
    },
  },
}));

import { WhatIfPanel } from './WhatIfPanel';

const postCalls = () => calls.filter((c) => c.method === 'POST');

/** 填一行参数变体：参数名 + 取值 */
function fillVariation(name: string, value: string) {
  const nameInput = screen.getByPlaceholderText('参数名') as HTMLInputElement;
  fireEvent.change(nameInput, { target: { value: name } });
  const valueInput = screen.getByPlaceholderText('取值') as HTMLInputElement;
  fireEvent.change(valueInput, { target: { value } });
}

beforeEach(() => {
  calls.length = 0;
});

describe('WhatIfPanel — 假设推演契约', () => {
  it('提交体必带 base_scenario，且四个键齐全', async () => {
    render(<WhatIfPanel defaultActionTypeId="rebalance" defaultTargetObjectId="n-1" defaultTargetObjectType="Node" />);

    fillVariation('intensity', '1');
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));
    const body = postCalls()[0].body as {
      base_scenario: Record<string, unknown>;
      param_variations: Array<Record<string, number>>;
    };

    // ① 没有 base_scenario 时后端会按空场景跑，等于白跑
    expect(body.base_scenario).toBeDefined();
    expect(body.base_scenario.action_type_id).toBe('rebalance');
    expect(body.base_scenario.target_object_id).toBe('n-1');
    expect(body.base_scenario.target_object_type).toBe('Node');
    // 参数默认值是 "{}"，应被解析成对象而不是原样传字符串
    expect(body.base_scenario.parameters).toEqual({});
  });

  it('param_variations 是 [{参数名: 数值}] 数组，不是 [{key, value}]', async () => {
    render(<WhatIfPanel />);

    fillVariation('intensity', '2');
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));
    const body = postCalls()[0].body as { param_variations: Array<Record<string, number>> };

    expect(body.param_variations).toEqual([{ intensity: 2 }]);
    // 负向：内部的表单行结构不得泄漏到报文里
    expect(body.param_variations.some((v) => 'key' in v || 'value' in v)).toBe(false);
  });

  it('报文里不得出现后端不读的 sandbox_id / scenario_id', async () => {
    render(<WhatIfPanel />);

    fillVariation('intensity', '1');
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    await waitFor(() => expect(postCalls()).toHaveLength(1));
    const body = postCalls()[0].body as Record<string, unknown>;

    expect(body).not.toHaveProperty('sandbox_id');
    expect(body).not.toHaveProperty('scenario_id');
    // 顶层只应有两个键
    expect(Object.keys(body).sort()).toEqual(['base_scenario', 'param_variations']);
  });

  it('敏感度表读 variation / delta：能渲染出正负变化量，不因缺 impact / direction 报错', async () => {
    render(<WhatIfPanel />);

    fillVariation('intensity', '1');
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    await waitFor(() => expect(screen.getByText('指标敏感度')).toBeTruthy());

    // delta 12 → "+12.0000"；delta -3.5 → "-3.5000"
    await waitFor(() => expect(screen.getByText('+12.0000')).toBeTruthy());
    expect(screen.getByText('-3.5000')).toBeTruthy();
    // variation 对象被摊平成 k=v
    expect(screen.getAllByText('intensity=1').length).toBeGreaterThan(0);
    // 旧实现会对 undefined 调 toFixed，渲染出 NaN —— 这条负向断言兜住它
    expect(document.body.textContent).not.toContain('NaN');
    expect(document.body.textContent).not.toContain('undefined');
  });

  it('逐变体结论读 results：场景 ID / 置信度百分比 / 建议都来自真实字段', async () => {
    render(<WhatIfPanel />);

    fillVariation('intensity', '1');
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    await waitFor(() => expect(screen.getByText('sc-1')).toBeTruthy());
    expect(screen.getByText('sc-2')).toBeTruthy();
    // confidence 0.82 → 82%
    expect(screen.getByText('82%')).toBeTruthy();
    expect(screen.getByText('可执行')).toBeTruthy();
  });

  it('未填任何参数变体时阻断提交，不发请求', async () => {
    render(<WhatIfPanel />);

    // 默认有一行空变体，直接提交
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    // 给 antd message 的 microtask 留出时间
    await new Promise((r) => setTimeout(r, 50));
    expect(postCalls()).toHaveLength(0);
  });

  it('基础参数不是合法 JSON 时报错并阻断，不发请求', async () => {
    render(<WhatIfPanel />);

    const paramsBox = screen.getByPlaceholderText('ObjectType');
    expect(paramsBox).toBeTruthy();
    const jsonBox = document.querySelector('textarea') as HTMLTextAreaElement;
    fireEvent.change(jsonBox, { target: { value: '{not json' } });

    fillVariation('intensity', '1');
    fireEvent.click(screen.getByRole('button', { name: /开始推演/ }));

    await new Promise((r) => setTimeout(r, 80));
    expect(postCalls()).toHaveLength(0);
  });
});
