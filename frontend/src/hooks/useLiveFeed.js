import { useEffect, useRef, useState, useCallback } from "react";

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/ws/live`;

/**
 * useLiveFeed — connects to the backend WebSocket, auto-reconnects with
 * backoff, and exposes the latest snapshot plus a connection status.
 *
 * Never throws on a missing field: consumers read snapshot with defaults.
 */
export function useLiveFeed() {
  const [snapshot, setSnapshot] = useState(null);
  const [status, setStatus] = useState("connecting"); // connecting | connected | disconnected
  const wsRef = useRef(null);
  const retryRef = useRef(0);
  const stoppedRef = useRef(false);

  const connect = useCallback(() => {
    if (stoppedRef.current) return;
    setStatus((s) => (s === "connected" ? s : "connecting"));
    let ws;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      retryRef.current = 0;
      setStatus("connected");
    };
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        setSnapshot(data);
      } catch (e) {
        /* ignore malformed frame */
      }
    };
    ws.onclose = () => {
      setStatus("disconnected");
      scheduleReconnect();
    };
    ws.onerror = () => {
      try {
        ws.close();
      } catch (e) {
        /* noop */
      }
    };
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (stoppedRef.current) return;
    retryRef.current = Math.min(retryRef.current + 1, 6);
    const delay = Math.min(1000 * 2 ** (retryRef.current - 1), 15000);
    setTimeout(() => connect(), delay);
  }, [connect]);

  useEffect(() => {
    stoppedRef.current = false;
    connect();
    return () => {
      stoppedRef.current = true;
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch (e) {
          /* noop */
        }
      }
    };
  }, [connect]);

  return { snapshot, status, wsUrl: WS_URL };
}
