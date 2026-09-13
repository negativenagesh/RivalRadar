import { ingestionMediaUrl } from "./api";
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

export function postVisualUrl(post: CompetitorPost): string | null {
  const key = post.media_keys?.[0];
  if (key) return ingestionMediaUrl(key);
  const url = post.image_url || post.media_urls?.[0] || null;
  if (!url) return null;
  if (url.includes("/screenshots/")) return null;
  if (url.startsWith("http") || url.startsWith("data:") || url.startsWith("/ingestion/media/")) {
    if (url.startsWith("/")) {
      const base = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";
      return `${base.replace(/\/$/, "")}${url}`;
    }
    return url;
  }
  const base = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${url.startsWith("/") ? url : `/${url}`}`;
}

function isoDay(iso: string): string {
  return iso.slice(0, 10);
}

/** LinkedIn activity IDs encode Unix ms in the high bits. Prefer that over scrape-time posted_at. */
export function linkedinActivityDay(post: CompetitorPost): string | null {
  const blob = `${post.external_post_id} ${themeList(post).join(" ")} ${post.theme_tags || ""}`;
  const match = blob.match(/(\d{18,})/);
  if (!match) return null;
  let tsMs = 0;
  try {
    tsMs = Number(BigInt(match[1]) >> BigInt(22));
  } catch {
    return null;
  }
  if (!Number.isFinite(tsMs) || tsMs < 1_500_000_000_000 || tsMs > 2_200_000_000_000) return null;
  const d = new Date(tsMs);
  if (d.getUTCFullYear() < 2018 || d.getUTCFullYear() > 2035) return null;
  return d.toISOString().slice(0, 10);
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
  const a = accountPlatform.toLowerCase() === "twitter" ? "x" : accountPlatform.toLowerCase();
  const t = targetPlatform.toLowerCase() === "twitter" ? "x" : targetPlatform.toLowerCase();
  return a === t;
}

const THEME_PLATFORMS = new Set([
  "instagram",
  "linkedin",
  "x",
  "twitter",
  "youtube",
  "tiktok",
  "threads",
  "mock",
]);

export function themePlatform(post: CompetitorPost): string | null {
  for (const t of themeList(post)) {
    const token = t.split(":")[0]?.trim().toLowerCase() ?? "";
    if (THEME_PLATFORMS.has(token)) {
      return token === "twitter" ? "x" : token;
    }
  }
  return null;
}

function compactHandle(raw: string): string {
  return normalizeHandle(raw).replace(/[-_.]/g, "");
}

function handlesMatch(a: string, b: string): boolean {
  if (!a || !b) return false;
  if (a === b) return true;
  if (a.includes(b) || b.includes(a)) return true;
  return compactHandle(a) === compactHandle(b);
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
  const href = link ? link.slice("link:".length).trim() : "";
  if (href.startsWith("http") && isPostPermalink(platform, href)) return href;

  const reconstructed = reconstructedPermalink(post, platform);
  if (reconstructed) return reconstructed;
  if (href.startsWith("http")) return href;
  return null;
}

function reconstructedPermalink(post: CompetitorPost, platform: string): string | null {
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
  return handlesAlign(account.handle, target);
}

function handlesAlign(handle: string, target: MissionTargetPreview): boolean {
  const ah = normalizeHandle(handle);
  const th = normalizeHandle(target.handleOrUrl);
  const url = normalizeHandle(target.url || "");
  if (!ah || !th) return false;
  if (handlesMatch(ah, th)) return true;
  if (url && (handlesMatch(url, ah) || url.includes(ah) || ah.includes(url))) return true;
  return false;
}

export function postMatchesTarget(
  post: CompetitorPost,
  account: CompetitorAccount | undefined,
  target: MissionTargetPreview,
): boolean {
  const platform = themePlatform(post) || account?.platform || "";
  if (!samePlatform(platform, target.platform)) return false;
  if (account && handlesAlign(account.handle, target)) return true;
  const th = normalizeHandle(target.handleOrUrl);
  const urlH = normalizeHandle(target.url || "");
  const href = (watchUrl(post, platform) || "").toLowerCase();
  const blob = `${href} ${themeList(post).join(" ")}`.toLowerCase();
  if (th && blob.includes(th)) return true;
  if (urlH && blob.includes(urlH)) return true;
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
    const themes = themeList(post);
    const snowDay = linkedinActivityDay(post);
    const day = snowDay || isoDay(post.posted_at);
    if (day < window.from || day > window.to) continue;
    if (themes.includes("posted_at_uncertain")) continue;
    if (themes.some((t) => t.startsWith("shot:screenshots"))) continue;
    if (isJunkCaption(post.caption || "")) continue;

    const account = byId[post.account_id];
    if (account && !allowMock && isMockHandle(account.handle)) continue;

    const target = realTargets.find((t) => postMatchesTarget(post, account, t));
    if (!target) continue;

    const platformRaw = (
      themePlatform(post) ||
      account?.platform ||
      target.platform ||
      "other"
    ).toLowerCase();
    const platform = platformRaw === "twitter" ? "x" : platformRaw;
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

export type FindingsLane = {
  platform: string;
  empty: boolean;
  days: { day: string; rows: FindingsRow[] }[];
};

export type FindingsCompanyColumn = {
  company: string;
  role: "brand" | "rival";
  lanes: FindingsLane[];
};

export function findingsBoard(
  rows: FindingsRow[],
  targets: MissionTargetPreview[],
): { brand: FindingsCompanyColumn[]; rivals: FindingsCompanyColumn[] } {
  const real = targets.filter((t) => t.platform !== "web" && t.platform !== "mock");

  function columns(role: "brand" | "rival"): FindingsCompanyColumn[] {
    const labels: string[] = [];
    for (const t of real) {
      if (t.role !== role) continue;
      if (!labels.includes(t.label)) labels.push(t.label);
    }
    return labels.map((company) => {
      const plats: string[] = [];
      for (const t of real) {
        if (t.role !== role || t.label !== company) continue;
        const p = t.platform.toLowerCase() === "twitter" ? "x" : t.platform.toLowerCase();
        if (!plats.includes(p)) plats.push(p);
      }
      const companyRows = rows.filter((r) => r.role === role && r.company === company);
      return {
        company,
        role,
        lanes: plats.map((platform) => {
          const laneRows = companyRows.filter((r) => samePlatform(r.platform, platform));
          const daysMap = new Map<string, FindingsRow[]>();
          for (const row of laneRows) {
            const list = daysMap.get(row.day) ?? [];
            list.push(row);
            daysMap.set(row.day, list);
          }
          const days = [...daysMap.entries()]
            .sort((a, b) => b[0].localeCompare(a[0]))
            .map(([day, rs]) => ({
              day,
              rows: [...rs].sort((a, b) => b.likes + b.comments - (a.likes + a.comments)),
            }));
          return { platform, empty: laneRows.length === 0, days };
        }),
      };
    });
  }

  return { brand: columns("brand"), rivals: columns("rival") };
}
