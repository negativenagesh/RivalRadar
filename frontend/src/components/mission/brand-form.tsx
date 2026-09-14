"use client";

import { motion } from "motion/react";
import { Globe2, KeyRound, Plus, Sparkles, Trash2, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { SocialLinkFields } from "@/components/mission/social-icons";
import { useOperatorModels } from "@/components/operator-models-provider";
import type { BrandProfile, CompetitorProfile } from "@/lib/types";
import { newCompetitor } from "@/lib/mission-store";
import { cn } from "@/lib/utils";

const FORMAT_OPTIONS = [
  { id: "meme", label: "Meme" },
  { id: "carousel", label: "Carousel" },
  { id: "founder_pov", label: "Founder POV" },
  { id: "product_demo", label: "Product demo" },
  { id: "ugc", label: "UGC" },
  { id: "thread", label: "Thread" },
] as const;

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
          {label}
        </span>
        {hint ? <span className="text-[10px] text-muted-foreground/70">{hint}</span> : null}
      </span>
      {children}
    </label>
  );
}

const inputClass =
  "h-11 w-full rounded-xl border border-border/50 bg-background/50 px-3.5 text-sm outline-none backdrop-blur transition-all placeholder:text-muted-foreground/45 focus-visible:border-primary/50 focus-visible:ring-3 focus-visible:ring-primary/20";

function GlassPanel({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 18 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.45, delay }}
      className={cn(
        "group/panel relative overflow-hidden rounded-3xl border border-border/45 bg-card/35 p-5 backdrop-blur-xl sm:p-6",
        "shadow-[0_0_0_0_transparent] transition-[box-shadow,border-color,background] duration-500",
        "hover:border-primary/35 hover:bg-card/55",
        "hover:shadow-[0_0_48px_-18px_oklch(0.87_0.24_128),inset_0_1px_0_0_oklch(0.87_0.24_128_/_0.12)]",
        className,
      )}
    >
      <div className="pointer-events-none absolute -right-20 -top-20 size-48 rounded-full bg-primary/0 blur-3xl transition-all duration-700 group-hover/panel:bg-primary/15" />
      <div className="pointer-events-none absolute -bottom-24 -left-16 size-40 rounded-full bg-primary/0 blur-3xl transition-all duration-700 group-hover/panel:bg-primary/10" />
      <div className="relative">{children}</div>
    </motion.section>
  );
}

function ModelsKillswitch() {
  const models = useOperatorModels();

  return (
    <GlassPanel delay={0.05} className={models.readyText ? undefined : "border-destructive/50"}>
      <div className="mb-4">
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
          <KeyRound className="size-3.5" />
          Model keys
        </p>
        <h2 className="mt-2 text-2xl font-bold tracking-tight">Your keys. Your tokens.</h2>
        <p className="mt-1 max-w-md text-sm text-muted-foreground">
          Gemini, DeepSeek V4.1 Flash, or NVIDIA gpt-oss-20b. Stored in this browser only — never
          the server .env. Test a key before it is saved.
        </p>
      </div>
      {models.readyText ? (
        <p className="mb-3 rounded-2xl border border-primary/30 bg-primary/10 px-3 py-2 font-mono text-sm text-primary">
          live {models.chipLabel}
        </p>
      ) : (
        <p className="mb-3 animate-pulse rounded-2xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          Warning: no text model key. The war room stays dark until you paste one.
        </p>
      )}
      <Button type="button" onClick={() => models.openSheet()}>
        Open Models
      </Button>
    </GlassPanel>
  );
}

