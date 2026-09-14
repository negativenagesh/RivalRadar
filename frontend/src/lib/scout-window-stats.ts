import type { AgentEvent } from "@/lib/types";

export type ScoutWindowStats = {
  found: number;
  ingested: number;
  skippedOutside: number;
  pastWindowStops: number;
};

/** Aggregate scout progress from the live event log for the In-window section. */
export function scoutWindowStatsFromEvents(events: AgentEvent[]): ScoutWindowStats {
  let found = 0;
  let ingested = 0;
  let skippedOutside = 0;
  let pastWindowStops = 0;

  for (const ev of events) {
    if (ev.step_type !== "action") continue;
    const detail = String(ev.payload.detail ?? "");
    const foundMatch = detail.match(/found_posts count=(\d+)/);
    if (foundMatch) found += Number(foundMatch[1]);
    const ingestedMatch = detail.match(/ingested_posts count=(\d+)/);
    if (ingestedMatch) ingested += Number(ingestedMatch[1]);
    // Prefer per-post skip events so the count stays live mid-run (avoid double-counting
    // the ingested_posts skipped_outside= summary).
    if (detail.includes("skipped_post reason=outside_window")) skippedOutside += 1;
    if (detail.startsWith("past_window_stop")) pastWindowStops += 1;
  }

  return { found, ingested, skippedOutside, pastWindowStops };
}
