import React, { useState, useCallback } from 'react';
import { message } from 'antd';
import { apiClient } from '@/modules/shared/services/apiClient';

export interface Session {
  session_id: string;
  summary: string;
  message_count: number;
  model: string;
  created_at: string;
  workspace_id?: string;
  scenario_id?: string;
}

export interface UseSessionOptions {
  onError?: (error: Error) => void;
  workspaceId?: string;
  scenarioId?: string;
}

export interface UseSessionReturn {
  sessions: Session[];
  loading: boolean;
  error: Error | null;
  fetchSessions: (workspaceId?: string, scenarioId?: string) => Promise<void>;
  loadSession: (sessionId: string) => Promise<Session | null>;
  deleteSession: (sessionId: string) => Promise<boolean>;
}

export function useSession({ onError, workspaceId, scenarioId }: UseSessionOptions = {}): UseSessionReturn {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchSessions = useCallback(async (wsId?: string, scId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (wsId) params.append('workspace_id', wsId);
      if (scId) params.append('scenario_id', scId);

      const queryString = params.toString();
      // T050-fix: 后端 /api/qa/sessions 返回 List[SessionResponse]（list 直接返回，不是 {sessions: [...]}）
      // 见 odap/biz/data/qa/api/routes.py:274-309 list_sessions
      // SessionResponse 字段：session_id/user_id/workspace_id/scenario_id/state/created_at/updated_at/message_count
      const data = await apiClient.get<Session[]>(
        queryString ? `/api/qa/sessions?${queryString}` : '/api/qa/sessions'
      ) as any;
      // 兼容两种返回：list 或 {sessions: [...]} 包装
      const rawSessions = Array.isArray(data) ? data : (data?.sessions || []);
      // 适配后端 SessionResponse 字段到前端 Session 接口
      const adapted: Session[] = rawSessions.map((s: any) => ({
        session_id: s.session_id,
        summary: s.title || `会话 ${s.session_id.slice(0, 8)}`,
        message_count: s.message_count ?? 0,
        model: s.model || '',
        created_at: s.created_at || '',
        workspace_id: s.workspace_id,
        scenario_id: s.scenario_id,
      }));
      setSessions(adapted);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('获取会话列表失败');
      setError(error);
      onError?.(error);
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  React.useEffect(() => {
    fetchSessions(workspaceId, scenarioId);
  }, [workspaceId, scenarioId, fetchSessions]);

  const loadSession = useCallback(async (sessionId: string): Promise<Session | null> => {
    try {
      // T050-fix: 后端返回 SessionDetailResponse {session_id, messages, total}，
      // messages 元素是 {role, content, timestamp, ...}
      const data = await apiClient.get<any>(`/api/qa/sessions/${sessionId}`);
      return {
        session_id: data.session_id || sessionId,
        summary: '',
        message_count: data.total ?? (data.messages?.length ?? 0),
        model: '',
        created_at: '',
      } as Session;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('加载会话失败');
      onError?.(error);
      message.error(error.message);
      return null;
    }
  }, [onError]);

  const loadSessionMessages = useCallback(async (sessionId: string): Promise<any[]> => {
    try {
      const data = await apiClient.get<any>(`/api/qa/sessions/${sessionId}`);
      return data.messages || [];
    } catch (err) {
      return [];
    }
  }, []);

  const deleteSession = useCallback(async (sessionId: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/api/qa/sessions/${sessionId}`);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      message.success('会话已删除');
      return true;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('删除会话失败');
      onError?.(error);
      message.error(error.message);
      return false;
    }
  }, [onError]);

  return {
    sessions,
    loading,
    error,
    fetchSessions,
    loadSession,
    deleteSession,
  };
}
