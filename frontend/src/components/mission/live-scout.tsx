"use client";

import { useCallback, useRef, useState } from "react";
import { Circle, Download, Maximize2, Radio, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ingestionRecordingUrl } from "@/lib/api";
import type { MissionTargetPreview } from "@/lib/mission-store";
import type { AgentEvent, IngestionRun } from "@/lib/types";

const LOOKBACK_PRESETS = [1, 3, 7, 14] as const;

export function LiveScout({
  recordSession,
  onRecordChange,
  lookbackDays,
  onLookbackChange,
  targets,
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
  lookbackDays: number;
  onLookbackChange: (days: number) => void;
  targets: MissionTargetPreview[];
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
  const [replayOpen, setReplayOpen] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const enterFullscreen = useCallback(() => {
    const el = videoRef.current;
    if (!el) return;
    void el.requestFullscreen?.();
  }, []);

  function eventDetail(ev: AgentEvent): string {
    if (ev.step_type === "nav") return String(ev.payload.url ?? "");
    if (ev.step_type === "action") {
      return String(ev.payload.detail ?? ev.payload.action ?? ev.payload.extracted ?? "");
    }
    if (ev.step_type === "status") return String(ev.payload.status ?? "");
    if (ev.step_type === "error") return String(ev.payload.detail ?? "");
    if (ev.step_type === "log") return String(ev.payload.message ?? "");
    if (ev.step_type === "screenshot") return "frame";
    return "";
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold">Live scout</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Start the headless browser. Watch frames stream in. Optional WebM recording for your
          team replay.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Scout runs in our headless Playwright agent — not your open Comet/Chrome tabs. YouTube
          channels use Data API v3 (yt-dlp fallback). Other networks use RivalRadar mock profiles
          for offline-safe screenshots; your real URLs stay for report context.
        </p>
      </div>

      <div id="scout-lookback" className="space-y-2">
        <p className="text-sm font-medium">Lookback window (required)</p>
        <div className="flex flex-wrap gap-2">
          {LOOKBACK_PRESETS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => onLookbackChange(d)}
              className={
                lookbackDays === d
                  ? "rounded-lg border border-primary bg-primary/15 px-3 py-1.5 text-sm font-semibold text-primary"
                  : "rounded-lg border border-border/60 px-3 py-1.5 text-sm text-muted-foreground hover:border-primary/40"
              }
            >
              {d}d
            </button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          Pull rival uploads / posts from the last {lookbackDays} days.
        </p>
      </div>

      <div className="rounded-xl border border-border/60 bg-card/30 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-primary">Mission targets</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {targets.map((t) => (
            <li
              key={`${t.platform}-${t.handleOrUrl}-${t.label}`}
              className="rounded-lg border border-border/50 bg-background/50 px-2.5 py-1.5 text-xs"
            >
              <span className="font-medium">{t.label}</span>
              <span className="text-muted-foreground"> · {t.platform} · {t.handleOrUrl}</span>
              <span className="ml-1 font-mono text-[10px] text-primary">{t.source}</span>
            </li>
          ))}
        </ul>
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
            <span className="font-mono text-xs text-muted-foreground">operator feed</span>
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
                <span className="text-primary">{ev.step_type}</span> {eventDetail(ev)}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {recordingReady && runId && (
        <div className="flex flex-wrap gap-3">
          <Button size="lg" onClick={() => setReplayOpen(true)}>
            Replay recording
          </Button>
          <Button variant="outline" asChild>
            <a href={ingestionRecordingUrl(runId)} download={`${runId}.webm`}>
              <Download className="size-3.5" />
              Download
            </a>
          </Button>
        </div>
      )}

      {replayOpen && runId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
          <div className="relative w-full max-w-5xl overflow-hidden rounded-2xl border border-border/60 bg-background shadow-2xl">
            <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
              <p className="font-mono text-xs text-muted-foreground">session replay · fullscreen ok</p>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={enterFullscreen}>
                  <Maximize2 className="size-3.5" />
                  Fullscreen
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setReplayOpen(false)}>
                  <X className="size-3.5" />
                </Button>
              </div>
            </div>
            <video
              ref={videoRef}
              src={ingestionRecordingUrl(runId)}
              controls
              autoPlay
              className="max-h-[80vh] w-full bg-black"
            />
          </div>
        </div>
      )}
    </div>
  );
}
