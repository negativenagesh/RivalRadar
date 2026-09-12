"use client";

import type { BrandProfile } from "@/lib/types";
import { isValidSocialUrl, type SocialKey } from "@/lib/social-validate";
import { cn } from "@/lib/utils";

type SocialMeta = {
  key: SocialKey;
  label: string;
  placeholder: string;
  accent: string;
  glow: string;
};

export const SOCIAL_META: SocialMeta[] = [
  {
    key: "linkedin",
    label: "LinkedIn",
    placeholder: "linkedin.com/company/acme",
    accent: "#0A66C2",
    glow: "rgba(10,102,194,0.45)",
  },
  {
    key: "x",
    label: "X",
    placeholder: "x.com/acme",
    accent: "#E7E9EA",
    glow: "rgba(231,233,234,0.25)",
  },
  {
    key: "instagram",
    label: "Instagram",
    placeholder: "instagram.com/acme",
    accent: "#E4405F",
    glow: "rgba(228,64,95,0.4)",
  },
  {
    key: "tiktok",
    label: "TikTok",
    placeholder: "tiktok.com/@acme",
    accent: "#25F4EE",
    glow: "rgba(37,244,238,0.35)",
  },
  {
    key: "youtube",
    label: "YouTube",
    placeholder: "youtube.com/@acme",
    accent: "#FF0000",
    glow: "rgba(255,0,0,0.4)",
  },
  {
    key: "threads",
    label: "Threads",
    placeholder: "threads.net/@acme",
    accent: "#FFFFFF",
    glow: "rgba(255,255,255,0.2)",
  },
];

function LinkedInIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932L18.901 1.153zM17.61 20.644h2.039L6.486 3.24H4.298L17.61 20.644z" />
    </svg>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
    </svg>
  );
}

function TikTokIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z" />
    </svg>
  );
}

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.016 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  );
}

function ThreadsIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden>
      <path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.028c.028-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.181 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.987-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.718 3.616 9.114 3.589 12v.021c.027 2.887.718 5.282 2.057 7.12 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.447-1.284 3.272-.757.94-1.843 1.638-3.243 2.083-.828.264-1.732.401-2.684.403-.002-2.105-.004-4.21 0-6.315.002-.74.084-1.47.306-2.17.4-1.26 1.25-2.23 2.4-2.75.7-.32 1.48-.48 2.27-.48 1.84 0 3.4.84 4.28 2.24.54.86.82 1.88.82 3.04 0 2.59-1.18 4.68-3.2 5.68-.7.35-1.48.53-2.28.53-.36 0-.72-.04-1.07-.11v-2.16c.24.05.48.07.72.07.9 0 1.66-.28 2.22-.82.56-.54.84-1.3.84-2.26 0-.9-.28-1.62-.84-2.12-.56-.5-1.3-.76-2.2-.76-.92 0-1.68.3-2.24.9-.56.6-.84 1.4-.84 2.38v8.74c0 .18.01.36.02.54z" />
    </svg>
  );
}

const ICONS: Record<SocialKey, React.FC<{ className?: string }>> = {
  linkedin: LinkedInIcon,
  x: XIcon,
  instagram: InstagramIcon,
  tiktok: TikTokIcon,
  youtube: YouTubeIcon,
  threads: ThreadsIcon,
};

export function SocialGlyph({
  platform,
  className,
}: {
  platform: SocialKey;
  className?: string;
}) {
  const Icon = ICONS[platform];
  return <Icon className={className} />;
}

export function SocialLinkFields({
  socials,
  onChange,
  idPrefix = "brand",
}: {
  socials: BrandProfile["socials"];
  onChange: (next: BrandProfile["socials"]) => void;
  idPrefix?: string;
}) {
  const validCount = SOCIAL_META.filter((m) => isValidSocialUrl(m.key, socials[m.key])).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/90">
          Social stack
        </p>
        <p className="text-[11px] text-muted-foreground">{validCount}/6 verified</p>
      </div>

      <div className="grid gap-2.5">
        {SOCIAL_META.map((meta) => {
          const value = socials[meta.key];
          const valid = isValidSocialUrl(meta.key, value);
          const dirty = Boolean(value.trim()) && !valid;
          const inputId = `${idPrefix}-social-${meta.key}`;

          return (
            <label
              key={meta.key}
              htmlFor={inputId}
              className={cn(
                "group flex items-center gap-3 rounded-2xl border bg-background/40 px-3 py-2.5 backdrop-blur-md transition-all duration-500",
                valid && "border-transparent",
                dirty && "border-destructive/50",
                !valid && !dirty && "border-border/50 hover:border-primary/30",
              )}
              style={
                valid
                  ? {
                      borderColor: `${meta.accent}55`,
                      boxShadow: `inset 3px 0 0 ${meta.accent}, 0 0 32px -14px ${meta.glow}`,
                    }
                  : undefined
              }
            >
              <span
                className={cn(
                  "flex size-9 shrink-0 items-center justify-center rounded-xl border border-border/40 bg-muted/30 transition-all duration-500",
                  valid && "scale-110",
                  dirty && "border-destructive/40 text-destructive",
                )}
                style={
                  valid
                    ? {
                        color: meta.accent,
                        borderColor: `${meta.accent}66`,
                        boxShadow: `0 0 18px -4px ${meta.glow}`,
                        backgroundColor: `${meta.accent}18`,
                      }
                    : undefined
                }
              >
                <SocialGlyph platform={meta.key} className="size-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {meta.label}
                  {dirty ? (
                    <span className="ml-2 font-normal normal-case tracking-normal text-destructive">
                      invalid URL
                    </span>
                  ) : null}
                </span>
                <input
                  id={inputId}
                  value={value}
                  placeholder={meta.placeholder}
                  onChange={(e) => onChange({ ...socials, [meta.key]: e.target.value })}
                  className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
                />
              </span>
              {valid && (
                <span
                  className="hidden size-1.5 shrink-0 rounded-full sm:block"
                  style={{ backgroundColor: meta.accent, boxShadow: `0 0 8px ${meta.glow}` }}
                />
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}
