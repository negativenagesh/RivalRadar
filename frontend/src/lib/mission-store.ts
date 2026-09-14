import type {
  BrandProfile,
  CompetitorProfile,
  CreativePermissions,
  IngestionTarget,
  MissionState,
} from "./types";
import { isValidSocialUrl, type SocialKey } from "./social-validate";

export const MISSION_STORAGE_KEY = "rivalradar.mission";
/** One-time bump: operators who still have the old default 3d lookback get 7d. */
export const LOOKBACK_DEFAULT_BUMP_KEY = "rivalradar.lookback_default_v7";
export const LOOKBACK_DEFAULT_DAYS = 7;
export const LOOKBACK_LEGACY_DEFAULT_DAYS = 3;

export const EMPTY_SOCIALS: BrandProfile["socials"] = {
  linkedin: "",
  x: "",
  instagram: "",
  tiktok: "",
  youtube: "",
  threads: "",
};

export const DEFAULT_PERMISSIONS: CreativePermissions = {
  draftReplies: true,
  draftTrendJack: true,
  suggestComments: false,
  imageConcepts: true,
  carouselOutlines: true,
  comparisonSlides: false,
};

export const DEFAULT_BRAND: BrandProfile = {
  displayName: "",
  category: "",
  website: "",
  socials: { ...EMPTY_SOCIALS },
  voiceNotes: "",
  forbiddenClaims: "",
  idealCustomer: "",
  contentPillars: "",
  preferredFormats: ["meme", "carousel", "founder_pov"],
  timezone: "UTC",
};

export const MOCK_HANDLES = ["nova.wear", "brewbros", "fitkit.co"] as const;

const SOCIAL_KEYS: SocialKey[] = [
  "linkedin",
  "x",
  "instagram",
  "tiktok",
  "youtube",
  "threads",
];

export function newCompetitor(): CompetitorProfile {
  return {
    id: crypto.randomUUID(),
    name: "",
    website: "",
    socials: { ...EMPTY_SOCIALS },
    whyTheyMatter: "",
  };
}

export const DEFAULT_MISSION: MissionState = {
  brand: DEFAULT_BRAND,
  competitors: [
    {
      id: "competitor-1",
      name: "",
      website: "",
      socials: { ...EMPTY_SOCIALS },
      whyTheyMatter: "",
    },
  ],
  permissions: DEFAULT_PERMISSIONS,
  recordSession: true,
  lookbackDays: LOOKBACK_DEFAULT_DAYS,
  dateFrom: null,
  dateTo: null,
  lastRunId: null,
};

/** Resolve lookback from storage, bumping the legacy 3d default once to 7d. */
export function resolveStoredLookbackDays(
  rawDays: unknown,
  dateFrom: string | null,
  dateTo: string | null,
  opts: { bumpDone: boolean },
): { days: number; didBump: boolean } {
  const parsed =
    typeof rawDays === "number" && rawDays >= 1 ? Math.min(90, rawDays) : LOOKBACK_DEFAULT_DAYS;
  const custom = Boolean(dateFrom && dateTo);
  if (!opts.bumpDone && !custom && parsed === LOOKBACK_LEGACY_DEFAULT_DAYS) {
    return { days: LOOKBACK_DEFAULT_DAYS, didBump: true };
  }
  return { days: parsed, didBump: false };
}

export function loadMission(): MissionState {
  if (typeof window === "undefined") return structuredClone(DEFAULT_MISSION);
  try {
    const raw = localStorage.getItem(MISSION_STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_MISSION);
    const parsed = JSON.parse(raw) as Partial<MissionState>;
    const dateFrom = typeof parsed.dateFrom === "string" ? parsed.dateFrom : null;
    const dateTo = typeof parsed.dateTo === "string" ? parsed.dateTo : null;
    const bumpDone = localStorage.getItem(LOOKBACK_DEFAULT_BUMP_KEY) === "1";
    const { days, didBump } = resolveStoredLookbackDays(
      parsed.lookbackDays,
      dateFrom,
      dateTo,
      { bumpDone },
    );
    if (didBump || !bumpDone) {
      localStorage.setItem(LOOKBACK_DEFAULT_BUMP_KEY, "1");
    }
    return {
      ...structuredClone(DEFAULT_MISSION),
      ...parsed,
      lookbackDays: days,
      dateFrom,
      dateTo,
    };
  } catch {
    return structuredClone(DEFAULT_MISSION);
  }
}

