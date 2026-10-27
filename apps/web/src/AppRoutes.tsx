import { Routes, Route, Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { WorkspacePage } from '@/modules/workspace/pages/WorkspacePage';
import { AuditLog } from '@/modules/audit';
import PolicyPage from '@/modules/audit/pages/PolicyPage';
import { OntologyDesignerPage } from '@/modules/ontology';
import { OntologyGraphPage } from '@/modules/ontology';
import { BlueprintDesignerPage } from '@/modules/ontology/pages/BlueprintDesignerPage';
import { GoalKanban } from '@/modules/ontology/pages/GoalKanban';
import { IngestPanel } from '@/modules/ingest';
import { SimulationPage } from '@/modules/simulation';
import { VersionHistory } from '@/modules/version';
import { RoleManager } from '@/modules/roles';
import { UserManagement } from '@/modules/roles/pages/UserManagement';
import { SkillManagement } from '@/modules/system';
import { BusinessProcess, Rules, Indicators, Logic, ObjectManagement } from '@/modules/business';
import { KnowledgeBase, KnowledgePage } from '@/modules/knowledge';
import { MyAgents, AgentChat, AgentManagement, AgentPage } from '@/modules/agent';
import { LoginPage } from '@/modules/shared/pages/LoginPage';
import { I18nAdminPage } from '@/modules/i18n-admin';
import { QAPage, QueryPage, EvaluationPage } from '@/modules/qa';
import { GuidePage } from '@/modules/guide';
import { SettingsPage } from '@/modules/settings';
import { ChannelManagementPage } from '@/modules/channels';
import { IframeViewerPage } from '@/modules/iframe-viewer';
import { MenuConfigPage } from '@/modules/menu-config';
import { HeExtractionPage } from '@/modules/hyper-extract';
import { McpToolsPage } from '@/modules/mcp-tools';
import { ServiceCatalogPage } from '@/modules/ontology/pages/ServiceCatalogPage';
import { SemanticMapPage } from '@/modules/ontology/pages/SemanticMapPage';
import { AbutionGraphPage } from '@/modules/ontology/pages/AbutionGraphPage';
import { MemoryDashboardPage } from '@/modules/simulation/pages/MemoryDashboardPage';
import { PerceptionPage } from '@/modules/simulation/pages/PerceptionPage';
import {
  DecisionLedgerPage,
  DecisionQueuePage,
  DecisionDetailPage,
} from '@/modules/decision';
import { KeepAliveOutlet } from '@/modules/shared/components/KeepAliveOutlet';
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

function ProtectedRoute({ children }: { children: ReactNode }) {
  const token = localStorage.getItem('token');
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* keep-alive 布局路由：所有受保护路由作为子路由，KeepAliveOutlet 缓存组件状态 */}
      <Route element={<KeepAliveOutlet />}>
        <Route path="/my-agents" element={<ProtectedRoute><MyAgents /></ProtectedRoute>} />
        <Route path="/agent-chat/:agentId" element={<ProtectedRoute><AgentChat /></ProtectedRoute>} />
        <Route path="/agent" element={<ProtectedRoute><AgentPage /></ProtectedRoute>} />

        <Route path="/ontology/designer" element={<ProtectedRoute><OntologyDesignerPage /></ProtectedRoute>} />
        {/* Iter 3 (D5): /ontology/graph → /ontology/explorer 改名消歧，旧路由 redirect 兼容 */}
        <Route path="/ontology/explorer" element={<ProtectedRoute><OntologyGraphPage /></ProtectedRoute>} />
        <Route path="/ontology/graph" element={<Navigate to="/ontology/explorer" replace />} />
        <Route path="/ontology" element={<Navigate to="/ontology/designer" replace />} />
        <Route path="/ontology/goals" element={<ProtectedRoute><GoalKanban /></ProtectedRoute>} />
        <Route path="/blueprint" element={<ProtectedRoute><BlueprintDesignerPage /></ProtectedRoute>} />
        <Route path="/versions" element={<ProtectedRoute><VersionHistory /></ProtectedRoute>} />
        <Route path="/business/process" element={<ProtectedRoute><BusinessProcess /></ProtectedRoute>} />
        <Route path="/business/rules" element={<ProtectedRoute><Rules /></ProtectedRoute>} />
        <Route path="/business/indicators" element={<ProtectedRoute><Indicators /></ProtectedRoute>} />
        <Route path="/business/logic" element={<ProtectedRoute><Logic /></ProtectedRoute>} />
        <Route path="/business/entities" element={<ProtectedRoute><ObjectManagement /></ProtectedRoute>} />
        <Route path="/business/extraction" element={<Navigate to="/ingest" replace />} />
        <Route path="/ingest" element={<ProtectedRoute><IngestPanel /></ProtectedRoute>} />
        {/* Iter 3 (D6): HE 抽取链 — 建本体下的知识抽取入口 */}
        <Route path="/he/extraction" element={<ProtectedRoute><HeExtractionPage /></ProtectedRoute>} />
        {/* Iter 3 (D7): MCP 工具集 — 用本体下的语义检索 MCP 工具入口 */}
        <Route path="/mcp/tools" element={<ProtectedRoute><McpToolsPage /></ProtectedRoute>} />
        {/* Iter 4: P3 缺失前端页面补齐 — 5 个新路由 */}
        <Route path="/ontology/service-catalog" element={<ProtectedRoute><ServiceCatalogPage /></ProtectedRoute>} />
        <Route path="/ontology/semantic-map" element={<ProtectedRoute><SemanticMapPage /></ProtectedRoute>} />
        <Route path="/ontology/abution-graph" element={<ProtectedRoute><AbutionGraphPage /></ProtectedRoute>} />
        <Route path="/simulation/memory" element={<ProtectedRoute><MemoryDashboardPage /></ProtectedRoute>} />
        <Route path="/simulation/perception" element={<ProtectedRoute><PerceptionPage /></ProtectedRoute>} />
        <Route path="/skills" element={<ProtectedRoute><SkillManagement /></ProtectedRoute>} />
        {/* Iter 2 (D4): 仿真入口合并 — /simulator + /simulation/deduction redirect 到 /simulation?tab=xxx */}
        <Route path="/simulator" element={<Navigate to="/simulation?tab=simulator" replace />} />
        <Route path="/simulation/deduction" element={<Navigate to="/simulation?tab=deduction" replace />} />
        <Route path="/simulation" element={<ProtectedRoute><SimulationPage /></ProtectedRoute>} />
        <Route path="/knowledge" element={<ProtectedRoute><KnowledgeBase /></ProtectedRoute>} />
        <Route path="/knowledge/navigation" element={<ProtectedRoute><KnowledgePage /></ProtectedRoute>} />
        <Route path="/qa" element={<ProtectedRoute><QAPage /></ProtectedRoute>} />
        <Route path="/qa/query" element={<ProtectedRoute><QueryPage /></ProtectedRoute>} />
        <Route path="/qa/evaluation" element={<ProtectedRoute><EvaluationPage /></ProtectedRoute>} />
        <Route path="/workspace/manage" element={<ProtectedRoute><WorkspacePage /></ProtectedRoute>} />
        <Route path="/workspace" element={<Navigate to="/workspace/manage" replace />} />
        <Route path="/i18n-admin" element={<ProtectedRoute><I18nAdminPage /></ProtectedRoute>} />
        <Route path="/roles" element={<ProtectedRoute><RoleManager /></ProtectedRoute>} />
        <Route path="/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
        <Route path="/policy-editor" element={<ProtectedRoute><PolicyPage /></ProtectedRoute>} />
        <Route path="/policies" element={<Navigate to="/policy-editor" replace />} />
        <Route path="/settings" element={<ProtectedRoute><SettingsPage /></ProtectedRoute>} />
        <Route path="/settings/channels/default" element={<ProtectedRoute><ChannelManagementPage /></ProtectedRoute>} />
        <Route path="/settings/channels/:workspaceId" element={<ProtectedRoute><ChannelManagementPage /></ProtectedRoute>} />
        <Route path="/audit" element={<ProtectedRoute><AuditLog /></ProtectedRoute>} />
        {/* 决策主线（ADR-091）：一级菜单仍只有「决策智能」一项，视图切换在路由内 */}
        <Route path="/decisions" element={<Navigate to="/decisions/ledger" replace />} />
        <Route path="/decisions/ledger" element={<ProtectedRoute><DecisionLedgerPage /></ProtectedRoute>} />
        <Route path="/decisions/queue" element={<ProtectedRoute><DecisionQueuePage /></ProtectedRoute>} />
        <Route path="/decisions/detail/:decisionId" element={<ProtectedRoute><DecisionDetailPage /></ProtectedRoute>} />
        <Route path="/admin/agents" element={<ProtectedRoute><AgentManagement /></ProtectedRoute>} />
        <Route path="/iframe-viewer" element={<ProtectedRoute><IframeViewerPage /></ProtectedRoute>} />
        <Route path="/menu-config" element={<ProtectedRoute><MenuConfigPage /></ProtectedRoute>} />
        <Route path="/semantic-admin" element={<ProtectedRoute><SemanticAdminIndex /></ProtectedRoute>} />
        <Route path="/semantic-admin/assets" element={<ProtectedRoute><SemanticAssetPipelinePage /></ProtectedRoute>} />
        <Route path="/semantic-admin/usl" element={<ProtectedRoute><UslConfigPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/usl-ontologies" element={<ProtectedRoute><UslOntologyPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/pipeline" element={<ProtectedRoute><PipelineRunsPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/pipeline-runs" element={<ProtectedRoute><PipelineRunsPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/candidates" element={<ProtectedRoute><CandidatesPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/quality" element={<ProtectedRoute><QualityDashboardPage /></ProtectedRoute>} />
        {/* Iter7 C3: 总览仪表盘与质量仪表盘调用同一组后端 API，合并到 quality，旧路由 redirect 兼容书签 */}
        <Route path="/semantic-admin/dashboard" element={<Navigate to="/semantic-admin/quality" replace />} />
        <Route path="/semantic-admin/approvals" element={<ProtectedRoute><ApprovalsPage /></ProtectedRoute>} />
        {/* 概念缺口回路：缺口池 / 缺口统计 / 缺口详情 */}
        <Route path="/semantic-admin/gaps" element={<ProtectedRoute><GapPoolPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/gaps/stats" element={<ProtectedRoute><GapStatsPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/gaps/:id" element={<ProtectedRoute><GapDetailPage /></ProtectedRoute>} />
        {/* 子项目 D：tool 层缺口路由工单（子路由，非顶层 Tab） */}
        <Route path="/semantic-admin/routing-tickets" element={<ProtectedRoute><RoutingTicketsPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/routing-tickets/:id" element={<ProtectedRoute><RoutingTicketDetailPage /></ProtectedRoute>} />
        <Route path="/guide" element={<ProtectedRoute><GuidePage /></ProtectedRoute>} />
        <Route path="/" element={<ProtectedRoute><GuidePage /></ProtectedRoute>} />
        <Route path="/admin" element={<Navigate to="/ontology/designer" replace />} />
      </Route>
    </Routes>
  );
}
