import { describe, expect, it } from "vitest";

import {
  accountMatchesTarget,
  filterFindingsPosts,
  findingsBoard,
  isJunkCaption,
  linkedinActivityDay,
  missionWindow,
  normalizeHandle,
  postMetrics,
  postVisualUrl,
  watchUrl,
} from "./findings-filter";
import type { CompetitorAccount, CompetitorPost } from "./types";
import type { MissionTargetPreview } from "./mission-store";

const pixisLi: MissionTargetPreview = {
  label: "Pixis",
  platform: "linkedin",
  handleOrUrl: "pixisai",
  url: "https://www.linkedin.com/company/pixisai",
  source: "browser",
  role: "brand",
};

const smartlyIg: MissionTargetPreview = {
  label: "Smartly",
  platform: "instagram",
  handleOrUrl: "smartlyio",
  url: "https://www.instagram.com/smartlyio",
  source: "browser",
  role: "rival",
};

function post(over: Partial<CompetitorPost> & Pick<CompetitorPost, "id" | "account_id">): CompetitorPost {
  return {
    external_post_id: over.external_post_id ?? over.id,
    format: "founder_post",
    theme_tags: "linkedin,link:https://www.linkedin.com/feed/update/urn:li:activity:1",
    caption: "A real post",
    image_url: null,
    likes: 12,
    comments: 3,
    shares: 1,
    views: 0,
    posted_at: "2026-09-11T12:00:00Z",
    engagement_score: 0,
    themes: ["linkedin", "link:https://www.linkedin.com/feed/update/urn:li:activity:1"],
    ...over,
  };
}

describe("missionWindow", () => {
  it("uses custom from/to when set", () => {
    expect(missionWindow({ dateFrom: "2026-09-10", dateTo: "2026-09-12", lookbackDays: 3 })).toEqual({
      from: "2026-09-10",
      to: "2026-09-12",
    });
  });

  it("lookback is inclusive UTC days", () => {
    const now = new Date("2026-09-13T08:00:00Z");
    expect(missionWindow({ lookbackDays: 3, dateFrom: null, dateTo: null }, now)).toEqual({
      from: "2026-09-11",
      to: "2026-09-13",
    });
  });
});

