/**
 * 路由一致性测试（AC-20 无死链 / AC-23 旧路由不 404）
 *
 * 只依赖纯数据清单 `routeManifest.ts`，因此不需要把整棵页面树加载进测试环境。
 * 断言四件事：
 *   1. 页面路径唯一（含 `:param` 归一后也不等价）
 *   2. 重定向路径不与页面路径冲突，且目标可达
 *   3. 6 个工作区的 home / 二级项的路径都真实存在
 *   4. 每条页面路由声明的工作区与「最长前缀归属」结果一致（导航不会高亮错工作区）
 */
import { describe, expect, it } from 'vitest';
import {
  PAGE_MANIFEST,
  PAGE_PATH_LIST,
  REDIRECT_MANIFEST,
  hasPageRoute,
  matchesPath,
  normalizePattern,
  pathnameOf,
} from '../routeManifest';
import { WORKSPACES, findWorkspaceByPath } from '@/modules/shared/navigation/workspaces';
import { LEGACY_REDIRECTS } from '@/modules/shared/navigation/legacyRedirects';

describe('路由清单', () => {
  it('页面路径无重复（AC-20）', () => {
    expect(new Set(PAGE_PATH_LIST).size).toBe(PAGE_PATH_LIST.length);
  });

  it('归一化后仍无等价路由（/a/:x 与 /a/:y 视为重复）', () => {
    const normalized = PAGE_PATH_LIST.map(normalizePattern);
    const dup = normalized.filter((p, i) => normalized.indexOf(p) !== i);
    expect(dup, `存在等价路由：${dup.join(', ')}`).toEqual([]);
  });

  it('重定向路径不与页面路径冲突（同路径不能既渲染又跳转）', () => {
    const collisions = REDIRECT_MANIFEST.map((r) => r.path).filter((p) => PAGE_PATH_LIST.includes(p));
    expect(collisions, `路径冲突：${collisions.join(', ')}`).toEqual([]);
  });

  it('每条重定向的目标都真实可达（含带 query 的目标）', () => {
    const dead = REDIRECT_MANIFEST.filter((r) => !hasPageRoute(r.to)).map((r) => `${r.path} -> ${r.to}`);
    expect(dead, `死链：${dead.join('; ')}`).toEqual([]);
  });

  it('重定向不做环（目标不会再被重定向回自己）', () => {
    const redirectPaths = new Set(REDIRECT_MANIFEST.map((r) => r.path));
    const cycles = REDIRECT_MANIFEST.filter((r) => redirectPaths.has(pathnameOf(r.to)));
    expect(cycles.map((r) => `${r.path} -> ${r.to}`)).toEqual([]);
  });

  it('F5 专项：/semantic-admin/pipeline 收敛到 pipeline-runs', () => {
    const entry = REDIRECT_MANIFEST.find((r) => r.path === '/semantic-admin/pipeline');
    expect(entry?.to).toBe('/semantic-admin/pipeline-runs');
    expect(PAGE_PATH_LIST).toContain('/semantic-admin/pipeline-runs');
  });

  it('重定向表与 legacyRedirects 单一真源一致', () => {
    expect(REDIRECT_MANIFEST.map((r) => r.path)).toEqual(LEGACY_REDIRECTS.map((r) => r.from));
    for (const r of REDIRECT_MANIFEST) expect(r.reason.length).toBeGreaterThan(0);
  });
});

describe('导航与路由的一致性', () => {
  it('6 个工作区的 home 都有对应页面（AC-19）', () => {
    for (const ws of WORKSPACES) {
      expect(hasPageRoute(ws.home), `${ws.id} 的 home ${ws.home} 无路由`).toBe(true);
    }
  });

  it('所有二级导航项都有对应页面（无死链）', () => {
    const dead = WORKSPACES.flatMap((ws) =>
      ws.items.filter((item) => !hasPageRoute(item.path)).map((item) => `${ws.id}: ${item.path}`),
    );
    expect(dead, `死链：${dead.join('; ')}`).toEqual([]);
  });

  it('每条页面路由声明的工作区 = 最长前缀归属结果（导航高亮不会错位）', () => {
    const mismatched = PAGE_MANIFEST.filter((entry) => findWorkspaceByPath(entry.path)?.id !== entry.workspace).map(
      (entry) => `${entry.path}: 声明 ${entry.workspace} / 实际 ${findWorkspaceByPath(entry.path)?.id ?? '未归属'}`,
    );
    expect(mismatched, `工作区归属不一致：${mismatched.join('; ')}`).toEqual([]);
  });

  it('每个静态页面都能从某个工作区菜单进入（无孤儿页面）', () => {
    const menuPaths = new Set(WORKSPACES.flatMap((ws) => ws.items.map((item) => item.path)));
    // 决策主线（ADR-101）：一级菜单仍只有「决策情报」一项，/decisions/queue 由台账页内切换进入
    const INTRA_PAGE_VIEWS = new Set<string>(['/decisions/queue']);
    // 详情页（含 :param）由列表页进入，不要求出现在菜单里
    const orphans = PAGE_MANIFEST.filter(
      (entry) =>
        !entry.path.includes(':') && !menuPaths.has(entry.path) && !INTRA_PAGE_VIEWS.has(entry.path),
    ).map((entry) => entry.path);
    expect(orphans, `以下页面无任何菜单入口：${orphans.join(', ')}`).toEqual([]);
  });
});

describe('路径匹配工具', () => {
  it('pathnameOf 去掉 query 与 hash', () => {
    expect(pathnameOf('/simulation?tab=simulator')).toBe('/simulation');
    expect(pathnameOf('/wiki/abc#versions')).toBe('/wiki/abc');
    expect(pathnameOf('/wiki')).toBe('/wiki');
  });

  it('matchesPath 支持单段动态参数，且不跨段匹配', () => {
    expect(matchesPath('/wiki/:entryId', '/wiki/01J9Z6Q2X8K3M4N5P6R7S8T9V1')).toBe(true);
    expect(matchesPath('/wiki/:entryId', '/wiki/abc/versions')).toBe(false);
    expect(matchesPath('/wiki', '/wiki/abc')).toBe(false);
  });

  it('hasPageRoute 兼容静态路由与动态路由', () => {
    expect(hasPageRoute('/semantic-admin/gaps/stats')).toBe(true);
    expect(hasPageRoute('/semantic-admin/gaps/01J9Z6Q2X8K3M4N5P6R7S8T9V1')).toBe(true);
    expect(hasPageRoute('/policies')).toBe(false);
  });
});
