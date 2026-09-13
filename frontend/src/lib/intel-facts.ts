import type { FindingsRow } from "./findings-filter";
import { missionWindow } from "./findings-filter";
import type { BrandProfile, IntelReport } from "./types";

export type IntelPlatformStats = {
  platform: string;
  posts: number;
  avgLikes: number;
  avgComments: number;
  avgShares: number;
  avgViews: number;
  commentRate: number;
  cadencePerDay: number;
};

export type IntelCompany = {
  name: string;
  role: "brand" | "rival";
  posts: number;
  avgEngagement: number;
  platforms: IntelPlatformStats[];
};

export type IntelPostRef = {
  company: string;
  role: "brand" | "rival";
  platform: string;
  caption: string;
  href: string | null;
  likes: number;
  comments: number;
  shares: number;
  views: number;
  format: string;
  score: number;
  hasMedia: boolean;
};

export type IntelFacts = {
  window: { from: string; to: string; days: number; label: string };
  brandName: string;
  companies: IntelCompany[];
  formatMix: { format: string; count: number; pct: number }[];
  topPosts: IntelPostRef[];
  bottomPosts: IntelPostRef[];
  winningBecause: string[];
  leakingBecause: string[];
  sniperQueue: IntelPostRef[];
};

function avg(nums: number[]): number {
  if (!nums.length) return 0;
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

function toRef(row: FindingsRow): IntelPostRef {
  return {
    company: row.company,
    role: row.role,
    platform: row.platform,
    caption: (row.post.caption.split("\n")[0] || row.post.caption).trim().slice(0, 180),
    href: row.href,
    likes: row.likes,
    comments: row.comments,
    shares: row.shares,
    views: row.views,
    format: row.post.format,
    score: row.post.engagement_score || row.likes + row.comments * 3 + row.shares * 5,
    hasMedia: Boolean(row.post.media_keys?.[0] || (row.post.image_url && !row.post.image_url.includes("/screenshots/"))),
  };
}

export function buildIntelFacts(
  rows: FindingsRow[],
  input: {
    brand: BrandProfile;
    dateFrom?: string | null;
    dateTo?: string | null;
    lookbackDays: number;
  },
  now = new Date(),
): IntelFacts {
  const window = missionWindow(input, now);
  const days = Math.max(
    1,
    Math.round(
      (new Date(`${window.to}T00:00:00Z`).getTime() - new Date(`${window.from}T00:00:00Z`).getTime()) /
        86_400_000,
    ) + 1,
  );
  const label =
    input.dateFrom && input.dateTo
      ? `${window.from} → ${window.to}`
      : `last ${input.lookbackDays} days`;

  const byCompany = new Map<string, FindingsRow[]>();
  for (const row of rows) {
    const list = byCompany.get(row.company) ?? [];
    list.push(row);
    byCompany.set(row.company, list);
  }

  const companies: IntelCompany[] = [...byCompany.entries()].map(([name, list]) => {
    const role = list[0]?.role ?? "rival";
    const byPlat = new Map<string, FindingsRow[]>();
    for (const row of list) {
      const bucket = byPlat.get(row.platform) ?? [];
      bucket.push(row);
      byPlat.set(row.platform, bucket);
    }
    const platforms: IntelPlatformStats[] = [...byPlat.entries()].map(([platform, posts]) => {
      const likes = posts.map((p) => p.likes);
      const comments = posts.map((p) => p.comments);
      const shares = posts.map((p) => p.shares);
      const views = posts.map((p) => p.views);
      const avgLikes = avg(likes);
      const avgComments = avg(comments);
      return {
        platform,
        posts: posts.length,
        avgLikes: round1(avgLikes),
        avgComments: round1(avgComments),
        avgShares: round1(avg(shares)),
        avgViews: round1(avg(views)),
        commentRate: round1(avgLikes > 0 ? (avgComments / avgLikes) * 100 : avgComments > 0 ? 100 : 0),
        cadencePerDay: round1(posts.length / days),
      };
    });
    const scores = list.map((p) => p.post.engagement_score || p.likes + p.comments * 3);
    return {
      name,
      role,
      posts: list.length,
      avgEngagement: round1(avg(scores)),
      platforms,
    };
  });

  companies.sort((a, b) => {
    if (a.role !== b.role) return a.role === "brand" ? -1 : 1;
    return b.avgEngagement - a.avgEngagement;
  });

  const formatCounts = new Map<string, number>();
  for (const row of rows) {
    formatCounts.set(row.post.format, (formatCounts.get(row.post.format) ?? 0) + 1);
  }
  const formatMix = [...formatCounts.entries()]
    .map(([format, count]) => ({
      format,
      count,
      pct: rows.length ? Math.round((count / rows.length) * 100) : 0,
    }))
    .sort((a, b) => b.count - a.count);

  const ranked = [...rows].sort((a, b) => (b.post.engagement_score || 0) - (a.post.engagement_score || 0));
  const topPosts = ranked.slice(0, 5).map(toRef);
  const bottomPosts = [...ranked].reverse().slice(0, 3).map(toRef);

  const brand = companies.find((c) => c.role === "brand");
  const rivals = companies.filter((c) => c.role === "rival");
  const winningBecause: string[] = [];
  const leakingBecause: string[] = [];

  const hottestRivalPlat = rivals
    .flatMap((c) => c.platforms.map((p) => ({ company: c.name, ...p })))
    .sort((a, b) => b.avgLikes + b.avgComments * 3 - (a.avgLikes + a.avgComments * 3))[0];
  if (hottestRivalPlat) {
    winningBecause.push(
      `${hottestRivalPlat.company} on ${hottestRivalPlat.platform}: ${hottestRivalPlat.posts} posts, avg ${hottestRivalPlat.avgLikes} likes / ${hottestRivalPlat.avgComments} comments`,
    );
  }
  const hotFormat = formatMix[0];
  if (hotFormat) {
    winningBecause.push(`Window mix is ${hotFormat.pct}% ${hotFormat.format} (${hotFormat.count} posts)`);
  }

  if (brand) {
    const rivalAvg = avg(rivals.map((r) => r.avgEngagement)) || 0;
    if (rivalAvg > 0 && brand.avgEngagement < rivalAvg * 0.7) {
      leakingBecause.push(
        `Your avg engagement ${brand.avgEngagement} vs rival ${round1(rivalAvg)} — you're under-cooking the heat`,
      );
    }
    const brandCadence = avg(brand.platforms.map((p) => p.cadencePerDay));
    const rivalCadence = avg(rivals.flatMap((r) => r.platforms.map((p) => p.cadencePerDay)));
    if (rivalCadence > 0 && brandCadence < rivalCadence * 0.6) {
      leakingBecause.push(
        `Cadence ${round1(brandCadence)} posts/day vs their ${round1(rivalCadence)} — you go dark, they stay in the feed`,
      );
    }
    const brandCommentRate = avg(brand.platforms.map((p) => p.commentRate));
    const rivalCommentRate = avg(rivals.flatMap((r) => r.platforms.map((p) => p.commentRate)));
    if (rivalCommentRate > 0 && brandCommentRate < rivalCommentRate * 0.7) {
      leakingBecause.push(
        `Comment rate ${round1(brandCommentRate)}% vs their ${round1(rivalCommentRate)}% — hooks aren't earning replies`,
      );
    }
    const brandTextOnly = rows.filter((r) => r.role === "brand" && !toRef(r).hasMedia).length;
    if (brand.posts > 0 && brandTextOnly / brand.posts >= 0.5) {
      leakingBecause.push(`${brandTextOnly}/${brand.posts} of your posts have no visual — feed algorithms ghost text-only`);
    }
  }
  if (!rows.length) {
    leakingBecause.push("Zero in-window posts — scout this lookback before the report can roast anyone");
  }

  const sniperQueue = ranked
    .filter((r) => r.role === "rival" && r.href)
    .slice(0, 8)
    .map(toRef);

  return {
    window: { from: window.from, to: window.to, days, label },
    brandName: input.brand.displayName || "your brand",
    companies,
    formatMix,
    topPosts,
    bottomPosts,
    winningBecause,
    leakingBecause,
    sniperQueue,
  };
}

function bullets(lines: string[], empty: string): string {
  if (!lines.length) return `- ${empty}`;
  return lines.map((line) => `- ${line}`).join("\n");
}

export function factsToMarkdown(facts: IntelFacts): string {
  const companyLines = facts.companies.map((c) => {
    const role = c.role === "brand" ? "you" : "rival";
    return `**${c.name}** (${role}): ${c.posts} posts, avg heat ${c.avgEngagement}`;
  });
  const mixLines = facts.formatMix.map(
    (row) => `**${row.format}** is ${row.pct}% of the window (${row.count} posts)`,
  );
  const receipts = facts.topPosts.map((row) => {
    const label = `${row.company} on ${row.platform}: ${row.likes}♡ / ${row.comments}💬 — ${row.caption.slice(0, 90)}`;
    return row.href ? `[${label}](${row.href})` : label;
  });
  const sniper = facts.sniperQueue.map((row) => {
    const label = `${row.company} · ${row.platform} · ${row.likes}♡ / ${row.comments}💬`;
    return row.href ? `[${label}](${row.href})` : label;
  });
  const mix = facts.formatMix[0];
  return [
    `# Intel brief — ${facts.brandName}`,
    "",
    `Window: **${facts.window.label}**. Numbers are from the scout, not vibes.`,
    "",
    "## Scoreboard",
    bullets(companyLines, "Zero in-window posts — scout this lookback first."),
    "",
    "## What you're actually good at",
    bullets(facts.winningBecause, "Scout more; the board is still loading."),
    "",
    "## What you're fumbling",
    bullets(
      facts.leakingBecause,
      facts.companies.length
        ? "No obvious leaks in this window — you're keeping pace."
        : "Not enough in-window posts to roast you yet.",
    ),
    "",
    "## Why engagement is mid",
    bullets(
      facts.leakingBecause.slice(0, 4).length
        ? facts.leakingBecause.slice(0, 4)
        : facts.winningBecause.slice(0, 3),
      "Need more in-window posts before we call the heat.",
    ),
    "",
    "## Gaps they own",
    bullets(
      facts.leakingBecause.slice(-3).length ? facts.leakingBecause.slice(-3) : mixLines.slice(0, 3),
      "No gap call until the mix fills in.",
    ),
    "",
    "## Format mix",
    bullets(mixLines, "No format mix yet — the window is empty."),
    "",
    "## This week's plays",
    bullets(
      [
        `Lean into **${mix?.format ?? "founder_post"}** — it's ${mix?.pct ?? 0}% of what the feed already rewards.`,
        "Ship one visual every post. Text-only gets ghosted.",
        "Comment on the hottest rival permalinks in the sniper docket — human approve, one at a time.",
        "Don't invent metrics in public. Cite the receipts below or stay quiet.",
      ],
      "No play until there are posts.",
    ),
    "",
    "## Receipts we can cite",
    bullets(receipts, "No permalinks in this window."),
    "",
    "## Sniper docket",
    bullets(sniper, "No rival permalinks queued."),
  ].join("\n");
}

function fallbackReports(facts: IntelFacts): IntelReport["reports"] {
  const mixLines = facts.formatMix.map(
    (row) => `- **${row.format}** — ${row.count} posts (${row.pct}%)`,
  );
  const sniperLines = facts.sniperQueue.map((row) => {
    const line = `**${row.company}** on ${row.platform} · ${row.likes} likes / ${row.comments} comments`;
    return row.href ? `- [${line}](${row.href})` : `- ${line}`;
  });
  return [
    {
      id: "plays",
      title: "This week's plays",
      markdown: [
        `## Plays for ${facts.brandName}`,
        "- Steal the room's dominant format, not their caption.",
        "- One visual per post. Algorithms ghost walls of text.",
        "- One sniper comment after a human hits Approve — never a spray.",
        "- Quote a real receipt (likes / comments / cadence) or don't dunk.",
        "- Keep forbidden claims out of the overlay and the caption.",
        "- If cadence is thin, post before you roast.",
        "- Trend-jack themes, not their words.",
        "- End LinkedIn on a question people will actually answer.",
      ].join("\n"),
    },
    {
      id: "format",
      title: "Format mix roast",
      markdown: [
        "## Format mix roast",
        ...(mixLines.length ? mixLines : ["- Window is empty — no mix to roast yet."]),
        "- Double down on whatever already has heat in this window.",
        "- If memes are missing and the room is meme-heavy, that's the gap.",
        "- Carousels without a hook slide are just PDFs in a trench coat.",
      ].join("\n"),
    },
    {
      id: "sniper",
      title: "Sniper docket",
      markdown: [
        "## Sniper docket",
        ...(sniperLines.length ? sniperLines : ["- No rival permalinks in this window."]),
        "- Human delays 10–15s. One hop. You approved this.",
        "- YouTube comments stay out of scope.",
      ].join("\n"),
    },
  ];
}

export function fallbackIntel(facts: IntelFacts): IntelReport {
  const leaking = facts.leakingBecause.slice(0, 5);
  const winning = facts.winningBecause.slice(0, 5);
  const mix = facts.formatMix[0];
  return {
    scoreboard_blurb: `${facts.brandName} vs the room — numbers first, vibes second.`,
    markdown: factsToMarkdown(facts),
    reports: fallbackReports(facts),
    good_at: winning.length ? winning : ["Scout more; the board is still loading."],
    fumbling: leaking.length
      ? leaking
      : facts.companies.length
        ? ["No obvious leaks in this window — you're keeping pace."]
        : ["Not enough in-window posts to roast you yet."],
    why_engagement_mid: leaking.slice(0, 3),
    gaps: leaking.slice(-2),
    plays: mix
      ? [
          {
            title: `Lean into ${mix.format}`,
            format: mix.format,
            platform: "linkedin",
            why: `It's ${mix.pct}% of the window — that's the language the feed already speaks.`,
          },
        ]
      : [],
    sniper_bait: facts.sniperQueue
      .slice(0, 5)
      .filter((item) => item.href)
      .map((item) => ({
        why: `Heat on ${item.platform}: ${item.likes} likes / ${item.comments} comments`,
        href: item.href as string,
        company: item.company,
      })),
  };
}

export function mergeIntel(facts: IntelFacts, remote: Partial<IntelReport> | null): IntelReport {
  const fallback = fallbackIntel(facts);
  if (!remote) return fallback;
  return {
    ...fallback,
    ...remote,
    markdown: remote.markdown?.trim() ? remote.markdown : fallback.markdown,
    reports: remote.reports?.length ? remote.reports : fallback.reports,
    good_at: remote.good_at?.length ? remote.good_at : fallback.good_at,
    fumbling: remote.fumbling?.length ? remote.fumbling : fallback.fumbling,
    plays: remote.plays?.length ? remote.plays : fallback.plays,
    sniper_bait: remote.sniper_bait?.length ? remote.sniper_bait : fallback.sniper_bait,
  };
}
