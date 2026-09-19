"use client";

import { useEffect } from "react";

import { fireDueReminders } from "@/lib/calendar";

/** When the app is open, nudge marketers ~30m before a calendar slot — never autoposts. */
export function CalendarRemindWatcher() {
  useEffect(() => {
    const tick = () => {
      try {
        fireDueReminders();
      } catch {
        // ignore
      }
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, []);

  return null;
}
