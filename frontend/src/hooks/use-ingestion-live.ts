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

const TERMINAL: IngestionRunStatus[] = ["done", "error", "cancelled"];

function slimEvent(event: AgentEvent): AgentEvent {
  if (event.step_type !== "screenshot") return event;
  const rest = { ...event.payload };
  delete rest.jpeg_b64;
  return {
    ...event,
    payload: { ...rest, has_frame: true },
  };
}

function hasTerminalStatusEvent(events: AgentEvent[]): boolean {
  return events.some(
    (e) =>
      e.step_type === "status" &&
      TERMINAL.includes(String(e.payload.status ?? "") as IngestionRunStatus),
  );
}

function syntheticStatusEvent(runId: string, status: IngestionRunStatus, detail: string): AgentEvent {
  return {
    run_id: runId,
    agent_id: "system",
    service: "system",
    step_type: "status",
    sequence: Date.now(),
    timestamp: new Date().toISOString(),
    payload: { status, detail },
  };
}

export function useIngestionLive(runId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [frames, setFrames] = useState<ScoutFrame[]>([]);
  const [latestScreenshot, setLatestScreenshot] = useState<string | null>(null);
  const [run, setRun] = useState<IngestionRun | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const runStatusRef = useRef<IngestionRunStatus | null>(null);

  const refreshRun = useCallback(async () => {
    if (!runId) return null;
    try {
      const latest = await getIngestionRun(runId);
      setRun(latest);
      runStatusRef.current = latest.status;
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
      runStatusRef.current = status;
    },
    [runId],
  );

  const primeRun = useCallback((id: string, status: IngestionRunStatus = "pending") => {
    setEvents([]);
    setFrames([]);
    setLatestScreenshot(null);
    setConnected(false);
    runStatusRef.current = status;
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

  const appendTerminalIfNeeded = useCallback((latest: IngestionRun) => {
    if (!TERMINAL.includes(latest.status)) return;
    setEvents((prev) => {
      if (hasTerminalStatusEvent(prev)) return prev;
      return [
        ...prev,
        syntheticStatusEvent(
          latest.id,
          latest.status,
          latest.error_detail ||
            "run finished (status polled — live event feed had dropped)",
        ),
      ];
    });
  }, []);

  useEffect(() => {
    if (!runId) return;

    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let attempt = 0;

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

    const connect = () => {
      if (cancelled) return;
      const ws = new WebSocket(ingestionLiveWsUrl(runId));
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        attempt = 0;
        setConnected(true);
      };
      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        const st = runStatusRef.current;
        if (st === "running" || st === "pending") {
          attempt += 1;
          const delay = Math.min(8_000, 500 * 2 ** Math.min(attempt, 4));
          reconnectTimer = setTimeout(connect, delay);
        }
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
                label: String(
                  event.payload.label ?? event.payload.url ?? `frame ${prev.length + 1}`,
                ),
                url: String(event.payload.url ?? ""),
                handle: typeof event.payload.handle === "string" ? event.payload.handle : undefined,
                mime: typeof event.payload.mime === "string" ? event.payload.mime : "jpeg",
              },
            ]);
          }
          setEvents((prev) => [...prev, slimEvent(event)]);
          if (event.step_type === "status") {
            const st = String(event.payload.status ?? "") as IngestionRunStatus;
            if (TERMINAL.includes(st) || st === "running" || st === "pending") {
              runStatusRef.current = st;
            }
            void refreshRun();
          }
        } catch {
          /* ignore malformed */
        }
      };
    };

    connect();

    const poll = setInterval(() => {
      void refreshRun().then((latest) => {
        if (!latest || cancelled) return;
        if (TERMINAL.includes(latest.status)) {
          appendTerminalIfNeeded(latest);
          clearInterval(poll);
          wsRef.current?.close();
        }
      });
    }, 2500);

    void Promise.resolve().then(() => {
      if (!cancelled) void refreshRun();
    });

    return () => {
      cancelled = true;
      clearInterval(poll);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [runId, refreshRun, appendTerminalIfNeeded]);

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
