"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { RealtimeEvent, RealtimeTopic } from "@/types/api";

/**
 * One WebSocket for the whole app.
 *
 * The server sends "something changed" events carrying identifiers only; screens
 * subscribe to the topics they care about and refetch over REST. That keeps every
 * permission check on the server and means a client can never be pushed data it would
 * not have been allowed to ask for.
 */

type Listener = (event: RealtimeEvent) => void;

export type ConnectionState = "connecting" | "open" | "closed";

interface RealtimeContextValue {
  status: ConnectionState;
  subscribe: (topics: RealtimeTopic[], listener: Listener) => () => void;
}

const RealtimeContext = createContext<RealtimeContextValue | null>(null);

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/api/v1/ws";
const BASE_RETRY_MS = 1_000;
const MAX_RETRY_MS = 30_000;

export function RealtimeProvider({
  enabled = true,
  children,
}: {
  /** Off on the auth screens: there is no session yet, so the socket would be refused. */
  enabled?: boolean;
  children: ReactNode;
}) {
  const [status, setStatus] = useState<ConnectionState>("closed");
  const listeners = useRef(new Map<Listener, Set<RealtimeTopic>>());
  const socket = useRef<WebSocket | null>(null);
  const retryAttempt = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const subscribe = useCallback((topics: RealtimeTopic[], listener: Listener) => {
    listeners.current.set(listener, new Set(topics));
    return () => {
      listeners.current.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      setStatus("connecting");

      let ws: WebSocket;
      try {
        // The session cookie rides along automatically: same host, so it is first-party.
        ws = new WebSocket(WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }
      socket.current = ws;

      ws.onopen = () => {
        if (disposed) return;
        retryAttempt.current = 0;
        setStatus("open");
      };

      ws.onmessage = (message) => {
        let event: RealtimeEvent;
        try {
          event = JSON.parse(message.data as string) as RealtimeEvent;
        } catch {
          return; // A frame we cannot parse is not worth tearing the connection down for.
        }
        for (const [listener, topics] of listeners.current) {
          if (topics.has(event.type)) listener(event);
        }
      };

      ws.onerror = () => ws.close();

      ws.onclose = () => {
        socket.current = null;
        if (disposed) return;
        setStatus("closed");
        scheduleReconnect();
      };
    };

    const scheduleReconnect = () => {
      if (disposed) return;
      // Exponential backoff, capped: a backend restart should not become a retry storm.
      const delay = Math.min(BASE_RETRY_MS * 2 ** retryAttempt.current, MAX_RETRY_MS);
      retryAttempt.current += 1;
      retryTimer.current = setTimeout(connect, delay);
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer.current) clearTimeout(retryTimer.current);
      socket.current?.close();
      socket.current = null;
    };
  }, [enabled]);

  const value = useMemo(() => ({ status, subscribe }), [status, subscribe]);
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

/**
 * Run `onEvent` when one of `topics` arrives.
 *
 * The callback is held in a ref so a caller can pass an inline function without
 * resubscribing on every render.
 */
export function useRealtime(topics: RealtimeTopic[], onEvent: Listener): void {
  const context = useContext(RealtimeContext);
  const callback = useRef(onEvent);
  callback.current = onEvent;

  const topicKey = topics.join(",");

  useEffect(() => {
    if (!context || topicKey === "") return;
    return context.subscribe(topicKey.split(",") as RealtimeTopic[], (event) =>
      callback.current(event),
    );
  }, [context, topicKey]);
}

/** Connection state, for the "Live" indicator in the top bar. */
export function useRealtimeStatus(): ConnectionState {
  return useContext(RealtimeContext)?.status ?? "closed";
}
