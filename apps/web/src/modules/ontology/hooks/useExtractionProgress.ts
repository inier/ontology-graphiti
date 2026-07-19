import { useState, useEffect, useCallback, useRef } from 'react';
import { ontologyApi } from '../services/ontologyApi';
import type { ExtractionProgress } from '../components/types';

export function useExtractionProgress(sessionId: string | null) {
  const [progress, setProgress] = useState<ExtractionProgress | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const subscribe = useCallback(async () => {
    if (!sessionId) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await ontologyApi.extraction.progressStream(sessionId);

      if (!response.ok) {
        throw new Error('Failed to connect to progress stream');
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('No response body');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              setProgress(data);

              if (data.is_completed) {
                return;
              }
            } catch (e) {
              console.warn('Failed to parse progress event:', e);
            }
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  const getStatus = useCallback(async () => {
    if (!sessionId) return;

    try {
      const result = await ontologyApi.extraction.progressStatus(sessionId);
      setProgress(result);
    } catch (e) {
      console.warn('Failed to get progress status:', e);
    }
  }, [sessionId]);

  useEffect(() => {
    if (sessionId) {
      getStatus();
      subscribe();
    }

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [sessionId, subscribe, getStatus]);

  return {
    progress,
    isLoading,
    error,
    getStatus,
  };
}