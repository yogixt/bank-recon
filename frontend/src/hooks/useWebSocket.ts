import { useEffect, useRef, useState } from 'react';
import { ProgressWebSocket } from '../api/websocket';
import type { TaskProgress } from '../types';

export function useWebSocket(sessionId: string | null) {
  const [progress, setProgress] = useState<TaskProgress | null>(null);
  const wsRef = useRef<ProgressWebSocket | null>(null);

  useEffect(() => {
    if (!sessionId) return;

    const ws = new ProgressWebSocket(sessionId, (data) => {
      setProgress(data);
    });
    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [sessionId]);

  return progress;
}
