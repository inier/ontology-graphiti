/**
 * useAIChat — 统一 AI 助手核心 Hook
 *
 * 职责：
 * 1. 消息状态管理（发送、接收、清空）
 * 2. SSE 流式连接到 /api/assistant/chat
 * 3. 直接工具调用 /api/assistant/tools/execute
 * 4. 会话管理（列表、创建、切换、删除）— 可选，full 模式启用
 * 5. ONTOLOGY_CHANGED / ANALYSIS_RESULT 自定义事件处理
 * 6. 本体上下文自动注入
 *
 * 这是所有 AI 助手功能（智能问答、AI助手）的唯一数据层，
 * full 模式和 compact 模式共享此 Hook。
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { apiClient } from '@/modules/shared/services/apiClient';

// ═══════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool';
  content: string;
  timestamp: number;
  toolName?: string;
  tool_calls?: Array<{ tool_name: string; status: 'pending' | 'done' }>;
  /** 富内容：图表、时序卡片等（full 模式渲染） */
  charts?: unknown[];
  temporal?: unknown[];
  reports?: unknown[];
  reasoning?: Array<{ step: string; description: string; detail?: unknown }>;
  sources?: Array<{ excerpt: string; source: string; confidence: number }>;
}

export interface ChatSession {
  session_id: string;
  summary?: string;
  message_count: number;
  created_at: string;
  updated_at?: string;
}

export interface AnalysisResult {
  id: string;
  toolName: string;
  result: Record<string, unknown>;
  timestamp: number;
}

export interface UseAIChatOptions {
  /** 本体 ID（可选，本体设计器场景传入） */
  ontologyId?: string;
  /** 工作空间 ID */
  workspaceId?: string;
  /** 额外上下文 */
  context?: Record<string, unknown>;
  /** 是否启用会话管理（full 模式启用） */
  enableSessions?: boolean;
  /** 本体被修改后的回调 */
  onOntologyChanged?: () => void;
}

export interface UseAIChatReturn {
  // ── 消息 ──
  messages: ChatMessage[];
  sendMessage: (text: string) => Promise<void>;
  clearMessages: () => void;
  sending: boolean;

  // ── 工具 ──
  executeTool: (toolName: string, params: Record<string, unknown>) => Promise<Record<string, unknown>>;
  analysisResults: AnalysisResult[];
  clearAnalysisResults: () => void;

  // ── 会话 ──
  sessions: ChatSession[];
  currentSessionId: string | null;
  loadSessions: () => Promise<void>;
  selectSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  createNewSession: () => void;

  // ── 控制 ──
  cancel: () => void;
  error: string | null;

  // ── 本体上下文 ──
  ontologyContext: Record<string, unknown> | null;
}

// ═══════════════════════════════════════════════════════════════
// Hook 实现
// ═══════════════════════════════════════════════════════════════

