import { describe, expect, it } from "vitest";

import {
  LOOKBACK_DEFAULT_DAYS,
  LOOKBACK_LEGACY_DEFAULT_DAYS,
  resolveStoredLookbackDays,
} from "./mission-store";

describe("resolveStoredLookbackDays", () => {
  it("bumps legacy default 3d to 7d once when no custom range", () => {
    const out = resolveStoredLookbackDays(LOOKBACK_LEGACY_DEFAULT_DAYS, null, null, {
      bumpDone: false,
    });
    expect(out).toEqual({ days: LOOKBACK_DEFAULT_DAYS, didBump: true });
  });

  it("keeps intentional 3d after the bump has already run", () => {
    const out = resolveStoredLookbackDays(3, null, null, { bumpDone: true });
    expect(out).toEqual({ days: 3, didBump: false });
  });

  it("does not bump when a custom date range is set", () => {
    const out = resolveStoredLookbackDays(3, "2026-09-12", "2026-09-14", {
      bumpDone: false,
    });
    expect(out).toEqual({ days: 3, didBump: false });
  });
});
