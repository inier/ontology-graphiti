export { OntologyDesignerPage } from './pages/OntologyDesignerPage';
export { OntologyGraphPage } from './pages/OntologyGraphPage';
export { GoalKanban } from './pages/GoalKanban';
export { useOntologyStore } from './stores/ontologyStore';

// Phase 11 Batch 1/2 — FR-031/032/033/034/035
export { BranchList } from './components/BranchList';
export { MergeDiffViewer } from './components/MergeDiffViewer';
export { InheritanceGraph } from './components/InheritanceGraph';
export { MixinConfig } from './components/MixinConfig';
export { default as ActionPanel } from './components/ActionPanel';
export { default as ViewDesigner } from './components/ViewDesigner';
export { ObjectViewPage } from './pages/ObjectViewPage';
export { ObjectViewsPage } from './pages/ObjectViewsPage';
export { default as DocumentImporter } from './components/DocumentImporter';
export { ComputedPropertyList } from './components/ComputedPropertyList';
export { MaterializationJobsPanel } from './components/MaterializationJobsPanel';

// Phase 11 Batch 3/4 — FR-036/037
export { ChangeProposalCard } from './components/ChangeProposalCard';
export { GoalLineage } from './components/GoalLineage';

export type { BranchInfo, BranchStatus } from './components/BranchList';

// Ontology redesign types
export type {
  Ontology,
  ObjectTypeDefinition,
  LinkTypeDefinition,
  ActionTypeDefinition,
  ProcessTypeDefinition,
  RuleTypeDefinition,
  FunctionTypeDefinition,
  IndicatorTypeDefinition,
  SchemaVersion,
} from './stores/ontologyStore';