export function useAIChat(options: UseAIChatOptions = {}): UseAIChatReturn {
  const {
    ontologyId,
    workspaceId = 'default',
    context,
    enableSessions = false,
    onOntologyChanged,
  } = options;

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult[]>([]);
  const [ontologyContext, setOntologyContext] = useState<Record<string, unknown> | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  // ═══════════════════════════════════════════════════════════════
  // 本体上下文自动注入
  // ═══════════════════════════════════════════════════════════════
  useEffect(() => {
    if (!ontologyId) {
      setOntologyContext(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const resp = await apiClient.post('/api/assistant/tools/execute', {
          tool_name: 'get_ontology_context',
          parameters: { ontology_id: ontologyId },
        });
        if (cancelled) return;
        const result = resp.data?.result || resp.result || resp;
        setOntologyContext(result.context || {});
      } catch {
        // 静默失败
      }
    })();
    return () => { cancelled = true; };
  }, [ontologyId]);

  // ═══════════════════════════════════════════════════════════════
  // 会话管理（可选）
  // ═══════════════════════════════════════════════════════════════
  const loadSessions = useCallback(async () => {
    if (!enableSessions) return;
    try {
      const resp = await apiClient.get(`/api/qa/sessions?workspace_id=${workspaceId}`);
      const data = resp.data || resp;
      setSessions(Array.isArray(data) ? data : (data.sessions || []));
    } catch {
      // 静默失败
    }
  }, [enableSessions, workspaceId]);

  useEffect(() => {
    if (enableSessions) {
      loadSessions();
    }
  }, [enableSessions, loadSessions]);

  const selectSession = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const resp = await apiClient.get(`/api/qa/sessions/${sessionId}`);
      const data = resp.data || resp;
      const msgs = data.messages || [];
      setMessages(msgs.map((m: Record<string, unknown>) => ({
        id: (m.id as string) || (m.message_id as string) || `${m.timestamp || ''}-${Math.random().toString(36).slice(2, 8)}`,
        role: m.role === 'user' ? 'user' : 'assistant',
        content: (m.content as string) || (m.text as string) || '',
        timestamp: m.timestamp ? new Date(m.timestamp as string).getTime() : Date.now(),
      })));
    } catch {
      // 静默失败
    }
  }, []);

  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      await apiClient.delete(`/api/qa/sessions/${sessionId}`);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      if (sessionId === currentSessionId) {
        setMessages([]);
        setCurrentSessionId(null);
      }
    } catch {
      // 静默失败
    }
  }, [currentSessionId]);

  const createNewSession = useCallback(() => {
    setMessages([]);
    setCurrentSessionId(null);
    setError(null);
  }, []);

  // ═══════════════════════════════════════════════════════════════
  // 发送消息（SSE 流式）
  // ═══════════════════════════════════════════════════════════════
  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
    };
    setMessages(prev => [...prev, userMsg]);
    setSending(true);
    setError(null);

    // 创建 assistant 占位消息
    const assistantMsgId = `ai-${Date.now()}`;
    setMessages(prev => [...prev, {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }]);

    abortRef.current = new AbortController();

    try {
      const response = await apiClient.stream('/api/assistant/chat', {
        message: trimmed,
        ontology_id: ontologyId || null,
        workspace_id: workspaceId,
        session_id: currentSessionId,
        context: context || {},
      }, { signal: abortRef.current.signal });

      const reader = response.body?.getReader();
      if (!reader) throw new Error('无法读取响应流');

      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let contentBody = '';
      const toolCalls: Array<{ tool_name: string; status: 'pending' | 'done' }> = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const data = line.slice(6).trim();
          if (data === '[DONE]') continue;

          try {
            const event = JSON.parse(data);

            switch (event.type) {
              case 'RUN_STARTED':
                if (event.session_id) setCurrentSessionId(event.session_id);
                break;

              case 'TEXT_MESSAGE_CONTENT':
                contentBody += event.delta || '';
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId
                    ? { ...m, content: contentBody, tool_calls: toolCalls.length > 0 ? [...toolCalls] : undefined }
                    : m
                ));
                break;

              case 'TOOL_CALL_START':
                toolCalls.push({ tool_name: event.tool_name || '', status: 'pending' });
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId
                    ? { ...m, tool_calls: [...toolCalls] }
                    : m
                ));
                break;

              case 'TOOL_CALL_END': {
                const tc = toolCalls.find(t => t.status === 'pending');
                if (tc) tc.status = 'done';
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId
                    ? { ...m, tool_calls: [...toolCalls] }
                    : m
                ));
                break;
              }

              case 'CUSTOM':
                if (event.custom_type === 'ANALYSIS_RESULT') {
                  const toolCallId = event.tool_call_id || '';
                  const toolName = event.tool_name || '';
                  const result = event.result || {};
                  if (toolCallId && toolName) {
                    setAnalysisResults(prev => {
                      const filtered = prev.filter(r => r.id !== toolCallId);
                      return [...filtered, { id: toolCallId, toolName, result, timestamp: Date.now() }].slice(-20);
                    });
                  }
                  // 追加分析摘要到消息内容
                  const summary = (result as Record<string, unknown>).summary as Record<string, number> || {};
                  const lines: string[] = ['\n📊 **分析结果**'];
                  if (summary.total_object_types !== undefined) lines.push(`对象类型: ${summary.total_object_types} 个`);
                  if (summary.orphan_count !== undefined) lines.push(`孤儿类型: ${summary.orphan_count} 个`);
                  if (summary.missing_audit_count !== undefined) lines.push(`缺失审计字段: ${summary.missing_audit_count} 个`);
                  contentBody += lines.join('\n');
                  setMessages(prev => prev.map(m =>
                    m.id === assistantMsgId ? { ...m, content: contentBody } : m
                  ));
                }
                if (event.custom_type === 'ONTOLOGY_CHANGED') {
                  contentBody += `\n\n✅ **${event.message || '本体已更新'}**`;
                  setMessages(prev => prev.map(m =>
                    m.id === assistantMsgId ? { ...m, content: contentBody } : m
                  ));
                  onOntologyChanged?.();
                }
                break;

              case 'RUN_FINISHED':
                break;

              case 'ERROR':
                contentBody += `\n\n❌ 错误: ${event.message}`;
                setMessages(prev => prev.map(m =>
                  m.id === assistantMsgId ? { ...m, content: contentBody } : m
                ));
                break;
            }
          } catch {
            // 跳过格式错误的 SSE 数据
          }
        }
      }

      // 最终更新
      setMessages(prev => prev.map(m =>
        m.id === assistantMsgId
          ? { ...m, content: contentBody || '已收到您的消息。', tool_calls: toolCalls.length > 0 ? toolCalls : undefined }
          : m
      ));

      // 刷新会话列表
      if (enableSessions) {
        loadSessions();
      }
    } catch (err: unknown) {
      if ((err as Error).name === 'AbortError') return;
      const errorMsg = err instanceof Error ? err.message : '请求失败';
      setError(errorMsg);
      setMessages(prev => prev.map(m =>
        m.id === assistantMsgId
          ? { ...m, content: `抱歉，请求失败：${errorMsg}` }
          : m
      ));
    } finally {
      setSending(false);
      abortRef.current = null;
    }
  }, [sending, ontologyId, workspaceId, currentSessionId, context, enableSessions, loadSessions, onOntologyChanged]);

  // ═══════════════════════════════════════════════════════════════
  // 直接工具调用（不经过 LLM）
  // ═══════════════════════════════════════════════════════════════
  const executeTool = useCallback(async (toolName: string, params: Record<string, unknown>) => {
    const resp = await apiClient.post('/api/assistant/tools/execute', {
      tool_name: toolName,
      parameters: params,
    });
    return resp.data?.result || resp.result || resp;
  }, []);

  // ═══════════════════════════════════════════════════════════════
  // 控制
  // ═══════════════════════════════════════════════════════════════
  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setSending(false);
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setSending(false);
  }, []);

  const clearAnalysisResults = useCallback(() => {
    setAnalysisResults([]);
  }, []);

  // 卸载时清理
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  return {
    messages,
    sendMessage,
    clearMessages,
    sending,
    executeTool,
    analysisResults,
    clearAnalysisResults,
    sessions,
    currentSessionId,
    loadSessions,
    selectSession,
    deleteSession,
    createNewSession,
    cancel,
    error,
    ontologyContext,
  };
}
