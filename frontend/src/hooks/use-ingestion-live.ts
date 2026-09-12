"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getIngestionRun, ingestionLiveWsUrl } from "@/lib/api";
import type { AgentEvent, IngestionRun } from "@/lib/types";

export function useIngestionLive(runId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [latestScreenshot, setLatestScreenshot] = useState<string | null>(null);
  const [run, setRun] = useState<IngestionRun | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const reset = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    setEvents([]);
    setLatestScreenshot(null);
    setRun(null);
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!runId) return;

    reset();
    const ws = new WebSocket(ingestionLiveWsUrl(runId));
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data as string) as AgentEvent;
        setEvents((prev) => [...prev, event]);
        if (event.step_type === "screenshot" && typeof event.payload.jpeg_b64 === "string") {
          setLatestScreenshot(event.payload.jpeg_b64);
        }
        if (event.step_type === "status") {
          void getIngestionRun(runId).then(setRun).catch(() => undefined);
        }
      } catch {
        /* ignore malformed */
      }
    };

    const poll = setInterval(() => {
      void getIngestionRun(runId)
        .then((latest) => {
          setRun(latest);
          if (latest.status === "done" || latest.status === "error") {
            clearInterval(poll);
          }
        })
        .catch(() => undefined);
    }, 2000);

    return () => {
      clearInterval(poll);
      ws.close();
    };
  }, [runId, reset]);

  const done = run?.status === "done" || run?.status === "error";

  return {
    events,
    latestScreenshot,
    run,
    connected,
    done,
    reset,
  };
}
