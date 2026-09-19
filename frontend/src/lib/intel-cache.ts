import type { IntelReport } from "./types";
import type { IntelFacts } from "./intel-facts";

const INTEL_CACHE_PREFIX = "rivalradar.intel.";

/** Stable cache key shared by Scout prefetch + War Room (local + gateway). */
export function intelFactsSig(facts: IntelFacts): string {
  return `${facts.window.label}|${facts.brandName}|${facts.companies
    .map((c) => `${c.name}:${c.posts}`)
    .join(",")}|${facts.sniperQueue.length}`;
}

export function intelCacheKey(sig: string, brandName: string): string {
  let hash = 0;
  const text = `${sig}|${brandName}`;
  for (let i = 0; i < text.length; i += 1) {
    hash = (Math.imul(hash, 31) + text.charCodeAt(i)) | 0;
  }
  return `${INTEL_CACHE_PREFIX}${(hash >>> 0).toString(36)}`;
}

export function readIntelCache(key: string): IntelReport | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as IntelReport;
    return parsed && typeof parsed.markdown === "string" ? parsed : null;
  } catch {
    return null;
  }
}

export function writeIntelCache(key: string, report: IntelReport): void {
  if (typeof window === "undefined") return;
  try {
    const stale = Object.keys(window.localStorage).filter(
      (k) => k.startsWith(INTEL_CACHE_PREFIX) && k !== key,
    );
    for (const k of stale.slice(0, Math.max(0, stale.length - 4))) {
      window.localStorage.removeItem(k);
    }
    window.localStorage.setItem(key, JSON.stringify(report));
  } catch {
    // storage full / private mode
  }
}

export function clearIntelCache(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}
