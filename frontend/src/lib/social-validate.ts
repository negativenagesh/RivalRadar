export type SocialKey = "linkedin" | "x" | "instagram" | "tiktok" | "youtube" | "threads";

/** Accept full URLs or common handle/path forms for each platform. */
export const SOCIAL_PATTERNS: Record<SocialKey, RegExp> = {
  linkedin: /^(https?:\/\/)?(www\.)?linkedin\.com\/(in|company|school)\/[\w%-]+\/?(\?.*)?$/i,
  x: /^(https?:\/\/)?(www\.)?(x|twitter)\.com\/@?[\w]+\/?(\?.*)?$/i,
  instagram: /^(https?:\/\/)?(www\.)?instagram\.com\/[\w.]+\/?(\?.*)?$/i,
  tiktok: /^(https?:\/\/)?(www\.)?tiktok\.com\/@[\w.]+\/?(\?.*)?$/i,
  youtube: /^(https?:\/\/)?(www\.)?youtube\.com\/(@|channel\/|c\/|user\/)[\w.-]+\/?(\?.*)?$/i,
  threads: /^(https?:\/\/)?(www\.)?threads\.net\/@?[\w.]+\/?(\?.*)?$/i,
};

export function isValidSocialUrl(platform: SocialKey, value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  return SOCIAL_PATTERNS[platform].test(text);
}

export function isValidWebsite(value: string): boolean {
  const text = value.trim();
  if (!text) return false;
  // pixis.ai or https://pixis.ai
  return /^(https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}(\/.*)?$/i.test(text);
}
