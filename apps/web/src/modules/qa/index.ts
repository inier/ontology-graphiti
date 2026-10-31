export { QAPage } from './pages/QAPage';

// 卡片数据类型（图表 / 时序 / 报告链接），与对话引擎解耦
export type { ChartSpec, TemporalCard, ReportLink } from './types';

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

// AG-UI 协议集成（v2.0 扩展）
// 注：useQAI / useChatStorage / qaStore / qaApi / QAIProvider / ChartRenderer 已删除 ——
// 它们是 QA v1 的独立对话栈，被 ai-assistant 的 useAIChat + AIChatPanel 取代
// （QAPage 直接渲染 AIChatPanel）。复活它等于造出第二套对话引擎。
// 卡片渲染（InlineChart / TemporalCardView / ReportLinkView）依赖的类型
// 已迁至 ./types，与其解耦后继续服务 AG-UI 生成式卡片。
export {
  AGUIProvider,
  useAGUIContext,
  CardRenderer,
  HITLPanel,
  StatePanel,
  QACopilotDemoPage,
  getRegisteredCardTypes,
} from './agui';
export type {
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
