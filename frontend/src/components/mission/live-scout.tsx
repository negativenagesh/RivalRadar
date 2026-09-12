"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { Circle, Download, Maximize2, Radio, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ingestionRecordingUrl } from "@/lib/api";
import type { MissionTargetPreview } from "@/lib/mission-store";
import type { AgentEvent, IngestionRun } from "@/lib/types";

const LOOKBACK_PRESETS = [1, 3, 7, 14] as const;

type Shot = { id: string; b64: string; platform: string; label: string; url: string };

function shotsFromEvents(events: AgentEvent[]): Shot[] {
  return events
    .filter((e) => e.step_type === "screenshot" && typeof e.payload.jpeg_b64 === "string")
    .map((e, i) => ({
      id: `${e.sequence}-${i}`,
      b64: String(e.payload.jpeg_b64),
      platform: String(e.payload.platform ?? "scout"),
      label: String(e.payload.label ?? e.payload.url ?? `frame ${i + 1}`),
      url: String(e.payload.url ?? ""),
    }));
}

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
  const [lightbox, setLightbox] = useState<Shot | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const shots = useMemo(() => shotsFromEvents(events), [events]);

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
    if (ev.step_type === "screenshot") {
      return String(ev.payload.platform ?? "frame");
    }
    return "";
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 text-center">
      <div className="space-y-3">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          operator console
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-5xl">Live scout</h2>
        <p className="font-accent mx-auto max-w-2xl text-base italic text-muted-foreground">
          Headless agent hits every link you dropped — YouTube API + browser walks for the rest.
          Frames stack below. Not your Comet tab.
        </p>
      </div>

      <div id="scout-lookback" className="space-y-3">
        <p className="font-display text-sm font-bold">Lookback window</p>
        <div className="flex flex-wrap justify-center gap-2">
          {LOOKBACK_PRESETS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => onLookbackChange(d)}
              className={
                lookbackDays === d
                  ? "font-ui rounded-full border border-primary bg-primary/20 px-4 py-2 text-sm font-bold text-primary"
                  : "font-ui rounded-full border border-border/60 px-4 py-2 text-sm text-muted-foreground hover:border-primary/40"
              }
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-3xl border border-border/60 bg-card/40 px-4 py-4 text-left">
        <p className="font-ui mb-3 text-center text-[11px] font-semibold uppercase tracking-[0.2em] text-primary">
          mission targets · all platforms
        </p>
        <ul className="flex flex-wrap justify-center gap-2">
          {targets.map((t) => (
            <li
              key={`${t.platform}-${t.handleOrUrl}-${t.label}`}
              className="rounded-2xl border border-border/50 bg-background/60 px-3 py-2 text-xs"
            >
              <span className="font-display font-semibold">{t.label}</span>
              <span className="text-muted-foreground"> · {t.platform}</span>
              <span className="font-ui ml-1 text-[10px] text-primary">{t.source}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-4">
        <Button size="lg" className="h-14 px-10 font-display text-base" onClick={onStart} disabled={starting || status === "running" || status === "pending"}>
          {starting || status === "running" || status === "pending" ? "Scouting…" : "Start Scout"}
        </Button>
        <label className="font-ui flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={recordSession}
            onChange={(e) => onRecordChange(e.target.checked)}
            className="size-4 accent-[var(--primary)]"
          />
          Record session
        </label>
        {runId && (
          <span className="font-ui inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <Radio className={`size-3 ${connected ? "text-primary" : "text-muted-foreground"}`} />
            {connected ? "live" : "connecting…"} · {runId.slice(0, 8)}
          </span>
        )}
      </div>

      {error && (
        <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="grid gap-4 text-left lg:grid-cols-[1.4fr_1fr]">
        <div className="overflow-hidden rounded-3xl border border-border/60 bg-black/50">
          <div className="flex items-center gap-2 border-b border-border/40 px-3 py-2">
            <Circle className="size-2 fill-primary text-primary" />
            <span className="font-ui text-xs text-muted-foreground">operator feed</span>
            {status && (
              <span className="font-ui ml-auto text-xs uppercase text-primary">{status}</span>
            )}
          </div>
          <div className="relative flex aspect-video items-center justify-center bg-[radial-gradient(circle_at_center,oklch(0.87_0.24_128_/_0.08),transparent_60%)]">
            {latestScreenshot ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`data:image/jpeg;base64,${latestScreenshot}`}
                alt="Live scout screenshot"
                className="h-full w-full object-contain"
              />
            ) : (
              <p className="font-accent px-6 text-center text-sm italic text-muted-foreground">
                Hit Start Scout — multi-platform frames land here.
              </p>
            )}
          </div>
        </div>

        <div className="flex max-h-[360px] flex-col overflow-hidden rounded-3xl border border-border/60">
          <div className="font-ui border-b border-border/40 px-3 py-2 text-xs text-muted-foreground">
            event log
          </div>
          <ul className="flex-1 space-y-1 overflow-y-auto p-3 font-ui text-[11px] leading-relaxed">
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

      {shots.length > 0 && (
        <div className="space-y-3 text-left">
          <h3 className="font-display text-center text-2xl font-bold">Screenshot reel</h3>
          <p className="font-accent text-center text-sm italic text-muted-foreground">
            One-by-one captures from each platform hop — tap to expand.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {shots.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setLightbox(s)}
                className="group overflow-hidden rounded-2xl border border-border/50 bg-card/30 text-left transition hover:-translate-y-0.5 hover:border-primary/50"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`data:image/jpeg;base64,${s.b64}`}
                  alt={s.label}
                  className="aspect-video w-full object-cover"
                />
                <div className="font-ui space-y-0.5 p-2 text-[10px]">
                  <p className="font-semibold uppercase text-primary">{s.platform}</p>
                  <p className="truncate text-muted-foreground">{s.label}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {recordingReady && runId && (
        <div className="space-y-4 rounded-3xl border border-primary/30 bg-primary/5 p-6">
          <h3 className="font-shout text-2xl uppercase">Session replay</h3>
          <p className="font-accent text-sm italic text-muted-foreground">
            Control center — play inline or go fullscreen.
          </p>
          <div className="overflow-hidden rounded-2xl border border-border/60 bg-black">
            <video
              ref={videoRef}
              src={ingestionRecordingUrl(runId)}
              controls
              className="max-h-[420px] w-full"
            />
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            <Button size="lg" onClick={enterFullscreen} className="gap-2 font-display">
              <Maximize2 className="size-4" />
              Fullscreen
            </Button>
            <Button size="lg" variant="outline" onClick={() => setReplayOpen(true)} className="font-display">
              Cinema mode
            </Button>
            <Button variant="outline" asChild>
              <a href={ingestionRecordingUrl(runId)} download={`${runId}.webm`}>
                <Download className="size-3.5" />
                Download
              </a>
            </Button>
          </div>
        </div>
      )}

      {replayOpen && runId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4">
          <div className="relative w-full max-w-6xl overflow-hidden rounded-3xl border border-primary/40 bg-background shadow-[0_0_80px_-20px_oklch(0.87_0.24_128)]">
            <div className="flex items-center justify-between border-b border-border/40 px-4 py-3">
              <p className="font-ui text-xs uppercase tracking-widest text-primary">cinema control</p>
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
              className="max-h-[85vh] w-full bg-black"
            />
          </div>
        </div>
      )}

      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 p-6"
          onClick={() => setLightbox(null)}
          onKeyDown={() => undefined}
          role="presentation"
        >
          <div className="max-w-5xl" onClick={(e) => e.stopPropagation()} role="presentation">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={`data:image/jpeg;base64,${lightbox.b64}`}
              alt={lightbox.label}
              className="max-h-[80vh] w-full rounded-2xl object-contain"
            />
            <p className="font-ui mt-3 text-center text-sm text-primary">
              {lightbox.platform} · {lightbox.label}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
