import { describe, expect, it } from "vitest";

import { postsForActiveScoutSession, scoutBaselineFromPosts } from "./scout-session-posts";
import type { CompetitorPost } from "./types";

function post(id: string): CompetitorPost {
  return {
    id,
    account_id: "a1",
    external_post_id: id,
    format: "meme",
    theme_tags: "instagram",
    caption: "hello",
    image_url: null,
    likes: 1,
    comments: 0,
    shares: 0,
    posted_at: "2026-09-19T00:00:00Z",
    engagement_score: 1,
    themes: ["instagram"],
  };
}

describe("postsForActiveScoutSession", () => {
  it("shows all posts when no baseline (idle / pre-session)", () => {
    const rows = [post("old-1"), post("old-2")];
    expect(postsForActiveScoutSession(rows, null)).toEqual(rows);
  });

  it("hides baseline posts and keeps only newly extracted ids", () => {
    const old = [post("old-1"), post("old-2")];
    const baseline = scoutBaselineFromPosts(old);
    const during = [...old, post("new-1"), post("new-2")];
    expect(postsForActiveScoutSession(during, baseline).map((p) => p.id)).toEqual([
      "new-1",
      "new-2",
    ]);
  });

  it("returns empty right after Start Scout when only baseline ids exist", () => {
    const old = [post("old-1")];
    const baseline = scoutBaselineFromPosts(old);
    expect(postsForActiveScoutSession(old, baseline)).toEqual([]);
    expect(postsForActiveScoutSession([], baseline)).toEqual([]);
  });
});