describe("filterFindingsPosts", () => {
  const accounts: CompetitorAccount[] = [
    { id: "a1", handle: "@pixisai", display_name: "Pixis | LinkedIn", platform: "linkedin" },
    { id: "a2", handle: "@smartlyio", display_name: "Smartly", platform: "instagram" },
    { id: "a3", handle: "nova.wear", display_name: "Nova Wear", platform: "mock" },
    { id: "a4", handle: "@pixisai", display_name: "Pixis", platform: "youtube" },
  ];

  it("keeps only brand + rival posts inside the date window", () => {
    const rows = filterFindingsPosts(
      [
        post({ id: "in", account_id: "a1", posted_at: "2026-09-11T00:00:00Z" }),
        post({
          id: "ig",
          account_id: "a2",
          posted_at: "2026-09-12T00:00:00Z",
          caption: "Smartly drop",
          theme_tags: "instagram",
          themes: ["instagram", "link:https://www.instagram.com/p/abc/"],
        }),
        post({ id: "old", account_id: "a1", posted_at: "2026-08-01T00:00:00Z" }),
        post({ id: "mock", account_id: "a3", posted_at: "2026-09-11T00:00:00Z", caption: "jacket drop" }),
        post({
          id: "other",
          account_id: "a4",
          posted_at: "2026-09-11T00:00:00Z",
          caption: "old video",
          theme_tags: "youtube,source:yt_dlp",
          themes: ["youtube", "source:yt_dlp"],
          external_post_id: "abc123vid",
        }),
      ],
      accounts,
      {
        targets: [pixisLi, smartlyIg],
        dateFrom: "2026-09-10",
        dateTo: "2026-09-12",
        lookbackDays: 3,
      },
    );
    expect(rows.map((r) => r.post.id).sort()).toEqual(["ig", "in"]);
    expect(rows.find((r) => r.post.id === "in")?.company).toBe("Pixis");
    expect(rows.find((r) => r.post.id === "in")?.role).toBe("brand");
    expect(rows.find((r) => r.post.id === "ig")?.role).toBe("rival");
  });

  it("uses LinkedIn activity snowflake dates instead of scrape time", () => {
    expect(
      linkedinActivityDay(
        post({
          id: "june",
          account_id: "a1",
          external_post_id: "linkedin:urn:li:activity:7477400820427251712",
          posted_at: "2026-09-13T11:00:00Z",
        }),
      ),
    ).toBe("2026-06-29");
    const rows = filterFindingsPosts(
      [
        post({
          id: "old-li",
          account_id: "a1",
          external_post_id: "linkedin:urn:li:activity:7477400820427251712",
          posted_at: "2026-09-13T11:00:00Z",
          theme_tags:
            "linkedin,link:https://www.linkedin.com/feed/update/urn:li:activity:7477400820427251712",
          themes: [
            "linkedin",
            "link:https://www.linkedin.com/feed/update/urn:li:activity:7477400820427251712",
          ],
        }),
        post({
          id: "in-li",
          account_id: "a1",
          external_post_id: "linkedin:urn:li:activity:7504186055726764032",
          posted_at: "2026-09-13T11:00:00Z",
          theme_tags:
            "linkedin,link:https://www.linkedin.com/feed/update/urn:li:activity:7504186055726764032",
          themes: [
            "linkedin",
            "link:https://www.linkedin.com/feed/update/urn:li:activity:7504186055726764032",
          ],
        }),
      ],
      accounts,
      { targets: [pixisLi], dateFrom: "2026-09-11", dateTo: "2026-09-13", lookbackDays: 3 },
    );
    expect(rows.map((r) => r.post.id)).toEqual(["in-li"]);
    expect(rows[0]?.day).toBe("2026-09-11");
  });

  it("drops profile screenshots, login walls, and undated YouTube dumps", () => {
    const rows = filterFindingsPosts(
      [
        post({ id: "login", account_id: "a1", caption: "Sign Up | LinkedIn" }),
        post({
          id: "guess",
          account_id: "a1",
          themes: ["linkedin", "posted_at_uncertain"],
          theme_tags: "linkedin,posted_at_uncertain",
        }),
        post({
          id: "shot",
          account_id: "a1",
          themes: ["linkedin", "shot:screenshots/abc/1.jpg", "link:https://www.linkedin.com/company/pixisai"],
          theme_tags: "linkedin,shot:screenshots/abc/1.jpg",
        }),
        post({
          id: "yt-old",
          account_id: "a4",
          caption: "Old undated video",
          posted_at: "2026-09-12T00:00:00Z",
          themes: ["youtube", "video", "source:yt_dlp", "views:13"],
          theme_tags: "youtube,video,source:yt_dlp,views:13",
          external_post_id: "hr8nxJib32Q",
        }),
      ],
      accounts,
      { targets: [pixisLi], dateFrom: "2026-09-10", dateTo: "2026-09-12", lookbackDays: 3 },
    );
    expect(rows).toEqual([]);
  });

  it("keeps dated YouTube videos and reads views from themes", () => {
    const yt: MissionTargetPreview = {
      label: "Pixis",
      platform: "youtube",
      handleOrUrl: "pixisai",
      url: "https://www.youtube.com/@pixisai",
      source: "yt-dlp",
      role: "brand",
    };
    const rows = filterFindingsPosts(
      [
        post({
          id: "yt1",
          account_id: "a4",
          caption: "How Site Ascension Uses Pixis",
          posted_at: "2026-09-12T00:00:00Z",
          likes: 0,
          views: 0,
          external_post_id: "hr8nxJib32Q",
          themes: [
            "youtube",
            "source:yt_dlp",
            "views:15000",
            "likes:40",
            "date_from:2026-09-10",
            "date_to:2026-09-12",
            "link:https://www.youtube.com/watch?v=hr8nxJib32Q",
          ],
          theme_tags: "youtube,source:yt_dlp,views:15000",
        }),
      ],
      accounts,
      { targets: [yt], dateFrom: "2026-09-10", dateTo: "2026-09-12", lookbackDays: 3 },
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].views).toBe(15000);
    expect(rows[0].likes).toBe(40);
    expect(rows[0].href).toContain("watch?v=hr8nxJib32Q");
  });

  it("maps LinkedIn posts even when the account row is YouTube with the same handle", () => {
    const rows = filterFindingsPosts(
      [
        post({
          id: "misattached",
          account_id: "a4",
          external_post_id: "linkedin:urn:li:activity:747400820427357712",
          caption: "Pixis LinkedIn drop",
          themes: [
            "linkedin",
            "source:linkedin_scraper",
            "link:https://www.linkedin.com/feed/update/urn:li:activity:747400820427357712",
          ],
          theme_tags: "linkedin,source:linkedin_scraper",
        }),
      ],
      accounts,
      {
        targets: [pixisLi, smartlyIg],
        dateFrom: "2026-09-10",
        dateTo: "2026-09-12",
        lookbackDays: 3,
      },
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].company).toBe("Pixis");
    expect(rows[0].role).toBe("brand");
    expect(rows[0].platform).toBe("linkedin");
  });

  it("builds company vs rivalry lanes so empty platforms still show", () => {
    const rows = filterFindingsPosts(
      [post({ id: "in", account_id: "a1", posted_at: "2026-09-11T00:00:00Z" })],
      accounts,
      {
        targets: [
          pixisLi,
          { ...pixisLi, platform: "x", handleOrUrl: "Pixis_AI", url: "https://x.com/Pixis_AI" },
          smartlyIg,
        ],
        dateFrom: "2026-09-10",
        dateTo: "2026-09-12",
        lookbackDays: 3,
      },
    );
    const board = findingsBoard(rows, [
      pixisLi,
      { ...pixisLi, platform: "x", handleOrUrl: "Pixis_AI", url: "https://x.com/Pixis_AI" },
      smartlyIg,
    ]);
    expect(board.brand).toHaveLength(1);
    expect(board.brand[0].lanes.map((l) => l.platform)).toEqual(["linkedin", "x"]);
    expect(board.brand[0].lanes.find((l) => l.platform === "linkedin")?.empty).toBe(false);
    expect(board.brand[0].lanes.find((l) => l.platform === "x")?.empty).toBe(true);
    expect(board.rivals[0].company).toBe("Smartly");
    expect(board.rivals[0].lanes[0].empty).toBe(true);
  });
});

