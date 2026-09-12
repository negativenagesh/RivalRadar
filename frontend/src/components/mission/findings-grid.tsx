"use client";

import { useMemo, type ReactNode } from "react";
import { ExternalLink, Heart, MessageCircle, Eye, Repeat2 } from "lucide-react";

import type { CompetitorAccount, CompetitorPost } from "@/lib/types";
import { ingestionMediaUrl } from "@/lib/api";
import {
  filterFindingsPosts,
  type FindingsRow,
} from "@/lib/findings-filter";
import type { MissionTargetPreview } from "@/lib/mission-store";
import { PLATFORM_LABELS } from "@/lib/mission-store";

function resolveImage(post: CompetitorPost): string | null {
  const key = post.media_keys?.[0];
  if (key) return ingestionMediaUrl(key);
  const url = post.image_url || post.media_urls?.[0] || null;
  if (!url) return null;
  if (url.includes("/screenshots/")) return null;
  if (url.startsWith("http") || url.startsWith("data:")) return url;
  const base = process.env.NEXT_PUBLIC_GATEWAY_URL || "http://localhost:8000";
  return `${base.replace(/\/$/, "")}${url.startsWith("/") ? url : `/${url}`}`;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1).replace(/\.0$/, "")}k`;
  return String(n);
}

type CompanySection = {
  company: string;
  role: "brand" | "rival";
  groups: { platform: string; day: string; rows: FindingsRow[] }[];
};

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

  const sections = useMemo(() => {
    const order = new Map<string, CompanySection>();
    for (const row of rows) {
      const key = `${row.role}::${row.company}`;
      const section =
        order.get(key) ??
        { company: row.company, role: row.role, groups: [] };
      const gkey = `${row.platform}||${row.day}`;
      let group = section.groups.find((g) => `${g.platform}||${g.day}` === gkey);
      if (!group) {
        group = { platform: row.platform, day: row.day, rows: [] };
        section.groups.push(group);
      }
      group.rows.push(row);
      order.set(key, section);
    }
    for (const section of order.values()) {
      section.groups.sort((a, b) => {
        const p = a.platform.localeCompare(b.platform);
        if (p) return p;
        return b.day.localeCompare(a.day);
      });
      for (const g of section.groups) {
        g.rows.sort((a, b) => b.likes + b.comments - (a.likes + a.comments));
      }
    }
    return [...order.values()].sort((a, b) => {
      if (a.role !== b.role) return a.role === "brand" ? -1 : 1;
      return a.company.localeCompare(b.company);
    });
  }, [rows]);

  const windowLabel =
    dateFrom && dateTo ? `${dateFrom} → ${dateTo}` : `last ${lookbackDays} days`;

  return (
    <div className="relative mx-auto max-w-6xl space-y-12">
      <div className="pointer-events-none absolute inset-x-0 -top-8 -z-10 h-64 bg-[radial-gradient(ellipse_at_top,oklch(0.87_0.24_128_/_0.14),transparent_60%)]" />

      <header className="space-y-3 text-center">
        <p className="font-ui text-xs font-semibold uppercase tracking-[0.28em] text-primary">
          intel dump
        </p>
        <h2 className="font-shout text-jumble-wild text-4xl uppercase sm:text-6xl">Findings</h2>
        <p className="font-accent mx-auto max-w-2xl text-base italic text-muted-foreground">
          Company + rivalry only · {windowLabel}
        </p>
      </header>

      {loading && (
        <p className="font-ui animate-pulse text-center text-sm text-muted-foreground">
          Pulling post media…
        </p>
      )}

      {!loading && rows.length === 0 && (
        <div className="mx-auto max-w-lg space-y-2 rounded-[2rem] border border-border/50 bg-card/20 px-6 py-12 text-center">
          <p className="font-display text-xl font-bold">No posts in this window</p>
          <p className="font-accent text-sm italic text-muted-foreground">
            Findings only shows your company and rivals inside {windowLabel}. Re-run scout if the
            grid is empty.
          </p>
        </div>
      )}

      {sections.map((section) => (
        <section
          key={`${section.role}-${section.company}`}
          className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-500"
        >
          <div className="flex flex-wrap items-end gap-3">
            <h3 className="font-display text-3xl font-bold tracking-tight">{section.company}</h3>
            <span className="font-ui mb-1 rounded-full bg-primary/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
              {section.role === "brand" ? "Company" : "Rivalry"}
            </span>
          </div>

          {section.groups.map((group) => (
            <div key={`${section.company}-${group.platform}-${group.day}`} className="space-y-4">
              <div className="flex flex-wrap items-end gap-3 border-b border-border/40 pb-3">
                <span className="font-ui rounded-full bg-card px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-primary">
                  {PLATFORM_LABELS[group.platform] ?? group.platform}
                </span>
                <span className="font-accent text-sm italic text-muted-foreground">{group.day}</span>
                <span className="font-ui ml-auto text-[11px] text-muted-foreground">
                  {group.rows.length} posts
                </span>
              </div>

              <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                {group.rows.map((row) => (
                  <PostTile key={row.post.id} row={row} />
                ))}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

function PostTile({ row }: { row: FindingsRow }) {
  const img = resolveImage(row.post);
  const title = (row.post.caption.split("\n")[0] ?? row.post.caption).trim() || "Untitled drop";
  const inner = (
    <>
      <div className="relative aspect-[4/5] overflow-hidden bg-[radial-gradient(circle_at_30%_20%,oklch(0.87_0.24_128_/_0.12),transparent_55%)]">
        {img ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={img}
            alt=""
            className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="font-shout flex h-full items-center justify-center text-2xl uppercase tracking-widest text-muted-foreground/40">
            {row.post.format}
          </div>
        )}
        {row.href && (
          <span className="font-ui absolute right-3 top-3 inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-white">
            Open
            <ExternalLink className="size-3" aria-hidden />
          </span>
        )}
      </div>

      <div className="grid grid-cols-4 gap-px border-y border-border/40 bg-border/30">
        <Metric cell label="likes" value={row.likes} icon={<Heart className="size-3" />} />
        <Metric
          cell
          label="comments"
          value={row.comments}
          icon={<MessageCircle className="size-3" />}
        />
        <Metric cell label="views" value={row.views} icon={<Eye className="size-3" />} />
        <Metric cell label="shares" value={row.shares} icon={<Repeat2 className="size-3" />} />
      </div>

      <div className="flex flex-1 flex-col gap-3 p-4">
        <p className="font-display line-clamp-3 text-[15px] font-semibold leading-snug">{title}</p>
      </div>
    </>
  );

  const className =
    "group flex flex-col overflow-hidden rounded-[1.75rem] border border-border/50 bg-gradient-to-b from-card/50 to-card/20 text-left text-foreground no-underline transition duration-300 hover:-translate-y-1 hover:border-primary/40 hover:shadow-[0_20px_60px_-30px_oklch(0.87_0.24_128_/_0.55)]";

  if (row.href) {
    return (
      <a href={row.href} target="_blank" rel="noopener noreferrer" className={className}>
        {inner}
      </a>
    );
  }
  return <article className={className}>{inner}</article>;
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
          ? "flex flex-col items-center gap-0.5 bg-background/80 px-1 py-2.5"
          : "flex items-center gap-1"
      }
    >
      <span className="text-primary/80">{icon}</span>
      <span className="font-shout text-sm leading-none tracking-tight">{fmt(value)}</span>
      <span className="font-ui text-[9px] uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
    </div>
  );
}
