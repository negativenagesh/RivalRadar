"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

import { GATEWAY_URL } from "@/lib/api";

const VID_KEY = "rr_vid";

function ensureVisitorToken(): string {
  try {
    const existing = window.localStorage.getItem(VID_KEY);
    if (existing && existing.length >= 8) return existing;
    const token =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID().replace(/-/g, "")
        : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
    window.localStorage.setItem(VID_KEY, token);
    return token;
  } catch {
    return "anon";
  }
}

/**
 * Fire-and-forget pageview → gateway → Supabase.
 * Never blocks UI; fails silently if API is cold or Supabase unset.
 */
export function VisitorTracker() {
  const pathname = usePathname();
  const lastPath = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname || lastPath.current === pathname) return;
    lastPath.current = pathname;

    const payload = {
      path: pathname,
      referrer: typeof document !== "undefined" ? document.referrer || null : null,
      title: typeof document !== "undefined" ? document.title || null : null,
      language: typeof navigator !== "undefined" ? navigator.language : null,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
      screen_w: typeof window !== "undefined" ? window.screen.width : null,
      screen_h: typeof window !== "undefined" ? window.screen.height : null,
      viewport_w: typeof window !== "undefined" ? window.innerWidth : null,
      viewport_h: typeof window !== "undefined" ? window.innerHeight : null,
      platform: typeof navigator !== "undefined" ? navigator.platform || null : null,
      visitor_token: ensureVisitorToken(),
    };

    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), 12000);
    void fetch(`${GATEWAY_URL}/analytics/pageview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-RR-Vid": payload.visitor_token,
      },
      body: JSON.stringify(payload),
      cache: "no-store",
      signal: ctrl.signal,
      keepalive: true,
    })
      .catch(() => undefined)
      .finally(() => window.clearTimeout(timer));
  }, [pathname]);

  return null;
}
