/**
 * TemplateRecommender 契约测试 —— HE 模板推荐
 *
 * 真实契约：
 *   POST /api/extraction/templates/recommend  body { text, ontology_id }
 *        resp { status, templates: candidate[], assessment }
 *   POST /api/extraction/templates/generate-web-search  body { text, ontology_id }
 *        resp { status, template }（template 可能为 null；失败回退时带 degradation_flag）
 *
 * candidate 字段（TemplateEngine.assess）：{ name, template_path, description, source, score, trial_result }
 * score ∈ [0,1]，threshold 默认 0.5。
 *
 * 旧实现三处硬伤：
 *  ① 读 `match_score`（真实是 `score`）→ 星级永不显示；
 *  ② 读 `id`（候选没有 id，唯一标识是 name）→ `selectedId === undefined` 恒成立，
 *     **所有候选同时显示为选中**；
 *  ③ 传 `top_k`（后端 assess 用配置 he.template_top_k，不读请求体）、
 *     读 `domain`/`applicable_scenarios`（候选没有这两键）、
 *     不展示 `trial_result`（"为什么推荐它"的唯一证据）。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/modules/shared/hooks/useI18n', () => {
  // 做真实插值，断言才读得懂：'得分 {{n}}' + {n:'0.920'} → '得分 0.920'
  const t = (key: string, opts?: Record<string, unknown>) => {
    if (!opts) return key;
    return key.replace(/\{\{(\w+)\}\}/g, (_, k: string) => String(opts[k] ?? ''));
  };
  return { useI18n: () => ({ t }) };
});

type Call = { fn: string; body: Record<string, unknown> };
const calls: Call[] = [];

const CANDIDATES = [
  {
    name: 'general/graph',
    template_path: 'general/graph.yaml',
    description: '通用图谱抽取',
    source: 'preset',
    score: 0.92,
    trial_result: {
      entity_count: 12,
      relation_count: 7,
      field_coverage: 0.8,
      type_diversity: 0.6,
      types_found: ['Customer', 'Order'],
    },
  },
  {
    name: 'domain/supply',
    template_path: 'domain/supply.yaml',
    description: '供应链专用',
    source: 'preset',
    score: 0.41,
    trial_result: { entity_count: 3, relation_count: 1, field_coverage: 0.4, type_diversity: 0.3, types_found: [] },
  },
];

let assessment = { best_score: 0.92, threshold: 0.5, needs_custom: false, settled_used: false };
let webTemplate: Record<string, unknown> | null = { name: 'web/generated', description: '联网生成' };

const recommendMock = vi.fn(async (body: Record<string, unknown>) => {
  calls.push({ fn: 'recommend', body });
  return { templates: CANDIDATES, assessment };
});

const webSearchMock = vi.fn(async (body: Record<string, unknown>) => {
  calls.push({ fn: 'webSearch', body });
  return { template: webTemplate };
});

vi.mock('@/modules/ontology/services/ontologyApi', () => ({
  ontologyApi: {
    extraction: {
      recommendTemplates: (body: Record<string, unknown>) => recommendMock(body),
      generateTemplateWebSearch: (body: Record<string, unknown>) => webSearchMock(body),
    },
  },
}));

import { TemplateRecommender } from './TemplateRecommender';

beforeEach(() => {
  calls.length = 0;
  recommendMock.mockClear();
  webSearchMock.mockClear();
  assessment = { best_score: 0.92, threshold: 0.5, needs_custom: false, settled_used: false };
  webTemplate = { name: 'web/generated', description: '联网生成' };
});

describe('TemplateRecommender — 模板推荐契约', () => {
  it('推荐请求体只含 text 与 ontology_id，不传后端不读的 top_k', async () => {
    render(<TemplateRecommender ontologyId="ont-1" text="客户下单记录" />);

    fireEvent.click(screen.getByRole('button', { name: /推荐模板/ }));

    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0].fn).toBe('recommend');
    expect(calls[0].body).toEqual({ text: '客户下单记录', ontology_id: 'ont-1' });
    // 负向：top_k 是旧实现的噪音字段
    expect(calls[0].body).not.toHaveProperty('top_k');
  });

  it('score 渲染为真实得分（0.92 → 0.920），不是读不存在的 match_score', async () => {
    render(<TemplateRecommender ontologyId="ont-1" text="x" />);
    fireEvent.click(screen.getByRole('button', { name: /推荐模板/ }));

    await waitFor(() => expect(screen.getByText('general/graph')).toBeTruthy());
    expect(screen.getByText('得分 0.920')).toBeTruthy();
    expect(screen.getByText('得分 0.410')).toBeTruthy();
    expect(document.body.textContent).not.toContain('NaN');
  });

  it('选中以 name 为标识：点第二项后只有它高亮（旧实现读 id 导致全选）', async () => {
    render(<TemplateRecommender ontologyId="ont-1" text="x" onSelect={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /推荐模板/ }));
    await waitFor(() => expect(screen.getByText('general/graph')).toBeTruthy());

    // 初始无选中
    expect(document.querySelectorAll('.anticon-check-circle')).toHaveLength(0);

    fireEvent.click(screen.getByText('domain/supply'));

    await waitFor(() => expect(document.querySelectorAll('.anticon-check-circle')).toHaveLength(1));
  });

  it('onSelect 回传真实候选（name / score / trial_result 都在）', async () => {
    const picked: Array<Record<string, unknown>> = [];
    render(<TemplateRecommender ontologyId="ont-1" text="x" onSelect={(tpl) => picked.push(tpl)} />);
    fireEvent.click(screen.getByRole('button', { name: /推荐模板/ }));
    await waitFor(() => expect(screen.getByText('general/graph')).toBeTruthy());

    fireEvent.click(screen.getByText('general/graph'));

    await waitFor(() => expect(picked).toHaveLength(1));
    expect(picked[0].name).toBe('general/graph');
    expect(picked[0].score).toBe(0.92);
    expect((picked[0].trial_result as Record<string, unknown>).entity_count).toBe(12);
  });

  it('展示 trial_result：试抽取实体数 / 关系数 / 字段覆盖 / 类型多样性', async () => {
    render(<TemplateRecommender ontologyId="ont-1" text="x" />);
    fireEvent.click(screen.getByRole('button', { name: /推荐模板/ }));

    await waitFor(() => expect(screen.getByText('试抽取实体 12')).toBeTruthy());
    expect(screen.getByText('关系 7')).toBeTruthy();
    expect(screen.getByText('字段覆盖 80%')).toBeTruthy();
    expect(screen.getByText('类型多样性 60%')).toBeTruthy();
    // types_found 用 Tag 渲染
    expect(screen.getByText('Customer')).toBeTruthy();
  });

  it('assessment.needs_custom 为 true 时提示改走联网生成', async () => {
    assessment = { best_score: 0.31, threshold: 0.5, needs_custom: true, settled_used: false };
    render(<TemplateRecommender ontologyId="ont-1" text="x" />);
    fireEvent.click(screen.getByRole('button', { name: /推荐模板/ }));

    await waitFor(() => expect(screen.getByText('没有候选达到阈值')).toBeTruthy());
    expect(screen.getByText(/最高分 0\.310/)).toBeTruthy();
  });

  it('联网生成成功时把新模板追加到列表', async () => {
    render(<TemplateRecommender ontologyId="ont-1" text="x" />);
    fireEvent.click(screen.getByRole('button', { name: /联网搜索生成/ }));

    await waitFor(() => expect(screen.getByText('web/generated')).toBeTruthy());
    const call = calls.find((c) => c.fn === 'webSearch')!;
    expect(call.body).toEqual({ text: 'x', ontology_id: 'ont-1' });
  });

  it('后端回退（degradation_flag）时明确提示，而不是假装生成成功', async () => {
    webTemplate = { name: 'fallback', score: 0, degradation_flag: 'custom_generation_failed' };
    render(<TemplateRecommender ontologyId="ont-1" text="x" />);
    fireEvent.click(screen.getByRole('button', { name: /联网搜索生成/ }));

    await waitFor(() => expect(screen.getByText('自定义生成失败')).toBeTruthy());
    expect(screen.getByText(/custom_generation_failed/)).toBeTruthy();
  });

  it('未输入文本时两个按钮都禁用（不发出空请求）', async () => {
    render(<TemplateRecommender ontologyId="ont-1" text="" />);

    const recommendBtn = screen.getByRole('button', { name: /推荐模板/ }) as HTMLButtonElement;
    const webBtn = screen.getByRole('button', { name: /联网搜索生成/ }) as HTMLButtonElement;
    expect(recommendBtn.disabled).toBe(true);
    expect(webBtn.disabled).toBe(true);

    fireEvent.click(recommendBtn);
    await new Promise((r) => setTimeout(r, 30));
    expect(calls).toHaveLength(0);
  });
});
