import { describe, expect, it } from "vitest";

import { isValidSocialUrl, isValidWebsite } from "./social-validate";
import { canReachStep, validateContext } from "./mission-validate";
import { DEFAULT_MISSION, newCompetitor } from "./mission-store";

describe("social URL validation", () => {
  it("accepts platform profile URLs", () => {
    expect(isValidSocialUrl("linkedin", "https://linkedin.com/company/pixis")).toBe(true);
    expect(isValidSocialUrl("x", "x.com/pixis")).toBe(true);
    expect(isValidSocialUrl("instagram", "instagram.com/pixis.ai")).toBe(true);
    expect(isValidSocialUrl("tiktok", "tiktok.com/@pixis")).toBe(true);
    expect(isValidSocialUrl("youtube", "youtube.com/@pixis")).toBe(true);
    expect(isValidSocialUrl("threads", "threads.net/@pixis")).toBe(true);
  });

  it("rejects junk", () => {
    expect(isValidSocialUrl("linkedin", "not-a-link")).toBe(false);
    expect(isValidSocialUrl("x", "facebook.com/x")).toBe(false);
    expect(isValidWebsite("")).toBe(false);
    expect(isValidWebsite("pixis.ai")).toBe(true);
  });
});

describe("mission step gating", () => {
  it("blocks leaving context without brand essentials", () => {
    const issues = validateContext(DEFAULT_MISSION);
    expect(issues.length).toBeGreaterThan(0);
    expect(issues.some((i) => i.fieldId === "brand-displayName")).toBe(true);
  });

  it("allows scout once context is complete", () => {
    const mission = structuredClone(DEFAULT_MISSION);
    mission.brand.displayName = "Pixis";
    mission.brand.category = "SaaS";
    mission.brand.website = "pixis.ai";
    mission.brand.voiceNotes = "witty";
    mission.competitors = [{ ...newCompetitor(), name: "Rival", website: "rival.com" }];
    expect(canReachStep(1, mission, 0)).toEqual([]);
    expect(canReachStep(2, mission, 0).some((i) => i.step === 1)).toBe(true);
  });
});
