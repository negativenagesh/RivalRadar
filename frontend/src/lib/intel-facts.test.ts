import { describe, expect, it } from "vitest";

import { filterFindingsPosts } from "./findings-filter";
import { buildIntelFacts, fallbackIntel } from "./intel-facts";
import type { CompetitorAccount, CompetitorPost } from "./types";
import type { MissionTargetPreview } from "./mission-store";
import { DEFAULT_BRAND } from "./mission-store";

const pixisLi: MissionTargetPreview = {
  label: "Pixis",
  platform: "linkedin",
  handleOrUrl: "pixisai",
  url: "https://www.linkedin.com/company/pixisai",
  source: "browser",
  role: "brand",
};

const smartlyLi: MissionTargetPreview = {
  label: "Smartly",
  platform: "linkedin",
  handleOrUrl: "smartly-io",
  url: "https://www.linkedin.com/company/smartly-io",
  source: "browser",
  role: "rival",
};

function post(
  over: Partial<CompetitorPost> & Pick<CompetitorPost, "id" | "account_id">,
): CompetitorPost {
  return {
    external_post_id: over.external_post_id ?? over.id,
    format: "founder_post",
    theme_tags: "linkedin,link:https://www.linkedin.com/feed/update/urn:li:activity:7504186055726764032",
    caption: "A real post",
    image_url: "/ingestion/media/x.jpg",
    likes: 10,
    comments: 2,
    shares: 1,
    views: 0,
    posted_at: "2026-09-11T12:00:00Z",
    engagement_score: 20,
    themes: ["linkedin", "link:https://www.linkedin.com/feed/update/urn:li:activity:7504186055726764032"],
    media_keys: ["media/x.jpg"],
    ...over,
  };
}

describe("buildIntelFacts", () => {
  const accounts: CompetitorAccount[] = [
    { id: "a1", handle: "@pixisai", display_name: "Pixis", platform: "linkedin" },
    { id: "a2", handle: "@smartly-io", display_name: "Smartly", platform: "linkedin" },
  ];

  it("builds a scoreboard and sniper queue from in-window rows", () => {
    const rows = filterFindingsPosts(
      [
        post({
          id: "b1",
          account_id: "a1",
          likes: 4,
          comments: 0,
          engagement_score: 4,
          caption: "we shipped a thing",
        }),
        post({
          id: "r1",
          account_id: "a2",
          likes: 80,
          comments: 12,
          engagement_score: 140,
          caption: "Performance marketing is being rewritten",
          theme_tags:
            "linkedin,link:https://www.linkedin.com/feed/update/urn:li:activity:7504262650881667073",
          themes: [
            "linkedin",
            "link:https://www.linkedin.com/feed/update/urn:li:activity:7504262650881667073",
          ],
          external_post_id: "linkedin:urn:li:activity:7504262650881667073",
        }),
      ],
      accounts,
      { targets: [pixisLi, smartlyLi], dateFrom: "2026-09-11", dateTo: "2026-09-13", lookbackDays: 3 },
    );
    const facts = buildIntelFacts(rows, {
      brand: { ...DEFAULT_BRAND, displayName: "Pixis" },
      dateFrom: "2026-09-11",
      dateTo: "2026-09-13",
      lookbackDays: 3,
    });
    expect(facts.brandName).toBe("Pixis");
    expect(facts.companies[0]?.role).toBe("brand");
    expect(facts.sniperQueue.length).toBeGreaterThan(0);
    expect(facts.sniperQueue[0]?.href).toContain("linkedin.com");
    expect(facts.leakingBecause.join(" ")).toMatch(/engagement|Cadence|Comment/i);
  });

  it("falls back to fact cards when Gemini is down", () => {
    const facts = buildIntelFacts([], {
      brand: { ...DEFAULT_BRAND, displayName: "Pixis" },
      lookbackDays: 3,
    });
    const intel = fallbackIntel(facts);
    expect(intel.scoreboard_blurb).toMatch(/Pixis/);
    expect(intel.fumbling.join(" ")).toMatch(/Zero in-window/i);
    expect(intel.markdown).toMatch(/# Intel brief/);
    expect(intel.markdown).toMatch(/## Sniper docket/);
    expect(intel.reports.map((r) => r.id)).toEqual([
      "plays",
      "format",
      "sniper",
      "platforms",
      "competitive",
    ]);
  });
});
