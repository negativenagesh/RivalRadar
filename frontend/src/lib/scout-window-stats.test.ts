import { describe, expect, it } from "vitest";

import { scoutWindowStatsFromEvents } from "./scout-window-stats";
import type { AgentEvent } from "./types";

function action(detail: string): AgentEvent {
  return {
    run_id: "r1",
    agent_id: "ingestion.socialfeed",
    service: "ingestion",
    step_type: "action",
    payload: { detail },
    sequence: 1,
    timestamp: "2026-09-14T00:00:00Z",
  };
}

describe("scoutWindowStatsFromEvents", () => {
  it("sums found, ingested, and outside-window skips", () => {
    const stats = scoutWindowStatsFromEvents([
      action("found_posts count=21 platform=linkedin source=browser"),
      action("skipped_post reason=outside_window day=2026-09-11 https://linkedin.com/x"),
      action("skipped_post reason=outside_window day=2026-09-10 https://linkedin.com/y"),
      action("past_window_stop platform=linkedin after=3 older than 2026-09-12"),
      action(
        "ingested_posts count=0 platform=linkedin window=2026-09-12→2026-09-14 skipped_outside=3 source=browser",
      ),
    ]);
    expect(stats.found).toBe(21);
    expect(stats.ingested).toBe(0);
    expect(stats.skippedOutside).toBe(2);
    expect(stats.pastWindowStops).toBe(1);
  });
});