export function saveMission(state: MissionState): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(MISSION_STORAGE_KEY, JSON.stringify(state));
}

export type MissionTargetPreview = {
  label: string;
  platform: string;
  handleOrUrl: string;
  url?: string;
  source: "youtube-api" | "yt-dlp" | "browser" | "mock-browser";
  role: "brand" | "rival";
};

/** Platforms that need a Connect session before Start Scout (not YouTube/yt-dlp or mock). */
export const CONNECT_SKIP_PLATFORMS = new Set(["youtube", "mock", "web"]);

export const PLATFORM_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  x: "X",
  instagram: "Instagram",
  tiktok: "TikTok",
  youtube: "YouTube",
  threads: "Threads",
  mock: "Mock feed",
  web: "Web",
};

export const PLATFORM_HOME: Record<string, string> = {
  linkedin: "https://www.linkedin.com/login",
  x: "https://x.com/i/flow/login",
  instagram: "https://www.instagram.com/accounts/login/",
  tiktok: "https://www.tiktok.com/login",
  threads: "https://www.threads.net/login",
};

/** Unique Playwright platforms from Context links that must be connected. */
export function requiredConnectPlatforms(targets: MissionTargetPreview[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const t of targets) {
    const p = t.platform.toLowerCase();
    if (CONNECT_SKIP_PLATFORMS.has(p) || seen.has(p)) continue;
    seen.add(p);
    out.push(p);
  }
  return out;
}

function ensureHttp(url: string): string {
  return url.startsWith("http") ? url : `https://${url}`;
}

