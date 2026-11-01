/**
 * 路由清单（纯数据，零组件依赖）
 *
 * 刻意与 `routeDefs.tsx`（含 React 元素）分离：
 *   - 本文件只描述「有哪些路径、属于哪个工作区、指向哪个元素键」
 *   - 因此路由一致性测试可以直接遍历它，无需把整棵页面树加载进测试环境
 *   - 元素键与 `routeDefs.tsx` 的 `PAGE_ELEMENTS` 之间由
 *     `Record<PageElementKey, ReactNode>` 在编译期强制一一对应（漏一个即 tsc 报错）
 *
 * 一致性断言见 `src/routes/__tests__/routeManifest.test.tsx`（AC-20 无死链）。
 */
import type { WorkspaceId } from '@/modules/shared/navigation/workspaces';
import { LEGACY_REDIRECTS } from '@/modules/shared/navigation/legacyRedirects';

/** 页面元素键：与 routeDefs.tsx 中的 PAGE_ELEMENTS 键一一对应 */
export type PageElementKey =
  | 'guide'
  | 'workspaceManage'
  | 'myAgents'
  | 'agent'
  | 'agentChat'
  | 'ontologyDesigner'
  | 'ontologyExplorer'
  | 'ontologyRelations'
  | 'ontologyHealth'
  | 'objectViews'
  | 'goalKanban'
  | 'serviceCatalog'
  | 'semanticMap'
  | 'abutionGraph'
  | 'blueprintDesigner'
  | 'versionHistory'
  | 'businessProcess'
  | 'businessRules'
  | 'businessIndicators'
  | 'businessLogic'
  | 'objectManagement'
  | 'wikiList'
  | 'wikiDedupe'
  | 'wikiEntry'
  | 'knowledgeBase'
  | 'ingest'
  | 'heExtraction'
  | 'mcpTools'
  | 'qa'
  | 'qaQuery'
  | 'qaEvaluation'
  | 'qaCognition'
  | 'qaCopilot'
  | 'qaMemory'
  | 'decisionsLedger'
  | 'decisionsQueue'
  | 'decisionsDetail'
  | 'decisionActions'
  | 'simulation'
  | 'simulationMemory'
  | 'simulationPerception'
  | 'simulationSandbox'
  | 'semanticAdminIndex'
  | 'semanticAssetPipeline'
  | 'uslConfig'
  | 'uslOntology'
  | 'pipelineRuns'
  | 'candidates'
  | 'qualityDashboard'
  | 'approvals'
  | 'gapPool'
  | 'gapStats'
  | 'gapDetail'
  | 'routingTickets'
  | 'routingTicketDetail'
  | 'settings'
  | 'channelDefault'
  | 'channelWorkspace'
  | 'roles'
  | 'users'
  | 'policyEditor'
  | 'opaMonitor'
  | 'audit'
  | 'menuConfig'
  | 'i18nAdmin'
  | 'skills'
  | 'agentManagement'
  | 'iframeViewer'
  | 'minioAdmin';

export interface PageEntry {
  readonly path: string;
  readonly workspace: WorkspaceId;
  readonly element: PageElementKey;
}

export interface RedirectEntry {
  readonly path: string;
  readonly to: string;
  readonly reason: string;
}

