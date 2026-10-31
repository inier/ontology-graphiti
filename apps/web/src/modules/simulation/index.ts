export { default as StrategyDeduction } from './pages/StrategyDeduction';
export { default as SimulationPage } from './pages/SimulationPage';
export { default as SandboxLabPage } from './pages/SandboxLabPage';
export { default as WhatIfPanel } from './components/WhatIfPanel';
export { default as FeedbackPanel } from './components/FeedbackPanel';

// F5 归并（AC-21）：ParallelComparison / SimulationProgress / TimelineView / RecommendationPanel
// 已删除，归档于 .workbuddy/archive/zero-ref-2026-10-20/。
// 理由：前三个是纯展示组件（仿真页已有等价能力）；RecommendationPanel 打
//       `/api/simulation/recommendations` —— 后端无此路由，属契约虚构。
