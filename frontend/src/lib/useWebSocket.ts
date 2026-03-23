"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type WsState = "connecting" | "connected" | "disconnected" | "reconnecting" | "failed";

interface UseWebSocketOptions<T = unknown> {
  url: string;
  onMessage?: (data: T) => void;
  onOpen?: () => void;
  onClose?: () => void;
  enabled?: boolean;
  heartbeatIntervalMs?: number;
  maxRetries?: number;
  maxBufferSize?: number;
}

interface UseWebSocketReturn<T = unknown> {
  state: WsState;
  lastMessage: T | null;
  send: (data: unknown) => void;
  reconnect: () => void;
  retryCount: number;
}

const MIN_BACKOFF = 1000;
const MAX_BACKOFF = 30000;
const DEFAULT_MAX_RETRIES = 15;
const DEFAULT_MAX_BUFFER = 100;

export function useWebSocket<T = unknown>(
  opts: UseWebSocketOptions<T>,
): UseWebSocketReturn<T> {
  const {
    url,
    onMessage,
    onOpen,
    onClose,
    enabled = true,
    heartbeatIntervalMs = 30000,
    maxRetries = DEFAULT_MAX_RETRIES,
    maxBufferSize = DEFAULT_MAX_BUFFER,
  } = opts;

  const [state, setState] = useState<WsState>("disconnected");
  const [lastMessage, setLastMessage] = useState<T | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(MIN_BACKOFF);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const bufferRef = useRef<unknown[]>([]);
  const mountedRef = useRef(true);

  const clearTimers = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (heartbeatTimerRef.current) {
      clearInterval(heartbeatTimerRef.current);
      heartbeatTimerRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current || !enabled) return;

    clearTimers();
    setState("connecting");

    const wsUrl = (() => {
      if (!url.startsWith("/")) return url;
      const { protocol, host } = globalThis.location;
      const wsScheme = protocol === "https:" ? "wss:" : "ws:";
      return `${wsScheme}//${host}${url}`;
    })();

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setState("connected");
      backoffRef.current = MIN_BACKOFF;
      retryCountRef.current = 0;
      setRetryCount(0);
      onOpen?.();

      // Flush buffered messages
      for (const msg of bufferRef.current) {
        ws.send(typeof msg === "string" ? msg : JSON.stringify(msg));
      }
      bufferRef.current = [];

      // Start heartbeat
      heartbeatTimerRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "pong" }));
        }
      }, heartbeatIntervalMs);
    };

    ws.onmessage = (evt) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(evt.data) as T;
        setLastMessage(data);
        onMessage?.(data);
      } catch {
        // non-JSON message
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      clearTimers();
      onClose?.();

      retryCountRef.current += 1;
      setRetryCount(retryCountRef.current);

      if (retryCountRef.current >= maxRetries) {
        setState("failed");
        return;
      }

      setState("reconnecting");
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF);
      reconnectTimerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [url, enabled, onMessage, onOpen, onClose, heartbeatIntervalMs, clearTimers]);

  const send = useCallback(
    (data: unknown) => {
      const ws = wsRef.current;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(typeof data === "string" ? data : JSON.stringify(data));
      } else if (bufferRef.current.length < maxBufferSize) {
        bufferRef.current.push(data);
      }
    },
    [maxBufferSize],
  );

  const reconnect = useCallback(() => {
    wsRef.current?.close();
    backoffRef.current = MIN_BACKOFF;
    retryCountRef.current = 0;
    setRetryCount(0);
    connect();
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    if (enabled) connect();

    return () => {
      mountedRef.current = false;
      clearTimers();
      wsRef.current?.close();
      setState("disconnected");
    };
  }, [enabled, connect, clearTimers]);

  return { state, lastMessage, send, reconnect, retryCount };
}
