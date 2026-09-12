"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  Circle,
  Download,
  ExternalLink,
  Maximize2,
  Radio,
  X,
} from "lucide-react";

import { ConnectCenter } from "@/components/mission/connect-center";
import { Button } from "@/components/ui/button";
import { ingestionRecordingUrl } from "@/lib/api";
import {
  PLATFORM_LABELS,
  requiredConnectPlatforms,
  type MissionTargetPreview,
} from "@/lib/mission-store";
import type { AgentEvent, IngestionRun } from "@/lib/types";

const LOOKBACK_PRESETS = [1, 3, 7, 14] as const;

const SOURCE_LABELS: Record<string, string> = {
  "youtube-api": "YouTube API",
  "yt-dlp": "yt-dlp",
  browser: "Browser",
  "mock-browser": "Mock",
};

type Shot = {
  id: string;
  b64: string;
  platform: string;
  label: string;
  url: string;
  company: string;
  mime?: string;
};

function frameSrc(b64: string, mime?: string): string {
  return `data:image/${mime || "jpeg"};base64,${b64}`;
}

function platformName(key: string): string {
  return PLATFORM_LABELS[key.toLowerCase()] ?? key;
}

function sourceName(key: string): string {
  return SOURCE_LABELS[key] ?? key;
}

function externalHref(t: MissionTargetPreview): string | null {
  if (t.url?.startsWith("http")) return t.url;
  if (t.platform === "mock") return null;
  const handle = t.handleOrUrl.replace(/^@/, "");
  if (!handle) return null;
  if (t.platform === "youtube") return `https://www.youtube.com/@${handle}`;
  if (t.platform === "x") return `https://x.com/${handle}`;
  if (t.platform === "instagram") return `https://instagram.com/${handle}`;
  if (t.platform === "linkedin") return `https://linkedin.com/company/${handle}`;
  if (t.platform === "tiktok") return `https://tiktok.com/@${handle}`;
  if (t.platform === "threads") return `https://threads.net/@${handle}`;
  return null;
}

function TargetChip({ t }: { t: MissionTargetPreview }) {
  const href = externalHref(t);
  const inner = (
    <>
      <span className="font-display font-semibold">{platformName(t.platform)}</span>
      <span className="font-ui text-muted-foreground">@{t.handleOrUrl.replace(/^@/, "")}</span>
      <span className="font-ui rounded-full bg-background/70 px-1.5 py-0.5 text-[10px] text-primary">
        {sourceName(t.source)}
      </span>
      {href ? <ExternalLink className="size-3 opacity-70" aria-hidden /> : null}
    </>
  );

  const className =
    "inline-flex items-center gap-2 rounded-full border border-border/50 bg-background/70 px-3.5 py-2 text-xs transition hover:-translate-y-0.5 hover:border-primary/50 hover:bg-primary/10 hover:shadow-[0_0_24px_-12px_oklch(0.87_0.24_128)]";

  if (!href) {
    return <span className={className}>{inner}</span>;
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
      title={`Open ${platformName(t.platform)} profile`}
    >
      {inner}
    </a>
  );
}

function shotsFromEvents(events: AgentEvent[], targets: MissionTargetPreview[]): Shot[] {
  return events
    .filter((e) => e.step_type === "screenshot" && typeof e.payload.jpeg_b64 === "string")
    .map((e, i) => {
      const platform = String(e.payload.platform ?? "scout");
      const label = String(e.payload.label ?? e.payload.url ?? `frame ${i + 1}`);
      const url = String(e.payload.url ?? "");
      const match =
        targets.find((t) => t.url && url && (url.includes(t.url) || t.url.includes(url))) ||
        targets.find(
          (t) =>
            t.platform.toLowerCase() === platform.toLowerCase() &&
            (label.toLowerCase().includes(t.handleOrUrl.toLowerCase().replace(/^@/, "")) ||
              url.toLowerCase().includes(t.handleOrUrl.toLowerCase().replace(/^@/, ""))),
        ) ||
        targets.find((t) => t.platform.toLowerCase() === platform.toLowerCase());
      return {
        id: `${e.sequence}-${i}`,
        b64: String(e.payload.jpeg_b64),
        platform,
        label,
        url,
        company: match?.label ?? String(e.payload.company ?? "Scout"),
        mime: String(e.payload.mime ?? "jpeg"),
      };
    });
}