export function BrandForm({
  brand,
  competitors,
  onBrandChange,
  onCompetitorsChange,
}: {
  brand: BrandProfile;
  competitors: CompetitorProfile[];
  onBrandChange: (b: BrandProfile) => void;
  onCompetitorsChange: (c: CompetitorProfile[]) => void;
}) {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <GlassPanel delay={0.02}>
        <div className="mb-5">
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-primary">
            <Zap className="size-3.5" />
            Brand drop
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight">Who are we arming?</h2>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            Name, niche, site — then paste socials. Icons glow only when the URL checks out.
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Display name">
            <input
              id="brand-displayName"
              className={inputClass}
              value={brand.displayName}
              placeholder="Pixis"
              onChange={(e) => onBrandChange({ ...brand, displayName: e.target.value })}
            />
          </Field>
          <Field label="Category">
            <input
              id="brand-category"
              className={inputClass}
              value={brand.category}
              placeholder="AI marketing / SaaS"
              onChange={(e) => onBrandChange({ ...brand, category: e.target.value })}
            />
          </Field>
          <Field label="Company website" hint="required">
            <div className="relative">
              <Globe2 className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-primary/70" />
              <input
                id="brand-website"
                className={`${inputClass} pl-10`}
                value={brand.website}
                placeholder="pixis.ai"
                onChange={(e) => onBrandChange({ ...brand, website: e.target.value })}
              />
            </div>
          </Field>
          <Field label="Timezone">
            <input
              id="brand-timezone"
              className={inputClass}
              value={brand.timezone}
              placeholder="America/Los_Angeles"
              onChange={(e) => onBrandChange({ ...brand, timezone: e.target.value })}
            />
          </Field>
        </div>
      </GlassPanel>

      <ModelsKillswitch />

      <GlassPanel delay={0.08}>
        <SocialLinkFields
          idPrefix="brand"
          socials={brand.socials}
          onChange={(socials) => onBrandChange({ ...brand, socials })}
        />
      </GlassPanel>

      <GlassPanel delay={0.12}>
        <div className="mb-4 flex items-center gap-2">
          <Sparkles className="size-4 text-primary" />
          <h2 className="text-lg font-bold">Voice + guardrails</h2>
        </div>
        <div className="space-y-4">
          <Field label="Brand voice notes">
            <Textarea
              id="brand-voice"
              value={brand.voiceNotes}
              placeholder="Witty, slightly chaotic, never corporate. Short sentences. Emoji sparingly."
              onChange={(e) => onBrandChange({ ...brand, voiceNotes: e.target.value })}
              rows={3}
              className="rounded-xl border-border/50 bg-background/50"
            />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Ideal customer">
              <Textarea
                id="brand-customer"
                value={brand.idealCustomer}
                placeholder="Growth marketers at mid-market SaaS…"
                onChange={(e) => onBrandChange({ ...brand, idealCustomer: e.target.value })}
                rows={2}
                className="rounded-xl border-border/50 bg-background/50"
              />
            </Field>
            <Field label="Content pillars">
              <Textarea
                id="brand-pillars"
                value={brand.contentPillars}
                placeholder="product drops, founder lessons, culture"
                onChange={(e) => onBrandChange({ ...brand, contentPillars: e.target.value })}
                rows={2}
                className="rounded-xl border-border/50 bg-background/50"
              />
            </Field>
          </div>
          <Field label="Forbidden claims / do-not-say">
            <Textarea
              id="brand-forbidden"
              value={brand.forbiddenClaims}
              placeholder="#1 in market, guaranteed ROI…"
              onChange={(e) => onBrandChange({ ...brand, forbiddenClaims: e.target.value })}
              rows={2}
              className="rounded-xl border-border/50 bg-background/50"
            />
          </Field>
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Preferred formats
            </p>
            <div className="flex flex-wrap gap-2">
              {FORMAT_OPTIONS.map((f) => {
                const on = brand.preferredFormats.includes(f.id);
                return (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => {
                      const next = on
                        ? brand.preferredFormats.filter((x) => x !== f.id)
                        : [...brand.preferredFormats, f.id];
                      onBrandChange({ ...brand, preferredFormats: next });
                    }}
                    className={cn(
                      "rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-300",
                      on
                        ? "scale-105 bg-primary text-primary-foreground shadow-[0_0_20px_-6px_oklch(0.87_0.24_128)]"
                        : "border border-border/60 text-muted-foreground hover:border-primary/40 hover:text-foreground",
                    )}
                  >
                    {f.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </GlassPanel>

      <GlassPanel delay={0.16}>
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">
              Rival radar
            </p>
            <h2 className="mt-2 text-2xl font-bold tracking-tight">Who are we watching?</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Drop rivals + their socials. More signal = sharper gaps.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            className="shrink-0 shadow-[0_0_24px_-8px_oklch(0.87_0.24_128)]"
            onClick={() => onCompetitorsChange([...competitors, newCompetitor()])}
          >
            <Plus className="size-3.5" />
            Add rival
          </Button>
        </div>

        <div className="space-y-4">
          {competitors.map((comp, idx) => (
            <motion.div
              key={comp.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              whileHover={{ scale: 1.005 }}
              className="space-y-4 rounded-2xl border border-border/50 bg-background/30 p-4 transition-shadow duration-500 hover:border-primary/30 hover:shadow-[0_0_36px_-16px_oklch(0.87_0.24_128)]"
            >
              <div className="flex items-center justify-between">
                <p className="font-mono text-xs text-primary">
                  RIVAL_{String(idx + 1).padStart(2, "0")}
                </p>
                {competitors.length > 1 && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    onClick={() =>
                      onCompetitorsChange(competitors.filter((c) => c.id !== comp.id))
                    }
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                )}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Name">
                  <input
                    id={`rival-${idx}-name`}
                    className={inputClass}
                    value={comp.name}
                    placeholder="Competitor Co"
                    onChange={(e) =>
                      onCompetitorsChange(
                        competitors.map((c) =>
                          c.id === comp.id ? { ...c, name: e.target.value } : c,
                        ),
                      )
                    }
                  />
                </Field>
                <Field label="Website">
                  <input
                    id={`rival-${idx}-website`}
                    className={inputClass}
                    value={comp.website}
                    placeholder="competitor.com"
                    onChange={(e) =>
                      onCompetitorsChange(
                        competitors.map((c) =>
                          c.id === comp.id ? { ...c, website: e.target.value } : c,
                        ),
                      )
                    }
                  />
                </Field>
              </div>
              <SocialLinkFields
                idPrefix={`rival-${idx}`}
                socials={comp.socials}
                onChange={(socials) =>
                  onCompetitorsChange(
                    competitors.map((c) => (c.id === comp.id ? { ...c, socials } : c)),
                  )
                }
              />
              <Field label="Why they matter">
                <input
                  id={`rival-${idx}-why`}
                  className={inputClass}
                  value={comp.whyTheyMatter}
                  placeholder="Same ICP, louder meme game…"
                  onChange={(e) =>
                    onCompetitorsChange(
                      competitors.map((c) =>
                        c.id === comp.id ? { ...c, whyTheyMatter: e.target.value } : c,
                      ),
                    )
                  }
                />
              </Field>
            </motion.div>
          ))}
        </div>
      </GlassPanel>
    </div>
  );
}
