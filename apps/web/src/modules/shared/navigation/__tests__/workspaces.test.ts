/**
 * 工作区信息架构测试（F4 / AC-19）
 *
 * 断言导航收敛到恰好 6 个顶级工作区，且「当前路由 → 工作区」的判定使用最长前缀，
 * 不会被宽泛前缀抢走。
 */
import { describe, expect, it } from 'vitest';
import { WORKSPACES, WORKSPACE_IDS, findWorkspaceByPath } from '../workspaces';

describe('WORKSPACES', () => {
  it('恰好 6 个顶级工作区，顺序即导航顺序（AC-19）', () => {
    expect(WORKSPACE_IDS).toEqual(['workspace', 'ontology', 'knowledge', 'ask', 'governance', 'platform']);
    expect(WORKSPACES).toHaveLength(6);
  });

  it('每个工作区都有唯一 home、非空二级项与目标图标角色', () => {
    for (const ws of WORKSPACES) {
      expect(ws.home, `${ws.id} 缺少 home`).toMatch(/^\//);
      expect(ws.items.length, `${ws.id} 没有二级导航项`).toBeGreaterThan(0);
      expect(ws.prefixes.length, `${ws.id} 没有路径前缀`).toBeGreaterThan(0);
      expect(ws.iconRole).toBeTruthy();
    }
  });

  it('二级导航项的 path 互不重复（避免菜单同目标多入口）', () => {
    const paths = WORKSPACES.flatMap((ws) => ws.items.map((item) => item.path));
    expect(new Set(paths).size).toBe(paths.length);
  });

  it('home 必定出现在本工作区的二级项里（点一级即可落地）', () => {
    for (const ws of WORKSPACES) {
      const paths = ws.items.map((item) => item.path);
      if (ws.home === '/') {
        expect(paths, `${ws.id} home=/ 无对应项`).toContain('/');
      } else {
        expect(paths, `${ws.id} 的 home ${ws.home} 不在 items 中`).toContain(ws.home);
      }
    }
  });
});

describe('findWorkspaceByPath', () => {
  it('根路径归工作台', () => {
    expect(findWorkspaceByPath('/')?.id).toBe('workspace');
  });

  it('按最长前缀归属，不让宽前缀抢走', () => {
    expect(findWorkspaceByPath('/settings/channels/default')?.id).toBe('platform');
    expect(findWorkspaceByPath('/semantic-admin/gaps/01J9Z6Q2X8K3M4N5P6R7S8T9V1')?.id).toBe('governance');
    expect(findWorkspaceByPath('/wiki/dedupe')?.id).toBe('knowledge');
    expect(findWorkspaceByPath('/knowledge')?.id).toBe('knowledge');
  });

  it('动态路由与嵌套路由都能归属', () => {
    expect(findWorkspaceByPath('/wiki/01J9Z6Q2X8K3M4N5P6R7S8T9V1')?.id).toBe('knowledge');
    expect(findWorkspaceByPath('/agent-chat/agent-7')?.id).toBe('workspace');
    expect(findWorkspaceByPath('/semantic-admin/routing-tickets/rt-2026-0417')?.id).toBe('governance');
  });

  it('前缀必须按路径段匹配，不做字符串包含（/wiki-x 不归知识）', () => {
    expect(findWorkspaceByPath('/wiki-x')).toBeUndefined();
    expect(findWorkspaceByPath('/settingsx')).toBeUndefined();
  });

  it('未登记路径返回 undefined，交给调用方兜底而不是错归', () => {
    expect(findWorkspaceByPath('/legacy-nowhere')).toBeUndefined();
  });
});
