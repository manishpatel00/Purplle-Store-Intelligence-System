import { useEffect, useState } from 'react';

const WS_URL = "ws://localhost:8000/ws/updates";

export function useAppWebSocket() {
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimer: any;

    const connect = () => {
      ws = new WebSocket(WS_URL);

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "new_event") {
            setEvents((prev) => [data.event, ...prev].slice(0, 50));
          }
        } catch (e) {
          console.error("WebSocket message error:", e);
        }
      };

      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      if (ws) ws.close();
    };
  }, []);

  return { events };
}
