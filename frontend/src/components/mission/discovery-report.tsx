"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  CalendarPlus,
  Copy,
  Download,
  ExternalLink,
  Flame,
  Loader2,
  MessageSquare,
  Send,
  Sparkles,
  Target,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useOperatorModels } from "@/components/operator-models-provider";
import { pushNotification } from "@/lib/notifications";
import {
  dropSocialComment,
  generateCreative,
  getIntelJob,
  listConnections,
  stagePlatformPost,
  startIntelJob,
  streamCommentDraft,
  streamPublishPlan,
  type PublishPlan,
  type PublishVariation,
  type StagePostResult,
} from "@/lib/api";
import { MarkdownReport } from "@/components/mission/markdown-report";
import { IntelVisuals } from "@/components/mission/intel-visuals";
import { mergeIntel, buildStudioRoastPack, type IntelFacts } from "@/lib/intel-facts";
import {
  clearIntelCache,
  intelCacheKey,
  intelFactsSig,
  readIntelCache,
  writeIntelCache,
} from "@/lib/intel-cache";
import {
  defaultScheduleLocalValue,
  localValueToIso,
  scheduleFromStudioAsset,
} from "@/lib/calendar";
import {
  appendStudioAssets,
  readStudioAssets,
  removeStudioAsset,
  type SavedStudioAsset,
} from "@/lib/studio-assets";
import {
  SNIPER_PLATFORMS,
  SNIPER_TONES,
  STUDIO_FORMATS,
  formatLabel,
  formatUnlocked,
} from "@/lib/studio-formats";
import { imageModelLabel, textModelLabel } from "@/lib/operator-models";
import type {
  BrandProfile,
  CompetitorProfile,
  ConnectionStatus,
  CreativePermissions,
  CreativeResult,
  IntelReport,
} from "@/lib/types";

const KEY_WARNING =
  "Paste a key in the Models chip, or set NVIDIA_API_KEY / AGNES_API_KEY in the server .env.";

const AGENT_LABELS: Record<string, string> = {
  intel_chief: "Intel Chief",
  play_caller: "Play Caller",
  platform_scout: "Platform Scout",
};

const PERM_OPTIONS: {
  key: keyof CreativePermissions;
  label: string;
  hint: string;
}[] = [
  {
    key: "draftReplies",
    label: "Draft reply / response posts",
    hint: "Comebacks to rival posts in your voice",
  },
  {
    key: "draftTrendJack",
    label: "Draft trend-jack originals",
    hint: "Unlocks the trend-jack chip",
  },
  {
    key: "suggestComments",
    label: "Suggest comments",
    hint: "Unlocks comment sniper — human-approve only",
  },
  {
    key: "imageConcepts",
    label: "Post visuals",
    hint: "Agnes 2.0 Flash frames (or Nano Banana / FLUX if you paste those keys)",
  },
  {
    key: "carouselOutlines",
    label: "Carousel / thread outlines",
    hint: "Receipt carousels + X threads",
  },
  {
    key: "comparisonSlides",
    label: "Competitive comparison slides",
    hint: "Myth-bust + us vs category (no rival logos)",
  },
];

function chipClass(on: boolean, locked?: boolean) {
  if (locked) {
    return "font-ui cursor-not-allowed rounded-full border border-border/40 px-3 py-1.5 text-xs text-muted-foreground/50";
  }
  return on
    ? "font-ui rounded-full border border-primary bg-primary/20 px-3 py-1.5 text-xs font-bold text-primary"
    : "font-ui rounded-full border border-border/60 px-3 py-1.5 text-xs text-muted-foreground hover:border-primary/40";
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // ignore
  }
}

function downloadImage(mime: string, b64: string, name: string) {
  const a = document.createElement("a");
  a.href = `data:${mime};base64,${b64}`;
  a.download = name;
  a.click();
}

