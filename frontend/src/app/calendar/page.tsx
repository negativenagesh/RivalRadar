"use client";

import { useMemo, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { CalendarDays, ChevronLeft, ChevronRight, Send, Trash2 } from "lucide-react";

import { NavBar } from "@/components/nav-bar";
import { Button } from "@/components/ui/button";
import {
  addDays,
  groupSlotsByDay,
  loadCalendarSlots,
  removeCalendarSlot,
  slotsForWeek,
  startOfWeek,
  subscribeCalendar,
  updateCalendarSlot,
  type CalendarSlot,
} from "@/lib/calendar";
import { stagePlatformPost } from "@/lib/api";
import { pushNotification } from "@/lib/notifications";
import { loadMission } from "@/lib/mission-store";
import { readStudioAssets } from "@/lib/studio-assets";

function snapshot(): string {
  return JSON.stringify(loadCalendarSlots());
}

export default function CalendarPage() {
  const raw = useSyncExternalStore(subscribeCalendar, snapshot, () => "[]");
  const slots = JSON.parse(raw) as CalendarSlot[];
  const [anchor, setAnchor] = useState(() => startOfWeek(new Date()));
  const [stagingId, setStagingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const weekStart = useMemo(() => startOfWeek(anchor), [anchor]);
  const weekSlots = useMemo(() => slotsForWeek(slots, weekStart), [slots, weekStart]);
  const days = useMemo(() => groupSlotsByDay(weekSlots, weekStart), [weekSlots, weekStart]);
  const weekLabel = `${weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} – ${addDays(weekStart, 6).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`;

  async function stageSlot(row: CalendarSlot): Promise<void> {
    const brand = row.brandName || loadMission().brand.displayName || "brand";
    const assets = readStudioAssets(brand);
    const asset = row.assetId ? assets.find((a) => a.id === row.assetId) : undefined;
    const caption = (row.caption || asset?.text || "").trim();
    const media = asset?.image_data_base64;
    if (!caption) {
      setError("This slot has no caption — re-schedule from Format Studio.");
      return;
    }
    if (
      !window.confirm(
        `Open ${row.platform} in Connect/noVNC with this caption staged? Nothing auto-publishes — you hit publish yourself.`,
      )
    ) {
      return;
    }
    setStagingId(row.id);
    setError(null);
    try {
      const result = await stagePlatformPost({
        platform: row.platform,
        caption,
        media_png_b64: media ?? undefined,
        approved: true,
      });
      updateCalendarSlot(row.id, { status: "staged" });
      pushNotification({
        kind: "stage_ready",
        title: `Staged — ${row.platform}`,
        body: `${row.format} for ${row.brandName} is in the Connect composer. Finish in noVNC.`,
        href: "/calendar",
        email: false,
      });
      const viewer = result.viewer_url?.trim();
      if (viewer) window.open(viewer, "_blank", "noopener,noreferrer");
      if (!result.ok) setError(result.detail || "Staging failed");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Staging failed");
    } finally {
      setStagingId(null);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <NavBar />
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-6 py-10">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="font-ui text-[10px] font-bold uppercase tracking-[0.22em] text-primary">
              Plan · remind · stage
            </p>
            <h1 className="mt-1 flex items-center gap-2 font-display text-4xl font-bold tracking-tight">
              <CalendarDays className="size-8 text-primary" />
              Content calendar
            </h1>
            <p className="mt-2 max-w-xl text-sm text-muted-foreground">
              Schedule Studio frames for later. We remind you ~30 minutes before — you still Stage in
              Connect and hit publish yourself. Never autoposts.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAnchor(addDays(weekStart, -7))}
              aria-label="Previous week"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="font-ui min-w-[11rem] text-center text-sm font-medium">{weekLabel}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAnchor(addDays(weekStart, 7))}
              aria-label="Next week"
            >
              <ChevronRight className="size-4" />
            </Button>
            <Button variant="secondary" size="sm" onClick={() => setAnchor(new Date())}>
              This week
            </Button>
          </div>
        </div>

        {error && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}

        {slots.length === 0 && (
          <div className="rounded-2xl border border-dashed border-border/60 px-6 py-12 text-center">
            <p className="font-accent text-lg italic text-muted-foreground">
              No planned posts yet.
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              Generate a frame in Format Studio, then hit{" "}
              <span className="text-foreground">Schedule</span> under Post to platform.
            </p>
            <Button className="mt-4" asChild>
              <Link href="/mission">Open Mission → Report</Link>
            </Button>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {days.map((day) => (
            <section
              key={day.day}
              className="min-h-[160px] rounded-2xl border border-border/50 bg-card/20 p-3"
            >
              <h2 className="font-ui mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                {day.label}
              </h2>
              {day.rows.length === 0 ? (
                <p className="font-accent text-xs italic text-muted-foreground/70">Open</p>
              ) : (
                <ul className="space-y-2">
                  {day.rows.map((row) => (
                    <li
                      key={row.id}
                      className="rounded-xl border border-border/40 bg-background/60 p-2.5 text-sm"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="font-ui text-[10px] font-semibold uppercase tracking-wider text-primary">
                            {new Date(row.scheduledAt).toLocaleTimeString(undefined, {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}{" "}
                            · {row.platform}
                          </p>
                          <p className="mt-0.5 font-medium leading-snug">
                            {row.overlayText || row.caption.slice(0, 80) || row.format}
                          </p>
                          <p className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                            {row.format} · {row.status.replace("_", " ")}
                          </p>
                        </div>
                        <button
                          type="button"
                          aria-label="Remove slot"
                          className="text-muted-foreground hover:text-destructive"
                          onClick={() => removeCalendarSlot(row.id)}
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {(row.status === "draft" || row.status === "approved") && (
                          <Button
                            size="sm"
                            className="h-7 gap-1 px-2 text-xs"
                            disabled={stagingId === row.id}
                            onClick={() => void stageSlot(row)}
                          >
                            <Send className="size-3" />
                            {stagingId === row.id ? "Staging…" : "Stage in Connect"}
                          </Button>
                        )}
                        {row.status === "staged" && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 px-2 text-xs"
                            onClick={() =>
                              updateCalendarSlot(row.id, { status: "published_manual" })
                            }
                          >
                            Mark published
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </main>
    </div>
  );
}
