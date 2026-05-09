import { Routes, Route } from 'react-router-dom';
import { Dashboard, SituationMap } from './pages';
import { WorkspaceManager } from './modules/workspace';
import { AuditLog } from './modules/audit';
import { ConfigCenter, PolicyManagement } from './modules/config';
import { OntologySemanticNetwork, Timeline, QueryView } from './modules/ontology';
import { IngestPanel, Simulator } from './modules/ingest';
import { VersionHistory } from './modules/version';
import { RoleManager } from './modules/roles';
import { QAChatPage } from './modules/qa/pages/QAChatPage';
import { SkillManagement } from './modules/system';

import { Alert } from 'antd';

function Placeholder({ title, description }: { title: string; description?: string }) {
  return (
    <Alert
      title={title}
      description={description || `${title} 功能正在开发中`}
      type="info"
      showIcon
    />
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/ontology" element={<OntologySemanticNetwork />} />
      <Route path="/timeline" element={<Timeline />} />
      <Route path="/map" element={<SituationMap />} />
      <Route path="/query" element={<QueryView />} />
      <Route path="/simulator" element={<Simulator />} />
      <Route path="/ingest" element={<IngestPanel />} />
      <Route path="/versions" element={<VersionHistory />} />
      <Route path="/workspace" element={<WorkspaceManager />} />
      <Route path="/audit" element={<AuditLog />} />
      <Route path="/config" element={<ConfigCenter />} />
      <Route path="/roles" element={<RoleManager />} />
      <Route path="/qa" element={<QAChatPage />} />
      <Route path="/policies" element={<PolicyManagement />} />
      <Route path="/skills" element={<SkillManagement />} />
    </Routes>
  );
}
