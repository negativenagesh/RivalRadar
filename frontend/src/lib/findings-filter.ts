import type { CompetitorAccount, CompetitorPost } from "./types";
import { MOCK_HANDLES, type MissionTargetPreview } from "./mission-store";

export type FindingsWindow = {
  from: string;
  to: string;
};

export type FindingsRow = {
  post: CompetitorPost;
  company: string;
  role: "brand" | "rival";
  platform: string;
  day: string;
  href: string | null;
  likes: number;
  comments: number;
  shares: number;
  views: number;
};

function isoDay(iso: string): string {
  return iso.slice(0, 10);
}

export function missionWindow(
  input: { dateFrom?: string | null; dateTo?: string | null; lookbackDays: number },
  now = new Date(),
): FindingsWindow {
  if (input.dateFrom && input.dateTo) {
    return { from: input.dateFrom, to: input.dateTo };
  }
  const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - (Math.max(1, input.lookbackDays) - 1));
  return { from: isoDay(start.toISOString()), to: isoDay(end.toISOString()) };
}

export function normalizeHandle(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/^www\./, "")
    .replace(/^@+/, "")
    .replace(/\/+$/, "")
    .split("/")
    .filter(Boolean)
    .slice(-1)[0] ?? "";
}

function samePlatform(accountPlatform: string, targetPlatform: string): boolean {
  const a = accountPlatform.toLowerCase();
  const t = targetPlatform.toLowerCase();
  if (a === t) return true;
  if ((a === "x" && t === "twitter") || (a === "twitter" && t === "x")) return true;
  return false;
}

export function isJunkCaption(caption: string): boolean {
  const text = caption.trim().toLowerCase();
  if (!text) return true;
  return (
    /sign up\s*\|?\s*linkedin/.test(text) ||
    /log in\s*\|?\s*linkedin/.test(text) ||
    text === "linkedin" ||
    text.startsWith("instagram photos and videos") ||
    /• instagram photos and videos$/.test(text) ||
    /^source:\s*https?:\/\//m.test(text)
  );
}

function isPostPermalink(platform: string, href: string | null): boolean {
  if (!href) return platform === "youtube";
  const u = href.toLowerCase();
  if (platform === "youtube") return u.includes("watch?v=") || u.includes("youtu.be/");
  if (platform === "x" || platform === "twitter") return /\/status\/\d+/.test(u);
  if (platform === "instagram") return /\/(p|reel|tv)\//.test(u);
  if (platform === "linkedin") {
    return u.includes("/feed/update/") || u.includes("/posts/") || u.includes("activity:");
  }
  if (platform === "tiktok") return u.includes("/video/");
  if (platform === "threads") return u.includes("/post/");
  return true;
}

function themeList(post: CompetitorPost): string[] {
  if (post.themes?.length) return post.themes;
  return (post.theme_tags || "")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

function metricFromThemes(themes: string[], key: string): number {
  const prefix = `${key}:`;
  let best = 0;
  for (const t of themes) {
    if (!t.toLowerCase().startsWith(prefix)) continue;
    const n = Number(t.slice(prefix.length).replace(/,/g, ""));
    if (Number.isFinite(n)) best = Math.max(best, n);
  }
  return best;
}

export function postMetrics(post: CompetitorPost): {
  likes: number;
  comments: number;
  shares: number;
  views: number;
} {
  const themes = themeList(post);
  return {
    likes: Math.max(post.likes || 0, metricFromThemes(themes, "likes")),
    comments: Math.max(post.comments || 0, metricFromThemes(themes, "comments")),
    shares: Math.max(post.shares || 0, metricFromThemes(themes, "shares"), metricFromThemes(themes, "reposts")),
    views: Math.max(post.views || 0, metricFromThemes(themes, "views")),
  };
}

export function watchUrl(post: CompetitorPost, platform: string): string | null {
  const themes = themeList(post);
  const link = themes.find((t) => t.startsWith("link:"));
  if (link) {
    const href = link.slice("link:".length).trim();
    if (href.startsWith("http")) return href;
  }
  const id = post.external_post_id || "";
  if (platform === "youtube" && id && !id.startsWith("web-") && !id.includes(":")) {
    return `https://www.youtube.com/watch?v=${id}`;
  }
  if (id.startsWith("instagram:")) {
    const code = id.slice("instagram:".length);
    return `https://www.instagram.com/p/${code}/`;
  }
  if (id.startsWith("tiktok:")) {
    return `https://www.tiktok.com/video/${id.slice("tiktok:".length)}`;
  }
  if (id.startsWith("x:")) {
    return `https://x.com/i/status/${id.slice("x:".length)}`;
  }
  if (id.startsWith("linkedin:") && id.includes("activity")) {
    const urn = id.replace(/^linkedin:/, "").replace(/-/g, ":");
    return `https://www.linkedin.com/feed/update/${urn}`;
  }
  return null;
}

export function accountMatchesTarget(
  account: CompetitorAccount | undefined,
  target: MissionTargetPreview,
): boolean {
  if (!account) return false;
  if (!samePlatform(account.platform, target.platform)) return false;
  const ah = normalizeHandle(account.handle);
  const th = normalizeHandle(target.handleOrUrl);
  const url = normalizeHandle(target.url || "");
  if (!ah || !th) return false;
  if (ah === th) return true;
  if (url && (url === ah || url.includes(ah) || ah.includes(url))) return true;
  if (ah.includes(th) || th.includes(ah)) return true;
  return false;
}

function isMockHandle(handle: string): boolean {
  const n = normalizeHandle(handle);
  return (MOCK_HANDLES as readonly string[]).some((h) => normalizeHandle(h) === n);
}

export function filterFindingsPosts(
  posts: CompetitorPost[],
  accounts: CompetitorAccount[],
  input: {
    targets: MissionTargetPreview[];
    dateFrom?: string | null;
    dateTo?: string | null;
    lookbackDays: number;
  },
  now = new Date(),
): FindingsRow[] {
  const window = missionWindow(input, now);
  const byId = Object.fromEntries(accounts.map((a) => [a.id, a]));
  const realTargets = input.targets.filter((t) => t.platform !== "web");
  const allowMock = realTargets.some((t) => t.platform === "mock");

  const rows: FindingsRow[] = [];
  for (const post of posts) {
    const day = isoDay(post.posted_at);
    if (day < window.from || day > window.to) continue;
    const themes = themeList(post);
    if (themes.includes("posted_at_uncertain")) continue;
    if (themes.some((t) => t.startsWith("shot:screenshots"))) continue;
    if (isJunkCaption(post.caption || "")) continue;

    const account = byId[post.account_id];
    if (account && !allowMock && isMockHandle(account.handle)) continue;

    const target = realTargets.find((t) => accountMatchesTarget(account, t));
    if (!target) continue;

    const platform = (account?.platform || target.platform || "other").toLowerCase();
    if (platform === "youtube" && !themes.some((t) => t.startsWith("date_from:"))) continue;
    const metrics = postMetrics(post);
    const href = watchUrl(post, platform);
    if (!isPostPermalink(platform, href)) continue;
    rows.push({
      post,
      company: target.label,
      role: target.role,
      platform,
      day,
      href,
      ...metrics,
    });
  }
  return rows;
}
