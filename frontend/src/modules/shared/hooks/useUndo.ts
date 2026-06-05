import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '../../config';
import { fetchJson } from '../../shared/services/apiClient';

interface UndoOperation {
  operation_id: string;
  workspace_id: string;
  user_id: string;
  action_type: string;
  resource_type: string;
  resource_id: string;
  before_state: Record<string, unknown> | null;
  after_state: Record<string, unknown> | null;
  created_at: string;
  undone: boolean;
}

interface UndoHistoryResult {
  operations: UndoOperation[];
  page: number;
  page_size: number;
  total: number;
}

interface UndoableResult {
  status: string;
  operations: UndoOperation[];
  count: number;
}

interface UseUndoOptions {
  workspaceId?: string;
  enabled?: boolean;
}

interface UseUndoReturn {
  canUndo: boolean;
  canRedo: boolean;
  undo: (operationId?: string) => Promise<void>;
  redo: (operationId?: string) => Promise<void>;
  history: UndoOperation[];
  refreshHistory: () => Promise<void>;
  undoableCount: number;
  redoableCount: number;
}

export function useUndo(options: UseUndoOptions = {}): UseUndoReturn {
  const { workspaceId, enabled = true } = options;
  const [history, setHistory] = useState<UndoOperation[]>([]);
  const [undoable, setUndoable] = useState<UndoOperation[]>([]);
  const [redoable, setRedoable] = useState<UndoOperation[]>([]);

  const refreshHistory = useCallback(async () => {
    if (!workspaceId || !enabled) return;
    try {
      const result = await fetchJson<UndoHistoryResult>(
        `${API_BASE}/api/undo/history?workspace_id=${encodeURIComponent(workspaceId)}&page=1&page_size=50`
      );
      setHistory(result.operations || []);
    } catch (e) {
      console.warn('获取操作历史失败:', e);
    }
  }, [workspaceId, enabled]);

  const refreshUndoable = useCallback(async () => {
    if (!workspaceId || !enabled) return;
    try {
      const result = await fetchJson<UndoableResult>(
        `${API_BASE}/api/undo/undoable?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      setUndoable(result.operations || []);
    } catch (e) {
      console.warn('获取可撤销操作失败:', e);
    }
  }, [workspaceId, enabled]);

  const refreshRedoable = useCallback(async () => {
    if (!workspaceId || !enabled) return;
    try {
      const result = await fetchJson<UndoableResult>(
        `${API_BASE}/api/undo/redoable?workspace_id=${encodeURIComponent(workspaceId)}`
      );
      setRedoable(result.operations || []);
    } catch (e) {
      console.warn('获取可重做操作失败:', e);
    }
  }, [workspaceId, enabled]);

  const refreshAll = useCallback(async () => {
    await Promise.all([refreshHistory(), refreshUndoable(), refreshRedoable()]);
  }, [refreshHistory, refreshUndoable, refreshRedoable]);

  const undo = useCallback(async (operationId?: string) => {
    const targetId = operationId || undoable[0]?.operation_id;
    if (!targetId) return;
    try {
      await fetchJson(`${API_BASE}/api/undo/${targetId}/undo`, { method: 'POST' });
      await refreshAll();
    } catch (e) {
      console.error('撤销失败:', e);
      throw e;
    }
  }, [undoable, refreshAll]);

  const redo = useCallback(async (operationId?: string) => {
    const targetId = operationId || redoable[0]?.operation_id;
    if (!targetId) return;
    try {
      await fetchJson(`${API_BASE}/api/undo/${targetId}/redo`, { method: 'POST' });
      await refreshAll();
    } catch (e) {
      console.error('重做失败:', e);
      throw e;
    }
  }, [redoable, refreshAll]);

  // 键盘快捷键监听
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Z / Cmd+Z = 撤销
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (undoable.length > 0) {
          undo();
        }
      }
      // Ctrl+Y / Cmd+Y 或 Ctrl+Shift+Z = 重做
      if (
        ((e.ctrlKey || e.metaKey) && e.key === 'y') ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'z')
      ) {
        e.preventDefault();
        if (redoable.length > 0) {
          redo();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [enabled, undo, redo, undoable.length, redoable.length]);

  // 初始化加载
  useEffect(() => {
    if (workspaceId && enabled) {
      refreshAll();
    }
  }, [workspaceId, enabled, refreshAll]);

  return {
    canUndo: undoable.length > 0,
    canRedo: redoable.length > 0,
    undo,
    redo,
    history,
    refreshHistory,
    undoableCount: undoable.length,
    redoableCount: redoable.length,
  };
}
