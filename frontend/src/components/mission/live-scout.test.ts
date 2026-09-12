import { describe, expect, it } from "vitest";

import { scoutActionLabel } from "./live-scout";

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
