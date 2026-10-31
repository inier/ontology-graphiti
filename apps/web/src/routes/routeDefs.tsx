/**
 * 路由表（装配层）
 *
 * 分工：
 *   - routeManifest.ts —— 纯数据（路径/工作区/元素键/重定向），可被测试直接遍历
 *   - 本文件 —— 把「元素键」解析成真实 React 元素，并在编译期保证键集合完备
 *
 * `PAGE_ELEMENTS` 的类型是 `Record<PageElementKey, ReactNode>`：
 * 清单里新增一条路由但忘了接元素 → tsc 直接报错，不会出现"死链到空白页"。
 */
import type { ReactNode } from 'react';
import { WorkspacePage } from '@/modules/workspace/pages/WorkspacePage';
import { AuditLog } from '@/modules/audit';
import PolicyPage from '@/modules/audit/pages/PolicyPage';
import { OPAMonitorPage } from '@/modules/audit/pages/OPAMonitorPage';
import { OntologyDesignerPage, OntologyGraphPage, ActionPanel } from '@/modules/ontology';
import { BlueprintDesignerPage } from '@/modules/ontology/pages/BlueprintDesignerPage';
import { OntologyRelationsPage } from '@/modules/ontology/pages/OntologyRelationsPage';
import { HealthDashboardPage } from '@/modules/ontology/pages/HealthDashboard';
import { ObjectViewsPage } from '@/modules/ontology/pages/ObjectViewsPage';
import { GoalKanban } from '@/modules/ontology/pages/GoalKanban';
import { IngestPanel } from '@/modules/ingest';
import { SimulationPage } from '@/modules/simulation';
import { VersionHistory } from '@/modules/version';
import { RoleManager } from '@/modules/roles';
import { UserManagement } from '@/modules/roles/pages/UserManagement';
import { SkillManagement } from '@/modules/system';
import { BusinessProcess, Rules, Indicators, Logic, ObjectManagement } from '@/modules/business';
import { KnowledgeBase } from '@/modules/knowledge';
import { MyAgents, AgentChat, AgentManagement, AgentPage } from '@/modules/agent';
import { I18nAdminPage } from '@/modules/i18n-admin';
import { QAPage, QueryPage, EvaluationPage } from '@/modules/qa';
import { CognitionPage } from '@/modules/agent/pages/CognitionPage';
import { SessionMemoryPage } from '@/modules/agent/pages/SessionMemoryPage';
import { QACopilotDemoPage } from '@/modules/qa/agui/QACopilotDemoPage';
import { GuidePage } from '@/modules/guide';
import { SettingsPage } from '@/modules/settings';
import { ChannelManagementPage } from '@/modules/channels';
import { IframeViewerPage } from '@/modules/iframe-viewer';
import { MinioAdminPage } from '@/modules/minio-admin';
import { MenuConfigPage } from '@/modules/menu-config';
import { HeExtractionPage } from '@/modules/hyper-extract';
import { McpToolsPage } from '@/modules/mcp-tools';
import { ServiceCatalogPage } from '@/modules/ontology/pages/ServiceCatalogPage';
import { SemanticMapPage } from '@/modules/ontology/pages/SemanticMapPage';
import { AbutionGraphPage } from '@/modules/ontology/pages/AbutionGraphPage';
import { MemoryDashboardPage } from '@/modules/simulation/pages/MemoryDashboardPage';
import { PerceptionPage } from '@/modules/simulation/pages/PerceptionPage';
import { SandboxLabPage } from '@/modules/simulation/pages/SandboxLabPage';
import { DecisionLedgerPage, DecisionQueuePage, DecisionDetailPage } from '@/modules/decision';
import { WikiListPage, WikiEntryPage, WikiDedupePage } from '@/modules/wiki';
import {
  SemanticAdminIndex,
  UslConfigPage,
  QualityDashboardPage,
  ApprovalsPage,
  CandidatesPage,
  PipelineRunsPage,
  SemanticAssetPipelinePage,
  UslOntologyPage,
  GapPoolPage,
  GapDetailPage,
  GapStatsPage,
  RoutingTicketsPage,
  RoutingTicketDetailPage,
} from '@/modules/semantic-admin';
import {
  PAGE_MANIFEST,
  REDIRECT_MANIFEST,
  hasPageRoute,
  matchesPath,
  normalizePattern,
  pathnameOf,
  type PageElementKey,
} from './routeManifest';