/** 受保护页面路由（不含 /login） */
export const PAGE_MANIFEST: readonly PageEntry[] = [
  // 工作台
  { path: '/', workspace: 'workspace', element: 'guide' },
  { path: '/guide', workspace: 'workspace', element: 'guide' },
  { path: '/workspace/manage', workspace: 'workspace', element: 'workspaceManage' },
  { path: '/my-agents', workspace: 'workspace', element: 'myAgents' },
  { path: '/agent', workspace: 'workspace', element: 'agent' },
  { path: '/agent-chat/:agentId', workspace: 'workspace', element: 'agentChat' },

  // 本体
  { path: '/ontology/designer', workspace: 'ontology', element: 'ontologyDesigner' },
  { path: '/ontology/explorer', workspace: 'ontology', element: 'ontologyExplorer' },
  // 质量健康度：规则/扫描/报告。此前后端 router 已写好但从未注册，前端页面无入口
  { path: '/ontology/health', workspace: 'ontology', element: 'ontologyHealth' },
  // 继承图 / Mixin / 计算属性 / 物化任务 的统一入口（此前四者无任何路由可达）
  { path: '/ontology/relations', workspace: 'ontology', element: 'ontologyRelations' },
  // 对象视图：列表/查询/导出 + 视图设计器（此前 ObjectViewPage 与 ViewDesigner 均无入口）
  { path: '/ontology/views', workspace: 'ontology', element: 'objectViews' },
  { path: '/ontology/goals', workspace: 'ontology', element: 'goalKanban' },
  { path: '/ontology/service-catalog', workspace: 'ontology', element: 'serviceCatalog' },
  { path: '/ontology/semantic-map', workspace: 'ontology', element: 'semanticMap' },
  { path: '/ontology/abution-graph', workspace: 'ontology', element: 'abutionGraph' },
  { path: '/blueprint', workspace: 'ontology', element: 'blueprintDesigner' },
  { path: '/versions', workspace: 'ontology', element: 'versionHistory' },
  { path: '/business/process', workspace: 'ontology', element: 'businessProcess' },
  { path: '/business/rules', workspace: 'ontology', element: 'businessRules' },
  { path: '/business/indicators', workspace: 'ontology', element: 'businessIndicators' },
  { path: '/business/logic', workspace: 'ontology', element: 'businessLogic' },
  { path: '/business/entities', workspace: 'ontology', element: 'objectManagement' },

  // 知识（Wiki + 知识库 + 摄入）
  { path: '/wiki', workspace: 'knowledge', element: 'wikiList' },
  { path: '/wiki/dedupe', workspace: 'knowledge', element: 'wikiDedupe' },
  { path: '/wiki/:entryId', workspace: 'knowledge', element: 'wikiEntry' },
  { path: '/knowledge', workspace: 'knowledge', element: 'knowledgeBase' },
  { path: '/ingest', workspace: 'knowledge', element: 'ingest' },
  { path: '/he/extraction', workspace: 'knowledge', element: 'heExtraction' },
  { path: '/mcp/tools', workspace: 'knowledge', element: 'mcpTools' },

  // 问答与决策
  { path: '/qa', workspace: 'ask', element: 'qa' },
  { path: '/qa/query', workspace: 'ask', element: 'qaQuery' },
  { path: '/qa/evaluation', workspace: 'ask', element: 'qaEvaluation' },
  // 认知引擎：意图识别 / 解释链 / 角色视图（/api/cognition）
  { path: '/qa/cognition', workspace: 'ask', element: 'qaCognition' },
  // 会话记忆：短期上下文 / 工作记忆 / 长期记忆（/api/session-memory）
  { path: '/qa/memory', workspace: 'ask', element: 'qaMemory' },
  // AG-UI 协议对话（POST /api/ag-ui/run + SSE）：与常规问答并列的 Copilot 形态
  { path: '/qa/copilot', workspace: 'ask', element: 'qaCopilot' },
  // 决策主线（ADR-101）：一级菜单仍只有「决策智能」一项，视图切换在路由内
  { path: '/decisions/ledger', workspace: 'ask', element: 'decisionsLedger' },
  { path: '/decisions/queue', workspace: 'ask', element: 'decisionsQueue' },
  { path: '/decisions/detail/:decisionId', workspace: 'ask', element: 'decisionsDetail' },
  { path: '/decisions/actions', workspace: 'ask', element: 'decisionActions' },
  { path: '/simulation', workspace: 'ask', element: 'simulation' },
  { path: '/simulation/memory', workspace: 'ask', element: 'simulationMemory' },
  { path: '/simulation/perception', workspace: 'ask', element: 'simulationPerception' },
  // 沙箱推演：/api/simulation/sandbox/* + /api/simulation/what-if + /api/feedback/*
  { path: '/simulation/sandbox', workspace: 'ask', element: 'simulationSandbox' },

  // 语义治理
  { path: '/semantic-admin', workspace: 'governance', element: 'semanticAdminIndex' },
  { path: '/semantic-admin/assets', workspace: 'governance', element: 'semanticAssetPipeline' },
  { path: '/semantic-admin/usl', workspace: 'governance', element: 'uslConfig' },
  { path: '/semantic-admin/usl-ontologies', workspace: 'governance', element: 'uslOntology' },
  { path: '/semantic-admin/pipeline-runs', workspace: 'governance', element: 'pipelineRuns' },
  { path: '/semantic-admin/candidates', workspace: 'governance', element: 'candidates' },
  { path: '/semantic-admin/quality', workspace: 'governance', element: 'qualityDashboard' },
  { path: '/semantic-admin/approvals', workspace: 'governance', element: 'approvals' },
  { path: '/semantic-admin/gaps', workspace: 'governance', element: 'gapPool' },
  { path: '/semantic-admin/gaps/stats', workspace: 'governance', element: 'gapStats' },
  { path: '/semantic-admin/gaps/:id', workspace: 'governance', element: 'gapDetail' },
  { path: '/semantic-admin/routing-tickets', workspace: 'governance', element: 'routingTickets' },
  { path: '/semantic-admin/routing-tickets/:id', workspace: 'governance', element: 'routingTicketDetail' },

  // 平台管理
  { path: '/settings', workspace: 'platform', element: 'settings' },
  { path: '/settings/channels/default', workspace: 'platform', element: 'channelDefault' },
  { path: '/settings/channels/:workspaceId', workspace: 'platform', element: 'channelWorkspace' },
  // 对象存储管理：/api/minio-admin/*（状态 / 桶 / 对象 / 预签名 / 统计）
  { path: '/settings/storage', workspace: 'platform', element: 'minioAdmin' },
  { path: '/roles', workspace: 'platform', element: 'roles' },
  { path: '/users', workspace: 'platform', element: 'users' },
  { path: '/policy-editor', workspace: 'platform', element: 'policyEditor' },
  // 策略运行时监控：消费 /api/opa/metrics + /api/opa/health（此前页面零引用）
  { path: '/opa-monitor', workspace: 'platform', element: 'opaMonitor' },
  { path: '/audit', workspace: 'platform', element: 'audit' },
  { path: '/menu-config', workspace: 'platform', element: 'menuConfig' },
  { path: '/i18n-admin', workspace: 'platform', element: 'i18nAdmin' },
  { path: '/skills', workspace: 'platform', element: 'skills' },
  { path: '/admin/agents', workspace: 'platform', element: 'agentManagement' },
  { path: '/iframe-viewer', workspace: 'platform', element: 'iframeViewer' },
];

