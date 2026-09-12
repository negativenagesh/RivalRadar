"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Lock, Unplug } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  cancelConnectSession,
  completeConnectSession,
  deleteConnection,
  listConnections,
  startConnectSession,
  type ConnectSession,
} from "@/lib/api";
import {
  PLATFORM_LABELS,
  requiredConnectPlatforms,
  type MissionTargetPreview,
} from "@/lib/mission-store";
import type { ConnectionStatus } from "@/lib/types";

type PlatformId = string;

function statusTone(status: ConnectionStatus["status"]): string {
  if (status === "connected") return "text-primary";
  if (status === "needs_reconnect") return "text-amber-600";
  return "text-muted-foreground";
}

export function ConnectCenter({
  targets,
  onGateChange,
}: {
  targets: MissionTargetPreview[];
  onGateChange?: (state: { ready: boolean; missing: string[] }) => void;
}) {
  const required = useMemo(() => requiredConnectPlatforms(targets), [targets]);
  const youtubeTargets = useMemo(
    () => targets.filter((t) => t.platform.toLowerCase() === "youtube"),
    [targets],
  );

  const [rows, setRows] = useState<ConnectionStatus[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<PlatformId | null>(null);
  const [activeSession, setActiveSession] = useState<ConnectSession | null>(null);

  function rowFor(platform: string): ConnectionStatus | undefined {
    const list = rows ?? [];
    return list.find((r) => r.platform === platform);
  }

  const missing = useMemo(() => {
    return required.filter((p) => rowFor(p)?.status !== "connected");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- rowFor depends on rows
  }, [required, rows]);

  const ready = required.length === 0 || missing.length === 0;

  useEffect(() => {
    onGateChange?.({ ready, missing });
  }, [ready, missing, onGateChange]);

  useEffect(() => {
    let cancelled = false;
    listConnections()
      .then((next) => {
        if (!cancelled) {
          setRows(next);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load connections");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      setRows(await listConnections());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connections");
    } finally {
      setLoading(false);
    }
  }

  async function openConnect(platform: PlatformId) {
    setDialog(platform);
    setError(null);
    setBusy(platform);
    setActiveSession(null);
    try {
      const session = await startConnectSession(platform);
      setActiveSession(session);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not open Connect browser — is the connect-agent running?",
      );
    } finally {
      setBusy(null);
    }
  }

  async function confirmLoggedIn() {
    if (!dialog || !activeSession) return;
    setBusy(dialog);
    setError(null);
    try {
      await completeConnectSession(dialog, activeSession.session_id);
      setDialog(null);
      setActiveSession(null);
      await refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not capture session — finish login in the browser, then try again",
      );
    } finally {
      setBusy(null);
    }
  }

  async function closeDialog() {
    const platform = dialog;
    const session = activeSession;
    setDialog(null);
    setActiveSession(null);
    setError(null);
    if (platform && session) {
      try {
        await cancelConnectSession(platform, session.session_id);
      } catch {
        // best-effort close
      }
    }
  }

  async function disconnect(platform: string) {
    setBusy(platform);
    try {
      await deleteConnection(platform);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBusy(null);
    }
  }

  const dialogLabel = dialog ? (PLATFORM_LABELS[dialog] ?? dialog) : "";

  return (
    <div
      id="connect-center"
      className="mx-auto w-full max-w-3xl space-y-4 rounded-3xl border border-border/60 bg-card/30 px-5 py-5 text-left"
    >
      <div className="text-center">
        <p className="font-ui text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
          required connections
        </p>
        <h3 className="font-display text-xl font-bold">Connect Center</h3>
        <p className="font-accent text-sm italic text-muted-foreground">
          Click Connect — we open a browser for that platform. Sign in there. Hit I&apos;ve logged
          in. RivalRadar captures the session automatically (never a password).
        </p>
      </div>

      <div
        className={
          ready
            ? "rounded-2xl border border-primary/40 bg-primary/10 px-3 py-2 text-center text-sm text-primary"
            : "rounded-2xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-center text-sm text-destructive"
        }
        role="status"
      >
        {loading
          ? "Checking connections…"
          : ready
            ? required.length === 0
              ? "No Playwright platforms in this mission — YouTube/yt-dlp can run without login."
              : `All required platforms connected (${required.length}). Scout unlocked.`
            : `Connect required: ${missing.map((p) => PLATFORM_LABELS[p] ?? p).join(", ")}. Start Scout stays locked.`}
      </div>

      {youtubeTargets.length > 0 && (
        <div className="flex items-start gap-3 rounded-2xl border border-border/50 bg-background/40 px-3 py-3">
          <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
          <div>
            <p className="font-display text-sm font-semibold">YouTube · no Connect needed</p>
            <p className="font-ui text-[11px] text-muted-foreground">
              Runs via Data API or yt-dlp in parallel with browser scouts.
            </p>
          </div>
        </div>
      )}

      {error && !dialog && (
        <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => void refresh()}>
            Retry
          </button>
        </p>
      )}

      {required.length === 0 && youtubeTargets.length === 0 && (
        <p className="font-accent text-center text-sm italic text-muted-foreground">
          Add LinkedIn / X / Instagram / TikTok / Threads links in Context to unlock Connect widgets.
        </p>
      )}

      <ul className="grid gap-2 sm:grid-cols-2">
        {required.map((platform) => {
          const row = rowFor(platform);
          const status = row?.status ?? "not_connected";
          const connected = status === "connected";
          const label = PLATFORM_LABELS[platform] ?? platform;
          return (
            <li
              key={platform}
              className={
                connected
                  ? "flex items-center justify-between gap-2 rounded-2xl border border-primary/50 bg-primary/10 px-3 py-3"
                  : "flex items-center justify-between gap-2 rounded-2xl border border-border/50 bg-background/40 px-3 py-3"
              }
            >
              <div className="min-w-0">
                <p className="font-display flex items-center gap-1.5 text-sm font-semibold">
                  {connected ? (
                    <CheckCircle2 className="size-4 shrink-0 text-primary" aria-hidden />
                  ) : null}
                  {label}
                </p>
                <p className={`font-ui text-[11px] ${statusTone(status)}`}>
                  {connected
                    ? "Connected · browser session saved for scout"
                    : "Not connected · required for Start Scout"}
                </p>
              </div>
              {connected ? (
                <div className="flex shrink-0 gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy === platform}
                    onClick={() => void openConnect(platform)}
                  >
                    Reconnect
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy === platform}
                    onClick={() => void disconnect(platform)}
                    aria-label={`Clear ${label}`}
                  >
                    <Unplug className="size-3.5" />
                  </Button>
                </div>
              ) : (
                <Button size="sm" disabled={busy === platform} onClick={() => void openConnect(platform)}>
                  Connect {label}
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      {dialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="presentation"
          onClick={() => void closeDialog()}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="connect-dialog-title"
            className="w-full max-w-lg space-y-4 rounded-3xl border border-border/60 bg-background p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div>
              <p className="font-ui text-[10px] font-bold uppercase tracking-[0.2em] text-primary">
                connect session
              </p>
              <h4 id="connect-dialog-title" className="font-display text-2xl font-bold">
                Connect {dialogLabel}
              </h4>
              <p className="font-accent text-sm italic text-muted-foreground">
                A browser window opens on your machine. Sign in to {dialogLabel} yourself — we never
                see your password. When you&apos;re in, confirm below and we capture the session.
              </p>
            </div>

            <ol className="font-ui space-y-3 text-sm text-muted-foreground">
              <li className="rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <span className="font-semibold text-foreground">1. Browser window</span>
                <p className="mt-1 text-xs">
                  {activeSession
                    ? activeSession.detail ||
                      `Opened ${dialogLabel} login — switch to that window and sign in.`
                    : busy === dialog
                      ? "Opening browser…"
                      : "Waiting to open browser…"}
                </p>
              </li>
              <li className="rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <span className="font-semibold text-foreground">2. Sign in on {dialogLabel}</span>
                <p className="mt-1 text-xs">
                  Use your normal account in the opened browser. Do not paste cookies or passwords
                  here.
                </p>
              </li>
              <li className="rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <span className="font-semibold text-foreground">3. Confirm</span>
                <p className="mt-1 text-xs">
                  Click I&apos;ve logged in — RivalRadar grabs the session from that browser and
                  saves it encrypted for scout.
                </p>
              </li>
            </ol>

            {error && dialog && (
              <p className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => void closeDialog()}>
                Cancel
              </Button>
              <Button
                disabled={busy === dialog || !activeSession}
                onClick={() => void confirmLoggedIn()}
              >
                {busy === dialog ? "Saving session…" : "I've logged in"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
