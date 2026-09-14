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
  /** Share of posts with real media (not screenshots). */
  visualPct: number;
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
  /** Clean content themes (no link:/shot:/metric: noise). */
  themes: string[];
};

export type IntelFacts = {
  window: { from: string; to: string; days: number; label: string };
  brandName: string;
  companies: IntelCompany[];
  formatMix: { format: string; count: number; pct: number }[];
  topThemes: { theme: string; count: number }[];
  topPosts: IntelPostRef[];
  bottomPosts: IntelPostRef[];
  winningBecause: string[];
  leakingBecause: string[];
  sniperQueue: IntelPostRef[];
};

const META_THEMES = new Set([
  "linkedin",
  "instagram",
  "x",
  "twitter",
  "youtube",
  "tiktok",
  "threads",
  "video",
  "posted_at_uncertain",
]);

function cleanThemes(post: FindingsRow["post"]): string[] {
  const raw = post.themes?.length
    ? post.themes
    : (post.theme_tags || "")
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
  const out: string[] = [];
  for (const t of raw) {
    const lower = t.toLowerCase();
    if (t.includes(":")) continue;
    if (META_THEMES.has(lower)) continue;
    if (out.includes(t)) continue;
    out.push(t);
    if (out.length >= 4) break;
  }
  return out;
}

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
    themes: cleanThemes(row.post),
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
    const withMedia = list.filter((p) => toRef(p).hasMedia).length;
    return {
      name,
      role,
      posts: list.length,
      avgEngagement: round1(avg(scores)),
      visualPct: list.length ? Math.round((withMedia / list.length) * 100) : 0,
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

  const themeCounts = new Map<string, number>();
  for (const row of rows) {
    for (const theme of cleanThemes(row.post)) {
      themeCounts.set(theme, (themeCounts.get(theme) ?? 0) + 1);
    }
  }
  const topThemes = [...themeCounts.entries()]
    .map(([theme, count]) => ({ theme, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8);

  return {
    window: { from: window.from, to: window.to, days, label },
    brandName: input.brand.displayName || "your brand",
    companies,
    formatMix,
    topThemes,
    topPosts,
    bottomPosts,
    winningBecause,
    leakingBecause,
    sniperQueue,
  };
}

/** Dense roast pack for Format Studio memes — brand dossier + rival metrics + receipts (no media URLs). */
export function buildStudioRoastPack(
  facts: IntelFacts,
  brand: BrandProfile,
  competitors: { name: string; whyTheyMatter: string }[] = [],
): Record<string, unknown> {
  const whyByName = new Map(
    competitors.map((c) => [c.name.trim().toLowerCase(), c.whyTheyMatter.trim()] as const),
  );
  const brandCo = facts.companies.find((c) => c.role === "brand");
  const rivals = facts.companies.filter((c) => c.role === "rival");
  const slimPost = (p: IntelPostRef) => ({
    company: p.company,
    role: p.role,
    platform: p.platform,
    format: p.format,
    caption: p.caption,
    likes: p.likes,
    comments: p.comments,
    shares: p.shares,
    views: p.views,
    score: p.score,
    hasMedia: p.hasMedia,
    themes: p.themes,
  });
  return {
    window: facts.window,
    brand: {
      name: brand.displayName || facts.brandName,
      category: brand.category || null,
      voice: brand.voiceNotes || null,
      idealCustomer: brand.idealCustomer || null,
      contentPillars: brand.contentPillars || null,
      preferredFormats: brand.preferredFormats || [],
      forbiddenClaims: brand.forbiddenClaims || null,
      scoreboard: brandCo
        ? {
            posts: brandCo.posts,
            avgEngagement: brandCo.avgEngagement,
            visualPct: brandCo.visualPct,
            platforms: brandCo.platforms,
          }
        : null,
    },
    rivals: rivals.map((r) => ({
      name: r.name,
      whyTheyMatter: whyByName.get(r.name.trim().toLowerCase()) || null,
      posts: r.posts,
      avgEngagement: r.avgEngagement,
      visualPct: r.visualPct,
      platforms: r.platforms,
    })),
    formatMix: facts.formatMix,
    topThemes: facts.topThemes,
    winningBecause: facts.winningBecause,
    leakingBecause: facts.leakingBecause,
    rivalReceipts: facts.topPosts.filter((p) => p.role === "rival").map(slimPost),
    brandReceipts: facts.topPosts.filter((p) => p.role === "brand").map(slimPost),
    sniperReceipts: facts.sniperQueue.slice(0, 6).map(slimPost),
  };
}

function bullets(lines: string[], empty: string): string {
  if (!lines.length) return `- ${empty}`;
  return lines.map((line) => `- ${line}`).join("\n");
}

export function factsToMarkdown(facts: IntelFacts): string {
  const companyLines = facts.companies.map((c) => {
    const role = c.role === "brand" ? "you" : "rival";
    return `**${c.name}** (${role}): ${c.posts} posts, avg heat ${c.avgEngagement}, visuals ${c.visualPct}%`;
  });
  const mixLines = facts.formatMix.map(
    (row) => `**${row.format}** is ${row.pct}% of the window (${row.count} posts)`,
  );
  const platformLines = facts.companies.flatMap((c) => {
    const role = c.role === "brand" ? "you" : "rival";
    return c.platforms.map(
      (p) =>
        `**${c.name}** (${role}) on **${p.platform}**: ${p.posts} posts · cadence ${p.cadencePerDay}/day · avg ${p.avgLikes}♡ / ${p.avgComments}💬 · comment-rate ${p.commentRate}%`,
    );
  });
  const receipts = facts.topPosts.map((row) => {
    const label = `${row.company} on ${row.platform}: ${row.likes}♡ / ${row.comments}💬 — ${row.caption.slice(0, 90)}`;
    return row.href ? `[${label}](${row.href})` : label;
  });
  const sniper = facts.sniperQueue.map((row) => {
    const label = `${row.company} · ${row.platform} · ${row.likes}♡ / ${row.comments}💬`;
    return row.href ? `[${label}](${row.href})` : label;
  });
  const mix = facts.formatMix[0];
  const fumbling = facts.leakingBecause.slice(0, 3);
  const whyMid = facts.leakingBecause.slice(1, 4);
  const gaps = facts.leakingBecause.slice(2, 5);
  return [
    `# Intel brief — ${facts.brandName}`,
    "",
    `Window: **${facts.window.label}**. Numbers are from the scout, not vibes.`,
    "",
    "## Scoreboard read",
    bullets(
      companyLines.length
        ? [
            ...companyLines,
            "This is the offline fact brief — paste a text model key so Intel Chief can evaluate, not just reprint.",
          ]
        : [],
      "Zero in-window posts — scout this lookback first.",
    ),
    "",
    "## What you're actually good at",
    bullets(facts.winningBecause, "Scout more; the board is still loading."),
    "",
    "## What you're fumbling",
    bullets(
      fumbling,
      facts.companies.length
        ? "No obvious leaks in this window — you're keeping pace."
        : "Not enough in-window posts to roast you yet.",
    ),
    "",
    "## Why engagement is mid",
    bullets(
      whyMid.length ? whyMid : mixLines.slice(0, 2),
      "Need more in-window posts before we call the heat.",
    ),
    "",
    "## Gaps they own",
    bullets(
      gaps.length ? gaps : platformLines.slice(0, 3),
      "No gap call until the mix fills in.",
    ),
    "",
    "## Platform evals",
    bullets(platformLines, "No platform stats in this window."),
    "",
    "## Format & creative read",
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
  const platformLines = facts.companies.flatMap((c) => {
    const role = c.role === "brand" ? "you" : "rival";
    return c.platforms.map(
      (p) =>
        `- **${c.name}** (${role}) on **${p.platform}**: ${p.posts} posts · cadence ${p.cadencePerDay}/day · avg ${p.avgLikes}♡ / ${p.avgComments}💬`,
    );
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
    {
      id: "platforms",
      title: "Platform evals",
      markdown: [
        "## Platform evals",
        ...(platformLines.length ? platformLines : ["- No platform stats yet — scout first."]),
        "- Treat each platform as its own arena: cadence, heat, and comment rate.",
      ].join("\n"),
    },
    {
      id: "competitive",
      title: "Head-to-head",
      markdown: [
        `## Head-to-head — ${facts.brandName}`,
        ...(platformLines.slice(0, 8).length
          ? platformLines.slice(0, 8)
          : ["- Need rival + brand posts in-window."]),
        "- Steal the move that already has heat; don't invent a new language.",
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
    why_engagement_mid: leaking.slice(1, 4).length ? leaking.slice(1, 4) : leaking.slice(0, 3),
    gaps: leaking.slice(2, 5).length ? leaking.slice(2, 5) : leaking.slice(-2),
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
    agents_used: [],
    narration: "fallback",
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
    why_engagement_mid: remote.why_engagement_mid?.length
      ? remote.why_engagement_mid
      : fallback.why_engagement_mid,
    gaps: remote.gaps?.length ? remote.gaps : fallback.gaps,
    plays: remote.plays?.length ? remote.plays : fallback.plays,
    sniper_bait: remote.sniper_bait?.length ? remote.sniper_bait : fallback.sniper_bait,
    agents_used: remote.agents_used?.length ? remote.agents_used : fallback.agents_used,
    narration: remote.narration ?? fallback.narration,
  };
}