function downloadMarkdown(name: string, source: string) {
  const blob = new Blob([source], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

function combinedMarkdown(intel: IntelReport, brandName: string): string {
  const extras = intel.reports
    .map((section) => `---\n\n# ${section.title}\n\n${section.markdown.trim()}`)
    .join("\n\n");
  return [`<!-- RivalRadar intel · ${brandName} -->`, intel.markdown.trim(), extras].filter(Boolean).join("\n\n");
}

export function DiscoveryReport({
  facts,
  permissions,
  onPermissionsChange,
  brand,
  competitors = [],
}: {
  facts: IntelFacts;
  permissions: CreativePermissions;
  onPermissionsChange: (p: CreativePermissions) => void;
  brand: BrandProfile;
  competitors?: CompetitorProfile[];
}) {
  const models = useOperatorModels();
  const factsJson = useMemo(() => JSON.stringify(facts), [facts]);
  const studioFactsJson = useMemo(
    () => JSON.stringify(buildStudioRoastPack(facts, brand, competitors)),
    [facts, brand, competitors],
  );
  const factsSig = intelFactsSig(facts);

  const [geminiIntel, setGeminiIntel] = useState<IntelReport | null>(null);
  const [intelFetchError, setIntelFetchError] = useState<string | null>(null);
  const [intelForSig, setIntelForSig] = useState(factsSig);
  const [reportTab, setReportTab] = useState("brief");
  const [intelTick, setIntelTick] = useState(0);
  const [intelStages, setIntelStages] = useState<Record<string, "writing" | "done">>({});
  const [intelLiveMarkdown, setIntelLiveMarkdown] = useState("");
  if (intelForSig !== factsSig) {
    setIntelForSig(factsSig);
    setGeminiIntel(null);
    setIntelFetchError(null);
    setIntelStages({});
    setIntelLiveMarkdown("");
    setReportTab("brief");
  }
  const intel = mergeIntel(facts, geminiIntel);
  const usedFallback = !geminiIntel || geminiIntel.narration === "fallback";
  const intelBusy =
    geminiIntel === null &&
    Object.values(intelStages).some((stage) => stage === "writing");
  const intelError = intelFetchError;
  const writingAgents = Object.entries(intelStages)
    .filter(([, status]) => status === "writing")
    .map(([agent]) => AGENT_LABELS[agent as keyof typeof AGENT_LABELS] ?? agent);

  const [studioFormat, setStudioFormat] = useState("hot_take");
  const [studioPlatform, setStudioPlatform] = useState("linkedin");
  const [studioSpice, setStudioSpice] = useState(3);
  const [studioCount, setStudioCount] = useState(1);
  const [studioBusy, setStudioBusy] = useState(false);
  const [studioLoadingSlot, setStudioLoadingSlot] = useState<number | null>(null);
  const [studioError, setStudioError] = useState<string | null>(null);
  const [studioOuts, setStudioOuts] = useState<CreativeResult[]>([]);
  const [studioLibrary, setStudioLibrary] = useState<SavedStudioAsset[]>(() =>
    readStudioAssets(brand.displayName || "brand"),
  );
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [studioMode, setStudioMode] = useState<"full" | "fast">("full");
  const [studioPhase, setStudioPhase] = useState<"writing" | "painting" | null>(null);
  const studioBrandKey = brand.displayName || "brand";
  const [libraryBrandKey, setLibraryBrandKey] = useState(studioBrandKey);
  if (libraryBrandKey !== studioBrandKey) {
    setLibraryBrandKey(studioBrandKey);
    setStudioLibrary(readStudioAssets(studioBrandKey));
  }

  const [sniperPlatform, setSniperPlatform] = useState("linkedin");
  const [sniperTone, setSniperTone] = useState<(typeof SNIPER_TONES)[number]>("witty");
  const [sniperSpice, setSniperSpice] = useState(3);
  const [sniperHref, setSniperHref] = useState<string>("");
  const [sniperBusy, setSniperBusy] = useState<"gen" | "drop" | null>(null);
  const [sniperError, setSniperError] = useState<string | null>(null);
  const [sniperDraft, setSniperDraft] = useState("");
  const [dropResult, setDropResult] = useState<{ detail: string; shot?: string | null } | null>(
    null,
  );
  const [connections, setConnections] = useState<ConnectionStatus[]>([]);

  const connectedSniper = useMemo(() => {
    const live = new Set(
      connections
        .filter((c) => c.status === "connected" && SNIPER_PLATFORMS.includes(c.platform as never))
        .map((c) => (c.platform === "twitter" ? "x" : c.platform)),
    );
    return SNIPER_PLATFORMS.filter((p) => live.has(p));
  }, [connections]);

  const queue = useMemo(() => {
    const seen = new Set<string>();
    const out: { href: string; label: string; caption: string }[] = [];
    for (const item of facts.sniperQueue) {
      if (!item.href || seen.has(item.href)) continue;
      seen.add(item.href);
      out.push({
        href: item.href,
        label: `${item.company} · ${item.platform} · ${item.likes}♡ ${item.comments}💬`,
        caption: item.caption,
      });
    }
    for (const bait of intel.sniper_bait) {
      if (!bait.href || seen.has(bait.href)) continue;
      seen.add(bait.href);
      out.push({ href: bait.href, label: `${bait.company} · bait`, caption: bait.why });
    }
    return out;
  }, [facts.sniperQueue, intel.sniper_bait]);

  const activeSniperPlatform =
    connectedSniper.includes(sniperPlatform as (typeof SNIPER_PLATFORMS)[number])
      ? sniperPlatform
      : (connectedSniper[0] ?? sniperPlatform);
  const activeSniperHref = sniperHref || queue[0]?.href || "";

  useEffect(() => {
    let cancelled = false;
    void listConnections()
      .then((rows) => {
        if (!cancelled) setConnections(rows);
      })
      .catch(() => {
        if (!cancelled) setConnections([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    // Refresh / mount: load cached intel only. Never start or stream a text model
    // unless the operator clicks Regenerate intel.
    let cancelled = false;
    const brandName = brand.displayName || "the brand";
    const cacheKey = intelCacheKey(factsSig, brandName);

    async function loadCachedIntel() {
      const local = readIntelCache(cacheKey);
      if (local) {
        if (!cancelled) {
          setGeminiIntel(local);
          setIntelFetchError(null);
        }
        return;
      }
      try {
        const job = await getIntelJob(cacheKey);
        if (cancelled) return;
        if (job.status === "done" && job.report) {
          writeIntelCache(cacheKey, job.report);
          setGeminiIntel(job.report);
          setIntelFetchError(null);
          return;
        }
        if (job.status === "running") {
          // Poll an already-running job; do not start a new one.
          setIntelStages({ intel_chief: "writing", play_caller: "writing", platform_scout: "writing" });
          for (let i = 0; i < 120 && !cancelled; i += 1) {
            await new Promise((r) => window.setTimeout(r, 2500));
            const next = await getIntelJob(cacheKey);
            if (cancelled) return;
            if (next.status === "done" && next.report) {
              writeIntelCache(cacheKey, next.report);
              setGeminiIntel(next.report);
              setIntelLiveMarkdown("");
              setIntelFetchError(null);
              return;
            }
            if (next.status === "error") {
              if (!cancelled) {
                setIntelFetchError(next.error || "Intel job failed");
                setGeminiIntel(null);
              }
              return;
            }
          }
        }
        // miss / idle — wait for Regenerate; show fact brief only.
        if (!cancelled) {
          setGeminiIntel(null);
          setIntelFetchError(null);
        }
      } catch {
        if (!cancelled) {
          setGeminiIntel(null);
          setIntelFetchError(null);
        }
      }
    }

    void loadCachedIntel();
    return () => {
      cancelled = true;
    };
  }, [
    factsSig,
    brand.displayName,
    intelTick,
  ]);

  async function runStudio(spice = studioSpice) {
    if (!models.readyImage) {
      setStudioError("Agnes (or another image model) must be available — paste a key or set AGNES_API_KEY.");
      return;
    }
    if (studioMode === "full" && !models.readyText) {
      setStudioError("Full generate needs a text model — paste a key in Models, or switch to Fast paint.");
      return;
    }
    if (!formatUnlocked(studioFormat, permissions)) {
      setStudioError("Flip on the matching creative permission first.");
      return;
    }
    const batch = studioCount;
    setStudioBusy(true);
    setStudioError(null);
    setStudioOuts([]);
    setStudioSpice(spice);
    const collected: CreativeResult[] = [];
    try {
      for (let i = 1; i <= batch; i += 1) {
        setStudioLoadingSlot(i);
        setStudioPhase(studioMode === "full" ? "writing" : "painting");
        // Soft progress: after a beat, show painting while the request is in flight.
        const paintTimer =
          studioMode === "full"
            ? window.setTimeout(() => setStudioPhase("painting"), 2500)
            : null;
        const result = await generateCreative({
          kind: "studio",
          brand_name: brand.displayName || "the brand",
          voice_notes: brand.voiceNotes,
          forbidden_claims: brand.forbiddenClaims,
          brand_category: brand.category,
          ideal_customer: brand.idealCustomer,
          content_pillars: brand.contentPillars,
          preferred_formats: brand.preferredFormats,
          platform: studioPlatform,
          format: studioFormat,
          spice,
          facts_json: studioFormat === "meme" ? studioFactsJson : factsJson,
          variant: i,
          variant_count: batch,
          studio_mode: studioMode,
        });
        if (paintTimer) window.clearTimeout(paintTimer);
        collected.push(result);
        setStudioOuts([...collected]);
      }
      if (collected.length) {
        const next = appendStudioAssets(brand.displayName || "brand", collected, {
          format: studioFormat,
          platform: studioPlatform,
        });
        setStudioLibrary(next);
        pushNotification({
          kind: "studio_done",
          title: "Studio frames ready",
          body: `${collected.length} × ${formatLabel(studioFormat)} for ${brand.displayName || "brand"} — open Post to stage.`,
          href: "/mission",
        });
      }
    } catch (err) {
      setStudioError(err instanceof Error ? err.message : "Studio generation failed");
      if (collected.length) {
        setStudioOuts([...collected]);
        const next = appendStudioAssets(brand.displayName || "brand", collected, {
          format: studioFormat,
          platform: studioPlatform,
        });
        setStudioLibrary(next);
      }
    } finally {
      setStudioLoadingSlot(null);
      setStudioPhase(null);
      setStudioBusy(false);
    }
  }

  function studioImageSrc(out: CreativeResult): string | null {
    return out.image_data_base64 && out.image_mime_type
      ? `data:${out.image_mime_type};base64,${out.image_data_base64}`
      : null;
  }

  async function runSniper() {
    if (!models.readyText) {
      setSniperError(KEY_WARNING);
      return;
    }
    if (!permissions.suggestComments) {
      setSniperError("Enable “Suggest comments” permission first.");
      return;
    }
    const picked = queue.find((q) => q.href === activeSniperHref);
    if (!picked?.href) {
      setSniperError("Pick a rival post with a permalink.");
      return;
    }
    setSniperBusy("gen");
    setSniperError(null);
    setDropResult(null);
    try {
      setSniperDraft("");
      const result = await streamCommentDraft(
        {
          kind: "comment",
          brand_name: brand.displayName || "the brand",
          voice_notes: brand.voiceNotes,
          forbidden_claims: brand.forbiddenClaims,
          platform: activeSniperPlatform,
          spice: sniperSpice,
          tone: sniperTone,
          post_url: picked.href,
          competitor_caption: picked.caption,
          facts_json: factsJson,
        },
        (event) => {
          if (event.event === "delta" && event.text) {
            setSniperDraft((prev) => `${prev}${event.text}`);
          }
        },
      );
      setSniperDraft(result.text);
    } catch (err) {
      setSniperError(err instanceof Error ? err.message : "Sniper draft failed");
    } finally {
      setSniperBusy(null);
    }
  }

  async function approveAndDrop() {
    if (!sniperDraft.trim() || !activeSniperHref) return;
    setSniperBusy("drop");
    setSniperError(null);
    try {
      const result = await dropSocialComment({
        platform: activeSniperPlatform,
        url: activeSniperHref,
        text: sniperDraft.trim(),
        approved: true,
      });
      setDropResult({ detail: result.detail, shot: result.screenshot_jpeg_b64 });
    } catch (err) {
      setSniperError(err instanceof Error ? err.message : "Drop failed");
    } finally {
      setSniperBusy(null);
    }
  }

  const activeReport =
    reportTab === "brief"
      ? geminiIntel
        ? intel.markdown
        : intelLiveMarkdown || intel.markdown
      : (intel.reports.find((section) => section.id === reportTab)?.markdown ?? intel.markdown);

  return (
    <div className="relative mx-auto w-full max-w-4xl space-y-12 text-center">
      <div className="pointer-events-none absolute -inset-x-16 -top-16 h-56 bg-[radial-gradient(ellipse_at_top,oklch(0.87_0.24_128_/_0.22),transparent_70%)]" />

      <div className="relative space-y-3">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          war room
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-6xl">
          Intel <span className="text-primary">brief</span>
        </h2>
        <p className="font-accent mx-auto max-w-xl text-base italic text-muted-foreground">
          {facts.window.label}. Receipts first. Agents narrate — they do not invent the numbers.
        </p>
      </div>

      {!models.readyText && (
        <p
          role="alert"
          className="animate-pulse rounded-2xl border border-primary/40 bg-primary/10 px-4 py-3 text-sm text-primary"
        >
          {KEY_WARNING}
        </p>
      )}

      <section className="relative space-y-4">
        <h3 className="font-display text-lg font-bold">Scoreboard</h3>
        <IntelVisuals facts={facts} />
      </section>

      <section className="relative space-y-4 text-left">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-display text-lg font-bold">War-room agents</h3>
          <div className="flex items-center gap-2">
            {intelBusy && <Loader2 className="size-4 animate-spin text-primary" />}
            <span className="font-ui text-[10px] uppercase tracking-widest text-muted-foreground">
              {intelBusy
                ? writingAgents.length
                  ? `${writingAgents.join(" + ")} writing · streaming`
                  : "agents writing"
                : usedFallback
                  ? "offline · fact brief"
                  : `${models.textModel ?? "model"} live`}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={!models.readyText || intelBusy}
              onClick={() => {
                const cacheKey = intelCacheKey(factsSig, brand.displayName || "the brand");
                clearIntelCache(cacheKey);
                void startIntelJob({
                  cache_key: cacheKey,
                  facts,
                  brand_name: brand.displayName || "the brand",
                  voice_notes: brand.voiceNotes,
                  forbidden_claims: brand.forbiddenClaims,
                  force: true,
                }).catch(() => undefined);
                setGeminiIntel(null);
                setIntelFetchError(null);
                setIntelStages({});
                setIntelLiveMarkdown("");
                setIntelTick((n) => n + 1);
              }}
            >
              Regenerate intel
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                downloadMarkdown(
                  `rivalradar-intel-${facts.brandName.replace(/\s+/g, "-").toLowerCase()}.md`,
                  combinedMarkdown(intel, facts.brandName),
                )
              }
            >
              <Download className="size-3.5" />
              Download .md
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {(["intel_chief", "play_caller", "platform_scout"] as const).map((id) => {
            const live = (intel.agents_used ?? []).includes(id);
            const stage = intelStages[id];
            const label = intelBusy
              ? stage === "done"
                ? " · done"
                : " · writing"
              : live
                ? " · live"
                : " · standby";
            return (
              <span
                key={id}
                className={
                  live || (intelBusy && stage === "done")
                    ? "font-ui rounded-full border border-primary/40 bg-primary/15 px-3 py-1 text-[11px] font-semibold text-primary"
                    : "font-ui rounded-full border border-border/50 px-3 py-1 text-[11px] text-muted-foreground"
                }
              >
                {AGENT_LABELS[id]}
                {label}
              </span>
            );
          })}
          <span className="font-ui rounded-full border border-border/50 px-3 py-1 text-[11px] text-muted-foreground">
            Format Director · studio
          </span>
          <span className="font-ui rounded-full border border-border/50 px-3 py-1 text-[11px] text-muted-foreground">
            Comment Sniper · approve-only
          </span>
        </div>
        {intelError && (
          <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {intelError}
          </p>
        )}
        <p className="font-accent text-lg italic text-foreground/90">{intel.scoreboard_blurb}</p>

        <div className="grid gap-3 sm:grid-cols-2">
          {(
            [
              ["Good at", intel.good_at],
              ["Fumbling", intel.fumbling],
              ["Why engagement is mid", intel.why_engagement_mid],
              ["Gaps they own", intel.gaps],
            ] as const
          ).map(([title, lines]) => (
            <div
              key={title}
              className="rounded-2xl border border-border/50 bg-card/20 px-4 py-3 text-left"
            >
              <p className="font-ui text-[10px] font-semibold uppercase tracking-widest text-primary">
                {title}
              </p>
              <ul className="mt-2 space-y-1.5 text-sm text-muted-foreground">
                {(lines.length ? lines : ["—"]).map((line) => (
                  <li key={`${title}-${line}`} className="leading-snug">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setReportTab("brief")}
            className={chipClass(reportTab === "brief")}
          >
            Main brief
          </button>
          {intel.reports.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => setReportTab(section.id)}
              className={chipClass(reportTab === section.id)}
            >
              {section.title}
            </button>
          ))}
        </div>
        <MarkdownReport source={activeReport} />
        {intel.plays.length > 0 && reportTab === "brief" && (
          <ol className="grid gap-2 sm:grid-cols-2">
            {intel.plays.map((play, i) => (
              <li
                key={`${play.title}-${i}`}
                className="rounded-2xl border border-primary/25 bg-primary/5 px-4 py-3 text-left"
              >
                <p className="text-sm font-semibold">
                  {i + 1}. {play.title}{" "}
                  <span className="text-xs font-normal text-primary">
                    {play.format} · {play.platform}
                  </span>
                </p>
                <p className="mt-1 text-xs text-muted-foreground">{play.why}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="space-y-3 text-left">
        <h3 className="font-display text-lg font-bold">Creative permissions</h3>
        <ul className="space-y-2">
          {PERM_OPTIONS.map((opt) => (
            <li key={opt.key}>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 px-3 py-3 transition hover:border-primary/40">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 accent-[var(--primary)]"
                  checked={permissions[opt.key]}
                  onChange={(e) =>
                    onPermissionsChange({ ...permissions, [opt.key]: e.target.checked })
                  }
                />
                <span>
                  <span className="block text-sm font-medium">{opt.label}</span>
                  <span className="text-xs text-muted-foreground">{opt.hint}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section className="space-y-4 text-left">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" />
          <h3 className="font-display text-lg font-bold">Format studio</h3>
        </div>
        <p className="text-sm text-muted-foreground">
          Pick what to make. {models.textModel ? textModelLabel(models.textModel) : "Your text model"}{" "}
          writes the caption; {imageModelLabel(models.imageModel)} paints the frame. No rival logos.
        </p>
        <p className="rounded-xl border border-border/50 bg-background/30 px-3 py-2 text-xs text-muted-foreground">
          Context used as joke fuel (not painted literally): brand dossier + scout roast pack (your
          metrics vs each rival, visual%, cadence, themes, post receipts). Memes invent absurdist
          metaphors about rival flaws — no laptop/dashboard scoreboards, no “Rival: N Likes”
          overlays. Logos and rival post art stay out of the frame.
        </p>
        <div className="flex flex-wrap gap-2">
          {STUDIO_FORMATS.map((fmt) => {
            const locked = !permissions[fmt.permission];
            return (
              <button
                key={fmt.id}
                type="button"
                disabled={locked}
                title={locked ? `Enable “${fmt.permission}” first` : fmt.hint}
                onClick={() => setStudioFormat(fmt.id)}
                className={chipClass(studioFormat === fmt.id, locked)}
              >
                {fmt.label}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {["linkedin", "instagram", "x", "youtube"].map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setStudioPlatform(p)}
              className={chipClass(studioPlatform === p)}
            >
              {p}
            </button>
          ))}
          <span className="font-ui ml-2 text-xs text-muted-foreground">spice</span>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setStudioSpice(n)}
              className={chipClass(studioSpice === n)}
            >
              {n}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-ui text-xs text-muted-foreground">variations</span>
          {[1, 2, 3].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setStudioCount(n)}
              className={chipClass(studioCount === n)}
            >
              {n}
            </button>
          ))}
          <span className="text-xs text-muted-foreground">
            Up to 3, generated one after another (loading between each).
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-ui text-xs text-muted-foreground">mode</span>
          <button
            type="button"
            onClick={() => setStudioMode("full")}
            className={chipClass(studioMode === "full")}
          >
            Full generate
          </button>
          <button
            type="button"
            onClick={() => setStudioMode("fast")}
            className={chipClass(studioMode === "fast")}
          >
            Fast paint
          </button>
          <span className="text-xs text-muted-foreground">
            {studioMode === "full"
              ? "LLM writes caption + brief, then Agnes paints."
              : "Template caption + Agnes only (no text model)."}
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={
              studioBusy || !models.readyImage || (studioMode === "full" && !models.readyText)
            }
            onClick={() => void runStudio()}
          >
            {studioBusy ? <Loader2 className="size-4 animate-spin" /> : <Flame className="size-4" />}
            Generate
            {studioCount > 1 ? ` ×${studioCount}` : ""}
          </Button>
          {studioOuts.length > 0 && (
            <Button
              variant="outline"
              disabled={
                studioBusy || !models.readyImage || (studioMode === "full" && !models.readyText)
              }
              onClick={() => void runStudio(Math.min(5, studioSpice + 1))}
            >
              Regenerate with more spice
            </Button>
          )}
        </div>
        {studioBusy && studioPhase && (
          <p className="font-ui text-xs text-primary">
            {studioPhase === "writing" ? "Writing copy…" : "Painting with Agnes…"}
            {studioLoadingSlot && studioCount > 1 ? ` · frame ${studioLoadingSlot}/${studioCount}` : ""}
          </p>
        )}
        {studioError && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {studioError}
          </p>
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {studioOuts.map((out, idx) => {
            const src = studioImageSrc(out);
            return (
              <div
                key={`studio-${idx}-${out.overlay_text ?? out.text.slice(0, 24)}`}
                className="overflow-hidden rounded-2xl border border-border/60 bg-background/40"
              >
                <div className="border-b border-border/40 px-4 py-2 font-mono text-xs uppercase text-primary">
                  {formatLabel(studioFormat)} · {studioPlatform}
                  {studioOuts.length > 1 ? ` · #${idx + 1}` : ""}
                </div>
                <div className="space-y-3 p-4 text-left">
                  <div className="text-sm leading-relaxed">
                    <MarkdownReport source={out.text} />
                  </div>
                  {out.why_slaps && (
                    <p className="text-xs text-primary">Why this slaps: {out.why_slaps}</p>
                  )}
                  {out.overlay_text && (
                    <p className="text-xs text-muted-foreground">Overlay: {out.overlay_text}</p>
                  )}
                  {src && (
                    <button type="button" onClick={() => setLightbox(src)} className="block w-full">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={src}
                        alt={`Studio output ${idx + 1}`}
                        className="max-h-80 w-full rounded-xl border border-border/40 object-contain"
                      />
                    </button>
                  )}
                  {!src && out.image_error && (
                    <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                      {out.image_error}
                    </p>
                  )}
                  {!src && !out.image_error && (
                    <p className="text-xs text-muted-foreground">
                      No PNG this round — caption still usable. Try Generate again.
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" onClick={() => void copyText(out.text)}>
                      <Copy className="size-3.5" />
                      Copy caption
                    </Button>
                    {out.image_data_base64 && out.image_mime_type && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          downloadImage(
                            out.image_mime_type as string,
                            out.image_data_base64 as string,
                            `rivalradar-studio-${idx + 1}.png`,
                          )
                        }
                      >
                        <Download className="size-3.5" />
                        Download PNG
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {studioLoadingSlot !== null && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-primary/40 bg-primary/5 px-4 py-8">
              <Loader2 className="size-8 animate-spin text-primary" />
              <p className="font-mono text-xs uppercase tracking-wider text-primary">
                Cooking {formatLabel(studioFormat)} {studioLoadingSlot}
                {studioCount > 1 ? ` of ${studioCount}` : ""}
                …
              </p>
              <p className="text-xs text-muted-foreground">
                {studioPhase === "writing"
                  ? "Writing copy with the text model…"
                  : studioPhase === "painting"
                    ? "Painting with Agnes…"
                    : studioFormat === "meme"
                      ? "Caption first, then the frame — hang tight."
                      : `Building your ${formatLabel(studioFormat).toLowerCase()} — hang tight.`}
              </p>
            </div>
          )}
        </div>
        {studioLibrary.length > 0 && (
          <div className="space-y-3 rounded-2xl border border-primary/30 bg-primary/5 p-4 sm:p-5">
            <div className="space-y-1">
              <h4 className="font-display text-base font-bold text-primary">Post to platform</h4>
              <p className="text-sm text-muted-foreground">
                Saved studio assets stay here across refresh and new generates (
                {studioLibrary.length} saved). Publish Strategist can write platform-native
                captions; <strong>Post</strong> opens Connect/noVNC with image + caption staged —
                you hit publish yourself.
              </p>
            </div>
            <PublishPanel
              outs={studioLibrary}
              brandName={brand.displayName}
              intelMarkdown={geminiIntel?.markdown ?? null}
              factsJson={studioFormat === "meme" ? studioFactsJson : factsJson}
              format={studioFormat}
              spice={studioSpice}
              defaultPlatform={studioPlatform}
              ready={models.readyText}
              onRemoveAsset={(id) => {
                setStudioLibrary(removeStudioAsset(brand.displayName || "brand", id));
              }}
            />
          </div>
        )}
      </section>

      <section className="space-y-4 text-left">
        <div className="flex items-center gap-2">
          <Target className="size-4 text-primary" />
          <h3 className="font-display text-lg font-bold">Comment sniper</h3>
        </div>
        <p className="rounded-2xl border border-primary/30 bg-primary/8 px-4 py-3 text-sm text-muted-foreground">
          This uses <em>your</em> logged-in session. Platforms hate bots. One-at-a-time, human delays
          (10–15s). You approved this.
        </p>
        <div className="flex flex-wrap gap-2">
          {SNIPER_PLATFORMS.map((p) => {
            const locked = !connectedSniper.includes(p);
            return (
              <button
                key={p}
                type="button"
                disabled={locked}
                onClick={() => setSniperPlatform(p)}
                className={chipClass(activeSniperPlatform === p, locked)}
              >
                {p}
                {locked ? " (connect)" : ""}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-2">
          {SNIPER_TONES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setSniperTone(t)}
              className={chipClass(sniperTone === t)}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-ui text-xs text-muted-foreground">spice</span>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setSniperSpice(n)}
              className={chipClass(sniperSpice === n)}
            >
              {n}
            </button>
          ))}
        </div>
        <label className="block space-y-1.5">
          <span className="font-ui text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Rival post
          </span>
          <select
            value={activeSniperHref}
            onChange={(e) => setSniperHref(e.target.value)}
            className="h-11 w-full rounded-xl border border-border/50 bg-background px-3 text-sm"
          >
            {queue.length === 0 && <option value="">No permalinks in this window</option>}
            {queue.map((q) => (
              <option key={q.href} value={q.href}>
                {q.label}
              </option>
            ))}
          </select>
        </label>
        {activeSniperHref && (
          <a
            href={activeSniperHref}
            target="_blank"
            rel="noopener noreferrer"
            className="font-ui inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
          >
            Open permalink
            <ExternalLink className="size-3" />
          </a>
        )}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            disabled={sniperBusy !== null || !models.readyText}
            onClick={() => void runSniper()}
          >
            {sniperBusy === "gen" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <MessageSquare className="size-4" />
            )}
            Generate
          </Button>
        </div>
        {sniperDraft && (
          <textarea
            value={sniperDraft}
            onChange={(e) => setSniperDraft(e.target.value)}
            rows={4}
            className="w-full rounded-xl border border-border/50 bg-background px-3 py-2 text-sm"
          />
        )}
        {sniperDraft && (
          <Button
            disabled={sniperBusy !== null || !connectedSniper.includes(activeSniperPlatform as never)}
            onClick={() => void approveAndDrop()}
          >
            {sniperBusy === "drop" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Target className="size-4" />
            )}
            {sniperBusy === "drop" ? "Waiting like a human…" : "Approve & drop"}
          </Button>
        )}
        {sniperError && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {sniperError}
          </p>
        )}
        {dropResult && (
          <div className="space-y-2 rounded-xl border border-primary/30 bg-primary/8 p-3 text-sm">
            <p>{dropResult.detail}</p>
            {dropResult.shot && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={`data:image/jpeg;base64,${dropResult.shot}`}
                alt="Comment drop screenshot"
                className="max-h-64 rounded-lg object-contain"
              />
            )}
          </div>
        )}
      </section>

      <div className="flex flex-wrap justify-center gap-3">
        <Button size="lg" asChild>
          <Link href="/digest">Open weekly digest</Link>
        </Button>
        <Button size="lg" variant="secondary" asChild>
          <Link href="/review">Review queue</Link>
        </Button>
      </div>

      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/88 p-4"
          onClick={() => setLightbox(null)}
          role="presentation"
        >
          <button
            type="button"
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white"
            onClick={() => setLightbox(null)}
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={lightbox}
            alt=""
            className="max-h-[80vh] w-auto max-w-full rounded-2xl object-contain"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}

const PUBLISH_PLATFORMS = ["linkedin", "instagram", "x", "youtube"];

function publishVariationText(variation: PublishVariation, platform: string): string {
  if (platform === "youtube") {
    const title = variation.title || variation.caption.split("\n")[0] || "RivalRadar post";
    const body = variation.description || variation.caption;
    const tags = variation.hashtags.join(" ");
    return [title, body, tags].filter(Boolean).join("\n\n");
  }
  const tags = variation.hashtags.join(" ");
  return [variation.caption, tags].filter(Boolean).join("\n\n");
}

function PublishPanel({
  outs,
  brandName,
  intelMarkdown,
  factsJson,
  format,
  spice,
  defaultPlatform,
  ready,
  onRemoveAsset,
}: {
  outs: SavedStudioAsset[];
  brandName: string;
  intelMarkdown: string | null;
  factsJson: string;
  format: string;
  spice: number;
  defaultPlatform: string;
  ready: boolean;
  onRemoveAsset?: (id: string) => void;
}) {
  const [assetIdx, setAssetIdx] = useState(0);
  const safeAssetIdx = Math.min(assetIdx, Math.max(outs.length - 1, 0));
  const out = outs[safeAssetIdx] ?? outs[0];
  const [platform, setPlatform] = useState(
    PUBLISH_PLATFORMS.includes(defaultPlatform) ? defaultPlatform : "x",
  );
  const [count, setCount] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [liveDraft, setLiveDraft] = useState("");
  const [plan, setPlan] = useState<PublishPlan | null>(null);
  const [stagingIdx, setStagingIdx] = useState<number | null>(null);
  const [stagingAll, setStagingAll] = useState(false);
  const [selected, setSelected] = useState<Record<number, boolean>>({});
  const [staged, setStaged] = useState<Record<number, StagePostResult>>({});
  const [scheduleLocal, setScheduleLocal] = useState(() => defaultScheduleLocalValue());
  const [scheduleNote, setScheduleNote] = useState<string | null>(null);

  function selectAsset(idx: number): void {
    if (idx === safeAssetIdx) return;
    setAssetIdx(idx);
    setPlan(null);
    setError(null);
    setStaged({});
    setSelected({});
    setLiveDraft("");
  }

  function selectPlatform(next: string): void {
    if (next === platform) return;
    setPlatform(next);
    setPlan(null);
    setError(null);
    setStaged({});
    setSelected({});
  }

  async function runPlan(): Promise<void> {
    if (!out) return;
    setBusy(true);
    setError(null);
    setStaged({});
    setSelected({});
    setLiveDraft("");
    try {
      const next = await streamPublishPlan(
        {
          brand_name: brandName,
          platform,
          asset_caption: out.text,
          overlay_text: out.overlay_text ?? undefined,
          asset_context: [out.overlay_text, out.why_slaps].filter(Boolean).join(" — "),
          image_concept: out.image_concept ?? undefined,
          intel_markdown: intelMarkdown ?? undefined,
          facts_json: factsJson,
          format,
          spice,
          variations: count,
        },
        (event) => {
          if (event.event === "delta" && event.text) {
            setLiveDraft((prev) => `${prev}${event.text}`);
          }
        },
      );
      setPlan(next);
      setLiveDraft("");
      const initial: Record<number, boolean> = {};
      next.variations.forEach((_, idx) => {
        initial[idx] = true;
      });
      setSelected(initial);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "publish plan failed");
    } finally {
      setBusy(false);
    }
  }

  async function openViewer(result: StagePostResult): Promise<void> {
    const url = result.viewer_url?.trim();
    if (url && typeof window !== "undefined") {
      window.open(url, "_blank", "noopener,noreferrer");
    }
  }

  async function stageVariation(idx: number, variation: PublishVariation): Promise<void> {
    if (!out) return;
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        `Open ${platform} in the Connect browser (noVNC) and stage this post with the image attached? Nothing gets published — you review and hit post yourself.`,
      )
    ) {
      return;
    }
    setStagingIdx(idx);
    setError(null);
    try {
      const result = await stagePlatformPost({
        platform,
        caption: publishVariationText(variation, platform),
        media_png_b64: out.image_data_base64 ?? undefined,
        approved: true,
      });
      setStaged((prev) => ({ ...prev, [idx]: result }));
      await openViewer(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "staging failed");
    } finally {
      setStagingIdx(null);
    }
  }

  async function stageStudioCaption(): Promise<void> {
    if (!out) return;
    const caption = (out.text || "").trim();
    if (!caption) {
      setError("Studio caption is empty — generate an asset first.");
      return;
    }
    if (!out.image_data_base64) {
      setError("No image on this asset — Generate a frame before Post.");
      return;
    }
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        `Open ${platform} in the Connect browser (noVNC) with this studio image + caption staged? You hit publish yourself.`,
      )
    ) {
      return;
    }
    setStagingIdx(-1);
    setError(null);
    try {
      const result = await stagePlatformPost({
        platform,
        caption,
        media_png_b64: out.image_data_base64,
        approved: true,
      });
      setStaged((prev) => ({ ...prev, [-1]: result }));
      await openViewer(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "staging failed");
    } finally {
      setStagingIdx(null);
    }
  }

  async function stageSelected(): Promise<void> {
    if (!plan || !out) return;
    const idxs = plan.variations.map((_, idx) => idx).filter((idx) => selected[idx]);
    if (idxs.length === 0) {
      setError("Select at least one variation to post.");
      return;
    }
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        `Post ${idxs.length} variation(s) to ${platform} via Connect/noVNC? Composer opens staged — nothing auto-publishes.`,
      )
    ) {
      return;
    }
    setStagingAll(true);
    setError(null);
    for (const idx of idxs) {
      setStagingIdx(idx);
      try {
        const result = await stagePlatformPost({
          platform,
          caption: publishVariationText(plan.variations[idx], platform),
          media_png_b64: out.image_data_base64 ?? undefined,
          approved: true,
        });
        setStaged((prev) => ({ ...prev, [idx]: result }));
        await openViewer(result);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "staging failed");
        break;
      }
    }
    setStagingIdx(null);
    setStagingAll(false);
  }

  if (!out) return null;

  const thumbSrc =
    out.image_data_base64 && out.image_mime_type
      ? `data:${out.image_mime_type};base64,${out.image_data_base64}`
      : null;

  return (
    <div className="space-y-4">
      {outs.length > 0 && (
        <div className="space-y-2">
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
            Saved assets ({outs.length})
          </p>
          <div className="flex flex-wrap gap-2">
            {outs.map((item, idx) => {
              const src =
                item.image_data_base64 && item.image_mime_type
                  ? `data:${item.image_mime_type};base64,${item.image_data_base64}`
                  : null;
              return (
                <div key={item.id} className="relative">
                  <button
                    type="button"
                    onClick={() => selectAsset(idx)}
                    className={`flex items-center gap-2 rounded-xl border px-2.5 py-1.5 text-left text-xs transition ${
                      safeAssetIdx === idx
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border/50 bg-background/50 text-muted-foreground hover:border-primary/40"
                    }`}
                  >
                    {src ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt="" className="size-8 rounded-md object-cover" />
                    ) : (
                      <span className="flex size-8 items-center justify-center rounded-md bg-muted font-mono text-[10px]">
                        #{idx + 1}
                      </span>
                    )}
                    <span className="max-w-28 truncate">
                      {item.overlay_text || item.text || `Asset ${idx + 1}`}
                    </span>
                    <span className="font-mono text-[9px] uppercase text-muted-foreground">
                      {item.format}
                    </span>
                  </button>
                  {onRemoveAsset && (
                    <button
                      type="button"
                      aria-label={`Remove asset ${idx + 1}`}
                      className="absolute -right-1 -top-1 rounded-full bg-background/90 p-0.5 text-muted-foreground shadow hover:text-destructive"
                      onClick={() => {
                        onRemoveAsset(item.id);
                        if (idx <= safeAssetIdx) {
                          setAssetIdx(Math.max(0, safeAssetIdx - 1));
                        }
                      }}
                    >
                      <X className="size-3" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="grid gap-3 sm:grid-cols-[auto_1fr] sm:items-start">
        {thumbSrc && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbSrc}
            alt="Selected studio asset"
            className="h-24 w-24 rounded-xl border border-border/40 object-cover"
          />
        )}
        <div className="space-y-3">
          <div className="space-y-1.5">
            <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Platform
            </p>
            <div className="flex flex-wrap gap-2">
              {PUBLISH_PLATFORMS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => selectPlatform(p)}
                  className={chipClass(platform === p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
              Caption variations (max 3)
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setCount(n)}
                  className={chipClass(count === n)}
                >
                  {n}
                </button>
              ))}
              <Button size="sm" disabled={busy || !ready} onClick={() => void runPlan()}>
                {busy ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Sparkles className="size-3.5" />
                )}
                {plan ? "Regenerate viral captions" : "Generate viral captions"}
              </Button>
              <Button
                size="sm"
                disabled={stagingAll || stagingIdx !== null || !out.image_data_base64}
                onClick={() => void stageStudioCaption()}
              >
                {stagingIdx === -1 ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Send className="size-3.5" />
                )}
                Post on {platform}
              </Button>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <label className="space-y-1">
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                  Schedule (remind to stage)
                </span>
                <input
                  type="datetime-local"
                  value={scheduleLocal}
                  onChange={(e) => setScheduleLocal(e.target.value)}
                  className="block rounded-md border border-border/60 bg-background px-2 py-1.5 text-sm"
                />
              </label>
              <Button
                size="sm"
                variant="outline"
                disabled={!out.text?.trim()}
                onClick={() => {
                  try {
                    const iso = localValueToIso(scheduleLocal);
                    scheduleFromStudioAsset(out, brandName, iso, platform);
                    setScheduleNote(
                      `Saved to Calendar for ${new Date(iso).toLocaleString()} — we remind ~30m before.`,
                    );
                    pushNotification({
                      kind: "generic",
                      title: "Added to calendar",
                      body: `${out.format || format} · ${platform} · open Calendar to review.`,
                      href: "/calendar",
                      email: false,
                    });
                  } catch (cause) {
                    setError(cause instanceof Error ? cause.message : "Could not schedule");
                  }
                }}
              >
                <CalendarPlus className="size-3.5" />
                Schedule
              </Button>
              {scheduleNote && <p className="text-xs text-primary">{scheduleNote}</p>}
            </div>
            <p className="text-xs text-muted-foreground">
              Post uses the selected studio image + its caption (or a variation below) and opens
              the Connect noVNC tab so you can publish. Schedule never autoposts — Calendar reminds
              you to Stage.
            </p>
            {!ready && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                Add a text-model key in Models (defaults to gpt-oss when the server key is set).
              </p>
            )}
          </div>
        </div>
      </div>

      {staged[-1] && (() => {
        const stagedStudio = staged[-1];
        const viewer = stagedStudio.viewer_url ?? undefined;
        return (
        <div className="space-y-1 rounded-xl border border-primary/30 bg-primary/5 p-3">
          <p className={`text-xs ${stagedStudio.ok ? "text-primary" : "text-destructive"}`}>
            {stagedStudio.ok
              ? `Staged in ${platform} composer — finish in noVNC and hit publish yourself.`
              : stagedStudio.detail}
          </p>
          {viewer ? (
            <a
              href={viewer}
              target="_blank"
              rel="noopener noreferrer"
              className="font-ui inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
            >
              Open Connect viewer
              <ExternalLink className="size-3" />
            </a>
          ) : null}
          {stagedStudio.screenshot_jpeg_b64 && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`data:image/jpeg;base64,${stagedStudio.screenshot_jpeg_b64}`}
              alt={`${platform} staged post screenshot`}
              className="max-h-56 w-auto rounded-lg border border-border/40"
            />
          )}
        </div>
        );
      })()}

      {error && <p className="text-sm text-destructive">{error}</p>}
      {busy && liveDraft && (
        <div className="rounded-xl border border-dashed border-primary/40 bg-background/60 p-3 text-left text-xs">
          <p className="mb-2 font-mono text-[10px] uppercase tracking-wider text-primary">
            Publish Strategist drafting…
          </p>
          <MarkdownReport source={liveDraft} />
        </div>
      )}

      {plan && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              disabled={stagingAll || stagingIdx !== null}
              onClick={() => void stageSelected()}
            >
              {stagingAll ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Send className="size-3.5" />
              )}
              Post selected on {platform}
            </Button>
            <button
              type="button"
              className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => {
                const all: Record<number, boolean> = {};
                plan.variations.forEach((_, idx) => {
                  all[idx] = true;
                });
                setSelected(all);
              }}
            >
              Select all
            </button>
            <button
              type="button"
              className="text-xs text-muted-foreground underline-offset-2 hover:underline"
              onClick={() => setSelected({})}
            >
              Clear
            </button>
          </div>
          {plan.variations.map((variation, idx) => {
            const stagedResult = staged[idx];
            return (
              <div
                key={`${platform}-${idx}`}
                className="space-y-2 rounded-xl border border-border/50 bg-background/70 p-3"
              >
                <label className="flex items-start gap-2 text-left">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={Boolean(selected[idx])}
                    onChange={(e) =>
                      setSelected((prev) => ({ ...prev, [idx]: e.target.checked }))
                    }
                  />
                  <span className="min-w-0 flex-1 text-left text-sm leading-relaxed">
                    <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Variation {idx + 1}
                    </span>
                    {variation.title ? (
                      <p className="mb-1 font-medium">{variation.title}</p>
                    ) : null}
                    <MarkdownReport source={variation.caption} />
                  </span>
                </label>
                {variation.description && (
                  <p className="whitespace-pre-wrap text-xs text-muted-foreground">
                    {variation.description}
                  </p>
                )}
                {variation.hashtags.length > 0 && (
                  <p className="text-xs text-primary">{variation.hashtags.join(" ")}</p>
                )}
                {variation.why && (
                  <p className="text-[11px] text-muted-foreground">
                    Why it travels: {variation.why}
                  </p>
                )}
                <div className="flex flex-wrap items-center gap-2 pt-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => void copyText(publishVariationText(variation, platform))}
                  >
                    <Copy className="size-3.5" />
                    Copy caption
                  </Button>
                  <Button
                    size="sm"
                    disabled={stagingIdx !== null || stagingAll}
                    onClick={() => void stageVariation(idx, variation)}
                  >
                    {stagingIdx === idx ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Send className="size-3.5" />
                    )}
                    Post on {platform}
                  </Button>
                </div>
                {stagedResult && (
                  <div className="space-y-1 border-t border-border/40 pt-2">
                    <p
                      className={`text-xs ${stagedResult.ok ? "text-primary" : "text-destructive"}`}
                    >
                      {stagedResult.ok
                        ? `Staged in ${platform} composer — review in noVNC & hit publish yourself.`
                        : stagedResult.detail}
                    </p>
                    {(() => {
                      const viewer = stagedResult.viewer_url ?? undefined;
                      return viewer ? (
                      <a
                        href={viewer}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-ui inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                      >
                        Open Connect viewer
                        <ExternalLink className="size-3" />
                      </a>
                      ) : null;
                    })()}
                    {stagedResult.detail && stagedResult.ok && (
                      <p className="text-[11px] text-muted-foreground">{stagedResult.detail}</p>
                    )}
                    {stagedResult.screenshot_jpeg_b64 && (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={`data:image/jpeg;base64,${stagedResult.screenshot_jpeg_b64}`}
                        alt={`${platform} staged post screenshot`}
                        className="max-h-56 w-auto rounded-lg border border-border/40"
                      />
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
