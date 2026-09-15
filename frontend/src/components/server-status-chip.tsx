"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, WifiOff } from "lucide-react";

import { GATEWAY_URL } from "@/lib/api";
import { cn } from "@/lib/utils";

type Status = "checking" | "waking" | "online" | "offline";

async function probe(path: "/health" | "/ready", timeoutMs: number): Promise<boolean> {
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${GATEWAY_URL}${path}`, {
      cache: "no-store",
      signal: ctrl.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timer);
  }
}

/**
 * Render free-tier cold-start chip: keep pinging until the API wakes, then show Online.
 * No personal operator info — only backend readiness.
 */
export function ServerStatusChip() {
  const [status, setStatus] = useState<Status>("checking");
  const [tries, setTries] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let attempt = 0;

    async function tick() {
      if (cancelled) return;
      attempt += 1;
      setTries(attempt);
      setStatus((prev) => (prev === "online" ? prev : attempt === 1 ? "checking" : "waking"));

      const healthOk = await probe("/health", attempt === 1 ? 8000 : 45000);
      if (cancelled) return;
      if (!healthOk) {
        setStatus("waking");
        window.setTimeout(() => void tick(), 2500);
        return;
      }

      const readyOk = await probe("/ready", 12000);
      if (cancelled) return;
      if (readyOk) {
        setStatus("online");
        return;
      }
      // Gateway up, generation still warming — keep trying briefly.
      setStatus("waking");
      window.setTimeout(() => void tick(), 2000);
    }

    void tick();
    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    status === "online"
      ? "API online"
      : status === "offline"
        ? "API offline"
        : status === "waking"
          ? `Waking API… (${tries})`
          : "Checking API…";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider",
        status === "online" && "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
        (status === "checking" || status === "waking") &&
          "border-amber-500/40 bg-amber-500/10 text-amber-300",
        status === "offline" && "border-destructive/40 bg-destructive/10 text-destructive",
      )}
      title={`Gateway ${GATEWAY_URL}`}
      role="status"
      aria-live="polite"
    >
      {status === "online" ? (
        <CheckCircle2 className="size-3" />
      ) : status === "offline" ? (
        <WifiOff className="size-3" />
      ) : (
        <Loader2 className="size-3 animate-spin" />
      )}
      {label}
    </span>
  );
}
