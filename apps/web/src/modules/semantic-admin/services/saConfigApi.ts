/**
 * Semantic Admin 动态配置 API 客户端
 * 后端契约对齐 docs/03-modules/semantic_admin/DESIGN.md §Sa-Config 动态配置
 *
 * 支持的 API 路径（严格对齐 AGENTS.md §F 快速命令 API 速查）：
 *   GET  /config
 *   GET  /config/{scope}/{key}
 *   GET  /config/domain/{domain_code}
 *   PUT  /config/{scope}/{key}
 *   POST /ensure-builtin
 */

import { fetchJson } from '@/modules/shared/services/apiClient';
import { API_BASE } from '@/config';

const URL_PREFIX = `${API_BASE}/api/semantic-admin/config`;

export interface SaConfigEntry {
  scope: 'global' | 'domain' | 'workspace' | 'pipeline' | 'quality_gate';
  key: string;
  value: string | number | boolean | null | Record<string, unknown> | unknown[];
  updated_at?: string;
  updated_by?: string;
  builtin?: boolean;
  description?: string;
  source?: string;
}

export type SaConfigScope = SaConfigEntry['scope'];

/** 列出全局所有生效配置（含 builtin + override） */
export async function listConfig(params?: {
  scope?: SaConfigScope;
  prefix?: string;
}): Promise<{ items: SaConfigEntry[]; total: number }> {
  const q = new URLSearchParams();
  if (params?.scope) q.set('scope', params.scope);
  if (params?.prefix) q.set('prefix', params.prefix);
  const qs = q.toString();
  return fetchJson<{ items: SaConfigEntry[]; total: number }>(
    `${URL_PREFIX}${qs ? `?${qs}` : ''}`,
  );
}

/** 读取单个配置 (scope + key) */
export async function getConfig(
  scope: SaConfigScope,
  key: string,
): Promise<SaConfigEntry> {
  return fetchJson<SaConfigEntry>(
    `${URL_PREFIX}/${encodeURIComponent(scope)}/${encodeURIComponent(key)}`,
  );
}

/** 读取单个域（domain_code）下的所有配置 — 等价按 scope=domain + prefix=domain_code 聚合 */
export async function getDomainConfig(domainCode: string): Promise<{
  code: string;
  items: SaConfigEntry[];
}> {
  return fetchJson<{ code: string; items: SaConfigEntry[] }>(
    `${URL_PREFIX}/domain/${encodeURIComponent(domainCode)}`,
  );
}

/** 更新单个配置项 — 非 builtin 允许覆盖；builtin 会抛 403 */
export async function setConfig(
  scope: SaConfigScope,
  key: string,
  value: SaConfigEntry['value'],
  updatedBy?: string,
): Promise<SaConfigEntry> {
  return fetchJson<SaConfigEntry>(
    `${URL_PREFIX}/${encodeURIComponent(scope)}/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value, updated_by: updatedBy }),
    },
  );
}

/** 确保 builtin 配置（后端 SaConfig 初始化入口）— dev 首次启动可调用；幂等 */
export async function ensureBuiltinConfig(forceReset = false): Promise<{
  inserted: number;
  skipped: number;
  total: number;
}> {
  return fetchJson<{ inserted: number; skipped: number; total: number }>(
    `${URL_PREFIX}/ensure-builtin${forceReset ? '?force=1' : ''}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    },
  );
}