function shotsFromFrames(
  frames: { id: string; b64: string; platform: string; label: string; url: string; mime?: string }[],
  targets: MissionTargetPreview[],
): Shot[] {
  return frames.map((f) => {
    const match =
      targets.find((t) => t.url && f.url && (f.url.includes(t.url) || t.url.includes(f.url))) ||
      targets.find(
        (t) =>
          t.platform.toLowerCase() === f.platform.toLowerCase() &&
          (f.label.toLowerCase().includes(t.handleOrUrl.toLowerCase().replace(/^@/, "")) ||
            f.url.toLowerCase().includes(t.handleOrUrl.toLowerCase().replace(/^@/, ""))),
      ) ||
      targets.find((t) => t.platform.toLowerCase() === f.platform.toLowerCase());
    return {
      ...f,
      company: match?.label ?? "Scout",
    };
  });
}


type YtDlpIntel = {
  channel_title: string;
  videos: { title: string; views: number; likes: number; comments: number; posted_at: string; url: string }[];
  date_from?: string;
  date_to?: string;
};

function ytdlpIntelFromEvents(events: AgentEvent[]): YtDlpIntel | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const e = events[i];
    if (e.step_type === "artifact" && e.payload?.kind === "ytdlp_intel") {
      return {
        channel_title: String(e.payload.channel_title ?? "YouTube"),
        videos: Array.isArray(e.payload.videos)
          ? (e.payload.videos as YtDlpIntel["videos"])
          : [],
        date_from: e.payload.date_from ? String(e.payload.date_from) : undefined,
        date_to: e.payload.date_to ? String(e.payload.date_to) : undefined,
      };
    }
  }
  return null;
}

/** Operator feed shows Playwright hops; yt-dlp/API actions stay out of the log. */
function operatorLogEvents(events: AgentEvent[]): AgentEvent[] {
  return events.filter((e) => {
    if (e.agent_id === "ingestion.youtube") {
      return e.step_type === "error" || e.step_type === "screenshot";
    }
    return e.step_type !== "artifact";
  });
}

export function scoutActionLabel(input: {
  locked: boolean;
  starting: boolean;
  stopping: boolean;
  live: boolean;
}): string {
  if (input.locked) return "Connect platforms to unlock";
  if (input.stopping) return "Stopping…";
  if (input.starting) return "Starting scout…";
  if (input.live) return "Stop Scout";
  return "Start Scout";
}

