import type { CreativePermissions } from "./types";

export const STUDIO_FORMATS: {
  id: string;
  label: string;
  hint: string;
  permission: keyof CreativePermissions;
}[] = [
  { id: "meme", label: "Shitpost / meme", hint: "Punchline + one bold frame", permission: "imageConcepts" },
  { id: "founder_2am", label: "Founder 2am thought", hint: "Intimate, specific, human", permission: "imageConcepts" },
  { id: "receipt_carousel", label: "Receipt carousel", hint: "3–6 slide beats", permission: "carouselOutlines" },
  { id: "myth_bust", label: "Myth-bust / they said we did", hint: "Category receipts, no rival logo", permission: "comparisonSlides" },
  { id: "hot_take", label: "Hot take quote card", hint: "One spicy overlay sentence", permission: "imageConcepts" },
  { id: "product_story", label: "Product flex + human story", hint: "Not a feature dump", permission: "imageConcepts" },
  { id: "trend_jack", label: "Trend-jack", hint: "Theme, not their words", permission: "draftTrendJack" },
  { id: "comparison", label: "Us vs the category", hint: "No fake rival logo", permission: "comparisonSlides" },
  { id: "ugc", label: "UGC-style caption", hint: "Customer-screenshot energy", permission: "imageConcepts" },
  { id: "case_study_15s", label: "Case-study 15s script", hint: "Hook / proof / CTA", permission: "imageConcepts" },
  { id: "poll", label: "Poll / question bait", hint: "A question people answer", permission: "imageConcepts" },
  { id: "linkedin_thought", label: "LinkedIn thought-leadership", hint: "Still a person, not LinkedIn-bro", permission: "imageConcepts" },
  { id: "x_thread", label: "X thread", hint: "5–7 short beats", permission: "carouselOutlines" },
  { id: "parody_play", label: "We tried their play", hint: "Affectionate parody, not libel", permission: "imageConcepts" },
];

export const SNIPER_TONES = [
  "wholesome hype",
  "witty",
  "petty",
  "deadpan",
  "founder",
  "unhinged-safe",
] as const;

export const SNIPER_PLATFORMS = ["linkedin", "x", "instagram"] as const;

export function formatUnlocked(
  formatId: string,
  permissions: CreativePermissions,
): boolean {
  const spec = STUDIO_FORMATS.find((f) => f.id === formatId);
  if (!spec) return false;
  return permissions[spec.permission];
}
