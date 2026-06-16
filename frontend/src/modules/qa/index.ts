export { useQAI } from './hooks/useQAI';
export type { QAMessage, UseQAIOptions, UseQAIReturn } from './hooks/useQAI';
export { useSession } from './hooks/useSession';
export type { Session, UseSessionOptions, UseSessionReturn } from './hooks/useSession';
export { QAChatPage } from './pages/QAChatPage';
export { QAPage } from './pages/QAPage';
export { default as ChartRenderer } from './components/ChartRenderer';
export { useQAStore } from './stores/qaStore';

// NL 本体查询服务（三检索支柱 + 五阶段管线）
export { QueryPage } from './pages/QueryPage';
export { EvaluationPage } from './pages/EvaluationPage';
export { useNLQueryStore } from './stores/nlQueryStore';
export { QueryInput } from './components/QueryInput';
export { QueryResultList } from './components/QueryResultList';
export { QueryPlanViewer } from './components/QueryPlanViewer';
export { PillarStatusPanel } from './components/PillarStatusPanel';
export { RetrievalResultCard } from './components/RetrievalResultCard';
export { QueryAuditTimeline } from './components/QueryAuditTimeline';
export { CypherPreview } from './components/CypherPreview';
export { NLQueryAuditPanel } from './components/NLQueryAuditPanel';

// AG-UI 协议集成（v2.0 扩展，与 useQAI 共存）
export {
  useAGUI,
  AGUIProvider,
  useAGUIContext,
  CardRenderer,
  HITLPanel,
  StatePanel,
  QACopilotDemoPage,
  getRegisteredCardTypes,
} from './agui';
export type {
  UseAGUIOptions,
  UseAGUIReturn,
  AGUIProviderProps,
  AGUIProviderConfig,
  AGUIContextValue,
  AGUIEvent,
  AGUIEventType,
  RunAgentInput,
  RunStartedEvent,
  RunFinishedEvent,
  RunErrorEvent,
  RunOutcome,
  StepStartedEvent,
  StepFinishedEvent,
  TextMessageStartEvent,
  TextMessageContentEvent,
  TextMessageEndEvent,
  ToolCallStartEvent,
  ToolCallArgsEvent,
  ToolCallEndEvent,
  ToolCallResultEvent,
  ToolCallChunkEvent,
  StateSnapshotEvent,
  StateDeltaEvent,
  StateDeltaOp,
  MessagesSnapshotEvent,
  Message,
  Interrupt,
  InterruptReason,
  InterruptStatus,
  ResumeEntry,
  CardType,
  CardMetadata,
} from './agui';
