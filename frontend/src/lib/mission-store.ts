import type {
  BrandProfile,
  CompetitorProfile,
  CreativePermissions,
  IngestionTarget,
  MissionState,
} from "./types";

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
  competitors: [newCompetitor()],
  permissions: DEFAULT_PERMISSIONS,
  recordSession: true,
  lastRunId: null,
};

export function loadMission(): MissionState {
  if (typeof window === "undefined") return structuredClone(DEFAULT_MISSION);
  try {
    const raw = localStorage.getItem(MISSION_STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_MISSION);
    return { ...structuredClone(DEFAULT_MISSION), ...JSON.parse(raw) } as MissionState;
  } catch {
    return structuredClone(DEFAULT_MISSION);
  }
}

export function saveMission(state: MissionState): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(MISSION_STORAGE_KEY, JSON.stringify(state));
}

/** Map mission form → ingestion run.
 * Live scout uses the bundled mock social profiles (screenshots + recording).
 * Real URLs stay in localStorage for report context — connectors aren't OAuth scrapers yet.
 */
export function missionToIngestionPayload(state: MissionState): {
  connector: "fixture" | "social_profile";
  targets: IngestionTarget[];
  record: boolean;
  headless: boolean;
} {
  const mockHandles = ["nova.wear", "brewbros", "fitkit.co"];
  return {
    connector: "social_profile",
    targets: mockHandles.map((handle) => ({
      handle,
      platform: "mock",
    })),
    record: state.recordSession,
    headless: true,
  };
}

export function buildDiscoveryReport(input: {
  brand: BrandProfile;
  competitors: CompetitorProfile[];
  posts: { caption: string; format: string; themes: string[]; engagement_score: number }[];
  permissions: CreativePermissions;
}): string {
  const top = [...input.posts]
    .sort((a, b) => b.engagement_score - a.engagement_score)
    .slice(0, 5);
  const themes = [...new Set(input.posts.flatMap((p) => p.themes))].slice(0, 8);
  const formats = [...new Set(input.posts.map((p) => p.format))];
  const rivalNames = input.competitors.map((c) => c.name || c.website).filter(Boolean);

  const allowed: string[] = [];
  if (input.permissions.draftReplies) allowed.push("reply/response posts");
  if (input.permissions.draftTrendJack) allowed.push("trend-jack originals");
  if (input.permissions.suggestComments) allowed.push("comment suggestions (human approve)");
  if (input.permissions.imageConcepts) allowed.push("image/meme concepts");
  if (input.permissions.carouselOutlines) allowed.push("carousel/thread outlines");
  if (input.permissions.comparisonSlides) allowed.push("internal comparison slides");

  return [
    `# RivalRadar discovery — ${input.brand.displayName || "your brand"}`,
    "",
    `Category: ${input.brand.category || "unspecified"}`,
    `Website: ${input.brand.website || "—"}`,
    `Rivals in scope: ${rivalNames.length ? rivalNames.join(", ") : "fixture demo rivals"}`,
    "",
    "## What we saw",
    `- Posts scanned: ${input.posts.length}`,
    `- Formats in play: ${formats.length ? formats.join(", ") : "n/a yet"}`,
    `- Themes heating up: ${themes.length ? themes.join(", ") : "awaiting denser feed"}`,
    "",
    "## Top heat (by engagement)",
    ...(top.length
      ? top.map(
          (p, i) =>
            `${i + 1}. [${p.format}] ${p.caption.slice(0, 120)}${p.caption.length > 120 ? "…" : ""} (score ${p.engagement_score})`,
        )
      : ["- No posts yet — run scout with fixture or real links."]),
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
