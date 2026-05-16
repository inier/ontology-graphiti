import { Routes, Route } from 'react-router-dom';
import { WorkspaceManager } from './modules/workspace';
import { AuditLog } from './modules/audit';
import { PolicyManagement } from './modules/config';
import { OntologySemanticNetwork } from './modules/ontology';
import { IngestPanel, Simulator } from './modules/ingest';
import { VersionHistory } from './modules/version';
import { RoleManager } from './modules/roles';
import { QAChatPage } from './modules/qa/pages/QAChatPage';
import { SkillManagement } from './modules/system';
import { BusinessProcess, Rules, Indicators, Logic, ObjectManagement, SmartGeneration } from './modules/business';
import { KnowledgeBase } from './modules/knowledge';
import { MyAgents, AgentChat, AgentManagement } from './modules/agent';

export function AppRoutes() {
  return (
    <Routes>
      {/* 我的智能体入口 */}
      <Route path="/my-agents" element={<MyAgents />} />
      <Route path="/agent-chat/:agentId" element={<AgentChat />} />

      {/* 管理后台 */}
      <Route path="/ontology" element={<OntologySemanticNetwork />} />
      <Route path="/versions" element={<VersionHistory />} />
      <Route path="/business/process" element={<BusinessProcess />} />
      <Route path="/business/rules" element={<Rules />} />
      <Route path="/business/indicators" element={<Indicators />} />
      <Route path="/business/logic" element={<Logic />} />
      <Route path="/business/entities" element={<ObjectManagement />} />
      <Route path="/business/extraction" element={<SmartGeneration />} />
      <Route path="/qa" element={<QAChatPage />} />
      <Route path="/skills" element={<SkillManagement />} />
      <Route path="/simulator" element={<Simulator />} />
      <Route path="/ingest" element={<IngestPanel />} />
      <Route path="/knowledge" element={<KnowledgeBase />} />
      <Route path="/workspace" element={<WorkspaceManager />} />
      <Route path="/roles" element={<RoleManager />} />
      <Route path="/policies" element={<PolicyManagement />} />
      <Route path="/audit" element={<AuditLog />} />
      <Route path="/admin/agents" element={<AgentManagement />} />

      {/* 默认入口 */}
      <Route path="/" element={<MyAgents />} />
      <Route path="/admin" element={<OntologySemanticNetwork />} />
    </Routes>
  );
}
