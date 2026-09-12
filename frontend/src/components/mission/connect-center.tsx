"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { deleteConnection, listConnections, upsertConnection } from "@/lib/api";
import type { ConnectionStatus } from "@/lib/types";
import type { MissionTargetPreview } from "@/lib/mission-store";

const PRIMARY = [
  { id: "youtube", label: "YouTube", hint: "API key / yt-dlp" },
  { id: "meta", label: "Meta", hint: "Instagram + Facebook OAuth" },
  { id: "linkedin", label: "LinkedIn", hint: "OAuth" },
  { id: "x", label: "X", hint: "OAuth" },
  { id: "tiktok", label: "TikTok", hint: "Connect session" },
] as const;

function statusTone(status: ConnectionStatus["status"]): string {
  if (status === "connected") return "text-primary";
  if (status === "needs_reconnect") return "text-amber-600";
  return "text-muted-foreground";
}

export function ConnectCenter({
  targets,
}: {
  targets: MissionTargetPreview[];
}) {
  const [rows, setRows] = useState<ConnectionStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRows(await listConnections());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connections");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const banner = useMemo(() => {
    const ready = rows.filter((r) => r.status === "connected").length;
    const needs = rows.filter((r) => r.status === "needs_reconnect");
    const linkedinNeeded = targets.some((t) => t.platform === "linkedin");
    const linkedin = rows.find((r) => r.platform === "linkedin");
    const warn =
      linkedinNeeded && linkedin && linkedin.status !== "connected"
        ? "LinkedIn URL present but not connected — scout will soft-warn and continue."
        : needs.length
          ? `${needs.map((n) => n.platform).join(", ")} need reconnect`
          : null;
    return { ready, warn };
  }, [rows, targets]);

  async function connectSession(platform: string) {
    setBusy(platform);
    setError(null);
    try {
      // Prototype: user finished login elsewhere; store opaque session marker (never a password).
      await upsertConnection(platform, {
        auth_type: platform === "youtube" ? "api_key" : "cookie",
        secret: {
          session: "connect-session-placeholder",
          note: "Replace with OAuth token or encrypted browser cookies after Connect session",
        },
        scopes: ["read"],
      });
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

  return (
    <div id="connect-center" className="mx-auto w-full max-w-3xl space-y-4 rounded-3xl border border-border/60 bg-card/30 px-5 py-5 text-left">
      <div className="text-center">
        <p className="font-ui text-[11px] font-semibold uppercase tracking-[0.22em] text-primary">
          connections
        </p>
        <h3 className="font-display text-xl font-bold">Connect Center</h3>
        <p className="font-accent text-sm italic text-muted-foreground">
          OAuth or one-time Connect session — RivalRadar never stores platform passwords.
        </p>
      </div>

      <p className="font-ui text-center text-xs text-muted-foreground">
        {loading ? "Checking…" : `${banner.ready} platforms ready`}
        {banner.warn ? ` · ${banner.warn}` : ""}
      </p>

      {error && (
        <p className="rounded-2xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </p>
      )}

      <ul className="grid gap-2 sm:grid-cols-2">
        {PRIMARY.map((p) => {
          const row = rows.find((r) => r.platform === p.id || (p.id === "meta" && (r.platform === "instagram" || r.platform === "facebook")));
          const status = row?.status ?? "not_connected";
          return (
            <li
              key={p.id}
              className="flex items-center justify-between gap-2 rounded-2xl border border-border/50 bg-background/40 px-3 py-3"
            >
              <div>
                <p className="font-display text-sm font-semibold">{p.label}</p>
                <p className={`font-ui text-[11px] ${statusTone(status)}`}>
                  {status.replace(/_/g, " ")}
                  {row?.detail ? ` · ${row.detail}` : ` · ${p.hint}`}
                </p>
              </div>
              {status === "connected" ? (
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy === p.id}
                  onClick={() => void disconnect(p.id)}
                >
                  Reconnect
                </Button>
              ) : (
                <Button
                  size="sm"
                  disabled={busy === p.id}
                  onClick={() => void connectSession(p.id)}
                >
                  {p.id === "tiktok" ? "Connect session" : "Connect"}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
