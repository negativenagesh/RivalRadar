"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { deleteConnection, listConnections, upsertConnection } from "@/lib/api";
import type { MissionTargetPreview } from "@/lib/mission-store";
import type { ConnectionStatus } from "@/lib/types";

const PRIMARY = [
  {
    id: "youtube",
    label: "YouTube",
    hint: "Uses workspace API key, or yt-dlp text intel",
    mode: "api_key" as const,
    cta: "Check YouTube",
  },
  {
    id: "meta",
    label: "Meta",
    hint: "Instagram + Facebook via Meta OAuth",
    mode: "oauth" as const,
    cta: "Connect Meta",
  },
  {
    id: "linkedin",
    label: "LinkedIn",
    hint: "Official LinkedIn OAuth",
    mode: "oauth" as const,
    cta: "Connect LinkedIn",
  },
  {
    id: "x",
    label: "X",
    hint: "Official X OAuth",
    mode: "oauth" as const,
    cta: "Connect X",
  },
  {
    id: "tiktok",
    label: "TikTok",
    hint: "One-time Connect session (cookies, not passwords)",
    mode: "cookie" as const,
    cta: "Connect session",
  },
] as const;

type PlatformId = (typeof PRIMARY)[number]["id"];

function statusTone(status: ConnectionStatus["status"]): string {
  if (status === "connected") return "text-primary";
  if (status === "needs_reconnect") return "text-amber-600";
  return "text-muted-foreground";
}

function statusLabel(status: ConnectionStatus["status"]): string {
  return status.replace(/_/g, " ");
}

