"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Copy,
  Download,
  ExternalLink,
  Flame,
  Loader2,
  MessageSquare,
  Sparkles,
  Target,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { useGeminiKey } from "@/components/gemini-key-provider";
import {
  dropSocialComment,
  generateCreative,
  generateIntelReport,
  listConnections,
} from "@/lib/api";
import { MarkdownReport } from "@/components/mission/markdown-report";
import { IntelVisuals } from "@/components/mission/intel-visuals";
import { mergeIntel, type IntelFacts } from "@/lib/intel-facts";
import {
  SNIPER_PLATFORMS,
  SNIPER_TONES,
  STUDIO_FORMATS,
  formatUnlocked,
} from "@/lib/studio-formats";
import type {
  BrandProfile,
  ConnectionStatus,
  CreativePermissions,
  CreativeResult,
  IntelReport,
} from "@/lib/types";

const KEY_WARNING = "Paste your Gemini API key in Context or the navbar chip.";

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
    label: "Nano Banana post visuals",
    hint: "Memes, quote cards, founder frames",
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
}: {
  facts: IntelFacts;
  permissions: CreativePermissions;
  onPermissionsChange: (p: CreativePermissions) => void;
  brand: BrandProfile;
}) {
  const gemini = useGeminiKey();
  const factsJson = useMemo(() => JSON.stringify(facts), [facts]);
  const factsSig = `${facts.window.label}|${facts.brandName}|${facts.companies
    .map((c) => `${c.name}:${c.posts}`)
    .join(",")}|${facts.sniperQueue.length}`;

  const [geminiIntel, setGeminiIntel] = useState<IntelReport | null>(null);
  const [intelFetchError, setIntelFetchError] = useState<string | null>(null);
  const [intelForSig, setIntelForSig] = useState(factsSig);
  const [reportTab, setReportTab] = useState("brief");
  if (intelForSig !== factsSig) {
    setIntelForSig(factsSig);
    setGeminiIntel(null);
    setIntelFetchError(null);
    setReportTab("brief");
  }
  const intel = mergeIntel(facts, geminiIntel);
  const usedFallback = geminiIntel === null;
  const intelBusy = gemini.ready && geminiIntel === null && intelFetchError === null;
  const intelError = !gemini.ready ? KEY_WARNING : intelFetchError;

  const [studioFormat, setStudioFormat] = useState("hot_take");
  const [studioPlatform, setStudioPlatform] = useState("linkedin");
  const [studioSpice, setStudioSpice] = useState(3);
  const [studioBusy, setStudioBusy] = useState(false);
  const [studioError, setStudioError] = useState<string | null>(null);
  const [studioOut, setStudioOut] = useState<CreativeResult | null>(null);
  const [lightbox, setLightbox] = useState<string | null>(null);

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
    if (!gemini.ready) return;
    let cancelled = false;
    void generateIntelReport({
      facts,
      brand_name: brand.displayName || "the brand",
      voice_notes: brand.voiceNotes,
      forbidden_claims: brand.forbiddenClaims,
    })
      .then((report) => {
        if (cancelled) return;
        setGeminiIntel(report);
        setIntelFetchError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setGeminiIntel(null);
        setIntelFetchError(
          err instanceof Error ? err.message : "Intel Chief is offline — facts still stand.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [facts, factsSig, gemini.ready, brand.displayName, brand.voiceNotes, brand.forbiddenClaims]);

  async function runStudio(spice = studioSpice) {
    if (!gemini.ready) {
      setStudioError(KEY_WARNING);
      return;
    }
    if (!formatUnlocked(studioFormat, permissions)) {
      setStudioError("Flip on the matching creative permission first.");
      return;
    }
    setStudioBusy(true);
    setStudioError(null);
    try {
      const result = await generateCreative({
        kind: "studio",
        brand_name: brand.displayName || "the brand",
        voice_notes: brand.voiceNotes,
        forbidden_claims: brand.forbiddenClaims,
        platform: studioPlatform,
        format: studioFormat,
        spice,
        facts_json: factsJson,
      });
      setStudioOut(result);
      setStudioSpice(spice);
    } catch (err) {
      setStudioError(err instanceof Error ? err.message : "Studio generation failed");
    } finally {
      setStudioBusy(false);
    }
  }

  async function runSniper() {
    if (!gemini.ready) {
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
      const result = await generateCreative({
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
      });
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

  const studioSrc =
    studioOut?.image_data_base64 && studioOut.image_mime_type
      ? `data:${studioOut.image_mime_type};base64,${studioOut.image_data_base64}`
      : null;

  const activeReport =
    reportTab === "brief"
      ? intel.markdown
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

      {!gemini.ready && (
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
          <h3 className="font-display text-lg font-bold">Intel Chief</h3>
          <div className="flex items-center gap-2">
            {intelBusy && <Loader2 className="size-4 animate-spin text-primary" />}
            <span className="font-ui text-[10px] uppercase tracking-widest text-muted-foreground">
              {intelBusy ? "agents writing" : usedFallback ? "offline · fact brief" : "gemini live"}
            </span>
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
        {intelError && (
          <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {intelError}
          </p>
        )}
        <p className="font-accent text-lg italic text-foreground/90">{intel.scoreboard_blurb}</p>
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
          Pick what to make. Gemini writes the caption; Nano Banana paints the frame. No rival logos.
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
        <div className="flex flex-wrap gap-2">
          <Button disabled={studioBusy || !gemini.ready} onClick={() => void runStudio()}>
            {studioBusy ? <Loader2 className="size-4 animate-spin" /> : <Flame className="size-4" />}
            Generate
          </Button>
          {studioOut && (
            <Button
              variant="outline"
              disabled={studioBusy || !gemini.ready}
              onClick={() => void runStudio(Math.min(5, studioSpice + 1))}
            >
              Regenerate with more spice
            </Button>
          )}
        </div>
        {studioError && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {studioError}
          </p>
        )}
        {studioOut && (
          <div className="overflow-hidden rounded-2xl border border-border/60 bg-background/40">
            <div className="border-b border-border/40 px-4 py-2 font-mono text-xs uppercase text-primary">
              {studioFormat} · {studioPlatform}
            </div>
            <div className="space-y-3 p-4">
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{studioOut.text}</p>
              {studioOut.why_slaps && (
                <p className="text-xs text-primary">Why this slaps: {studioOut.why_slaps}</p>
              )}
              {studioOut.overlay_text && (
                <p className="text-xs text-muted-foreground">Overlay: {studioOut.overlay_text}</p>
              )}
              {studioSrc && (
                <button type="button" onClick={() => setLightbox(studioSrc)} className="block w-full">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={studioSrc}
                    alt="Studio output"
                    className="max-h-80 w-full rounded-xl border border-border/40 object-contain"
                  />
                </button>
              )}
              {!studioSrc && studioOut.image_error && (
                <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  {studioOut.image_error}
                </p>
              )}
              {!studioSrc && !studioOut.image_error && (
                <p className="text-xs text-muted-foreground">
                  No PNG this round — caption still usable. Try Generate again.
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => void copyText(studioOut.text)}>
                  <Copy className="size-3.5" />
                  Copy caption
                </Button>
                {studioOut.image_data_base64 && studioOut.image_mime_type && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      downloadImage(
                        studioOut.image_mime_type as string,
                        studioOut.image_data_base64 as string,
                        "rivalradar-studio.png",
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
            disabled={sniperBusy !== null || !gemini.ready}
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
