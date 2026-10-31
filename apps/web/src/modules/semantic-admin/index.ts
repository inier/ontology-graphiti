export { SemanticAdminIndex } from './pages/SemanticAdminIndex';
export { UslConfigPage } from './pages/UslConfigPage';
export { QualityDashboardPage } from './pages/QualityDashboardPage';
export {
  SemanticAdminTabsContainer,
  QualityKpiCards,
  QualityChartRow,
} from './pages/QualityDashboardPage';
export { ApprovalsPage } from './pages/ApprovalsPage';
export { default as CandidatesPage } from './pages/CandidatesPage';
export { default as PipelineRunsPage } from './pages/PipelineRunsPage';
// DashboardPage 已删除：与 QualityDashboardPage 打同一组端点
// （/api/semantic-admin/dashboard/{summary,terms-trend,approvals-breakdown}），
// 且 legacyRedirects 早已把 /semantic-admin/dashboard 收敛到 /semantic-admin/quality。
// 归档：.workbuddy/archive/zero-ref-2026-10-20/modules/semantic-admin/pages/DashboardPage.tsx
export { default as SemanticAssetPipelinePage } from './pages/SemanticAssetPipelinePage';
export { default as UslOntologyPage } from './pages/UslOntologyPage';
export { GapPoolPage } from './pages/GapPoolPage';
export { GapDetailPage } from './pages/GapDetailPage';
export { GapStatsPage } from './pages/GapStatsPage';
export { RoutingTicketsPage } from './pages/RoutingTicketsPage';
export { RoutingTicketDetailPage } from './pages/RoutingTicketDetailPage';

export { semanticAdminRouteMeta } from './routes';

export type {
  UslDomain,
  UslTerm,
  UslHierarchy,
  UslPropertySpec,
  UslDisjointPair,
  UslCardinality,
  DomainPayload,
  TermPayload,
  SemanticType,
  HierarchyRelType,
  PropertyDataType,
  PagedResponse,
  CandidateStatus,
} from './types';
export {
  SEMANTIC_TYPE_LABEL,
  SEMANTIC_TYPE_COLOR,
  PROPERTY_DATA_TYPE_OPTIONS,
  HIERARCHY_REL_OPTIONS,
} from './types';

export { useSemanticAdminStore } from './store/useSemanticAdminStore';
export type {
  CandidateFilters,
  PipelineRunFilters,
  AdminTopTab,
  UslSubTab,
} from './store/useSemanticAdminStore';
export { useUslPermissions } from './hooks/useUslPermissions';

export * as uslApi from './services/uslApi';
export * as pipelineApi from './services/pipelineApi';
export type {
  Candidate,
  PipelineRun,
  PipelineRunStatus,
  PipelineRunStats,
  QualityReport,
  CreatePipelineRunRequest,
  ReviewPayload,
} from './services/pipelineApi';
