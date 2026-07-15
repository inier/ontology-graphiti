import { useState, useEffect, useRef } from 'react';

interface BuildProgressEvent {
  type: 'build_progress';
  data: {
    stage: string;
    progress: number;
    message: string;
    ingest_id?: string;
    scenario_id?: string;
  };
}

interface BuildProgressState {
  stage: string;
  progress: number;
  message: string;
  isConnected: boolean;
}

export function useBuildProgress(scenarioId?: string) {
  const [state, setState] = useState<BuildProgressState>({
    stage: '',
    progress: 0,
    message: '',
    isConnected: false,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scenarioIdRef = useRef(scenarioId);

  // Keep ref in sync
  useEffect(() => {
    scenarioIdRef.current = scenarioId;
  }, [scenarioId]);

  useEffect(() => {
    function doConnect() {
      // Clean up any existing connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/ontology/build-progress`;
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setState(prev => ({ ...prev, isConnected: true }));
      };

      ws.onclose = () => {
        setState(prev => ({ ...prev, isConnected: false }));
        // Reconnect after 5s
        reconnectTimerRef.current = setTimeout(doConnect, 5000);
      };

      ws.onmessage = (event) => {
        try {
          const data: BuildProgressEvent = JSON.parse(event.data);
          if (data.type === 'build_progress') {
            const sid = scenarioIdRef.current;
            if (!sid || data.data.scenario_id === sid) {
              setState({
                stage: data.data.stage,
                progress: data.data.progress,
                message: data.data.message,
                isConnected: true,
              });
            }
          }
        } catch {
          // ignore parse errors
        }
      };

      wsRef.current = ws;
    }

    doConnect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
  }, [scenarioId]);

  return state;
}
