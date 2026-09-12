"use client";

import { useState } from "react";
import Link from "next/link";
import { ImageIcon, MessageSquare, PenLine, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MarkdownReport } from "@/components/mission/markdown-report";
import { generateCreative } from "@/lib/api";
import type { CreativePermissions, CreativeResult } from "@/lib/types";

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
    hint: "Ride the theme without quoting them",
  },
  {
    key: "suggestComments",
    label: "Suggest comments",
    hint: "Human-approve only — never auto-comment",
  },
  {
    key: "imageConcepts",
    label: "Nano Banana post visuals",
    hint: "Gemini image gen (concept fallback if quota is empty)",
  },
  {
    key: "carouselOutlines",
    label: "Carousel / thread outlines",
    hint: "Slide-by-slide or tweet-thread skeletons",
  },
  {
    key: "comparisonSlides",
    label: "Competitive comparison slides",
    hint: "Internal-only rival vs you decks",
  },
];

export function DiscoveryReport({
  report,
  permissions,
  onPermissionsChange,
  brandName,
  voiceNotes,
  competitorCaption,
}: {
  report: string;
  permissions: CreativePermissions;
  onPermissionsChange: (p: CreativePermissions) => void;
  brandName: string;
  voiceNotes: string;
  competitorCaption: string;
}) {
  const [busy, setBusy] = useState<"image" | "comment" | "reply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<CreativeResult[]>([]);

  async function run(kind: "image" | "comment" | "reply") {
    if (kind === "image" && !permissions.imageConcepts) {
      setError("Enable “Nano Banana post visuals” permission first.");
      return;
    }
    if (kind === "comment" && !permissions.suggestComments) {
      setError("Enable “Suggest comments” permission first.");
      return;
    }
    if (kind === "reply" && !permissions.draftReplies) {
      setError("Enable “Draft reply / response posts” permission first.");
      return;
    }

    setError(null);
    setBusy(kind);
    try {
      const result = await generateCreative({
        kind,
        report_markdown: report,
        brand_name: brandName || "the brand",
        voice_notes: voiceNotes,
        competitor_caption: competitorCaption,
      });
      setResults((prev) => [result, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Creative generation failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-bold">Discovery report</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Parsed brief on what&apos;s winning — then generate images, comments, and replies under
          your permissions.
        </p>
      </div>

      <MarkdownReport source={report} />

      <div>
        <h3 className="font-bold">Creative permissions</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Flip on what RivalRadar is allowed to propose. Publishing always needs a human.
        </p>
        <ul className="mt-4 space-y-3">
          {PERM_OPTIONS.map((opt) => (
            <li key={opt.key}>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border/60 px-3 py-3 transition hover:border-primary/40 hover:shadow-[0_0_28px_-16px_oklch(0.87_0.24_128)]">
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
      </div>

      <div className="space-y-3">
        <h3 className="font-bold">Generate from this report</h3>
        <div className="flex flex-wrap gap-3">
          <Button
            size="lg"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void run("image")}
            className="gap-2"
          >
            {busy === "image" ? <Loader2 className="size-4 animate-spin" /> : <ImageIcon className="size-4" />}
            Nano Banana image
          </Button>
          <Button
            size="lg"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void run("comment")}
            className="gap-2"
          >
            {busy === "comment" ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <MessageSquare className="size-4" />
            )}
            Suggest comment
          </Button>
          <Button
            size="lg"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void run("reply")}
            className="gap-2"
          >
            {busy === "reply" ? <Loader2 className="size-4 animate-spin" /> : <PenLine className="size-4" />}
            Draft reply
          </Button>
        </div>
        {error && (
          <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        )}
      </div>

      {results.length > 0 && (
        <div className="space-y-4">
          <h3 className="font-bold">Creative output</h3>
          {results.map((r, i) => (
            <div
              key={`${r.kind}-${i}`}
              className="overflow-hidden rounded-2xl border border-border/60 bg-background/40"
            >
              <div className="border-b border-border/40 px-4 py-2 font-mono text-xs uppercase text-primary">
                {r.kind}
              </div>
              <div className="space-y-3 p-4">
                <p className="text-sm leading-relaxed">{r.text}</p>
                {r.image_concept && r.kind === "image" && (
                  <p className="text-xs text-muted-foreground">
                    Concept: {r.image_concept}
                    {!r.image_data_base64
                      ? " — pixels need a paid Gemini / Nano Banana quota; concept shown instead."
                      : ""}
                  </p>
                )}
                {r.image_data_base64 && r.image_mime_type && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={`data:${r.image_mime_type};base64,${r.image_data_base64}`}
                    alt="Generated creative"
                    className="max-h-80 rounded-xl border border-border/40 object-contain"
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <Button size="lg" asChild>
          <Link href="/digest">Open weekly digest</Link>
        </Button>
        <Button size="lg" variant="secondary" asChild>
          <Link href="/review">Review queue</Link>
        </Button>
      </div>
    </div>
  );
}
