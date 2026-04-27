import { useState, useCallback } from 'react';
import { message } from 'antd';

const API_BASE = 'http://localhost:8000/api/qa';

export interface Session {
  session_id: string;
  summary: string;
  message_count: number;
  model: string;
  created_at: number;
}

export interface UseSessionOptions {
  onError?: (error: Error) => void;
}

export interface UseSessionReturn {
  sessions: Session[];
  loading: boolean;
  error: Error | null;
  fetchSessions: () => Promise<void>;
  loadSession: (sessionId: string) => Promise<Session | null>;
  deleteSession: (sessionId: string) => Promise<boolean>;
}

export function useSession({ onError }: UseSessionOptions = {}): UseSessionReturn {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/sessions`);
      if (!response.ok) {
        throw new Error(`获取会话列表失败: ${response.status}`);
      }
      const data = await response.json();
      setSessions(data.sessions || []);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('获取会话列表失败');
      setError(error);
      onError?.(error);
      message.error(error.message);
    } finally {
      setLoading(false);
    }
  }, [onError]);

  const loadSession = useCallback(async (sessionId: string): Promise<Session | null> => {
    try {
      const response = await fetch(`${API_BASE}/sessions/${sessionId}`);
      if (!response.ok) {
        throw new Error(`加载会话失败: ${response.status}`);
      }
      const data = await response.json();
      return data;
    } catch (err) {
      const error = err instanceof Error ? err : new Error('加载会话失败');
      onError?.(error);
      message.error(error.message);
      return null;
    }
  }, [onError]);

  const deleteSession = useCallback(async (sessionId: string): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/sessions/${sessionId}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        throw new Error(`删除会话失败: ${response.status}`);
      }
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