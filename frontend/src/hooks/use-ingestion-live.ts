"use client";

import { useEffect, useRef, useState } from "react";

import { getIngestionRun, ingestionLiveWsUrl } from "@/lib/api";
import type { AgentEvent, IngestionRun } from "@/lib/types";

export function useIngestionLive(runId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [latestScreenshot, setLatestScreenshot] = useState<string | null>(null);
  const [run, setRun] = useState<IngestionRun | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!runId) return;

    let cancelled = false;
    const ws = new WebSocket(ingestionLiveWsUrl(runId));
    wsRef.current = ws;

    // Defer state reset so we don't setState synchronously inside the effect body.
    void Promise.resolve().then(() => {
      if (cancelled) return;
      setEvents([]);
      setLatestScreenshot(null);
      setRun(null);
      setConnected(false);
    });

    ws.onopen = () => {
      if (!cancelled) setConnected(true);
    };
    ws.onclose = () => {
      if (!cancelled) setConnected(false);
    };
    ws.onerror = () => {
      if (!cancelled) setConnected(false);
    };
    ws.onmessage = (msg) => {
      if (cancelled) return;
      try {
        const event = JSON.parse(msg.data as string) as AgentEvent;
        setEvents((prev) => [...prev, event]);
        if (event.step_type === "screenshot" && typeof event.payload.jpeg_b64 === "string") {
          setLatestScreenshot(event.payload.jpeg_b64);
        }
        if (event.step_type === "status") {
          void getIngestionRun(runId).then((latest) => {
            if (!cancelled) setRun(latest);
          }).catch(() => undefined);
        }
      } catch {
        /* ignore malformed */
      }
    };

    const poll = setInterval(() => {
      void getIngestionRun(runId)
        .then((latest) => {
          if (cancelled) return;
          setRun(latest);
          if (latest.status === "done" || latest.status === "error") {
            clearInterval(poll);
          }
        })
        .catch(() => undefined);
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(poll);
      ws.close();
      if (wsRef.current === ws) wsRef.current = null;
    };
  }, [runId]);

  const done = run?.status === "done" || run?.status === "error";

  return {
    events,
    latestScreenshot,
    run,
    connected,
    done,
  };
}
