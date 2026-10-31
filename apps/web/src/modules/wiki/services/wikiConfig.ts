/**
 * Wiki 服务层（SPEC §5 端点，前缀 /api/v1）
 *
 * 与 legacy `shared/services/api.ts`（2329 行）刻意隔离：Wiki 是新模块，
 * 不往巨型文件里塞端点。
 *
 * mock 开关：WIKI_API_MOCK=true 时走 services/wikiMock.ts（页面必须显示"演示数据"横幅）。
 */

/** 后端 F1 端点本轮未就绪 → 默认开启 mock；接入真实后端时设为 false 或置 VITE_WIKI_MOCK=off */
export const WIKI_API_MOCK: boolean = (() => {
  const env = typeof import.meta !== 'undefined' ? import.meta.env : undefined;
  if (env?.VITE_WIKI_MOCK === 'off') return false;
  if (env?.VITE_WIKI_MOCK === 'on') return true;
  return true;
})();

export const API_BASE = '/api/v1';

export const WIKI_ENDPOINTS = {
  list: '/wiki/entries',
  detail: (entryId: string) => `/wiki/entries/${encodeURIComponent(entryId)}`,
  versions: (entryId: string) => `/wiki/entries/${encodeURIComponent(entryId)}/versions`,
  references: (entryId: string) => `/wiki/entries/${encodeURIComponent(entryId)}/references`,
  dedupe: '/docs/governance/dedupe',
} as const;
