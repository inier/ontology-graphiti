import { Routes, Route, Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { WorkspacePage } from '@/modules/workspace/pages/WorkspacePage';
import { AuditLog } from '@/modules/audit';
import PolicyPage from '@/modules/audit/pages/PolicyPage';
import { OntologyDesignerPage } from '@/modules/ontology';
import { OntologyGraphPage } from '@/modules/ontology';
import { BlueprintDesignerPage } from '@/modules/ontology/pages/BlueprintDesignerPage';
import { GoalKanban } from '@/modules/ontology/pages/GoalKanban';
import { IngestPanel, Simulator } from '@/modules/ingest';
import { StrategyDeduction, SimulationPage } from '@/modules/simulation';
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
import { KeepAliveOutlet } from '@/modules/shared/components/KeepAliveOutlet';
import {
  SemanticAdminIndex,
  UslConfigPage,
  QualityDashboardPage,
  ApprovalsPage,
  CandidatesPage,
  PipelineRunsPage,
  DashboardPage,
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
        <Route path="/ontology/graph" element={<ProtectedRoute><OntologyGraphPage /></ProtectedRoute>} />
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
        <Route path="/skills" element={<ProtectedRoute><SkillManagement /></ProtectedRoute>} />
        <Route path="/simulator" element={<ProtectedRoute><Simulator /></ProtectedRoute>} />
        <Route path="/simulation/deduction" element={<ProtectedRoute><StrategyDeduction /></ProtectedRoute>} />
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
        <Route path="/admin/agents" element={<ProtectedRoute><AgentManagement /></ProtectedRoute>} />
        <Route path="/iframe-viewer" element={<ProtectedRoute><IframeViewerPage /></ProtectedRoute>} />
        <Route path="/menu-config" element={<ProtectedRoute><MenuConfigPage /></ProtectedRoute>} />
        <Route path="/semantic-admin" element={<ProtectedRoute><SemanticAdminIndex /></ProtectedRoute>} />
        <Route path="/semantic-admin/usl" element={<ProtectedRoute><UslConfigPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/pipeline" element={<ProtectedRoute><PipelineRunsPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/pipeline-runs" element={<ProtectedRoute><PipelineRunsPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/candidates" element={<ProtectedRoute><CandidatesPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/quality" element={<ProtectedRoute><QualityDashboardPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
        <Route path="/semantic-admin/approvals" element={<ProtectedRoute><ApprovalsPage /></ProtectedRoute>} />
        <Route path="/guide" element={<ProtectedRoute><GuidePage /></ProtectedRoute>} />
        <Route path="/" element={<ProtectedRoute><GuidePage /></ProtectedRoute>} />
        <Route path="/admin" element={<Navigate to="/ontology/designer" replace />} />
      </Route>
    </Routes>
  );
}