describe("helpers", () => {
  it("normalizes handles", () => {
    expect(normalizeHandle("@Pixis_AI")).toBe("pixis_ai");
    expect(normalizeHandle("https://www.linkedin.com/company/pixisai")).toBe("pixisai");
  });

  it("matches linkedin company accounts", () => {
    expect(
      accountMatchesTarget(
        { id: "a1", handle: "@pixisai", display_name: "Pixis", platform: "linkedin" },
        pixisLi,
      ),
    ).toBe(true);
  });

  it("reads metrics from columns and theme fallbacks", () => {
    expect(
      postMetrics({
        id: "p",
        account_id: "a",
        external_post_id: "v1",
        format: "founder_post",
        theme_tags: "youtube,views:15000,likes:40",
        caption: "vid",
        image_url: null,
        likes: 0,
        comments: 2,
        shares: 0,
        views: 0,
        posted_at: "2026-09-11T00:00:00Z",
        engagement_score: 0,
        themes: ["youtube", "views:15000", "likes:40"],
      }),
    ).toEqual({ likes: 40, comments: 2, shares: 0, views: 15000 });
  });

  it("recovers Instagram likes/comments from OG-style captions", () => {
    expect(
      postMetrics({
        id: "ig",
        account_id: "a",
        external_post_id: "instagram:DdYy_F9NG9W",
        format: "reel",
        theme_tags: "instagram",
        caption: '2 likes, 0 comments - pixis_ai on September 17, 2026: "Can search…"',
        image_url: null,
        likes: 0,
        comments: 0,
        shares: 0,
        views: 0,
        posted_at: "2026-09-17T00:00:00Z",
        engagement_score: 0,
        themes: ["instagram"],
      }),
    ).toEqual({ likes: 2, comments: 0, shares: 0, views: 0 });
  });

  it("opens original URLs", () => {
    expect(
      watchUrl(
        post({
          id: "x1",
          account_id: "a",
          external_post_id: "x:1896962592331219042",
          themes: [],
          theme_tags: "",
        }),
        "x",
      ),
    ).toBe("https://x.com/i/status/1896962592331219042");
    expect(
      watchUrl(
        post({
          id: "li1",
          account_id: "a",
          external_post_id: "linkedin:urn:li:activity:747400820427357712",
          themes: ["linkedin", "link:https://www.linkedin.com/company/pixisai"],
          theme_tags: "linkedin,link:https://www.linkedin.com/company/pixisai",
        }),
        "linkedin",
      ),
    ).toBe("https://www.linkedin.com/feed/update/urn:li:activity:747400820427357712");
  });

  it("flags junk captions", () => {
    expect(isJunkCaption("Sign Up | LinkedIn")).toBe(true);
    expect(isJunkCaption("Launch day at Pixis")).toBe(false);
  });

  it("prefers stored media keys over remote URLs", () => {
    expect(
      postVisualUrl(
        post({
          id: "m1",
          account_id: "a",
          image_url: "https://cdn.example/hotlink.jpg",
          media_keys: ["media/run/post.jpg"],
        }),
      ),
    ).toContain("/ingestion/media/media/run/post.jpg");
    expect(
      postVisualUrl(
        post({
          id: "shot",
          account_id: "a",
          image_url: "/ingestion/runs/abc/screenshots/1.jpg",
        }),
      ),
    ).toBeNull();
  });
});
