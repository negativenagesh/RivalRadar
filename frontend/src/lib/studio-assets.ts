import type { CreativeResult } from "./types";

const STUDIO_CACHE_PREFIX = "rivalradar.studio.";
const MAX_ASSETS = 12;

export type SavedStudioAsset = CreativeResult & {
  id: string;
  savedAt: number;
  format: string;
  platform: string;
};

export function studioAssetsKey(brandName: string): string {
  const brand = (brandName || "brand").trim().toLowerCase() || "brand";
  let hash = 0;
  for (let i = 0; i < brand.length; i += 1) {
    hash = (Math.imul(hash, 31) + brand.charCodeAt(i)) | 0;
  }
  return `${STUDIO_CACHE_PREFIX}${(hash >>> 0).toString(36)}`;
}

function isAsset(value: unknown): value is SavedStudioAsset {
  if (!value || typeof value !== "object") return false;
  const row = value as SavedStudioAsset;
  return (
    typeof row.id === "string" &&
    typeof row.text === "string" &&
    typeof row.kind === "string" &&
    typeof row.savedAt === "number"
  );
}

export function readStudioAssets(brandName: string): SavedStudioAsset[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(studioAssetsKey(brandName));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isAsset);
  } catch {
    return [];
  }
}

function writeStudioAssets(brandName: string, assets: SavedStudioAsset[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(studioAssetsKey(brandName), JSON.stringify(assets));
  } catch {
    // storage full / private mode — drop oldest and retry once
    try {
      const trimmed = assets.slice(-Math.max(4, Math.floor(MAX_ASSETS / 2)));
      window.localStorage.setItem(studioAssetsKey(brandName), JSON.stringify(trimmed));
    } catch {
      // ignore
    }
  }
}

export function appendStudioAssets(
  brandName: string,
  items: CreativeResult[],
  meta: { format: string; platform: string },
): SavedStudioAsset[] {
  const existing = readStudioAssets(brandName);
  const stamped = items.map((item, idx) => ({
    ...item,
    id: `studio-${Date.now().toString(36)}-${idx}-${Math.random().toString(36).slice(2, 8)}`,
    savedAt: Date.now() + idx,
    format: meta.format,
    platform: meta.platform,
  }));
  const next = [...existing, ...stamped].slice(-MAX_ASSETS);
  writeStudioAssets(brandName, next);
  return next;
}

export function removeStudioAsset(brandName: string, id: string): SavedStudioAsset[] {
  const next = readStudioAssets(brandName).filter((item) => item.id !== id);
  writeStudioAssets(brandName, next);
  return next;
}

export function clearStudioAssets(brandName: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(studioAssetsKey(brandName));
  } catch {
    // ignore
  }
}