/** 旧路由重定向（来自 navigation/legacyRedirects.ts，此处仅做形态转换） */
export const REDIRECT_MANIFEST: readonly RedirectEntry[] = LEGACY_REDIRECTS.map((r) => ({
  path: r.from,
  to: r.to,
  reason: r.reason,
}));

export const PAGE_PATH_LIST: readonly string[] = PAGE_MANIFEST.map((p) => p.path);

/** 去掉 query/hash，只留路径段（校验重定向目标存在性用） */
export function pathnameOf(to: string): string {
  return to.split('?')[0].split('#')[0];
}

/** 把 `:param` 形式动态段统一成 `*`，用于判断两条路由是否等价 */
export function normalizePattern(pattern: string): string {
  return pattern
    .split('/')
    .map((seg) => (seg.startsWith(':') ? '*' : seg))
    .join('/');
}

/** 把 `:param` 动态路由转成可比较的正则 */
export function matchesPath(pattern: string, candidate: string): boolean {
  const regex = new RegExp(
    `^${pattern
      .split('/')
      .map((seg) => (seg.startsWith(':') ? '[^/]+' : seg.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
      .join('/')}$`,
  );
  return regex.test(candidate);
}

export function hasPageRoute(target: string, patterns: readonly string[] = PAGE_PATH_LIST): boolean {
  const path = pathnameOf(target);
  return patterns.some((pattern) => pattern === path || matchesPath(pattern, path));
}
