/**
 * AI Assistant Module — 独立 AI 助手模块
 *
 * 基于 OpenHarness QueryEngine + AG-UI 协议。
 * 提供双模式组件（full/compact），可内嵌或全屏使用。
 *
 * 架构层次：
 * - hooks/useAIChat — 统一数据层（SSE 流式、工具调用、会话管理）
 * - components/AIChatPanel — 统一展示层（full/compact 双模式）
 *
 * 使用方式：
 *   import { AIChatPanel } from '@/modules/ai-assistant';
 *   <AIChatPanel mode="full" ontologyId="ont-001" />
 */

export { AIChatPanel } from './components/AIChatPanel';
export type { AIChatPanelProps } from './components/AIChatPanel';

export { useAIChat } from './hooks/useAIChat';
export type {
  ChatMessage,
  ChatSession,
  UseAIChatOptions,
  UseAIChatReturn,
  AnalysisResult,
} from './hooks/useAIChat';
