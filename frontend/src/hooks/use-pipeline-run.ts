"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { getPipelineRun } from "@/lib/api";
import type { PipelineRun } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export function usePipelineRun() {
  const [run, setRun] = useState<PipelineRun | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const track = useCallback(
    (runId: string) => {
      stopPolling();
      timerRef.current = setInterval(async () => {
        try {
          const latest = await getPipelineRun(runId);
          setRun(latest);
          if (latest.status === "done" || latest.status === "error") {
            stopPolling();
          }
        } catch {
          stopPolling();
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  useEffect(() => stopPolling, [stopPolling]);

  return { run, track, isRunning: run?.status === "pending" || run?.status === "running" };
}