export function LiveScout({
  recordSession,
  onRecordChange,
  lookbackDays,
  onLookbackChange,
  dateFrom,
  dateTo,
  onCustomRangeChange,
  targets,
  onStart,
  onKill,
  starting,
  killing,
  runId,
  connected,
  events,
  frames,
  latestScreenshot,
  run,
  error,
}: {
  recordSession: boolean;
  onRecordChange: (v: boolean) => void;
  lookbackDays: number;
  onLookbackChange: (days: number) => void;
  dateFrom: string | null;
  dateTo: string | null;
  onCustomRangeChange: (from: string | null, to: string | null) => void;
  targets: MissionTargetPreview[];
  onStart: () => void;
  onKill?: () => void;
  starting: boolean;
  killing?: boolean;
  runId: string | null;
  connected: boolean;
  events: AgentEvent[];
  frames?: { id: string; b64: string; platform: string; label: string; url: string; mime?: string }[];
  latestScreenshot: string | null;
  run: IngestionRun | null;
  error: string | null;
}) {
  const status = run?.status;
  const recordingReady = Boolean(run?.recording_key) && status === "done";
  const [replayOpen, setReplayOpen] = useState(false);
  const [lightbox, setLightbox] = useState<Shot | null>(null);
  const requiredPlatforms = useMemo(() => requiredConnectPlatforms(targets), [targets]);
  const [connectionsReady, setConnectionsReady] = useState(
    () => requiredConnectPlatforms(targets).length === 0,
  );
  const [missingPlatforms, setMissingPlatforms] = useState<string[]>([]);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const shots = useMemo(
    () =>
      frames && frames.length > 0
        ? shotsFromFrames(frames, targets)
        : shotsFromEvents(events, targets),
    [frames, events, targets],
  );
  const ytdlpIntel = useMemo(() => ytdlpIntelFromEvents(events), [events]);
  const logEvents = useMemo(() => operatorLogEvents(events), [events]);

  const brandTargets = useMemo(() => targets.filter((t) => t.role === "brand"), [targets]);
  const rivalRows = useMemo(() => {
    const map = new Map<string, MissionTargetPreview[]>();
    for (const t of targets) {
      if (t.role !== "rival") continue;
      const list = map.get(t.label) ?? [];
      list.push(t);
      map.set(t.label, list);
    }
    return [...map.entries()];
  }, [targets]);

  const onGateChange = useCallback(
    (state: { ready: boolean; missing: string[] }) => {
      setConnectionsReady(state.ready);
      setMissingPlatforms(state.missing);
    },
    [],
  );

  // Prefer Connect Center gate; until it reports, only lock when Connect is required.
  const scoutLocked = requiredPlatforms.length > 0 ? !connectionsReady : false;
  const priorActive = status === "running" || status === "pending";
  const scoutBusy = starting || Boolean(killing);
  const actionLabel = scoutActionLabel({
    locked: scoutLocked,
    starting,
    stopping: Boolean(killing),
    live: priorActive,
  });

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
    if (ev.step_type === "status") {
      const st = String(ev.payload.status ?? "");
      const detail = ev.payload.detail ? ` · ${String(ev.payload.detail)}` : "";
      return `${st}${detail}`;
    }
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
              onClick={() => {
                onCustomRangeChange(null, null);
                onLookbackChange(d);
              }}
              className={
                !dateFrom && lookbackDays === d
                  ? "font-ui rounded-full border border-primary bg-primary/20 px-4 py-2 text-sm font-bold text-primary"
                  : "font-ui rounded-full border border-border/60 px-4 py-2 text-sm text-muted-foreground hover:border-primary/40"
              }
            >
              {d}d
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-2 pt-1">
          <label className="font-ui text-xs text-muted-foreground">
            From
            <input
              type="date"
              value={dateFrom ?? ""}
              onChange={(e) => onCustomRangeChange(e.target.value || null, dateTo)}
              className="ml-2 rounded-lg border border-border/60 bg-background px-2 py-1 text-sm text-foreground"
            />
          </label>
          <label className="font-ui text-xs text-muted-foreground">
            To
            <input
              type="date"
              value={dateTo ?? ""}
              onChange={(e) => onCustomRangeChange(dateFrom, e.target.value || null)}
              className="ml-2 rounded-lg border border-border/60 bg-background px-2 py-1 text-sm text-foreground"
            />
          </label>
          {(dateFrom || dateTo) && (
            <button
              type="button"
              className="font-ui text-xs text-primary underline"
              onClick={() => onCustomRangeChange(null, null)}
            >
              Clear custom
            </button>
          )}
        </div>
      </div>

      <ConnectCenter targets={targets} onGateChange={onGateChange} />

      <div className="mx-auto w-full max-w-3xl rounded-3xl border border-border/60 bg-gradient-to-b from-card/50 to-card/20 px-6 py-6 text-center shadow-[inset_0_1px_0_oklch(1_0_0_/_0.04)]">
        <p className="font-ui mb-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
          mission targets · all platforms
        </p>
        <p className="font-accent mb-5 text-sm italic text-muted-foreground">
          Tap a chip to open that profile in a new tab.
        </p>

        {brandTargets.length > 0 && (
          <div className="mb-6 space-y-3">
            <p className="font-ui text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
              Your company
            </p>
            <p className="font-display text-xl font-bold sm:text-2xl">{brandTargets[0]?.label}</p>
            <ul className="flex flex-wrap items-center justify-center gap-2">
              {brandTargets.map((t) => (
                <li key={`brand-${t.platform}-${t.handleOrUrl}`}>
                  <TargetChip t={t} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {rivalRows.length > 0 && (
          <div className="space-y-5 border-t border-border/40 pt-5">
            <p className="font-ui text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Rivals
            </p>
            {rivalRows.map(([name, platforms]) => (
              <div key={name} className="space-y-2.5">
                <p className="font-display text-lg font-bold">{name}</p>
                <ul className="flex flex-wrap items-center justify-center gap-2">
                  {platforms.map((t) => (
                    <li key={`rival-${name}-${t.platform}-${t.handleOrUrl}`}>
                      <TargetChip t={t} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}

        {brandTargets.length === 0 && rivalRows.length === 0 && (
          <p className="font-accent text-sm italic text-muted-foreground">
            Add social links in Context — they show up here as clickable targets.
          </p>
        )}
      </div>

      <div className="flex flex-col items-center gap-3">
        {scoutLocked && (
          <p className="font-ui max-w-xl rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
            Start Scout is locked until you connect:{" "}
            {missingPlatforms.map((p) => PLATFORM_LABELS[p] ?? p).join(", ") || "required platforms"}.
            YouTube / yt-dlp does not need a Connect widget.
          </p>
        )}
        {priorActive && !scoutLocked && (
          <p
            role="status"
            className="font-ui max-w-xl rounded-2xl border border-primary/40 bg-primary/10 px-4 py-2 text-sm text-primary"
          >
            Scout is live — post images stream below as they ingest. Hit Stop Scout, then Continue to Findings.
          </p>
        )}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <Button
            size="lg"
            variant={priorActive && !starting ? "destructive" : "default"}
            className="h-14 px-10 font-display text-base"
            onClick={() => {
              if (priorActive && onKill) {
                onKill();
                return;
              }
              onStart();
            }}
            disabled={scoutBusy || scoutLocked}
            title={
              scoutLocked
                ? "Connect every Context platform first"
                : priorActive
                  ? "Stop this scout"
                  : undefined
            }
          >
            {actionLabel}
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
              {connected ? "live" : starting || priorActive ? "connecting…" : "idle"} · {runId.slice(0, 8)}
            </span>
          )}
        </div>
      </div>

      {error && (
        <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      )}
      {run?.status === "cancelled" && !starting && !killing && (
        <p className="rounded-2xl border border-border/50 bg-card/30 px-4 py-3 text-sm text-muted-foreground">
          Scout stopped. Continue to Findings to review ingested posts, or Start Scout again.
        </p>
      )}
      {run?.status === "error" && run.error_detail && (
        <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          Scout failed: {run.error_detail}
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
                src={frameSrc(latestScreenshot, frames?.at(-1)?.mime)}
                alt="Live scout screenshot"
                className="h-full w-full object-contain"
              />
            ) : priorActive || starting ? (
              <p className="font-accent px-6 text-center text-sm italic text-primary">
                Scouting now — post images land as each post is ingested.
              </p>
            ) : (
              <p className="font-accent px-6 text-center text-sm italic text-muted-foreground">
                Hit Start Scout — multi-platform frames land here.
              </p>
            )}
          </div>
        </div>

        <div className="flex max-h-[360px] flex-col overflow-hidden rounded-3xl border border-border/60">
          <div className="font-ui border-b border-border/40 px-3 py-2 text-xs text-muted-foreground">
            event log · browser scout (yt-dlp runs parallel, quiet)
          </div>
          <ul className="flex-1 space-y-1 overflow-y-auto p-3 font-ui text-[11px] leading-relaxed">
            {logEvents.length === 0 && (
              <li className="text-muted-foreground">
                {priorActive || starting
                  ? "Scout started — waiting for the first hop…"
                  : "Waiting for browser scout events…"}
              </li>
            )}
            {logEvents.map((ev, i) => (
              <li key={`${ev.sequence}-${i}`} className="text-muted-foreground">
                <span className="text-primary">{ev.step_type}</span> {eventDetail(ev)}
              </li>
            ))}
          </ul>
        </div>
      </div>

      
      {ytdlpIntel && (
        <div className="space-y-3 rounded-3xl border border-border/60 bg-black/40 p-5 text-left font-mono text-xs">
          <h3 className="font-display text-center text-xl font-bold text-primary">yt-dlp intel</h3>
          <p className="font-ui text-center text-[11px] text-muted-foreground">
            {ytdlpIntel.channel_title}
            {ytdlpIntel.date_from && ytdlpIntel.date_to
              ? ` · ${ytdlpIntel.date_from} → ${ytdlpIntel.date_to}`
              : ""}{" "}
            · text only (no screenshots)
          </p>
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {ytdlpIntel.videos.map((v) => (
              <li key={v.url} className="rounded-xl border border-border/40 px-3 py-2">
                <a href={v.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                  {v.title}
                </a>
                <p className="text-muted-foreground">
                  {v.views.toLocaleString()} views · {v.likes} likes · {v.comments} comments · {v.posted_at.slice(0, 10)}
                </p>
              </li>
            ))}
            {ytdlpIntel.videos.length === 0 && (
              <li className="text-muted-foreground">No uploads in window</li>
            )}
          </ul>
        </div>
      )}

{shots.length > 0 && (
        <div className="space-y-4 text-left">
          <h3 className="font-display text-center text-2xl font-bold">Screenshot reel</h3>
          <p className="font-accent text-center text-sm italic text-muted-foreground">
            One-by-one captures — company + platform on each tile. Tap to expand.
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
                  src={frameSrc(s.b64, s.mime)}
                  alt={`${s.company} ${s.platform}`}
                  className="aspect-video w-full object-cover"
                />
                <div className="font-ui space-y-0.5 p-2.5 text-[10px]">
                  <p className="font-display truncate text-xs font-bold">{s.company}</p>
                  <p className="font-semibold uppercase tracking-wide text-primary">
                    {platformName(s.platform)}
                  </p>
                  <p className="truncate text-muted-foreground">{s.label}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {recordingReady && runId && (
        <div className="mx-auto w-full max-w-3xl space-y-4 rounded-3xl border border-primary/30 bg-primary/5 p-6 text-center">
          <h3 className="font-shout text-2xl uppercase">Session replay</h3>
          <p className="font-accent text-sm italic text-muted-foreground">
            Control center — play inline or go fullscreen.
          </p>
          <div className="overflow-hidden rounded-2xl border border-border/60 bg-black text-left">
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
              src={frameSrc(lightbox.b64, lightbox.mime)}
              alt={lightbox.label}
              className="max-h-[80vh] w-full rounded-2xl object-contain"
            />
            <p className="font-ui mt-3 text-center text-sm text-primary">
              <span className="font-display font-bold text-foreground">{lightbox.company}</span>
              {" · "}
              {platformName(lightbox.platform)}
              {" · "}
              {lightbox.label}
            </p>
            {lightbox.url ? (
              <p className="mt-2 text-center">
                <a
                  href={lightbox.url.startsWith("http") ? lightbox.url : `https://${lightbox.url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-ui inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
                >
                  Open captured page
                  <ExternalLink className="size-3" />
                </a>
              </p>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
