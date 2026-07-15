/**
 * AG-UI Protocol TypeScript Types
 *
 * 镜像后端 odap/infra/openharness/agui/agui_models.py 的 Pydantic 模型。
 * v2.0 架构：纯 TypeScript 镜像（不依赖 @ag-ui/core SDK，0 新 npm 包）。
 *
 * 字段名严格遵循 AG-UI v0.x 协议 (camelCase)
 */

export type AGUIEventType =
  | 'RUN_STARTED'
  | 'RUN_FINISHED'
  | 'RUN_ERROR'
  | 'STEP_STARTED'
  | 'STEP_FINISHED'
  | 'TEXT_MESSAGE_START'
  | 'TEXT_MESSAGE_CONTENT'
  | 'TEXT_MESSAGE_END'
  | 'TOOL_CALL_START'
  | 'TOOL_CALL_ARGS'
  | 'TOOL_CALL_END'
  | 'TOOL_CALL_CHUNK'
  | 'TOOL_CALL_RESULT'
  | 'STATE_SNAPSHOT'
  | 'STATE_DELTA'
  | 'MESSAGES_SNAPSHOT'
  | 'ACTIVITY_SNAPSHOT';

export type RunOutcome = 'success' | { type: 'interrupt'; interrupts: Interrupt[] } | { type: 'error'; error: string };

export interface RunStartedEvent {
  type: 'RUN_STARTED';
  threadId: string;
  runId: string;
  parentRunId?: string | null;
  input?: { messages?: Message[] } | null;
}

export interface RunFinishedEvent {
  type: 'RUN_FINISHED';
  threadId: string;
  runId: string;
  outcome: RunOutcome;
  result?: Record<string, unknown> | null;
}

export interface RunErrorEvent {
  type: 'RUN_ERROR';
  message: string;
  code?: string | null;
}

export interface StepStartedEvent {
  type: 'STEP_STARTED';
  stepName: string;
}

export interface StepFinishedEvent {
  type: 'STEP_FINISHED';
  stepName: string;
}

export interface TextMessageStartEvent {
  type: 'TEXT_MESSAGE_START';
  messageId: string;
  role: 'assistant' | 'user' | 'system' | 'tool';
}

export interface TextMessageContentEvent {
  type: 'TEXT_MESSAGE_CONTENT';
  messageId: string;
  delta: string;
}

export interface TextMessageEndEvent {
  type: 'TEXT_MESSAGE_END';
  messageId: string;
}

export interface ToolCallStartEvent {
  type: 'TOOL_CALL_START';
  toolCallId: string;
  toolCallName: string;
  parentMessageId?: string;
}

export interface ToolCallArgsEvent {
  type: 'TOOL_CALL_ARGS';
  toolCallId: string;
  delta: string; // JSON 字符串
}

export interface ToolCallEndEvent {
  type: 'TOOL_CALL_END';
  toolCallId: string;
}

export interface ToolCallChunkEvent {
  type: 'TOOL_CALL_CHUNK';
  toolCallId: string;
  delta: string;
}

export interface ToolCallResultEvent {
  type: 'TOOL_CALL_RESULT';
  messageId: string;
  toolCallId: string;
  content: string;
  role: 'tool';
}

export interface StateSnapshotEvent {
  type: 'STATE_SNAPSHOT';
  snapshot: Record<string, unknown>;
}

export interface StateDeltaOp {
  op: 'add' | 'remove' | 'replace' | 'move' | 'copy' | 'test';
  path: string;
  value?: unknown;
  from?: string;
}

export interface StateDeltaEvent {
  type: 'STATE_DELTA';
  delta: StateDeltaOp[];
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content?: string | null;
  name?: string | null;
  toolCallId?: string | null;
  toolCalls?: Array<Record<string, unknown>> | null;
  createdAt?: string | null;
}

export interface MessagesSnapshotEvent {
  type: 'MESSAGES_SNAPSHOT';
  messages: Message[];
}

export interface ActivitySnapshotEvent {
  type: 'ACTIVITY_SNAPSHOT';
  activity: Array<Record<string, unknown>>;
}

export type AGUIEvent =
  | RunStartedEvent
  | RunFinishedEvent
  | RunErrorEvent
  | StepStartedEvent
  | StepFinishedEvent
  | TextMessageStartEvent
  | TextMessageContentEvent
  | TextMessageEndEvent
  | ToolCallStartEvent
  | ToolCallArgsEvent
  | ToolCallEndEvent
  | ToolCallChunkEvent
  | ToolCallResultEvent
  | StateSnapshotEvent
  | StateDeltaEvent
  | MessagesSnapshotEvent
  | ActivitySnapshotEvent;

// === Interrupt / Resume ===

export type InterruptReason = 'confirmation' | 'input_required' | 'tool_call' | 'cancellation';

export type InterruptStatus = 'resolved' | 'cancelled';

export interface Interrupt {
  id: string;
  reason: InterruptReason;
  message: string;
  responseSchema?: Record<string, unknown> | null;
  toolCallId?: string | null;
  metadata?: Record<string, unknown>;
}

export interface ResumeEntry {
  interruptId: string;
  status: InterruptStatus;
  response: Record<string, unknown>;
}

// === Request / Response ===

export interface RunAgentInput {
  threadId: string;
  runId: string;
  parentRunId?: string | null;
  messages: Message[];
  tools?: Array<{ name: string; description: string; parameters?: Record<string, unknown> }>;
  context?: Array<{ description?: string; value?: unknown }>;
  state?: Record<string, unknown>;
  resume?: ResumeEntry[];
  forwardedProps?: Record<string, unknown> | null;
  // ODAP 扩展
  workspaceId?: string | null;
  userId?: string | null;
  model?: string | null;
}

// === Generative UI 卡片 ===

export type CardType = 'chart' | 'graph' | 'temporal' | 'report_link' | 'action' | 'confirm' | 'input';

export interface CardMetadata {
  card_type: CardType;
  card_props: Record<string, unknown>;
  toolCallId?: string | null;
  toolName?: string | null;
}
