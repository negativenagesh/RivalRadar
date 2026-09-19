/** Content calendar slots — remind to stage, never autopost. */

import { pushNotification } from "@/lib/notifications";
import type { SavedStudioAsset } from "@/lib/studio-assets";

export type CalendarSlotStatus = "draft" | "approved" | "staged" | "published_manual";

export type CalendarSlot = {
  id: string;
  brandName: string;
  scheduledAt: string;
  platform: string;
  format: string;
  status: CalendarSlotStatus;
  caption: string;
  overlayText?: string;
  assetId?: string;
  remindedAt?: string | null;
  createdAt: string;
};

const STORAGE_KEY = "rivalradar.calendar.slots";
const EVENT = "rivalradar:calendar";
const MAX_SLOTS = 80;
/** Remind when due within this window (and not already reminded). */
export const REMIND_WINDOW_MS = 30 * 60 * 1000;

function emit(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(EVENT));
}

export function subscribeCalendar(onChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function loadCalendarSlots(): CalendarSlot[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isSlot).slice(0, MAX_SLOTS);
  } catch {
    return [];
  }
}

function isSlot(value: unknown): value is CalendarSlot {
  if (!value || typeof value !== "object") return false;
  const row = value as CalendarSlot;
  return (
    typeof row.id === "string" &&
    typeof row.brandName === "string" &&
    typeof row.scheduledAt === "string" &&
    typeof row.platform === "string" &&
    typeof row.format === "string" &&
    typeof row.status === "string" &&
    typeof row.caption === "string" &&
    typeof row.createdAt === "string"
  );
}

function saveSlots(rows: CalendarSlot[]): CalendarSlot[] {
  const next = rows
    .slice()
    .sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt))
    .slice(0, MAX_SLOTS);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // private mode / quota
    }
  }
  emit();
  return next;
}

export type ScheduleInput = {
  brandName: string;
  scheduledAt: string;
  platform: string;
  format: string;
  caption: string;
  overlayText?: string;
  assetId?: string;
  status?: CalendarSlotStatus;
};

export function scheduleSlot(input: ScheduleInput): CalendarSlot {
  const row: CalendarSlot = {
    id: `cal-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    brandName: input.brandName.trim() || "brand",
    scheduledAt: input.scheduledAt,
    platform: input.platform,
    format: input.format,
    status: input.status ?? "approved",
    caption: input.caption,
    overlayText: input.overlayText,
    assetId: input.assetId,
    remindedAt: null,
    createdAt: new Date().toISOString(),
  };
  saveSlots([...loadCalendarSlots(), row]);
  return row;
}

export function scheduleFromStudioAsset(
  asset: SavedStudioAsset,
  brandName: string,
  scheduledAt: string,
  platform?: string,
): CalendarSlot {
  return scheduleSlot({
    brandName,
    scheduledAt,
    platform: platform || asset.platform || "linkedin",
    format: asset.format || "studio",
    caption: asset.text || "",
    overlayText: asset.overlay_text ?? undefined,
    assetId: asset.id,
    status: "approved",
  });
}

export function updateCalendarSlot(
  id: string,
  patch: Partial<Pick<CalendarSlot, "status" | "scheduledAt" | "remindedAt" | "caption">>,
): CalendarSlot[] {
  const next = loadCalendarSlots().map((row) => (row.id === id ? { ...row, ...patch } : row));
  return saveSlots(next);
}

export function removeCalendarSlot(id: string): CalendarSlot[] {
  return saveSlots(loadCalendarSlots().filter((row) => row.id !== id));
}

/** Monday 00:00 local of the week containing `d`. */
export function startOfWeek(d: Date): Date {
  const day = d.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const start = new Date(d);
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() + mondayOffset);
  return start;
}

export function addDays(d: Date, n: number): Date {
  const next = new Date(d);
  next.setDate(next.getDate() + n);
  return next;
}

export function dayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function slotsForWeek(slots: CalendarSlot[], weekStart: Date): CalendarSlot[] {
  const from = weekStart.getTime();
  const to = addDays(weekStart, 7).getTime();
  return slots.filter((row) => {
    const t = new Date(row.scheduledAt).getTime();
    return Number.isFinite(t) && t >= from && t < to;
  });
}

export function groupSlotsByDay(
  slots: CalendarSlot[],
  weekStart: Date,
): { day: string; label: string; rows: CalendarSlot[] }[] {
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = addDays(weekStart, i);
    const key = dayKey(d);
    return {
      day: key,
      label: d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }),
      rows: [] as CalendarSlot[],
    };
  });
  const byKey = Object.fromEntries(days.map((d) => [d.day, d]));
  for (const row of slots) {
    const key = dayKey(new Date(row.scheduledAt));
    const bucket = byKey[key];
    if (bucket) bucket.rows.push(row);
  }
  for (const d of days) {
    d.rows.sort((a, b) => a.scheduledAt.localeCompare(b.scheduledAt));
  }
  return days;
}

/** Slots that should fire a remind-to-stage notification. */
export function findDueReminders(
  slots: CalendarSlot[],
  now = new Date(),
  windowMs = REMIND_WINDOW_MS,
): CalendarSlot[] {
  const nowMs = now.getTime();
  return slots.filter((row) => {
    if (row.status === "staged" || row.status === "published_manual") return false;
    if (row.remindedAt) return false;
    const due = new Date(row.scheduledAt).getTime();
    if (!Number.isFinite(due)) return false;
    const delta = due - nowMs;
    return delta >= 0 && delta <= windowMs;
  });
}

/** Fire in-app (+ email) reminds for due slots; marks them reminded. Returns how many fired. */
export function fireDueReminders(now = new Date()): number {
  const due = findDueReminders(loadCalendarSlots(), now);
  if (due.length === 0) return 0;
  const stamped = now.toISOString();
  for (const row of due) {
    const when = new Date(row.scheduledAt).toLocaleString();
    pushNotification({
      kind: "calendar_due",
      title: `Post due soon — ${row.platform}`,
      body: `${row.format} for ${row.brandName} at ${when}. Open Calendar → Stage in Connect (you still hit publish).`,
      href: "/calendar",
      email: true,
    });
    updateCalendarSlot(row.id, { remindedAt: stamped });
  }
  return due.length;
}

/** Default schedule: tomorrow 10:00 local, as datetime-local value. */
export function defaultScheduleLocalValue(from = new Date()): string {
  const d = new Date(from);
  d.setDate(d.getDate() + 1);
  d.setHours(10, 0, 0, 0);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day}T${hh}:${mm}`;
}

export function localValueToIso(localValue: string): string {
  const d = new Date(localValue);
  if (!Number.isFinite(d.getTime())) throw new Error("Invalid schedule time");
  return d.toISOString();
}
