import type {
  BrandProfile,
  CompetitorProfile,
  CreativePermissions,
  IngestionTarget,
  MissionState,
} from "./types";
import { isValidSocialUrl } from "./social-validate";

export const MISSION_STORAGE_KEY = "rivalradar.mission";

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
  lookbackDays: 3,
  lastRunId: null,
};

export function loadMission(): MissionState {
  if (typeof window === "undefined") return structuredClone(DEFAULT_MISSION);
  try {
    const raw = localStorage.getItem(MISSION_STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_MISSION);
    const parsed = JSON.parse(raw) as Partial<MissionState>;
    return {
      ...structuredClone(DEFAULT_MISSION),
      ...parsed,
      lookbackDays:
        typeof parsed.lookbackDays === "number" && parsed.lookbackDays >= 1
          ? Math.min(14, parsed.lookbackDays)
          : 3,
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
  source: "youtube-api" | "yt-dlp" | "mock-browser";
};

function youtubeHandleFromUrl(url: string): string {
  const at = url.match(/youtube\.com\/@([\w.-]+)/i);
  if (at) return at[1];
  const ch = url.match(/youtube\.com\/channel\/(UC[\w-]+)/i);
  if (ch) return ch[1];
  return url.replace(/^https?:\/\//, "").slice(0, 40);
}

/** Visible Mission targets derived from Context (Operator strip). */
export function buildMissionTargets(state: MissionState): MissionTargetPreview[] {
  const out: MissionTargetPreview[] = [];
  const rivals = state.competitors.filter((c) => c.name.trim() || c.socials.youtube.trim());

  rivals.forEach((c, idx) => {
    const yt = c.socials.youtube.trim();
    if (yt && isValidSocialUrl("youtube", yt)) {
      out.push({
        label: c.name || "Rival",
        platform: "youtube",
        handleOrUrl: youtubeHandleFromUrl(yt),
        source: "youtube-api",
      });
      return;
    }
    out.push({
      label: c.name || `Rival ${idx + 1}`,
      platform: "mock",
      handleOrUrl: MOCK_HANDLES[idx % MOCK_HANDLES.length],
      source: "mock-browser",
    });
  });

  if (out.length === 0) {
    MOCK_HANDLES.forEach((handle) => {
      out.push({
        label: handle,
        platform: "mock",
        handleOrUrl: handle,
        source: "mock-browser",
      });
    });
  }
  return out;
}

/** Map mission form → ingestion run. YouTube URLs use API/yt-dlp; others map to mock profiles. */
export function missionToIngestionPayload(state: MissionState): {
  connector: "auto";
  targets: IngestionTarget[];
  record: boolean;
  headless: boolean;
  lookback_days: number;
} {
  const targets: IngestionTarget[] = [];
  const rivals = state.competitors.filter((c) => c.name.trim() || c.website.trim() || c.socials.youtube.trim());

  rivals.forEach((c, idx) => {
    const yt = c.socials.youtube.trim();
    if (yt && isValidSocialUrl("youtube", yt)) {
      targets.push({
        handle: youtubeHandleFromUrl(yt),
        platform: "youtube",
        url: yt.startsWith("http") ? yt : `https://${yt}`,
      });
      return;
    }
    const handle = MOCK_HANDLES[idx % MOCK_HANDLES.length];
    targets.push({
      handle,
      platform: "mock",
      url: undefined,
    });
  });

  if (targets.length === 0) {
    MOCK_HANDLES.forEach((handle) => {
      targets.push({ handle, platform: "mock" });
    });
  }

  // Also pull brand YouTube if set (channel-as-self scout)
  const brandYt = state.brand.socials.youtube.trim();
  if (brandYt && isValidSocialUrl("youtube", brandYt)) {
    targets.unshift({
      handle: youtubeHandleFromUrl(brandYt),
      platform: "youtube",
      url: brandYt.startsWith("http") ? brandYt : `https://${brandYt}`,
    });
  }

  return {
    connector: "auto",
    targets,
    record: state.recordSession,
    headless: true,
    lookback_days: state.lookbackDays,
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
  const lookback = input.lookbackDays ?? 3;

  const allowed: string[] = [];
  if (input.permissions.draftReplies) allowed.push("reply/response posts");
  if (input.permissions.draftTrendJack) allowed.push("trend-jack originals");
  if (input.permissions.suggestComments) allowed.push("comment suggestions (human approve)");
  if (input.permissions.imageConcepts) allowed.push("Nano Banana post visuals");
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
      : ["- No posts yet — run scout with fixture or YouTube links."]),
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