function youtubeHandleFromUrl(url: string): string {
  const at = url.match(/youtube\.com\/@([\w.-]+)/i);
  if (at) return at[1];
  const ch = url.match(/youtube\.com\/channel\/(UC[\w-]+)/i);
  if (ch) return ch[1];
  return url.replace(/^https?:\/\//, "").slice(0, 40);
}

function handleFromSocial(platform: SocialKey, url: string): string {
  if (platform === "youtube") return youtubeHandleFromUrl(url);
  const cleaned = url.replace(/^https?:\/\//, "").replace(/\/$/, "");
  const parts = cleaned.split("/");
  return (parts[parts.length - 1] || cleaned).slice(0, 40);
}

function collectSocialTargets(
  label: string,
  socials: BrandProfile["socials"],
  role: "brand" | "rival",
): { preview: MissionTargetPreview; target: IngestionTarget }[] {
  const out: { preview: MissionTargetPreview; target: IngestionTarget }[] = [];
  for (const key of SOCIAL_KEYS) {
    const raw = socials[key].trim();
    if (!raw || !isValidSocialUrl(key, raw)) continue;
    const url = ensureHttp(raw);
    const handle = handleFromSocial(key, url);
    out.push({
      preview: {
        label,
        platform: key,
        handleOrUrl: handle,
        url,
        source: key === "youtube" ? "youtube-api" : "browser",
        role,
      },
      target: {
        handle,
        platform: key,
        url,
      },
    });
  }
  return out;
}

/** Visible Mission targets derived from Context (Operator strip). */
export function buildMissionTargets(state: MissionState): MissionTargetPreview[] {
  const out: MissionTargetPreview[] = [];
  out.push(
    ...collectSocialTargets(state.brand.displayName || "Brand", state.brand.socials, "brand").map(
      (x) => x.preview,
    ),
  );

  state.competitors.forEach((c, idx) => {
    const label = c.name || `Rival ${idx + 1}`;
    const socials = collectSocialTargets(label, c.socials, "rival");
    if (socials.length) {
      out.push(...socials.map((x) => x.preview));
      return;
    }
    if (c.name.trim() || c.website.trim()) {
      out.push({
        label,
        platform: "mock",
        handleOrUrl: MOCK_HANDLES[idx % MOCK_HANDLES.length],
        source: "mock-browser",
        role: "rival",
      });
    }
  });

  if (out.length === 0) {
    MOCK_HANDLES.forEach((handle) => {
      out.push({
        label: handle,
        platform: "mock",
        handleOrUrl: handle,
        source: "mock-browser",
        role: "rival",
      });
    });
  }
  return out;
}

/** Map mission form → ingestion run across every linked platform. */
export function missionToIngestionPayload(state: MissionState): {
  connector: "auto";
  targets: IngestionTarget[];
  record: boolean;
  headless: boolean;
  lookback_days: number;
  date_from?: string | null;
  date_to?: string | null;
} {
  const targets: IngestionTarget[] = [];
  const seen = new Set<string>();

  function push(t: IngestionTarget) {
    const key = `${t.platform}|${t.url || t.handle}`;
    if (seen.has(key)) return;
    seen.add(key);
    targets.push(t);
  }

  for (const item of collectSocialTargets("brand", state.brand.socials, "brand")) {
    push(item.target);
  }

  state.competitors.forEach((c, idx) => {
    const socials = collectSocialTargets(c.name || `rival-${idx}`, c.socials, "rival");
    if (socials.length) {
      socials.forEach((s) => push(s.target));
      return;
    }
    if (c.name.trim() || c.website.trim()) {
      push({
        handle: MOCK_HANDLES[idx % MOCK_HANDLES.length],
        platform: "mock",
      });
    }
  });

  if (targets.length === 0) {
    MOCK_HANDLES.forEach((handle) => push({ handle, platform: "mock" }));
  }

  const custom = Boolean(state.dateFrom && state.dateTo);
  return {
    connector: "auto",
    targets,
    record: state.recordSession,
    headless: true,
    lookback_days: state.lookbackDays,
    ...(custom ? { date_from: state.dateFrom, date_to: state.dateTo } : {}),
  };
}

export function buildDiscoveryReport(input: {
  brand: BrandProfile;
  competitors: CompetitorProfile[];
  posts: { caption: string; format: string; themes: string[]; engagement_score: number }[];
  permissions: CreativePermissions;
  lookbackDays?: number;
}): string {
  const top = [...input.posts]
    .sort((a, b) => b.engagement_score - a.engagement_score)
    .slice(0, 5);
  const themes = [...new Set(input.posts.flatMap((p) => p.themes))].slice(0, 8);
  const formats = [...new Set(input.posts.map((p) => p.format))];
  const rivalNames = input.competitors.map((c) => c.name || c.website).filter(Boolean);
  const lookback = input.lookbackDays ?? LOOKBACK_DEFAULT_DAYS;

  const allowed: string[] = [];
  if (input.permissions.draftReplies) allowed.push("reply/response posts");
  if (input.permissions.draftTrendJack) allowed.push("trend-jack originals");
  if (input.permissions.suggestComments) allowed.push("comment suggestions (human approve)");
  if (input.permissions.imageConcepts) allowed.push("post visuals (Nano Banana / Agnes / FLUX)");
  if (input.permissions.carouselOutlines) allowed.push("carousel/thread outlines");
  if (input.permissions.comparisonSlides) allowed.push("internal comparison slides");

  return [
    `# RivalRadar discovery — ${input.brand.displayName || "your brand"}`,
    "",
    `Category: ${input.brand.category || "unspecified"}`,
    `Website: ${input.brand.website || "—"}`,
    `Lookback: last ${lookback} days`,
    `Rivals in scope: ${rivalNames.length ? rivalNames.join(", ") : "fixture demo rivals"}`,
    "",
    "## What we saw",
    `- Posts / uploads scanned: ${input.posts.length}`,
    `- Formats in play: ${formats.length ? formats.join(", ") : "n/a yet"}`,
    `- Themes heating up: ${themes.length ? themes.join(", ") : "awaiting denser feed"}`,
    "",
    "## Top heat (by engagement)",
    ...(top.length
      ? top.map(
          (p, i) =>
            `${i + 1}. [${p.format}] ${p.caption.slice(0, 120)}${p.caption.length > 120 ? "…" : ""} (score ${p.engagement_score})`,
        )
      : ["- No posts yet — run scout with social links."]),
    "",
    "## Gaps & plays",
    input.brand.contentPillars
      ? `- Your pillars: ${input.brand.contentPillars}`
      : "- Add content pillars so drafts stay on-lane.",
    input.brand.voiceNotes
      ? `- Voice notes locked: ${input.brand.voiceNotes.slice(0, 200)}`
      : "- Add voice notes for sharper caption match.",
    "- Opportunity: reply where rivals go broad — go specific + receipts.",
    "- Opportunity: meme formats they skip; founder POV they underuse.",
    "",
    "## What RivalRadar can create next (per your permissions)",
    ...(allowed.length ? allowed.map((a) => `- ${a}`) : ["- Enable at least one creative permission."]),
    "",
    "## Guardrails",
    input.brand.forbiddenClaims
      ? `- Do-not-say: ${input.brand.forbiddenClaims}`
      : "- No forbidden claims listed yet.",
    "- Nothing publishes without human approval.",
  ].join("\n");
}
