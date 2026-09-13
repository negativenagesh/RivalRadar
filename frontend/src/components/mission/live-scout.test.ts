import { describe, expect, it } from "vitest";

import { scoutActionLabel, shotsForTarget, targetLaneStatus } from "./live-scout";
import type { MissionTargetPreview } from "@/lib/mission-store";
import type { AgentEvent } from "@/lib/types";

describe("scoutActionLabel", () => {
  it("starts idle as Start Scout", () => {
    expect(
      scoutActionLabel({ locked: false, starting: false, stopping: false, live: false }),
    ).toBe("Start Scout");
  });

  it("shows Starting then Stop Scout while a run is live", () => {
    expect(
      scoutActionLabel({ locked: false, starting: true, stopping: false, live: false }),
    ).toBe("Starting scout…");
    expect(
      scoutActionLabel({ locked: false, starting: false, stopping: false, live: true }),
    ).toBe("Stop Scout");
    expect(
      scoutActionLabel({ locked: false, starting: false, stopping: true, live: true }),
    ).toBe("Stopping…");
  });

  it("stays locked until platforms are connected", () => {
    expect(
      scoutActionLabel({ locked: true, starting: false, stopping: false, live: false }),
    ).toBe("Connect platforms to unlock");
  });
});

const pixisLi: MissionTargetPreview = {
  label: "Pixis",
  platform: "linkedin",
  handleOrUrl: "pixisai",
  url: "https://www.linkedin.com/company/pixisai",
  source: "browser",
  role: "brand",
};

const pixisX: MissionTargetPreview = {
  label: "Pixis",
  platform: "x",
  handleOrUrl: "Pixis_AI",
  url: "https://x.com/Pixis_AI",
  source: "browser",
  role: "brand",
};

function ev(detail: string, extra: Partial<AgentEvent> = {}): AgentEvent {
  return {
    run_id: "r",
    agent_id: "ingestion.socialfeed",
    service: "ingestion",
    step_type: "action",
    payload: { detail },
    timestamp: "2026-09-13T00:00:00Z",
    sequence: extra.sequence ?? 1,
    ...extra,
  };
}

describe("targetLaneStatus", () => {
  it("tracks scout_next then ingested_posts per handle", () => {
    const events = [
      ev("scout_next platform=linkedin target=1/5 handle=pixisai"),
      ev("found_posts count=8 platform=linkedin source=oss"),
      ev("ingested_posts count=8 platform=linkedin window=2026-09-11→2026-09-13 source=oss"),
      ev("scout_next platform=x target=2/5 handle=Pixis_AI"),
      ev("found_posts count=14 platform=x source=browser"),
      ev("ingested_posts count=0 platform=x window=2026-09-11→2026-09-13 source=browser"),
    ];
    expect(targetLaneStatus(events, pixisLi)).toEqual({
      state: "done",
      found: 8,
      ingested: 8,
    });
    expect(targetLaneStatus(events, pixisX)).toEqual({
      state: "done",
      found: 14,
      ingested: 0,
    });
  });
});

describe("shotsForTarget", () => {
  it("keeps LinkedIn frames on Pixis even without the slug in the permalink", () => {
    const shots = [
      {
        id: "1",
        b64: "x",
        platform: "linkedin",
        label: "@pixisai media",
        url: "https://www.linkedin.com/feed/update/urn:li:activity:1",
        company: "Pixis",
        handle: "@pixisai",
      },
    ];
    expect(shotsForTarget(shots, pixisLi)).toHaveLength(1);
    expect(shotsForTarget(shots, pixisX)).toHaveLength(0);
  });
});

describe("scoutActionLabel", () => {
  it("starts idle as Start Scout", () => {
    expect(
      scoutActionLabel({ locked: false, starting: false, stopping: false, live: false }),
    ).toBe("Start Scout");
  });

  it("shows Starting then Stop Scout while a run is live", () => {
    expect(
      scoutActionLabel({ locked: false, starting: true, stopping: false, live: false }),
    ).toBe("Starting scout…");
    expect(
      scoutActionLabel({ locked: false, starting: false, stopping: false, live: true }),
    ).toBe("Stop Scout");
    expect(
      scoutActionLabel({ locked: false, starting: false, stopping: true, live: true }),
    ).toBe("Stopping…");
  });

  it("stays locked until platforms are connected", () => {
    expect(
      scoutActionLabel({ locked: true, starting: false, stopping: false, live: false }),
    ).toBe("Connect platforms to unlock");
  });
});
