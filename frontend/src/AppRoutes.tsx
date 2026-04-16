import { Routes, Route } from 'react-router-dom';
import { Dashboard, OntologyGraph, Timeline, SituationMap, Simulator, IngestPanel, VersionHistory } from './pages';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/ontology" element={<OntologyGraph />} />
      <Route path="/timeline" element={<Timeline />} />
      <Route path="/map" element={<SituationMap />} />
      <Route path="/simulator" element={<Simulator />} />
      <Route path="/ingest" element={<IngestPanel />} />
      <Route path="/versions" element={<VersionHistory />} />
      <Route path="/config" element={<div style={{ padding: 24 }}>配置中心 - 建设中</div>} />
      <Route path="/roles" element={<div style={{ padding: 24 }}>角色管理 - 建设中</div>} />
      <Route path="/policies" element={<div style={{ padding: 24 }}>OPA 策略 - 建设中</div>} />
      <Route path="/audit" element={<div style={{ padding: 24 }}>审计日志 - 建设中</div>} />
      <Route path="/skills" element={<div style={{ padding: 24 }}>Skill 管理 - 建设中</div>} />
    </Routes>
  );
}
