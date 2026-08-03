import { useEffect, useRef } from "react";

import { api } from "../../api/api";
import { useAppDispatch, useAppSelector } from "../../app/hooks";

const WS_BASE = import.meta.env.VITE_WS_BASE || "/ws";

/**
 * Opens a WebSocket to the backend event stream and invalidates the Event
 * cache whenever a new event arrives, so lists/badges refresh in real time.
 * Reconnects with a simple backoff.
 */
export function useLiveEvents() {
  const dispatch = useAppDispatch();
  const access = useAppSelector((s) => s.auth.access);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!access) return;
    let closed = false;
    let retry = 0;
    let timer: number | undefined;

    const url = () => {
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const base = WS_BASE.startsWith("http")
        ? WS_BASE.replace(/^http/, "ws")
        : `${proto}://${window.location.host}${WS_BASE}`;
      return `${base}/events?token=${access}`;
    };

    const connect = () => {
      const ws = new WebSocket(url());
      wsRef.current = ws;
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "event") {
            dispatch(api.util.invalidateTags(["Event"]));
          }
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        retry = Math.min(retry + 1, 6);
        timer = window.setTimeout(connect, retry * 1000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      wsRef.current?.close();
    };
  }, [access, dispatch]);
}
