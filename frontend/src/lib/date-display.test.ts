import { describe, expect, it } from "vitest";

import { dmyToIso, isoToDmy, showCustomDateFields } from "./date-display";

describe("date-display", () => {
  it("round-trips ISO and dd/mm/yyyy", () => {
    expect(isoToDmy("2026-09-11")).toBe("11/09/2026");
    expect(dmyToIso("11/09/2026")).toBe("2026-09-11");
    expect(dmyToIso("1/9/2026")).toBe("2026-09-01");
  });

  it("rejects junk", () => {
    expect(dmyToIso("32/01/2026")).toBeNull();
    expect(dmyToIso("13/13/2026")).toBeNull();
    expect(isoToDmy("not-a-date")).toBe("");
  });

  it("hides From/To until Custom is open", () => {
    expect(showCustomDateFields(false, null, null)).toBe(false);
    expect(showCustomDateFields(true, null, null)).toBe(true);
    expect(showCustomDateFields(false, "2026-09-01", null)).toBe(true);
  });
});
