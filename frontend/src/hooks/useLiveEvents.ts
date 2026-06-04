import { useCallback, useEffect, useState } from "react";
import { WS_URL, type IngestedEvent } from "@/lib/api";

export interface LiveEventRow extends IngestedEvent {
  receivedAt: string;
}

export function useLiveEvents(maxEvents = 80) {
  const [events, setEvents] = useState<LiveEventRow[]>([]);
  const [connected, setConnected] = useState(false);
  const [paused, setPaused] = useState(false);

  const clear = useCallback(() => setEvents([]), []);

  useEffect(() => {
    if (paused) return;

    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let active = true;

    const connect = () => {
      if (!active) return;

      const socket = new WebSocket(WS_URL);
      ws = socket;

      socket.onopen = () => {
        if (active && socket === ws) setConnected(true);
      };

      socket.onmessage = (msg) => {
        if (!active || socket !== ws) return;
        try {
          const data = JSON.parse(msg.data as string);
          if (data.type === "new_event" && data.event) {
            const row: LiveEventRow = {
              ...data.event,
              receivedAt: new Date().toISOString(),
            };
            setEvents((prev) => [row, ...prev].slice(0, maxEvents));
          }
        } catch {
          /* ignore malformed */
        }
      };

      socket.onclose = () => {
        if (!active || socket !== ws) return;
        setConnected(false);
        reconnectTimer = setTimeout(connect, 3000);
      };

      socket.onerror = () => {
        if (socket.readyState !== WebSocket.CLOSING && socket.readyState !== WebSocket.CLOSED) {
          socket.close();
        }
      };
    };

    const connectTimer = setTimeout(connect, 0);

    return () => {
      active = false;
      if (connectTimer) clearTimeout(connectTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
      setConnected(false);
    };
  }, [paused, maxEvents]);

  return { events, connected, paused, setPaused, clear };
}
