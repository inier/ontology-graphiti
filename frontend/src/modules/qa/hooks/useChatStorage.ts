import { useCallback, useEffect, useRef } from 'react';
import type { QAMessage } from './useQAI';

const STORAGE_KEY = 'qa_chat_state';
const DEBOUNCE_MS = 500;

export interface ChatStorageData {
  sessionId: string | null;
  messages: QAMessage[];
  currentSessionId: string | null;
  lastUpdated: number;
}

function getStorageKey(sessionId: string | null): string {
  if (sessionId) {
    return `${STORAGE_KEY}_${sessionId}`;
  }
  return `${STORAGE_KEY}_default`;
}

export function useChatStorage(sessionId: string | null) {
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedDataRef = useRef<string>('');

  const saveState = useCallback((data: ChatStorageData) => {
    const serialized = JSON.stringify(data);
    if (serialized === lastSavedDataRef.current) {
      return;
    }
    lastSavedDataRef.current = serialized;

    try {
      localStorage.setItem(getStorageKey(data.currentSessionId), serialized);
    } catch (error) {
      console.warn('保存聊天状态到 localStorage 失败:', error);
    }
  }, []);

  const debouncedSave = useCallback((data: ChatStorageData) => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      saveState(data);
    }, DEBOUNCE_MS);
  }, [saveState]);

  const loadState = useCallback((): ChatStorageData | null => {
    try {
      const stored = localStorage.getItem(getStorageKey(sessionId));
      if (!stored) {
        const defaultStored = localStorage.getItem(getStorageKey(null));
        if (defaultStored) {
          return JSON.parse(defaultStored);
        }
        return null;
      }
      return JSON.parse(stored);
    } catch (error) {
      console.warn('从 localStorage 加载聊天状态失败:', error);
      return null;
    }
  }, [sessionId]);

  const clearState = useCallback(() => {
    try {
      const key = getStorageKey(sessionId);
      localStorage.removeItem(key);
      localStorage.removeItem(getStorageKey(null));
      lastSavedDataRef.current = '';
    } catch (error) {
      console.warn('清除 localStorage 中的聊天状态失败:', error);
    }
  }, [sessionId]);

  const persistMessages = useCallback((messages: QAMessage[], currentSessionId: string | null) => {
    const data: ChatStorageData = {
      sessionId: currentSessionId,
      messages,
      currentSessionId,
      lastUpdated: Date.now(),
    };
    debouncedSave(data);
  }, [debouncedSave]);

  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  return {
    loadState,
    persistMessages,
    clearState,
  };
}
