"use client";

import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, ExternalLink, Lock, Unplug } from "lucide-react";

import { Button } from "@/components/ui/button";
import { deleteConnection, listConnections, upsertConnection } from "@/lib/api";
import {
  PLATFORM_HOME,
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

function parseCookieSecret(raw: string): Record<string, unknown> {
  const trimmed = raw.trim();
  if (!trimmed) throw new Error("Paste session cookies before confirming.");
  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (Array.isArray(parsed)) return { cookies: parsed };
    if (parsed && typeof parsed === "object") {
      const obj = parsed as Record<string, unknown>;
      if ("password" in obj || "passwd" in obj || "pass" in obj) {
        throw new Error("Passwords are not accepted. Use session cookies only.");
      }
      return obj;
    }
  } catch (err) {
    if (err instanceof Error && err.message.startsWith("Passwords")) throw err;
  }
  // name=value; name2=value2
  if (trimmed.includes("=")) {
    const cookies = trimmed.split(/;\s*/).flatMap((part) => {
      const eq = part.indexOf("=");
      if (eq <= 0) return [];
      return [{ name: part.slice(0, eq).trim(), value: part.slice(eq + 1).trim() }];
    });
    if (cookies.length) return { cookies };
  }
  return { cookies: trimmed };
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
  const [sessionBlob, setSessionBlob] = useState("");

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

  function openConnect(platform: PlatformId) {
    setDialog(platform);
    setSessionBlob("");
    setError(null);
  }

  async function confirmConnect() {
    if (!dialog) return;
    setBusy(dialog);
    setError(null);
    try {
      const secret = parseCookieSecret(sessionBlob);
      await upsertConnection(dialog, {
        auth_type: "cookie",
        secret,
        scopes: ["read", "scout"],
      });
      setDialog(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setBusy(null);
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
  const dialogHome = dialog ? (PLATFORM_HOME[dialog] ?? "https://example.com") : "";

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
          Every non-YouTube link from Context must be connected before Start Scout. RivalRadar never
          asks for platform passwords — only a one-time Connect session (cookies).
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
              Runs via Data API or yt-dlp in parallel with browser scouts. Login widget not required.
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
                    ? `Connected · ${row?.auth_type ?? "session"} saved for scout`
                    : "Not connected · required for Start Scout"}
                </p>
              </div>
              {connected ? (
                <div className="flex shrink-0 gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy === platform}
                    onClick={() => openConnect(platform)}
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
                <Button size="sm" disabled={busy === platform} onClick={() => openConnect(platform)}>
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
          onClick={() => setDialog(null)}
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
                connect widget
              </p>
              <h4 id="connect-dialog-title" className="font-display text-2xl font-bold">
                Connect {dialogLabel}
              </h4>
              <p className="font-accent text-sm italic text-muted-foreground">
                Sign in on {dialogLabel} yourself, then deposit a Connect session. Never paste a
                password.
              </p>
            </div>

            <ol className="font-ui space-y-3 text-sm text-muted-foreground">
              <li className="rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <span className="font-semibold text-foreground">1. Open {dialogLabel} and sign in</span>
                <div className="mt-2">
                  <a
                    href={dialogHome}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 text-primary underline"
                  >
                    Open {dialogLabel}
                    <ExternalLink className="size-3.5" aria-hidden />
                  </a>
                </div>
              </li>
              <li className="rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <span className="font-semibold text-foreground">
                  2. Paste session cookies (JSON array or name=value)
                </span>
                <textarea
                  value={sessionBlob}
                  onChange={(e) => setSessionBlob(e.target.value)}
                  rows={5}
                  placeholder='[{"name":"li_at","value":"...","domain":".linkedin.com"}]'
                  className="font-mono mt-2 w-full rounded-2xl border border-border/60 bg-background px-3 py-2 text-xs"
                />
              </li>
              <li className="rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <span className="font-semibold text-foreground">3. Confirm connection</span>
                <p className="mt-1 text-xs">
                  Scout injects this session into Playwright for {dialogLabel} hops only.
                </p>
              </li>
            </ol>

            {error && dialog && (
              <p className="rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setDialog(null)}>
                Cancel
              </Button>
              <Button disabled={busy === dialog} onClick={() => void confirmConnect()}>
                {busy === dialog ? "Saving…" : `Confirm ${dialogLabel} connected`}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
