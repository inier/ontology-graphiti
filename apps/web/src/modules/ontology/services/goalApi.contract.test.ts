/**
 * goalApi 契约测试 —— Goal / ChangeProposal / ImpactAnalysis
 *
 * 为什么需要这一层测试：`ChangeProposalCard` 用到的 `getProposal` 与 `getImpact`
 * 两个方法在后端**长期没有对应路由**（仓储 `get_proposal`/`get_impact` 与
 * `_proposal_to_dict`/`_impact_to_dict` 都写好了，但 service 与 HTTP 层都没暴露）。
 * 组件一旦挂载，展开提案详情必然 404。
 *
 * 本轮已补：
 *   GET /api/ontology/goals/proposals/{proposal_id}
 *   GET /api/ontology/goals/impacts/{impact_id}
 * 这个测试钉住「前端拼的 URL」与「后端注册的路径」逐字对齐，
 * 以后任意一侧改名都会在这里失败。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { goalApi } from '../services/goalApi';

type Call = { url: string; init?: { method?: string; body?: string } };
const calls: Call[] = [];

vi.mock('@/modules/shared/services/apiClient', () => ({
  fetchJson: (url: string, init?: { method?: string; body?: string }) => {
    calls.push({ url, init });
    return Promise.resolve({});
  },
}));

const lastUrl = () => calls[calls.length - 1].url;
/** 去掉测试环境的 VITE_API_BASE 前缀，只留路径 */
const pathOf = (url: string) => url.replace(/^https?:\/\/[^/]+/, '');

beforeEach(() => {
  calls.length = 0;
});

describe('goalApi — 路径与方法契约', () => {
  it('getLineage 走 GET /api/ontology/goals/{id}/lineage', async () => {
    await goalApi.getLineage('g-1');
    expect(pathOf(lastUrl())).toBe('/api/ontology/goals/g-1/lineage');
    expect(calls[0].init?.method).toBeUndefined(); // fetchJson 默认 GET
  });

  it('getProposal 走 GET /api/ontology/goals/proposals/{id}（后端本轮补齐）', async () => {
    await goalApi.getProposal('p-1');
    expect(pathOf(lastUrl())).toBe('/api/ontology/goals/proposals/p-1');
  });

  it('getImpact 走 GET /api/ontology/goals/impacts/{id}（后端本轮补齐）', async () => {
    await goalApi.getImpact('imp-1');
    expect(pathOf(lastUrl())).toBe('/api/ontology/goals/impacts/imp-1');
  });

  it('reviewProposal 走 POST /proposals/{id}/review，body 只含 decision 与 reviewer_notes', async () => {
    await goalApi.reviewProposal('p-1', { decision: 'approve', reviewer_notes: 'ok' });

    expect(pathOf(lastUrl())).toBe('/api/ontology/goals/proposals/p-1/review');
    expect(calls[0].init?.method).toBe('POST');
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({
      decision: 'approve',
      reviewer_notes: 'ok',
    });
  });

  it('transition 走 POST /{id}/transition，body 键是 new_status', async () => {
    await goalApi.transition('g-1', 'approved');

    expect(pathOf(lastUrl())).toBe('/api/ontology/goals/g-1/transition');
    expect(JSON.parse(calls[0].init?.body as string)).toEqual({ new_status: 'approved' });
  });

  it('list 把 workspace_id 放进 query（后端 workspace_id 是必填 Query）', async () => {
    await goalApi.list({ workspace_id: 'ws-1', status: 'approved', page: 2, page_size: 50 });

    const p = pathOf(lastUrl());
    expect(p.startsWith('/api/ontology/goals?')).toBe(true);
    expect(p).toContain('workspace_id=ws-1');
    expect(p).toContain('status=approved');
    expect(p).toContain('page=2');
    expect(p).toContain('page_size=50');
  });

  it('proposeChange 走 POST /{id}/propose-change，changes 原样透传', async () => {
    await goalApi.proposeChange('g-1', {
      title: '新增客户属性',
      changes: [{ op: 'add_property', target: 'Customer' }],
      proposed_by: 'u-1',
    });

    expect(pathOf(lastUrl())).toBe('/api/ontology/goals/g-1/propose-change');
    const body = JSON.parse(calls[0].init?.body as string);
    expect(body.changes).toEqual([{ op: 'add_property', target: 'Customer' }]);
    expect(body.proposed_by).toBe('u-1');
  });
});
