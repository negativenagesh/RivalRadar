import { afterEach, describe, expect, it, vi } from "vitest";

import {
  defaultScheduleLocalValue,
  findDueReminders,
  fireDueReminders,
  groupSlotsByDay,
  loadCalendarSlots,
  localValueToIso,
  removeCalendarSlot,
  scheduleFromStudioAsset,
  scheduleSlot,
  slotsForWeek,
  startOfWeek,
  updateCalendarSlot,
} from "./calendar";
import { loadNotifications } from "./notifications";
import type { SavedStudioAsset } from "./studio-assets";

afterEach(() => {
  window.localStorage.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

function asset(partial?: Partial<SavedStudioAsset>): SavedStudioAsset {
  return {
    id: "studio-1",
    kind: "studio",
    text: "AI without an explanation is a vibe.",
    overlay_text: "Still true.",
    image_concept: "lime card",
    image_mime_type: "image/png",
    image_data_base64: "aaa",
    savedAt: Date.now(),
    format: "hot_take",
    platform: "linkedin",
    ...partial,
  };
}

describe("calendar slots", () => {
  it("schedules from a studio asset and lists by week", () => {
    const when = new Date("2026-09-22T10:00:00");
    const row = scheduleFromStudioAsset(asset(), "Pixis", when.toISOString());
    expect(row.status).toBe("approved");
    expect(row.overlayText).toBe("Still true.");
    expect(loadCalendarSlots()).toHaveLength(1);

    const week = startOfWeek(when);
    const inWeek = slotsForWeek(loadCalendarSlots(), week);
    expect(inWeek).toHaveLength(1);
    const days = groupSlotsByDay(inWeek, week);
    expect(days).toHaveLength(7);
    expect(days.some((d) => d.rows.some((r) => r.id === row.id))).toBe(true);
  });

  it("updates status and removes slots", () => {
    const row = scheduleSlot({
      brandName: "Pixis",
      scheduledAt: "2026-09-23T14:00:00.000Z",
      platform: "x",
      format: "meme",
      caption: "hi",
    });
    updateCalendarSlot(row.id, { status: "staged" });
    expect(loadCalendarSlots()[0].status).toBe("staged");
    removeCalendarSlot(row.id);
    expect(loadCalendarSlots()).toHaveLength(0);
  });

  it("parses datetime-local defaults", () => {
    const local = defaultScheduleLocalValue(new Date("2026-09-19T12:00:00"));
    expect(local).toMatch(/^2026-09-20T10:00$/);
    expect(localValueToIso(local)).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });
});

describe("remind to stage", () => {
  it("finds due slots inside the 30m window only once", () => {
    const now = new Date("2026-09-19T15:00:00.000Z");
    const dueSoon = scheduleSlot({
      brandName: "Pixis",
      scheduledAt: "2026-09-19T15:20:00.000Z",
      platform: "linkedin",
      format: "hot_take",
      caption: "Still true.",
    });
    scheduleSlot({
      brandName: "Pixis",
      scheduledAt: "2026-09-19T18:00:00.000Z",
      platform: "instagram",
      format: "meme",
      caption: "later",
    });
    scheduleSlot({
      brandName: "Pixis",
      scheduledAt: "2026-09-19T14:50:00.000Z",
      platform: "x",
      format: "meme",
      caption: "past",
    });

    const due = findDueReminders(loadCalendarSlots(), now);
    expect(due.map((r) => r.id)).toEqual([dueSoon.id]);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
    expect(fireDueReminders(now)).toBe(1);
    expect(loadNotifications()[0].kind).toBe("calendar_due");
    expect(loadCalendarSlots().find((r) => r.id === dueSoon.id)?.remindedAt).toBeTruthy();
    expect(fireDueReminders(now)).toBe(0);
  });

  it("skips staged / published slots", () => {
    const now = new Date("2026-09-19T15:00:00.000Z");
    const row = scheduleSlot({
      brandName: "Pixis",
      scheduledAt: "2026-09-19T15:10:00.000Z",
      platform: "linkedin",
      format: "hot_take",
      caption: "x",
      status: "staged",
    });
    expect(findDueReminders(loadCalendarSlots(), now).map((r) => r.id)).not.toContain(row.id);
  });
});
