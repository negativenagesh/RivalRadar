"use client";

import { Circle, Download, Radio } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ingestionRecordingUrl } from "@/lib/api";
import type { AgentEvent, IngestionRun } from "@/lib/types";

export function LiveScout({
  recordSession,
  onRecordChange,
  onStart,
  starting,
  runId,
  connected,
  events,
  latestScreenshot,
  run,
  error,
}: {
  recordSession: boolean;
  onRecordChange: (v: boolean) => void;
  onStart: () => void;
  starting: boolean;
  runId: string | null;
  connected: boolean;
  events: AgentEvent[];
  latestScreenshot: string | null;
  run: IngestionRun | null;
  error: string | null;
}) {
  const status = run?.status;
  const recordingReady = Boolean(run?.recording_key) && status === "done";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Live scout</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Start the headless browser. Watch frames stream in. Optional WebM recording for your
          team replay.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Demo scout browses RivalRadar&apos;s bundled mock social profiles (live screenshots
          work offline). Your real URLs stay saved for report context.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <Button size="lg" onClick={onStart} disabled={starting || status === "running" || status === "pending"}>
          {starting || status === "running" || status === "pending" ? "Scouting…" : "Start Scout"}
        </Button>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={recordSession}
            onChange={(e) => onRecordChange(e.target.checked)}
            className="size-4 accent-[var(--primary)]"
          />
          Record session
        </label>
        {runId && (
          <span className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
            <Radio className={`size-3 ${connected ? "text-primary" : "text-muted-foreground"}`} />
            {connected ? "live" : "connecting…"} · {runId.slice(0, 8)}
          </span>
        )}
      </div>

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="overflow-hidden rounded-xl border border-border/60 bg-black/40">
          <div className="flex items-center gap-2 border-b border-border/40 px-3 py-2">
            <Circle className="size-2 fill-primary text-primary" />
            <span className="font-mono text-xs text-muted-foreground">browser frame</span>
            {status && (
              <span className="ml-auto font-mono text-xs uppercase text-primary">{status}</span>
            )}
          </div>
          <div className="relative flex aspect-video items-center justify-center bg-[radial-gradient(circle_at_center,oklch(0.87_0.24_128_/_0.06),transparent_60%)]">
            {latestScreenshot ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`data:image/jpeg;base64,${latestScreenshot}`}
                alt="Live scout screenshot"
                className="h-full w-full object-contain"
              />
            ) : (
              <p className="px-6 text-center text-sm text-muted-foreground">
                Hit Start Scout — frames appear here as the agent navigates.
              </p>
            )}
          </div>
        </div>

        <div className="flex max-h-[360px] flex-col overflow-hidden rounded-xl border border-border/60">
          <div className="border-b border-border/40 px-3 py-2 font-mono text-xs text-muted-foreground">
            event log
          </div>
          <ul className="flex-1 space-y-1 overflow-y-auto p-3 font-mono text-[11px] leading-relaxed">
            {events.length === 0 && (
              <li className="text-muted-foreground">Waiting for events…</li>
            )}
            {events.map((ev, i) => (
              <li key={`${ev.sequence}-${i}`} className="text-muted-foreground">
                <span className="text-primary">{ev.step_type}</span>{" "}
                {ev.step_type === "nav" && String(ev.payload.url ?? "")}
                {ev.step_type === "action" && String(ev.payload.detail ?? ev.payload.action ?? "")}
                {ev.step_type === "status" && String(ev.payload.status ?? "")}
                {ev.step_type === "error" && String(ev.payload.detail ?? "")}
                {ev.step_type === "log" && String(ev.payload.message ?? "")}
                {ev.step_type === "screenshot" && "frame"}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {recordingReady && runId && (
        <Button variant="outline" asChild>
          <a href={ingestionRecordingUrl(runId)} download={`${runId}.webm`}>
            <Download className="size-3.5" />
            Download recording
          </a>
        </Button>
      )}
    </div>
  );
}
