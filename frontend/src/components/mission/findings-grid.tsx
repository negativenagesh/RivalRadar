"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ExternalLink, Heart, MessageCircle, Eye, Repeat2, X } from "lucide-react";

import type { CompetitorAccount, CompetitorPost } from "@/lib/types";
import {
  filterFindingsPosts,
  findingsBoard,
  postVisualUrl,
  type FindingsRow,
} from "@/lib/findings-filter";
import type { MissionTargetPreview } from "@/lib/mission-store";
import { PLATFORM_LABELS } from "@/lib/mission-store";
import { cn } from "@/lib/utils";

function resolveImage(post: CompetitorPost): string | null {
  return postVisualUrl(post);
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(n);
}

export function FindingsGrid({
  posts,
  accounts,
  targets,
  loading,
  lookbackDays,
  dateFrom,
  dateTo,
}: {
  posts: CompetitorPost[];
  accounts: CompetitorAccount[];
  targets: MissionTargetPreview[];
  loading: boolean;
  lookbackDays: number;
  dateFrom?: string | null;
  dateTo?: string | null;
}) {
  const rows = useMemo(
    () =>
      filterFindingsPosts(posts, accounts, {
        targets,
        dateFrom,
        dateTo,
        lookbackDays,
      }),
    [posts, accounts, targets, dateFrom, dateTo, lookbackDays],
  );

  const board = useMemo(() => findingsBoard(rows, targets), [rows, targets]);
  const hasSides = board.brand.length > 0 || board.rivals.length > 0;
  const [lightbox, setLightbox] = useState<FindingsRow | null>(null);
  useEffect(() => {
    if (!lightbox) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLightbox(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox]);

  const windowLabel =
    dateFrom && dateTo ? `${dateFrom} → ${dateTo}` : `last ${lookbackDays} days`;

  return (
    <div className="relative w-full space-y-8">
      <div className="pointer-events-none absolute inset-x-0 -top-8 -z-10 h-64 bg-[radial-gradient(ellipse_at_top,oklch(0.87_0.24_128_/_0.14),transparent_60%)]" />

      <header className="space-y-3 text-center">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          intel dump
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-6xl">Findings</h2>
        <p className="font-accent mx-auto max-w-2xl text-base italic text-muted-foreground">
          Company left · rivalry right · {windowLabel}
        </p>
      </header>

      {loading && (
        <p className="font-ui animate-pulse text-center text-sm text-muted-foreground">
          Pulling post media…
        </p>
      )}

      {!loading && !hasSides && (
        <div className="mx-auto max-w-lg space-y-2 rounded-[2rem] border border-border/50 bg-card/20 px-6 py-12 text-center">
          <p className="font-display text-xl font-bold">No posts in this window</p>
          <p className="font-accent text-sm italic text-muted-foreground">
            Add company + rival links in Context, then re-run scout for {windowLabel}.
          </p>
        </div>
      )}

      {hasSides && (
        <div className="grid items-start gap-4 lg:grid-cols-2 lg:gap-6">
          <FindingsSide
            eyebrow="Your company"
            columns={board.brand}
            accent="brand"
            onOpenImage={setLightbox}
          />
          <FindingsSide
            eyebrow="Rivalry"
            columns={board.rivals}
            accent="rival"
            onOpenImage={setLightbox}
          />
        </div>
      )}

      {lightbox && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/88 p-4 sm:p-8"
          onClick={() => setLightbox(null)}
          onKeyDown={() => undefined}
          role="presentation"
        >
          <button
            type="button"
            className="absolute right-4 top-4 rounded-full bg-white/10 p-2 text-white hover:bg-white/20"
            onClick={() => setLightbox(null)}
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
          <div
            className="flex max-h-[92vh] max-w-5xl flex-col items-center"
            onClick={(e) => e.stopPropagation()}
            role="presentation"
          >
            {resolveImage(lightbox.post) ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={resolveImage(lightbox.post) ?? ""}
                alt=""
                className="max-h-[80vh] w-auto max-w-full rounded-2xl object-contain"
              />
            ) : null}
            <p className="font-display mt-4 max-w-2xl text-center text-sm font-semibold text-white">
              {(lightbox.post.caption.split("\n")[0] ?? lightbox.post.caption).trim()}
            </p>
            {lightbox.href ? (
              <a
                href={lightbox.href}
                target="_blank"
                rel="noopener noreferrer"
                className="font-ui mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-primary hover:underline"
              >
                Open original post
                <ExternalLink className="size-3" />
              </a>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}

function FindingsSide({
  eyebrow,
  columns,
  accent,
  onOpenImage,
}: {
  eyebrow: string;
  columns: ReturnType<typeof findingsBoard>["brand"];
  accent: "brand" | "rival";
  onOpenImage: (row: FindingsRow) => void;
}) {
  return (
    <section
      className={cn(
        "min-h-[280px] space-y-8 rounded-[2rem] border p-4 sm:p-6",
        accent === "brand"
          ? "border-primary/40 bg-gradient-to-b from-primary/10 via-card/30 to-card/10 shadow-[0_0_80px_-40px_oklch(0.87_0.24_128)]"
          : "border-border/50 bg-gradient-to-b from-card/50 via-card/20 to-background",
      )}
    >
      <header className="space-y-1">
        <p
          className={cn(
            "font-ui text-[10px] font-bold uppercase tracking-[0.22em]",
            accent === "brand" ? "text-primary" : "text-muted-foreground",
          )}
        >
          {eyebrow}
        </p>
        {columns.length === 0 && (
          <p className="font-accent text-sm italic text-muted-foreground">Nobody on this side yet.</p>
        )}
      </header>

      {columns.map((column) => (
        <div key={`${column.role}-${column.company}`} className="space-y-6">
          <h3 className="font-display text-3xl font-bold tracking-tight">{column.company}</h3>
          {column.lanes.map((lane) => (
            <div key={`${column.company}-${lane.platform}`} className="space-y-3">
              <div className="flex flex-wrap items-end gap-3 border-b border-border/40 pb-2">
                <span className="font-ui rounded-full bg-background/70 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
                  {PLATFORM_LABELS[lane.platform] ?? lane.platform}
                </span>
                <span className="font-ui ml-auto text-[11px] text-muted-foreground">
                  {lane.empty
                    ? "0 in window"
                    : `${lane.days.reduce((n, d) => n + d.rows.length, 0)} posts`}
                </span>
              </div>
              {lane.empty ? (
                <p className="font-accent rounded-2xl border border-dashed border-border/50 px-4 py-8 text-center text-sm italic text-muted-foreground">
                  No {PLATFORM_LABELS[lane.platform] ?? lane.platform} drops in this lookback.
                </p>
              ) : (
                lane.days.map((group) => (
                  <div key={`${lane.platform}-${group.day}`} className="space-y-3">
                    <p className="font-accent text-sm italic text-muted-foreground">{group.day}</p>
                    <div className="grid grid-cols-3 gap-2 xl:grid-cols-4">
                      {group.rows.map((row) => (
                        <PostTile key={row.post.id} row={row} onOpenImage={onOpenImage} />
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}

function PostTile({
  row,
  onOpenImage,
}: {
  row: FindingsRow;
  onOpenImage: (row: FindingsRow) => void;
}) {
  const img = resolveImage(row.post);
  const title = (row.post.caption.split("\n")[0] ?? row.post.caption).trim() || "Untitled drop";

  return (
    <article className="group flex flex-col overflow-hidden rounded-2xl border border-border/50 bg-gradient-to-b from-card/50 to-card/20 text-left text-foreground">
      <button
        type="button"
        onClick={() => img && onOpenImage(row)}
        className="relative aspect-square overflow-hidden bg-black/40"
        disabled={!img}
        aria-label={img ? "View image fullscreen" : title}
      >
        {img ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={img}
            alt=""
            className="h-full w-full object-contain transition duration-300 group-hover:scale-[1.02]"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="font-shout flex h-full items-center justify-center text-lg uppercase tracking-widest text-muted-foreground/40">
            {row.post.format}
          </div>
        )}
      </button>

      <div className="grid grid-cols-4 gap-px border-y border-border/40 bg-border/30">
        <Metric cell label="likes" value={row.likes} icon={<Heart className="size-2.5" />} />
        <Metric
          cell
          label="comments"
          value={row.comments}
          icon={<MessageCircle className="size-2.5" />}
        />
        <Metric cell label="views" value={row.views} icon={<Eye className="size-2.5" />} />
        <Metric cell label="shares" value={row.shares} icon={<Repeat2 className="size-2.5" />} />
      </div>

      <div className="flex flex-1 flex-col gap-2 p-2.5">
        {row.href ? (
          <a
            href={row.href}
            target="_blank"
            rel="noopener noreferrer"
            className="font-display line-clamp-2 text-[13px] font-semibold leading-snug text-foreground no-underline hover:text-primary hover:underline"
          >
            {title}
            <ExternalLink className="ml-1 inline size-3 align-text-top opacity-70" aria-hidden />
          </a>
        ) : (
          <p className="font-display line-clamp-2 text-[13px] font-semibold leading-snug">{title}</p>
        )}
      </div>
    </article>
  );
}

function Metric({
  label,
  value,
  icon,
  cell,
}: {
  label: string;
  value: number;
  icon: ReactNode;
  cell?: boolean;
}) {
  return (
    <div
      className={
        cell
          ? "flex flex-col items-center gap-0.5 bg-background/80 px-0.5 py-1.5"
          : "flex items-center gap-1"
      }
    >
      <span className="text-primary/80">{icon}</span>
      <span className="font-shout text-xs leading-none tracking-tight">{fmt(value)}</span>
      <span className="font-ui text-[8px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