const PAGE_ELEMENTS: Record<PageElementKey, ReactNode> = {
  guide: <GuidePage />,
  workspaceManage: <WorkspacePage />,
  myAgents: <MyAgents />,
  agent: <AgentPage />,
  agentChat: <AgentChat />,
  ontologyDesigner: <OntologyDesignerPage />,
  ontologyExplorer: <OntologyGraphPage />,
  ontologyRelations: <OntologyRelationsPage />,
  ontologyHealth: <HealthDashboardPage />,
  objectViews: <ObjectViewsPage />,
  goalKanban: <GoalKanban />,
  serviceCatalog: <ServiceCatalogPage />,
  semanticMap: <SemanticMapPage />,
  abutionGraph: <AbutionGraphPage />,
  blueprintDesigner: <BlueprintDesignerPage />,
  versionHistory: <VersionHistory />,
  businessProcess: <BusinessProcess />,
  businessRules: <Rules />,
  businessIndicators: <Indicators />,
  businessLogic: <Logic />,
  objectManagement: <ObjectManagement />,
  wikiList: <WikiListPage />,
  wikiDedupe: <WikiDedupePage />,
  wikiEntry: <WikiEntryPage />,
  knowledgeBase: <KnowledgeBase />,
  ingest: <IngestPanel />,
  heExtraction: <HeExtractionPage />,
  mcpTools: <McpToolsPage />,
  qa: <QAPage />,
  qaQuery: <QueryPage />,
  qaEvaluation: <EvaluationPage />,
  qaCognition: <CognitionPage />,
  qaMemory: <SessionMemoryPage />,
  qaCopilot: <QACopilotDemoPage />,
  decisionsLedger: <DecisionLedgerPage />,
  decisionsQueue: <DecisionQueuePage />,
  decisionsDetail: <DecisionDetailPage />,
  decisionActions: <ActionPanel />,
  simulation: <SimulationPage />,
  simulationMemory: <MemoryDashboardPage />,
  simulationPerception: <PerceptionPage />,
  simulationSandbox: <SandboxLabPage />,
  semanticAdminIndex: <SemanticAdminIndex />,
  semanticAssetPipeline: <SemanticAssetPipelinePage />,
  uslConfig: <UslConfigPage />,
  uslOntology: <UslOntologyPage />,
  pipelineRuns: <PipelineRunsPage />,
  candidates: <CandidatesPage />,
  qualityDashboard: <QualityDashboardPage />,
  approvals: <ApprovalsPage />,
  gapPool: <GapPoolPage />,
  gapStats: <GapStatsPage />,
  gapDetail: <GapDetailPage />,
  routingTickets: <RoutingTicketsPage />,
  routingTicketDetail: <RoutingTicketDetailPage />,
  settings: <SettingsPage />,
  channelDefault: <ChannelManagementPage />,
  channelWorkspace: <ChannelManagementPage />,
  roles: <RoleManager />,
  users: <UserManagement />,
  policyEditor: <PolicyPage />,
  opaMonitor: <OPAMonitorPage />,
  audit: <AuditLog />,
  menuConfig: <MenuConfigPage />,
  i18nAdmin: <I18nAdminPage />,
  skills: <SkillManagement />,
  agentManagement: <AgentManagement />,
  iframeViewer: <IframeViewerPage />,
  minioAdmin: <MinioAdminPage />,
};

export interface PageRouteDef {
  kind: 'page';
  path: string;
  /** 路由所属工作区（用于无死链校验与调试） */
  workspace: string;
  element: ReactNode;
}

export interface RedirectRouteDef {
  kind: 'redirect';
  path: string;
  /** 目标路径，可能含 query（如 /simulation?tab=simulator） */
  to: string;
  reason: string;
}

export type RouteDef = PageRouteDef | RedirectRouteDef;

export const PAGE_ROUTES: PageRouteDef[] = PAGE_MANIFEST.map((entry) => ({
  kind: 'page',
  path: entry.path,
  workspace: entry.workspace,
  element: PAGE_ELEMENTS[entry.element],
}));

export const REDIRECT_ROUTES: RedirectRouteDef[] = REDIRECT_MANIFEST.map((entry) => ({
  kind: 'redirect',
  path: entry.path,
  to: entry.to,
  reason: entry.reason,
}));

export const APP_ROUTE_DEFS: RouteDef[] = [...PAGE_ROUTES, ...REDIRECT_ROUTES];

export const PAGE_PATHS: readonly string[] = PAGE_ROUTES.map((r) => r.path);

export { hasPageRoute, matchesPath, normalizePattern, pathnameOf };
