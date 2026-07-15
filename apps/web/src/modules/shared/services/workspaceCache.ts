/**
 * workspaceCache — 模块级缓存
 *
 * 工作空间/场景数据在模块变量中保留引用，
 * Layout 切换（卸载/重挂）时不丢失，避免重复请求。
 *
 * 使用方式：
 *   1. Layout 挂载时：先 getWorkspacesCache()，有数据则直接用
 *   2. API 加载成功后：setWorkspacesCache(data) 填入缓存
 *   3. 切换工作空间时：clearScenariosCache()
 */
import type { Workspace, Scenario } from '@/modules/shared/components/LayoutContexts';

let workspacesCache: Workspace[] = [];
let scenariosCache: Scenario[] = [];
let scenariosCacheWorkspaceId: string = '';
let currentWorkspaceId = localStorage.getItem('currentWorkspaceId') || '';
let currentScenarioId = localStorage.getItem('currentScenarioId') || '';

/* ── 工作空间缓存 ── */

export function getWorkspacesCache(): Workspace[] {
  return workspacesCache;
}

export function setWorkspacesCache(data: Workspace[]) {
  workspacesCache = data;
}

export function hasWorkspacesCache(): boolean {
  return workspacesCache.length > 0;
}

/* ── 场景缓存（按 workspaceId 区分） ── */

export function getScenariosCache(workspaceId: string): Scenario[] | null {
  if (scenariosCache.length > 0 && scenariosCacheWorkspaceId === workspaceId) {
    return scenariosCache;
  }
  return null;
}

export function setScenariosCache(workspaceId: string, data: Scenario[]) {
  scenariosCache = data;
  scenariosCacheWorkspaceId = workspaceId;
}

export function clearScenariosCache() {
  scenariosCache = [];
  scenariosCacheWorkspaceId = '';
}

/* ── 当前选中 ID ── */

export function getCachedWorkspaceId(): string {
  return currentWorkspaceId;
}

export function getCachedScenarioId(): string {
  return currentScenarioId;
}

export function setCachedWorkspaceId(id: string) {
  currentWorkspaceId = id;
  localStorage.setItem('currentWorkspaceId', id);
}

export function setCachedScenarioId(id: string) {
  currentScenarioId = id;
  localStorage.setItem('currentScenarioId', id);
}
