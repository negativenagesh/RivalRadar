import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) =>
    React.createElement("a", { href }, children),
}));

vi.mock("@/lib/api", () => ({
  generateIntelReport: vi.fn(),
  generateCreative: vi.fn(),
  dropSocialComment: vi.fn(),
  listConnections: vi.fn(async () => [{ platform: "linkedin", status: "connected" }]),
}));

import { GeminiKeyProvider } from "@/components/gemini-key-provider";
import { DiscoveryReport } from "./discovery-report";
import type { IntelFacts } from "@/lib/intel-facts";
import { DEFAULT_BRAND, DEFAULT_PERMISSIONS } from "@/lib/mission-store";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

const facts: IntelFacts = {
  window: { from: "2026-09-11", to: "2026-09-13", days: 3, label: "2026-09-11 → 2026-09-13" },
  brandName: "Pixis",
  companies: [
    {
      name: "Pixis",
      role: "brand",
      posts: 2,
      avgEngagement: 4,
      platforms: [
        {
          platform: "linkedin",
          posts: 2,
          avgLikes: 4,
          avgComments: 0,
          avgShares: 0,
          avgViews: 0,
          commentRate: 0,
          cadencePerDay: 0.7,
        },
      ],
    },
  ],
  formatMix: [{ format: "founder_post", count: 2, pct: 100 }],
  topPosts: [],
  bottomPosts: [],
  winningBecause: ["Smartly on linkedin: 1 posts, avg 80 likes"],
  leakingBecause: ["Your avg engagement 4 vs rival 140"],
  sniperQueue: [
    {
      company: "Smartly",
      role: "rival",
      platform: "linkedin",
      caption: "Performance marketing is being rewritten",
      href: "https://www.linkedin.com/feed/update/urn:li:activity:1",
      likes: 80,
      comments: 12,
      shares: 0,
      views: 0,
      format: "founder_post",
      score: 140,
      hasMedia: true,
    },
  ],
};

describe("DiscoveryReport war room", () => {
  it("renders fact scoreboard, format chips, and key warning without Gemini", () => {
    render(
      <GeminiKeyProvider>
        <DiscoveryReport
          facts={facts}
          permissions={DEFAULT_PERMISSIONS}
          onPermissionsChange={() => undefined}
          brand={{ ...DEFAULT_BRAND, displayName: "Pixis" }}
        />
      </GeminiKeyProvider>,
    );

    expect(screen.getByRole("alert")).toHaveTextContent(/Paste a Gemini, DeepSeek, or NVIDIA key/i);
    expect(screen.getAllByText("Scoreboard").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Pixis").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Hot take quote card" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Shitpost / meme" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download \.md/i })).toBeInTheDocument();
    expect(screen.getAllByText(/Intel brief/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/heat vs the room/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "This week's plays" })).toBeInTheDocument();
    expect(screen.getByText("Comment sniper")).toBeInTheDocument();
    expect(screen.getByText(/human delays/i)).toBeInTheDocument();
  });
});
