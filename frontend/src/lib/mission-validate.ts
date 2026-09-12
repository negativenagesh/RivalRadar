import type { BrandProfile, MissionState } from "./types";
import { isValidSocialUrl, isValidWebsite, type SocialKey } from "./social-validate";

export type MissionStep = 0 | 1 | 2 | 3;

export type FieldIssue = {
  step: MissionStep;
  fieldId: string;
  message: string;
};

function socialIssues(
  socials: BrandProfile["socials"],
  prefix: string,
  step: MissionStep,
): FieldIssue[] {
  const issues: FieldIssue[] = [];
  (Object.keys(socials) as SocialKey[]).forEach((key) => {
    const value = socials[key].trim();
    if (!value) return;
    if (!isValidSocialUrl(key, value)) {
      issues.push({
        step,
        fieldId: `${prefix}-social-${key}`,
        message: `${key} link looks invalid — use a full profile URL`,
      });
    }
  });
  return issues;
}

/** Context step must have brand identity + at least one rival name/site. */
export function validateContext(mission: MissionState): FieldIssue[] {
  const issues: FieldIssue[] = [];
  const { brand, competitors } = mission;

  if (!brand.displayName.trim()) {
    issues.push({ step: 0, fieldId: "brand-displayName", message: "Add your brand display name" });
  }
  if (!brand.category.trim()) {
    issues.push({ step: 0, fieldId: "brand-category", message: "Add your category / niche" });
  }
  if (!isValidWebsite(brand.website)) {
    issues.push({
      step: 0,
      fieldId: "brand-website",
      message: "Add a valid company website (e.g. pixis.ai)",
    });
  }
  if (!brand.voiceNotes.trim()) {
    issues.push({ step: 0, fieldId: "brand-voice", message: "Drop brand voice notes so drafts sound like you" });
  }

  issues.push(...socialIssues(brand.socials, "brand", 0));

  const validRival = competitors.some(
    (c) => c.name.trim() && (isValidWebsite(c.website) || c.website.trim().length > 2),
  );
  if (!validRival) {
    issues.push({
      step: 0,
      fieldId: "rival-0-name",
      message: "Add at least one rival with a name + website",
    });
  }

  competitors.forEach((c, idx) => {
    if (c.website.trim() && !isValidWebsite(c.website) && c.website.length < 3) {
      issues.push({
        step: 0,
        fieldId: `rival-${idx}-website`,
        message: `Rival ${idx + 1}: website looks off`,
      });
    }
    issues.push(...socialIssues(c.socials, `rival-${idx}`, 0));
  });

  return issues;
}

export function validateScout(mission: MissionState): FieldIssue[] {
  if (!mission.lastRunId) {
    return [
      {
        step: 1,
        fieldId: "scout-start",
        message: "Start a scout run before leaving this step",
      },
    ];
  }
  return [];
}

export function validateFindings(postsLength: number): FieldIssue[] {
  if (postsLength === 0) {
    return [
      {
        step: 2,
        fieldId: "findings-grid",
        message: "No posts yet — finish scout or refresh findings",
      },
    ];
  }
  return [];
}

/** Can the user navigate TO targetStep from current? */
export function canReachStep(
  target: MissionStep,
  mission: MissionState,
  postsLength: number,
): FieldIssue[] {
  if (target <= 0) return [];
  const issues: FieldIssue[] = [];
  if (target >= 1) issues.push(...validateContext(mission));
  if (target >= 2) issues.push(...validateScout(mission));
  if (target >= 3) issues.push(...validateFindings(postsLength));
  return issues;
}

export function focusField(fieldId: string): void {
  const el = document.getElementById(fieldId);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  if ("focus" in el && typeof (el as HTMLElement).focus === "function") {
    (el as HTMLElement).focus();
  }
  el.classList.add("ring-2", "ring-destructive", "ring-offset-2", "ring-offset-background");
  window.setTimeout(() => {
    el.classList.remove("ring-2", "ring-destructive", "ring-offset-2", "ring-offset-background");
  }, 2200);
}