export function ConnectCenter({
  targets,
}: {
  targets: MissionTargetPreview[];
}) {
  const [rows, setRows] = useState<ConnectionStatus[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<PlatformId | null>(null);
  const [sessionBlob, setSessionBlob] = useState("");
  const [oauthNote, setOauthNote] = useState("");

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

  const banner = useMemo(() => {
    const list = rows ?? [];
    const ready = list.filter((r) => r.status === "connected").length;
    const needs = list.filter((r) => r.status === "needs_reconnect");
    const linkedinNeeded = targets.some((t) => t.platform === "linkedin");
    const linkedin = list.find((r) => r.platform === "linkedin");
    const warn =
      linkedinNeeded && (!linkedin || linkedin.status !== "connected")
        ? "LinkedIn URL present but not connected — scout soft-warns and continues."
        : needs.length
          ? `${needs.map((n) => n.platform).join(", ")} need reconnect`
          : null;
    return { ready, warn };
  }, [rows, targets]);

  function openConnect(platform: PlatformId) {
    setDialog(platform);
    setSessionBlob("");
    setOauthNote("");
    setError(null);
  }

  async function confirmConnect() {
    if (!dialog) return;
    const meta = PRIMARY.find((p) => p.id === dialog);
    if (!meta) return;
    setBusy(dialog);
    setError(null);
    try {
      if (meta.mode === "cookie") {
        const trimmed = sessionBlob.trim();
        if (!trimmed) {
          setError("Paste session cookies JSON from your Connect session browser — never a password.");
          return;
        }
        let parsed: Record<string, unknown>;
        try {
          parsed = JSON.parse(trimmed) as Record<string, unknown>;
        } catch {
          parsed = { cookies: trimmed };
        }
        if ("password" in parsed) {
          setError("Passwords are not accepted. Use cookies or an OAuth token.");
          return;
        }
        await upsertConnection(dialog, {
          auth_type: "cookie",
          secret: parsed,
          scopes: ["read"],
        });
      } else if (meta.mode === "oauth") {
        // Scaffold until developer app credentials are wired — stores a reconnect marker.
        await upsertConnection(dialog, {
          auth_type: "oauth",
          secret: {
            oauth_placeholder: true,
            note: oauthNote.trim() || "Awaiting developer OAuth client credentials",
          },
          scopes: ["read"],
        });
      } else {
        await upsertConnection(dialog, {
          auth_type: "api_key",
          secret: { source: "workspace_env" },
          scopes: ["youtube.readonly"],
        });
      }
      setDialog(null);
      refresh();
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
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Disconnect failed");
    } finally {
      setBusy(null);
    }
  }

  const dialogMeta = dialog ? PRIMARY.find((p) => p.id === dialog) : null;

  return (
    <div
      id="connect-center"
      className="mx-auto w-full max-w-3xl space-y-4 rounded-3xl border border-border/60 bg-card/30 px-5 py-5 text-left"
    >
      <div className="text-center">
        <p className="font-ui text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
          connections
        </p>
        <h3 className="font-display text-xl font-bold">Connect Center</h3>
        <p className="font-accent text-sm italic text-muted-foreground">
          Official OAuth or one-time Connect session. RivalRadar never asks for platform passwords.
        </p>
      </div>

      <p className="font-ui text-center text-xs text-muted-foreground">
        {loading ? "Checking…" : `${banner.ready} platforms ready`}
        {banner.warn ? ` · ${banner.warn}` : ""}
      </p>

      {error && !dialog && (
        <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => refresh()}>
            Retry
          </button>
        </p>
      )}

      <ul className="grid gap-2 sm:grid-cols-2">
        {PRIMARY.map((p) => {
          const row = (rows ?? []).find(
            (r) =>
              r.platform === p.id ||
              (p.id === "meta" && (r.platform === "instagram" || r.platform === "facebook")),
          );
          const status = row?.status ?? "not_connected";
          return (
            <li
              key={p.id}
              className="flex items-center justify-between gap-2 rounded-2xl border border-border/50 bg-background/40 px-3 py-3"
            >
              <div>
                <p className="font-display text-sm font-semibold">{p.label}</p>
                <p className={`font-ui text-[11px] ${statusTone(status)}`}>
                  {statusLabel(status)}
                  {row?.detail ? ` · ${row.detail}` : ` · ${p.hint}`}
                </p>
              </div>
              {status === "connected" ? (
                <div className="flex gap-1.5">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy === p.id}
                    onClick={() => openConnect(p.id)}
                  >
                    Reconnect
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy === p.id}
                    onClick={() => void disconnect(p.id)}
                  >
                    Clear
                  </Button>
                </div>
              ) : (
                <Button size="sm" disabled={busy === p.id} onClick={() => openConnect(p.id)}>
                  {p.cta}
                </Button>
              )}
            </li>
          );
        })}
      </ul>

      {dialog && dialogMeta && (
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
                {dialogMeta.cta}
              </h4>
              <p className="font-accent text-sm italic text-muted-foreground">{dialogMeta.hint}</p>
            </div>

            {dialogMeta.mode === "cookie" && (
              <label className="block space-y-2">
                <span className="font-ui text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Session cookies (JSON) — not a password
                </span>
                <textarea
                  value={sessionBlob}
                  onChange={(e) => setSessionBlob(e.target.value)}
                  rows={5}
                  placeholder='{"sessionid":"...","csrftoken":"..."}'
                  className="font-mono w-full rounded-2xl border border-border/60 bg-card/40 px-3 py-2 text-xs"
                />
              </label>
            )}

            {dialogMeta.mode === "oauth" && (
              <div className="space-y-2 rounded-2xl border border-border/50 bg-card/30 px-3 py-3">
                <p className="font-ui text-xs text-muted-foreground">
                  OAuth apps need your developer client IDs. Until those are wired, mark this
                  platform as connected so Scout soft-warns instead of blocking.
                </p>
                <label className="block space-y-1">
                  <span className="font-ui text-[10px] uppercase tracking-wide text-muted-foreground">
                    Optional note
                  </span>
                  <input
                    value={oauthNote}
                    onChange={(e) => setOauthNote(e.target.value)}
                    placeholder="e.g. awaiting Meta app review"
                    className="font-ui w-full rounded-xl border border-border/60 bg-background px-3 py-2 text-sm"
                  />
                </label>
              </div>
            )}

            {dialogMeta.mode === "api_key" && (
              <p className="font-ui rounded-2xl border border-border/50 bg-card/30 px-3 py-3 text-xs text-muted-foreground">
                YouTube reads <code className="text-primary">YOUTUBE_API_KEY</code> from the
                workspace env. Without it, Scout falls back to yt-dlp text intel (no screenshots).
              </p>
            )}

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
                {busy === dialog ? "Saving…" : "Save connection"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
