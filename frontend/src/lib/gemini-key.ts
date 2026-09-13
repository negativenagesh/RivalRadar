export const GEMINI_KEY_STORAGE = "rivalradar.operator.geminiKey";
export const GEMINI_KEY_EVENT = "rivalradar:gemini-key";

export function loadGeminiKey(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(GEMINI_KEY_STORAGE)?.trim() ?? "";
  } catch {
    return "";
  }
}

export function saveGeminiKey(raw: string): string {
  const key = raw.trim();
  if (typeof window === "undefined") return key;
  try {
    if (key) window.localStorage.setItem(GEMINI_KEY_STORAGE, key);
    else window.localStorage.removeItem(GEMINI_KEY_STORAGE);
  } catch {
    // private mode
  }
  window.dispatchEvent(new Event(GEMINI_KEY_EVENT));
  return key;
}

export function clearGeminiKey(): void {
  saveGeminiKey("");
}

export function maskGeminiKey(key: string): string {
  const trimmed = key.trim();
  if (!trimmed) return "";
  if (trimmed.length <= 4) return "••••";
  return `••••${trimmed.slice(-4)}`;
}

export function hasGeminiKey(key: string): boolean {
  return key.trim().length >= 8;
}

export function geminiChipClasses(ready: boolean): string {
  return ready
    ? "border-primary/40 bg-primary/10 text-primary"
    : "animate-pulse border-primary/60 bg-primary/15 text-primary shadow-[0_0_28px_-4px_oklch(0.87_0.24_128)]";
}
