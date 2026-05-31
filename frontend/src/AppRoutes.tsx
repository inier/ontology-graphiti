import { Routes, Route, Navigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { WorkspaceManager } from './modules/workspace';
import { WorkspacePage } from './modules/workspace/pages/WorkspacePage';
import { AuditLog } from './modules/audit';
import { PolicyManagement } from './modules/config';
import { OntologySemanticNetwork, OntologyDesignerPage } from './modules/ontology';
import { BlueprintDesignerPage } from './modules/ontology/pages/BlueprintDesignerPage';
import { IngestPanel, Simulator } from './modules/ingest';
import { StrategyDeduction } from './modules/simulation';
import { VersionHistory } from './modules/version';
import { RoleManager } from './modules/roles';
import { UserManagement } from './modules/roles/pages/UserManagement';
import { SkillManagement } from './modules/system';
import { BusinessProcess, Rules, Indicators, Logic, ObjectManagement, SmartGeneration } from './modules/business';
import { KnowledgeBase } from './modules/knowledge';
import { MyAgents, AgentChat, AgentManagement } from './modules/agent';
import { LoginPage } from './modules/shared/pages/LoginPage';
import { I18nAdminPage } from './modules/i18n-admin';

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

      <Route path="/my-agents" element={<ProtectedRoute><MyAgents /></ProtectedRoute>} />
      <Route path="/agent-chat/:agentId" element={<ProtectedRoute><AgentChat /></ProtectedRoute>} />

      <Route path="/ontology" element={<ProtectedRoute><OntologySemanticNetwork /></ProtectedRoute>} />
      <Route path="/ontology/designer" element={<ProtectedRoute><OntologyDesignerPage /></ProtectedRoute>} />
      <Route path="/blueprint" element={<ProtectedRoute><BlueprintDesignerPage /></ProtectedRoute>} />
      <Route path="/versions" element={<ProtectedRoute><VersionHistory /></ProtectedRoute>} />
      <Route path="/business/process" element={<ProtectedRoute><BusinessProcess /></ProtectedRoute>} />
      <Route path="/business/rules" element={<ProtectedRoute><Rules /></ProtectedRoute>} />
      <Route path="/business/indicators" element={<ProtectedRoute><Indicators /></ProtectedRoute>} />
      <Route path="/business/logic" element={<ProtectedRoute><Logic /></ProtectedRoute>} />
      <Route path="/business/entities" element={<ProtectedRoute><ObjectManagement /></ProtectedRoute>} />
      <Route path="/business/extraction" element={<ProtectedRoute><SmartGeneration /></ProtectedRoute>} />
      <Route path="/skills" element={<ProtectedRoute><SkillManagement /></ProtectedRoute>} />
      <Route path="/simulator" element={<ProtectedRoute><Simulator /></ProtectedRoute>} />
      <Route path="/simulation/deduction" element={<ProtectedRoute><StrategyDeduction /></ProtectedRoute>} />
      <Route path="/ingest" element={<ProtectedRoute><IngestPanel /></ProtectedRoute>} />
      <Route path="/knowledge" element={<ProtectedRoute><KnowledgeBase /></ProtectedRoute>} />
      <Route path="/workspace" element={<ProtectedRoute><WorkspaceManager /></ProtectedRoute>} />
      <Route path="/workspace/manage" element={<ProtectedRoute><WorkspacePage /></ProtectedRoute>} />
      <Route path="/i18n-admin" element={<ProtectedRoute><I18nAdminPage /></ProtectedRoute>} />
      <Route path="/roles" element={<ProtectedRoute><RoleManager /></ProtectedRoute>} />
      <Route path="/users" element={<ProtectedRoute><UserManagement /></ProtectedRoute>} />
      <Route path="/policies" element={<ProtectedRoute><PolicyManagement /></ProtectedRoute>} />
      <Route path="/audit" element={<ProtectedRoute><AuditLog /></ProtectedRoute>} />
      <Route path="/admin/agents" element={<ProtectedRoute><AgentManagement /></ProtectedRoute>} />

      <Route path="/" element={<ProtectedRoute><MyAgents /></ProtectedRoute>} />
      <Route path="/admin" element={<ProtectedRoute><OntologySemanticNetwork /></ProtectedRoute>} />
    </Routes>
  );
}
