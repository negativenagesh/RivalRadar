import { describe, expect, it } from "vitest";

import type { IntelFacts } from "./intel-facts";
import { formatScoutDoneEmail } from "./scout-done-email";

const sampleFacts: IntelFacts = {
  window: { from: "2026-09-14", to: "2026-09-20", days: 7, label: "2026-09-14 → 2026-09-20" },
  brandName: "Pixis",
  companies: [
    {
      name: "Pixis",
      role: "brand",
      posts: 10,
      avgEngagement: 42,
      visualPct: 80,
      platforms: [
        {
          platform: "linkedin",
          posts: 8,
          avgLikes: 20,
          avgComments: 2,
          avgShares: 1,
          avgViews: 0,
          commentRate: 10,
          cadencePerDay: 1.1,
        },
      ],
    },
    {
      name: "Smartly",
      role: "rival",
      posts: 12,
      avgEngagement: 55,
      visualPct: 70,
      platforms: [
        {
          platform: "instagram",
          posts: 12,
          avgLikes: 40,
          avgComments: 5,
          avgShares: 2,
          avgViews: 100,
          commentRate: 12.5,
          cadencePerDay: 1.7,
        },
      ],
    },
  ],
  formatMix: [{ format: "founder_post", count: 9, pct: 41 }],
  topThemes: [{ theme: "automation", count: 3 }],
  topPosts: [
    {
      company: "Pixis",
      role: "brand",
      platform: "linkedin",
      caption: "Prism keeps Black Friday pacing on track",
      href: "https://www.linkedin.com/feed/update/urn:li:activity:1",
      likes: 40,
      comments: 4,
      shares: 2,
      views: 0,
      format: "founder_post",
      score: 62,
      hasMedia: true,
      themes: ["automation"],
    },
  ],
  bottomPosts: [],
  winningBecause: ["Smartly on instagram: 12 posts, avg 40 likes / 5 comments"],
  leakingBecause: ["Your avg engagement 42 vs rival 55 — you're under-cooking the heat"],
  sniperQueue: [],
};

describe("formatScoutDoneEmail", () => {
  it("includes brand/rival metrics and top posts", () => {
    const copy = formatScoutDoneEmail(sampleFacts);
    expect(copy.shortBody).toContain("22 posts");
    expect(copy.emailBody).toContain("Pixis [YOUR BRAND]");
    expect(copy.emailBody).toContain("Smartly [RIVAL]");
    expect(copy.emailBody).toContain("linkedin:");
    expect(copy.emailBody).toContain("Top posts by engagement");
    expect(copy.emailHtml).toContain("avg engagement");
    expect(copy.emailHtml).toContain("Prism keeps Black Friday");
    expect(copy.emailHtml).toContain("What's working");
  });
});
