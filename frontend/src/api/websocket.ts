import type { TaskProgress } from '../types';

export class ProgressWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: number | null = null;
  private sessionId: string;
  private onMessage: (data: TaskProgress) => void;

  constructor(sessionId: string, onMessage: (data: TaskProgress) => void) {
    this.sessionId = sessionId;
    this.onMessage = onMessage;
  }

  connect() {
    const wsUrl = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`;
    this.ws = new WebSocket(`${wsUrl}/api/ws/progress/${this.sessionId}`);

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as TaskProgress;
        this.onMessage(data);
      } catch {
        // ignore parse errors
      }
    };

    this.ws.onclose = () => {
      // Auto-reconnect after 2 seconds
      this.reconnectTimer = window.setTimeout(() => this.connect(), 2000);
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
