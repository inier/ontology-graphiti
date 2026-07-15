export { GraphCanvas } from '@/modules/shared/modules/graph/components/GraphCanvas';
export { GraphToolbar } from './GraphToolbar';
export { GraphControls } from './GraphControls';
export { default as EditLockIndicator } from './EditLockIndicator';
export { OntologySelector } from './OntologySelector';
export type { OntologyItem, OntologySelectorProps } from './OntologySelector';
export { DesignMethodSelector } from './DesignMethodSelector';
export type { DesignMethod, DesignMethodSelectorProps } from './DesignMethodSelector';
export { VersionHistoryPanel } from './VersionHistoryPanel';
export type { VersionHistoryPanelProps } from './VersionHistoryPanel';
export { VersionDiffView } from './VersionDiffView';
export type { VersionDiffViewProps } from './VersionDiffView';
export type { GraphNode, GraphEdge } from '@/modules/shared/modules/graph';
export type { LayoutType } from './constants';
export {
  getNodeColor, getNodeShape, getEdgeStyle, getContrastColor, getSideColor,
  ZOOM_STEP, ZOOM_MIN, ZOOM_MAX,
} from './constants';

// AI Assistant components (T070-T073)
export { AIInlineCompletion } from './AIInlineCompletion';
export type { AIInlineCompletionProps } from './AIInlineCompletion';
export { AISuggestionList } from './AISuggestionList';
export type { AISuggestionListProps } from './AISuggestionList';

// Extraction components (US3)
export { DocumentUploader } from './DocumentUploader';
export type { DocumentUploaderProps } from './DocumentUploader';
export { KnowledgeBaseSelector } from './KnowledgeBaseSelector';
export type { KnowledgeBaseSelectorProps } from './KnowledgeBaseSelector';
export { ProvenanceViewer } from './ProvenanceViewer';
export type { ProvenanceViewerProps } from './ProvenanceViewer';
export { TemplateRecommender } from './TemplateRecommender';
export type { TemplateRecommenderProps, HETemplate } from './TemplateRecommender';