"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getIngestionRun, ingestionLiveWsUrl } from "@/lib/api";
import type { AgentEvent, IngestionRun, IngestionRunStatus } from "@/lib/types";

export type ScoutFrame = {
  id: string;
  b64: string;
  platform: string;
  label: string;
  url: string;
  mime?: string;
  handle?: string;
};

function slimEvent(event: AgentEvent): AgentEvent {
  if (event.step_type !== "screenshot") return event;
  const rest = { ...event.payload };
  delete rest.jpeg_b64;
  return {
    ...event,
    payload: { ...rest, has_frame: true },
  };
}

export function useIngestionLive(runId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [frames, setFrames] = useState<ScoutFrame[]>([]);
  const [latestScreenshot, setLatestScreenshot] = useState<string | null>(null);
  const [run, setRun] = useState<IngestionRun | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const refreshRun = useCallback(async () => {
    if (!runId) return null;
    try {
      const latest = await getIngestionRun(runId);
      setRun(latest);
      return latest;
    } catch {
      return null;
    }
  }, [runId]);

  const markOptimistic = useCallback(
    (status: IngestionRunStatus, detail?: string) => {
      setRun((prev) => {
        if (!runId) return prev;
        const base: IngestionRun = prev ?? {
          id: runId,
          connector_type: "auto",
          status,
          record: false,
          recording_key: null,
          error_detail: detail ?? null,
          result: null,
          created_at: new Date().toISOString(),
        };
        return {
          ...base,
          status,
          error_detail: detail ?? base.error_detail,
        };
      });
    },
    [runId],
  );

  const primeRun = useCallback((id: string, status: IngestionRunStatus = "pending") => {
    setEvents([]);
    setFrames([]);
    setLatestScreenshot(null);
    setConnected(false);
    setRun({
      id,
      connector_type: "auto",
      status,
      record: false,
      recording_key: null,
      error_detail: null,
      result: null,
      created_at: new Date().toISOString(),
    });
  }, []);

  useEffect(() => {
    if (!runId) return;

    let cancelled = false;
    const ws = new WebSocket(ingestionLiveWsUrl(runId));
    wsRef.current = ws;

    void Promise.resolve().then(() => {
      if (cancelled) return;
      setEvents([]);
      setFrames([]);
      setLatestScreenshot(null);
      setConnected(false);
      setRun((prev) =>
        prev?.id === runId
          ? prev
          : {
              id: runId,
              connector_type: "auto",
              status: "pending",
              record: false,
              recording_key: null,
              error_detail: null,
              result: null,
              created_at: new Date().toISOString(),
            },
      );
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
        if (event.step_type === "screenshot" && typeof event.payload.jpeg_b64 === "string") {
          const b64 = event.payload.jpeg_b64;
          setLatestScreenshot(b64);
          setFrames((prev) => [
            ...prev,
            {
              id: `${event.sequence}-${prev.length}`,
              b64,
              platform: String(event.payload.platform ?? "scout"),
              label: String(event.payload.label ?? event.payload.url ?? `frame ${prev.length + 1}`),
              url: String(event.payload.url ?? ""),
              handle: typeof event.payload.handle === "string" ? event.payload.handle : undefined,
              mime: typeof event.payload.mime === "string" ? event.payload.mime : "jpeg",
            },
          ]);
        }
        setEvents((prev) => [...prev, slimEvent(event)]);
        if (event.step_type === "status") {
          void refreshRun();
        }
      } catch {
        /* ignore malformed */
      }
    };

    const poll = setInterval(() => {
      void refreshRun().then((latest) => {
        if (!latest || cancelled) return;
        if (latest.status === "done" || latest.status === "error" || latest.status === "cancelled") {
          clearInterval(poll);
        }
      });
    }, 4000);

    // Defer so we don't setState synchronously inside the effect body (eslint).
    void Promise.resolve().then(() => {
      if (!cancelled) void refreshRun();
    });

    return () => {
      cancelled = true;
      clearInterval(poll);
      ws.close();
      if (wsRef.current === ws) wsRef.current = null;
    };
  }, [runId, refreshRun]);

  const done =
    run?.status === "done" || run?.status === "error" || run?.status === "cancelled";

  return {
    events,
    frames,
    latestScreenshot,
    run,
    connected,
    done,
    refreshRun,
    markOptimistic,
    primeRun,
  };
}
